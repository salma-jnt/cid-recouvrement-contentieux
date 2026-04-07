from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RecouvrementFacture(models.Model):
    _name = 'recouvrement.facture'
    _description = 'Facture de recouvrement'
    _order = 'date_facture desc, id desc'

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
        return super().create(vals_list)

    def write(self, vals):
        if any(rec.state != 'draft' for rec in self) and not self.env.context.get('recouvrement_import'):
            raise UserError(_('Les factures importées ne peuvent pas être modifiées manuellement.'))
        inferred_type = self._infer_facture_type_from_sheet(vals.get('source_sheet'))
        if inferred_type:
            vals['facture_type'] = inferred_type
        return super().write(vals)


class RecouvrementEncaissement(models.Model):
    _name = 'recouvrement.encaissement'
    _description = 'Encaissement de recouvrement'

    name = fields.Char(string='Référence', required=True)
    facture_id = fields.Many2one('recouvrement.facture', string='Facture', required=True)
    recouvrement_id = fields.Many2one('recouvrement.recouvrement', string='Dossier de recouvrement')
    montant = fields.Monetary(string='Montant encaissé', required=True)
    date_encaissement = fields.Date(string='Date d’encaissement', required=True)
    mode_paiement = fields.Selection([
        ('virement', 'Virement'),
        ('espece', 'Espèces'),
        ('cheque', 'Chèque'),
        ('autre', 'Autre'),
    ], string='Mode de paiement', default='virement')
    currency_id = fields.Many2one('res.currency', string='Devise', default=lambda self: self.env.company.currency_id)
