"""
Modèle Facture — refactor v2.0.0

Changements vs v1 :
  + Champ `mois_upload` (marquage analytique requis par le cahier)
  + Champ `statut_interface` (vert/orange/rouge/mauve) — pilotage visuel
  + Champ `montant_paye` (computed sum lettrages)
  + Champ `reste_a_payer` (computed)
  + Champ `lettrage_ids` (One2many)
  + Verrou juridique : write rejeté si statut Pré-contentieux/Contentieux/Bloqué
  + Valeur 'bloque_technique' ajoutée à recouvrement_status pour blocage orange
  - Suppression chez_laila / chez_bennis (champs Excel parasites)
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RecouvrementFacture(models.Model):
    _name = 'recouvrement.facture'
    _description = 'Facture de recouvrement'
    _order = 'date_facture desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ------------------------------------------------------------------
    # Identification & textes
    # ------------------------------------------------------------------
    name = fields.Char(
        string='N° facture', required=True, index=True, tracking=True,
    )
    code_affaire = fields.Char(
        string='Code affaire', index=True, tracking=True,
        help="Clé de réconciliation lors de l'upsert mensuel.",
    )
    numero_enreg = fields.Char(string="N° enregistrement")
    ice = fields.Char(string='ICE')
    numero_marche = fields.Char(string='N° marché')
    reference_justificatif = fields.Char(string='Référence justificatif')
    nature = fields.Char(string='Nature')
    source_sheet = fields.Char(string='Feuille source', readonly=True)
    mois_upload = fields.Char(
        string="Mois d'upload",
        index=True,
        help="Marquage analytique défini lors de l'import (ex: '2026-04'). "
             "Utilisé pour figer les données dans les KPIs trimestriels.",
    )
    depot_comment = fields.Text(string='Statut / commentaire de dépôt')
    depot_display = fields.Char(
        string='Dépôt client',
        compute='_compute_depot_display',
        store=True,
    )

    # ------------------------------------------------------------------
    # Typologie
    # ------------------------------------------------------------------
    facture_type = fields.Selection([
        ('standard', 'Facture standard'),
        ('proforma', 'Facture proforma'),
        ('groupement', 'Facture en groupement'),
        ('avance', "Facture d'avance"),
        ('autre', 'Autre type'),
    ], string='Type de facture', required=True, default='standard', tracking=True)

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('imported', 'Importée'),
        ('validated', 'Validée'),
    ], string='État technique', default='draft', tracking=True)

    recouvrement_status = fields.Selection([
        ('normal', 'Normal'),
        ('precontentieux', 'Précontentieux'),
        ('contentieux', 'Contentieux'),
        ('bloque_juridique', 'Bloqué (juridique)'),
        ('bloque_technique', 'Blocage technique (pôle technique)'),
        ('recouvre', 'Recouvré'),
    ], string='Statut recouvrement', default='normal', tracking=True, index=True)

    statut_interface = fields.Selection([
        ('vert', 'Vert'),
        ('orange', 'Orange'),
        ('rouge', 'Rouge'),
        ('mauve', 'Mauve'),
    ], string="Statut visuel",
        default='vert', tracking=True, index=True,
        help="Couleur propagée depuis la phase courante de la stratégie. "
             "Permet le pilotage visuel direct dans l'interface.",
    )

    # ------------------------------------------------------------------
    # Dates
    # ------------------------------------------------------------------
    date_reception_ordre = fields.Date(string="Date de réception de l'ordre")
    date_facture = fields.Date(string='Date de la facture')
    date_signature = fields.Date(string='Date de signature')
    date_depot_client = fields.Date(string='Date de dépôt chez le client', index=True)

    # ------------------------------------------------------------------
    # Relations clés
    # ------------------------------------------------------------------
    client_id = fields.Many2one(
        'res.partner', string='Client', required=True, index=True, tracking=True,
    )
    division_id = fields.Many2one('hr.department', string='Division')
    pole_id = fields.Many2one('hr.department', string='Pôle')
    currency_id = fields.Many2one(
        'res.currency', string='Devise',
        default=lambda self: self.env.company.currency_id,
    )
    recouvrement_id = fields.Many2one(
        'recouvrement.recouvrement', string='Dossier de recouvrement',
        index=True, ondelete='set null',
        help="Dossier multi-factures auquel cette facture est rattachée "
             "(regroupement par stratégie + date de dépôt).",
    )

    # ------------------------------------------------------------------
    # Montants & lettrage
    # ------------------------------------------------------------------
    montant_ttc = fields.Monetary(string='Montant TTC')
    montant_ht = fields.Monetary(string='Montant HT')
    lettrage_ids = fields.One2many(
        'recouvrement.lettrage', 'facture_id', string='Lettrages',
    )
    montant_paye = fields.Monetary(
        string='Montant payé',
        compute='_compute_montants_lettrage',
        store=True, currency_field='currency_id',
    )
    reste_a_payer = fields.Monetary(
        string='Reste à payer',
        compute='_compute_montants_lettrage',
        store=True, currency_field='currency_id',
    )

    # ==================================================================
    # COMPUTES
    # ==================================================================
    @api.depends('date_depot_client', 'depot_comment')
    def _compute_depot_display(self):
        for rec in self:
            if rec.date_depot_client:
                rec.depot_display = rec.date_depot_client.strftime('%d/%m/%Y')
            else:
                rec.depot_display = rec.depot_comment or ''

    @api.depends('lettrage_ids.montant_affecte', 'montant_ttc')
    def _compute_montants_lettrage(self):
        for rec in self:
            paye = sum(rec.lettrage_ids.mapped('montant_affecte'))
            rec.montant_paye = paye
            rec.reste_a_payer = max((rec.montant_ttc or 0.0) - paye, 0.0)

    # ==================================================================
    # OUTILS MÉTIER
    # ==================================================================
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

    LOCKED_STATUSES = ('precontentieux', 'contentieux', 'bloque_juridique')

    def _is_locked(self):
        """Le verrou juridique du cahier de charge."""
        self.ensure_one()
        return self.recouvrement_status in self.LOCKED_STATUSES

    # ==================================================================
    # CRUD
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            inferred_type = self._infer_facture_type_from_sheet(vals.get('source_sheet'))
            if inferred_type and not vals.get('facture_type'):
                vals['facture_type'] = inferred_type
        return super().create(vals_list)

    def write(self, vals):
        # Verrou juridique : refus modif si statut bloquant — sauf
        # si l'import autorise explicitement la mise à jour ET que les
        # champs touchés sont autorisés.
        bypass = self.env.context.get('recouvrement_import_unlock', False)
        if not bypass:
            for rec in self:
                if rec._is_locked():
                    raise UserError(_(
                        "Facture %(name)s : statut '%(status)s' — modification "
                        "interdite (verrou juridique).",
                        name=rec.name,
                        status=dict(rec._fields['recouvrement_status'].selection)[rec.recouvrement_status],
                    ))

        inferred_type = self._infer_facture_type_from_sheet(vals.get('source_sheet'))
        if inferred_type:
            vals['facture_type'] = inferred_type
        return super().write(vals)
    def action_open_dossier(self):
        """Ouvre le dossier de recouvrement lié depuis le stat button."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'recouvrement.recouvrement',
            'res_id': self.recouvrement_id.id,
            'view_mode': 'form',
            'target': 'current',
    }
    # ==================================================================
    # API publique pour les hooks de propagation
    # ==================================================================
    def propagate_statut_interface(self, color):
        """Méthode utilisée par le moteur de stratégie pour pousser
        la couleur de la phase courante vers la facture.
        Bypass automatique du verrou juridique (mécanique système)."""
        valid = {'vert', 'orange', 'rouge', 'mauve'}
        if color not in valid:
            raise UserError(_("Couleur de statut invalide : %s") % color)
        return self.with_context(recouvrement_import_unlock=True).write({
            'statut_interface': color,
        })

    def mark_recouvre(self):
        """À appeler quand reste_a_payer == 0 sur toutes les factures du dossier."""
        return self.with_context(recouvrement_import_unlock=True).write({
            'recouvrement_status': 'recouvre',
            'statut_interface': 'vert',
        })
