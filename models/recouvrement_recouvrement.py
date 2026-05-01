"""
Modèle Dossier de recouvrement — refactor v2.0.0

CHANGEMENT MAJEUR : passage de 1:1 (1 dossier = 1 facture) à 1:N
(1 dossier = plusieurs factures partageant la même stratégie + date de dépôt).

C'est la « logique du convoi » du chapitre 1 du cahier de charge.

Changements vs v1 :
  - facture_id (Many2one) → facture_ids (One2many)  ← RUPTURE
  + Champ nombre_factures (computed)
  + montant_ttc / montant_encaisse / reste_a_recouvrer recalculés en SOMME
  + États : ouvert / solde / bloque (alignés cahier)
  + _compute_next_action_date : chronomètre strict basé sur la phase prévue
  + Méthode classmethod _get_or_create_dossier(facture) — factorisée pour l'import
"""
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class Recouvrement(models.Model):
    _name = 'recouvrement.recouvrement'
    _description = 'Dossier de recouvrement (regroupement multi-factures)'
    _order = 'prochaine_echeance asc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ------------------------------------------------------------------
    # Identifiants
    # ------------------------------------------------------------------
    name = fields.Char(
        string='Référence', required=True, default='Nouveau dossier',
        copy=False, index=True,
    )

    state = fields.Selection([
        ('ouvert', 'Ouvert'),
        ('en_cours', 'En cours de relance'),
        ('en_retard', 'En retard'),
        ('bloque', 'Bloqué'),
        ('solde', 'Soldé'),
    ], string='Statut', default='ouvert', tracking=True, index=True)

    motif_blocage = fields.Text(string='Motif de blocage')

    # ------------------------------------------------------------------
    # Stratégie & regroupement
    # ------------------------------------------------------------------
    procedure_id = fields.Many2one(
        'recouvrement.procedure',
        string='Procédure / Stratégie',
        index=True, required=True,
    )
    date_depot_groupe = fields.Date(
        string='Date de dépôt (clé de regroupement)',
        index=True, required=True,
        help="Toutes les factures de ce dossier partagent cette date de dépôt.",
    )

    # ------------------------------------------------------------------
    # Relations
    # ------------------------------------------------------------------
    facture_ids = fields.One2many(
        'recouvrement.facture', 'recouvrement_id',
        string='Factures du dossier',
    )
    action_ids = fields.One2many(
        'recouvrement.action', 'recouvrement_id',
        string='Actions',
    )
    encaissement_ids = fields.One2many(
        'recouvrement.encaissement', 'recouvrement_id',
        string='Encaissements (informatif)',
        help="Encaissements explicitement rattachés à ce dossier. "
             "Le lettrage réel passe par recouvrement.lettrage et peut concerner "
             "des encaissements client-level non rattachés ici.",
    )
    currency_id = fields.Many2one(
        'res.currency', string='Devise',
        default=lambda self: self.env.company.currency_id,
    )

    # ------------------------------------------------------------------
    # Indicateurs (computed)
    # ------------------------------------------------------------------
    nombre_factures = fields.Integer(
        string='Nb factures',
        compute='_compute_nombre_factures',
        store=True,
    )
    nombre_clients = fields.Integer(
        string='Nb clients',
        compute='_compute_nombre_clients',
        store=True,
    )
    montant_ttc = fields.Monetary(
        string='Montant total TTC',
        compute='_compute_montants',
        store=True, currency_field='currency_id',
    )
    montant_encaisse = fields.Monetary(
        string='Montant encaissé',
        compute='_compute_montants',
        store=True, currency_field='currency_id',
    )
    reste_a_recouvrer = fields.Monetary(
        string='Reste à recouvrer',
        compute='_compute_montants',
        store=True, currency_field='currency_id',
    )

    phase_courante = fields.Char(
        string='Phase courante',
        compute='_compute_phase_courante',
        store=True,
    )

    last_action_date = fields.Date(
        string='Dernière action',
        compute='_compute_last_action_date',
        store=True,
    )
    next_action_date = fields.Date(
        string='Prochaine échéance technique',
        compute='_compute_next_action_date',
        store=True,
    )
    prochaine_echeance = fields.Date(
        string='Prochaine échéance',
        compute='_compute_prochaine_echeance',
        store=True,
        index=True,
    )

    # ==================================================================
    # COMPUTES
    # ==================================================================
    @api.depends('facture_ids')
    def _compute_nombre_factures(self):
        for rec in self:
            rec.nombre_factures = len(rec.facture_ids)

    @api.depends('facture_ids.client_id')
    def _compute_nombre_clients(self):
        for rec in self:
            rec.nombre_clients = len(rec.facture_ids.mapped('client_id'))

    @api.depends('facture_ids.montant_ttc', 'facture_ids.montant_paye',
                 'facture_ids.reste_a_payer')
    def _compute_montants(self):
        for rec in self:
            rec.montant_ttc = sum(rec.facture_ids.mapped('montant_ttc'))
            rec.montant_encaisse = sum(rec.facture_ids.mapped('montant_paye'))
            rec.reste_a_recouvrer = sum(rec.facture_ids.mapped('reste_a_payer'))

    @api.depends('action_ids.mandatory_date', 'action_ids.state',
                 'procedure_id', 'state')
    def _compute_phase_courante(self):
        for record in self:
            if record.state == 'bloque':
                record.phase_courante = 'Bloqué'
                continue
            if record.state == 'solde':
                record.phase_courante = 'Soldé'
                continue
            pending = record.action_ids.filtered(
                lambda a: a.state in ('todo', 'reporte')
            ).sorted(key=lambda a: (a.mandatory_date or fields.Date.today(), a.id))
            record.phase_courante = pending[:1].name if pending else (
                record.procedure_id.name or 'Suivi'
            )

    @api.depends('action_ids.mandatory_date', 'action_ids.state',
                 'action_ids.date_done')
    def _compute_last_action_date(self):
        for rec in self:
            done_dates = rec.action_ids.filtered(
                lambda a: a.state == 'done'
            ).mapped('date_done')
            rec.last_action_date = max(done_dates) if done_dates else False

    @api.depends('action_ids', 'action_ids.mandatory_date', 'action_ids.state')
    def _compute_next_action_date(self):
        for rec in self:
            pending_dates = rec.action_ids.filtered(
                lambda a: a.state in ('todo', 'reporte') and a.mandatory_date
            ).mapped('mandatory_date')
            rec.next_action_date = min(pending_dates) if pending_dates else False

    @api.depends('next_action_date', 'date_depot_groupe')
    def _compute_prochaine_echeance(self):
        for rec in self:
            rec.prochaine_echeance = rec.next_action_date or rec.date_depot_groupe

    # ==================================================================
    # CRUD & génération d'actions
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau dossier') == 'Nouveau dossier':
                seq = self.env['ir.sequence'].next_by_code('recouvrement.recouvrement')
                vals['name'] = seq or _('Dossier #%d') % self.env['recouvrement.recouvrement'].search_count([])
        records = super().create(vals_list)
        for rec in records:
            if rec.procedure_id and not rec.action_ids:
                rec.action_generate_actions()
        return records

    def _get_action_base_date(self):
        """Date de référence pour le calcul des délais des actions."""
        self.ensure_one()
        # Priorité : date du convoi > première facture
        if self.date_depot_groupe:
            return self.date_depot_groupe
        first = self.facture_ids[:1]
        return (
            (first and first.date_depot_client)
            or (first and first.date_facture)
            or fields.Date.today()
        )

    def action_generate_actions(self):
        """Génère les actions d'un dossier à partir des templates de la procédure.
        Une action est créée par template ET par client distinct dans le dossier
        (logique du convoi : chaque client doit valider chaque phase)."""
        action_obj = self.env['recouvrement.action']
        for record in self:
            if not record.procedure_id:
                raise UserError(_(
                    "Veuillez sélectionner une procédure avant de générer les actions."
                ))
            base_date = record._get_action_base_date()

            # Wipe les actions non encore réalisées
            record.action_ids.filtered(lambda a: a.state != 'done').unlink()

            clients = record.facture_ids.mapped('client_id')
            templates = record.procedure_id.action_template_ids.sorted(
                key=lambda t: (t.sequence, t.id)
            )

            actions_to_create = []
            for client in clients:
                running_date = base_date
                for template in templates:
                    running_date = running_date + timedelta(days=template.delay or 0)
                    actions_to_create.append({
                        'name': template.name,
                        'recouvrement_id': record.id,
                        'client_id': client.id,
                        'action_template_id': template.id,
                        'action_type': template.action_type,
                        'mandatory_date': running_date,
                        'comment': template.description or False,
                        'responsible_id': self.env.user.id,
                    })
            if actions_to_create:
                action_obj.create(actions_to_create)

            record._update_state()
        return True

    # ==================================================================
    # ÉTAT & PROPAGATION
    # ==================================================================
    def _update_state(self):
        """Recalcule le statut du dossier à partir des actions et des factures."""
        today = fields.Date.today()
        for rec in self:
            if rec.state == 'bloque':
                continue

            # Soldé : toutes les factures ont reste_a_payer == 0
            if rec.facture_ids and all(
                (f.reste_a_payer or 0.0) <= 0.0 for f in rec.facture_ids
            ):
                rec.state = 'solde'
                rec.facture_ids.mark_recouvre()
                continue

            pending = rec.action_ids.filtered(
                lambda a: a.state in ('todo', 'reporte')
            )
            overdue = pending.filtered(
                lambda a: a.mandatory_date and a.mandatory_date < today
            )

            if overdue:
                rec.state = 'en_retard'
            elif pending:
                rec.state = 'en_cours'
            else:
                rec.state = 'ouvert'

    def action_block(self, motif=None):
        for rec in self:
            rec.state = 'bloque'
            if motif:
                rec.motif_blocage = motif

    # ==================================================================
    # FACTORY : regroupement automatique à l'import
    # ==================================================================
    @api.model
    def get_or_create_for_facture(self, facture):
        """
        Trouve ou crée le dossier de recouvrement pour une facture donnée
        selon la règle du cahier :
            « Un dossier regroupe les factures partageant la même Stratégie
              et la même Date de dépôt. »

        Renvoie le dossier (existant ou créé), la facture est rattachée par l'appelant.
        """
        if not facture:
            return False

        # Stratégie déduite via le type du client
        procedure = (
            facture.client_id
            and facture.client_id.client_type_id
            and facture.client_id.client_type_id.procedure_id
        )
        if not procedure:
            procedure = self.env.ref(
                'recouvrement_contentieux.procedure_standard',
                raise_if_not_found=False,
            )
        if not procedure:
            raise UserError(_(
                "Aucune procédure de recouvrement disponible. Configurez "
                "au moins une procédure standard."
            ))

        date_depot = facture.date_depot_client
        if not date_depot:
            # Sans date de dépôt, on ne peut pas regrouper proprement.
            # Création d'un dossier dédié pour ne pas mélanger.
            date_depot = facture.date_facture or fields.Date.today()

        existing = self.search([
            ('procedure_id', '=', procedure.id),
            ('date_depot_groupe', '=', date_depot),
            ('state', 'not in', ('solde', 'bloque')),
        ], limit=1)

        if existing:
            return existing

        return self.create({
            'procedure_id': procedure.id,
            'date_depot_groupe': date_depot,
        })

    def action_open_dossier_page(self):
        """Ouvre la page OWL (SaaS) détaillée du dossier."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'recouvrement_contentieux.dossier_detail_page',
            'context': {'dossier_id': self.id},
            'target': 'current',
        }
