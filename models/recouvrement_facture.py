from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RecouvrementFacture(models.Model):
    _name = 'recouvrement.facture'
    _description = 'Facture de recouvrement'
    _order = 'date_facture desc, id desc'

    def init(self):
        self.env.cr.execute(
            """
            UPDATE recouvrement_facture
               SET date_echeance = date_depot_client + INTERVAL '60 days'
             WHERE date_echeance IS NULL
               AND date_depot_client IS NOT NULL
            """
        )

    @api.model
    def _infer_facture_type_from_sheet(self, source_sheet):
        value = (source_sheet or '').strip().lower()
        if 'groupement' in value:
            return 'groupement'
        if 'pro-forma' in value or 'proforma' in value:
            return 'proforma'
        if 'avance' in value:
            return 'avance'
        if 'suivi de facturation' in value or '2eme envoi' in value:
            return 'standard'
        return False

    name = fields.Char(string='N° facture', required=True, index=True)
    facture_type = fields.Selection([
        ('standard', 'Facture standard'),
        ('proforma', 'Facture proforma'),
        ('groupement', 'Facture en groupement'),
        ('avance', 'Facture d\'avance'),
        ('autre', 'Autre type'),
    ], string='Type de facture', required=True, default='standard')
    client_id = fields.Many2one('res.partner', string='Client', required=True)
    date_reception_ordre = fields.Date(string="Date de réception de l'ordre")
    chez_laila = fields.Char(string='Chez Laila')
    chez_bennis = fields.Char(string='Chez Bennis')
    date_facture = fields.Date(string='Date de la facture')
    date_signature = fields.Date(string='Date de signature')
    date_depot_client = fields.Date(string='Date de dépôt chez le client')
    date_echeance = fields.Date(string="Date d'échéance")
    depot_comment = fields.Text(string='Statut / commentaire de dépôt')
    depot_display = fields.Char(string='Dépôt client', compute='_compute_depot_display', store=True)
    montant_ttc = fields.Monetary(string='Montant TTC')
    montant_ht = fields.Monetary(string='Montant HT')
    reference_justificatif = fields.Char(string='Référence justificatif')
    division_id = fields.Many2one('hr.department', string='Division')
    pole_id = fields.Many2one('hr.department', string='Pôle')
    code_affaire = fields.Char(string='Code affaire')
    numero_enreg = fields.Char(string='N° enregistrement')
    ice = fields.Char(string='ICE')
    numero_marche = fields.Char(string='N° marché')
    source_sheet = fields.Char(string='Feuille source', readonly=True)
    nature = fields.Char(string='Nature')
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('imported', 'Importée'),
        ('validated', 'Validée'),
    ], string='Statut', default='draft')
    recouvrement_status = fields.Selection([
        ('normal', 'Normal'),
        ('precontentieux', 'Précontentieux'),
        ('contentieux', 'Contentieux'),
        ('bloque', 'Bloqué'),
        ('recouvre', 'Recouvré'),
    ], string='Statut recouvrement', default='normal')
    currency_id = fields.Many2one('res.currency', string='Devise', default=lambda self: self.env.company.currency_id)
    recouvrement_id = fields.Many2one('recouvrement.recouvrement', string='Recouvrement associé')

    @api.depends('date_depot_client', 'depot_comment')
    def _compute_depot_display(self):
        for rec in self:
            if rec.date_depot_client:
                rec.depot_display = rec.date_depot_client.strftime('%d/%m/%Y')
            else:
                rec.depot_display = rec.depot_comment or ''

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            inferred_type = self._infer_facture_type_from_sheet(vals.get('source_sheet'))
            if inferred_type:
                vals['facture_type'] = inferred_type
            if not vals.get('date_echeance') and vals.get('date_depot_client'):
                vals['date_echeance'] = fields.Date.to_date(vals['date_depot_client']) + timedelta(days=60)
        return super().create(vals_list)

    def write(self, vals):
        if any(rec.state != 'draft' for rec in self) and not self.env.context.get('recouvrement_import'):
            raise UserError(_('Les factures importées ne peuvent pas être modifiées manuellement.'))
        inferred_type = self._infer_facture_type_from_sheet(vals.get('source_sheet'))
        if inferred_type:
            vals['facture_type'] = inferred_type
        if not vals.get('date_echeance') and vals.get('date_depot_client'):
            vals['date_echeance'] = fields.Date.to_date(vals['date_depot_client']) + timedelta(days=60)
        return super().write(vals)

    def action_open_import(self):
        """Open the import wizard for factures.

        This returns an action dict at runtime so views don't need to resolve the
        external id during XML parsing.
        """
        action = False
        try:
            action = self.env.ref('recouvrement_contentieux.action_recouvrement_import_factures')
        except Exception:
            action = False
        if action:
            return action.read()[0]
        return {
            'type': 'ir.actions.act_window',
            'name': 'Importer des factures',
            'res_model': 'recouvrement.facture.import.wizard',
            'view_mode': 'form',
            'target': 'new',
        }
