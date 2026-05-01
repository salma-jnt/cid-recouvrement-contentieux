"""
Modèle Encaissement — refactor v2.0.0

Changements vs v1 :
  - Suppression du lien direct facture_id (le lettrage passe par recouvrement.lettrage)
  + client_id devient direct (Many2one), plus un related sur facture
  + montant_alloue (computed via lettrages)
  + reste_a_allouer (computed)
  + etat_lettrage Selection (en_cours / solde)
  + lettrage_ids (One2many)
  + recouvrement_id reste optionnel pour rattachement informatif

Workflow chap. 5 du cahier :
  1. Import / création de l'encaissement avec un montant et un client
  2. Agent ouvre l'encaissement → page custom OWL (à venir phase 3)
  3. Page affiche reste_a_allouer + factures non soldées du client
  4. Agent crée des lettrages (recouvrement.lettrage) — montants validés par contraintes
  5. Quand reste_a_allouer == 0 → etat_lettrage = solde
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class RecouvrementEncaissement(models.Model):
    _name = 'recouvrement.encaissement'
    _description = 'Encaissement (paiement client global)'
    _order = 'date_operation desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Référence', required=True, default='Nouveau',
        copy=False, index=True,
    )
    client_id = fields.Many2one(
        'res.partner', string='Client', required=True, index=True, tracking=True,
        help="Le client à qui appartient ce paiement. Le lettrage ciblera "
             "uniquement les factures non soldées de ce client.",
    )

    # Champs métier directs (plus de related sur une facture)
    code_affaire = fields.Char(string="Code d'affaire")
    pole_id = fields.Many2one('hr.department', string='Pôle')

    montant = fields.Monetary(
        string='Montant',
        required=True, tracking=True,
    )
    penalite = fields.Monetary(string='Pénalité')

    date_operation = fields.Date(
        string="Date d'opération", required=True,
        default=fields.Date.context_today,
    )
    banque = fields.Char(string='Banque')
    observation = fields.Text(string='Observation')

    mode_paiement = fields.Selection([
        ('virement', 'Virement'),
        ('espece', 'Espèces'),
        ('cheque', 'Chèque'),
        ('autre', 'Autre'),
    ], string='Mode de paiement', default='virement', tracking=True)

    currency_id = fields.Many2one(
        'res.currency', string='Devise',
        default=lambda self: self.env.company.currency_id,
    )

    # Lettrage
    lettrage_ids = fields.One2many(
        'recouvrement.lettrage', 'encaissement_id', string='Lettrages',
    )
    montant_alloue = fields.Monetary(
        string='Montant alloué',
        compute='_compute_alloue',
        store=True, currency_field='currency_id',
    )
    reste_a_allouer = fields.Monetary(
        string='Reste à allouer',
        compute='_compute_alloue',
        store=True, currency_field='currency_id',
    )
    etat_lettrage = fields.Selection([
        ('en_cours', 'En cours'),
        ('solde', 'Soldé'),
    ], string='État du lettrage',
        default='en_cours',
        compute='_compute_etat_lettrage',
        store=True, tracking=True, index=True,
    )

    # Lien informatif vers un dossier (optionnel — le rattachement réel
    # passe par les lettrages individuels vers les factures)
    recouvrement_id = fields.Many2one(
        'recouvrement.recouvrement', string='Dossier (informatif)',
        ondelete='set null',
    )

    # ==================================================================
    # COMPUTES
    # ==================================================================
    @api.depends('lettrage_ids.montant_affecte', 'montant')
    def _compute_alloue(self):
        for rec in self:
            alloue = sum(rec.lettrage_ids.mapped('montant_affecte'))
            rec.montant_alloue = alloue
            rec.reste_a_allouer = max((rec.montant or 0.0) - alloue, 0.0)

    @api.depends('reste_a_allouer', 'montant')
    def _compute_etat_lettrage(self):
        for rec in self:
            if (rec.montant or 0.0) > 0 and rec.reste_a_allouer < 1e-6:
                rec.etat_lettrage = 'solde'
            else:
                rec.etat_lettrage = 'en_cours'

    # ==================================================================
    # CRUD
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                seq = self.env['ir.sequence'].next_by_code('recouvrement.encaissement')
                vals['name'] = seq or 'ENC/%s' % fields.Datetime.now().strftime('%Y%m%d%H%M%S')
        return super().create(vals_list)

    # ==================================================================
    # API publique pour la page de lettrage OWL (phase 3)
    # ==================================================================
    def get_factures_disponibles(self):
        """RPC : renvoie les factures non soldées du client, prêtes à être lettrées."""
        self.ensure_one()
        if not self.client_id:
            return []
        factures = self.env['recouvrement.facture'].search([
            ('client_id', '=', self.client_id.id),
            ('reste_a_payer', '>', 0.0),
            ('recouvrement_status', '!=', 'recouvre'),
        ], order='date_facture asc, id asc')
        return [{
            'id': f.id,
            'name': f.name,
            'code_affaire': f.code_affaire or '',
            'date_facture': f.date_facture and f.date_facture.isoformat() or '',
            'montant_ttc': f.montant_ttc or 0.0,
            'montant_paye': f.montant_paye or 0.0,
            'reste_a_payer': f.reste_a_payer or 0.0,
            'recouvrement_status': f.recouvrement_status,
            'statut_interface': f.statut_interface,
        } for f in factures]

    def appliquer_lettrage(self, facture_id, montant):
        """RPC : crée un lettrage avec validation côté serveur (en plus de la contrainte)."""
        self.ensure_one()
        facture = self.env['recouvrement.facture'].browse(facture_id)
        if not facture.exists():
            raise UserError(_("Facture introuvable."))
        if facture.client_id != self.client_id:
            raise UserError(_("Cette facture n'appartient pas au client de l'encaissement."))
        if montant <= 0:
            raise UserError(_("Le montant doit être strictement positif."))
        if montant > self.reste_a_allouer + 1e-6:
            raise UserError(_(
                "Montant supérieur au reste à allouer (%.2f).",
            ) % self.reste_a_allouer)
        if montant > facture.reste_a_payer + 1e-6:
            raise UserError(_(
                "Montant supérieur au reste à payer de la facture (%.2f).",
            ) % facture.reste_a_payer)

        return self.env['recouvrement.lettrage'].create({
            'encaissement_id': self.id,
            'facture_id': facture.id,
            'montant_affecte': montant,
        }).id

    def auto_allouer_fifo(self):
        """Alloue automatiquement le reste à allouer aux factures non soldées
        du client, par ordre chronologique (FIFO)."""
        self.ensure_one()
        if self.reste_a_allouer <= 0:
            return False
        factures = self.env['recouvrement.facture'].search([
            ('client_id', '=', self.client_id.id),
            ('reste_a_payer', '>', 0.0),
        ], order='date_facture asc, id asc')

        lettrages = []
        restant = self.reste_a_allouer
        for facture in factures:
            if restant <= 0:
                break
            a_affecter = min(restant, facture.reste_a_payer)
            if a_affecter > 0:
                lettrages.append({
                    'encaissement_id': self.id,
                    'facture_id': facture.id,
                    'montant_affecte': a_affecter,
                })
                restant -= a_affecter
        if lettrages:
            self.env['recouvrement.lettrage'].create(lettrages)
        return len(lettrages)

    def action_open_lettrage_page(self):
        """Ouvre la page OWL moderne de lettrage live."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'recouvrement_contentieux.encaissement_lettrage_page',
            'name': 'Lettrage de %s' % self.name,
            'context': {'encaissement_id': self.id},
            'target': 'current',
        }
