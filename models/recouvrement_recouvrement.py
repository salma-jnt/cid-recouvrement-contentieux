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

    # Index de la phase en cours (0 = première phase, -1 = terminée)
    # Toutes les actions créées appartiennent à UN seul numéro de phase.
    phase_index = fields.Integer(
        string='Index phase courante',
        default=0,
        help="0 = phase 1 active, 1 = phase 2, etc. -1 = procédure terminée.",
    )

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
        # NOTE: on ne génère PAS les actions ici car les factures ne sont pas
        # encore rattachées au dossier à ce stade. La planification est
        # déclenchée par _planifier_apres_rattachement() après le write()
        # de la facture (recouvrement_id) dans le wizard ou le modèle facture.
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

    def _planifier_apres_rattachement(self):
        """
        Appelé APRÈS qu'une ou plusieurs factures ont été rattachées au dossier.

        Cas 1 — Dossier nouveau (aucune action) :
            Génère la phase 0 pour tous les clients présents.

        Cas 2 — Dossier existant avec phase en cours (actions déjà là) :
            Vérifie si un nouveau client vient d'être ajouté (pas encore
            d'action pour lui dans la phase courante) et crée son action.

        Méthode idempotente — sûre à appeler plusieurs fois.
        """
        self.ensure_one()
        if not self.procedure_id:
            return
        # Uniquement les clients avec factures non recouvrées
        clients = self._get_clients_actifs()
        if not clients:
            return

        # Cas 1 : aucune action → planifier la phase 0 complète
        if not self.action_ids:
            self._planifier_phase(0)
            return

        # Cas 2 : phase en cours → vérifier les nouveaux clients sans action
        if self.phase_index < 0:
            return  # procédure terminée

        templates = self.procedure_id.action_template_ids.sorted(
            key=lambda t: (t.sequence, t.id)
        )
        if not templates or self.phase_index >= len(templates):
            return
        current_template = templates[self.phase_index]

        # Clients actifs (non soldés) sans action pour la phase courante
        clients_with_action = self.action_ids.filtered(
            lambda a: a.action_template_id == current_template
        ).mapped('client_id')
        # clients = déjà filtrés par _get_clients_actifs (reste_a_payer > 0)
        new_clients = clients - clients_with_action

        if not new_clients:
            return

        base_date = self._get_action_base_date()
        cumul_delay = sum(
            (t.delay or 0) for t in templates[:self.phase_index + 1]
        )
        action_date = base_date + timedelta(days=cumul_delay)

        actions_to_create = []
        for client in new_clients:
            actions_to_create.append({
                'name': current_template.name,
                'recouvrement_id': self.id,
                'client_id': client.id,
                'action_template_id': current_template.id,
                'action_type': current_template.action_type,
                'mandatory_date': action_date,
                'comment': current_template.description or False,
                'responsible_id': self.env.user.id,
            })
        if actions_to_create:
            self.env['recouvrement.action'].create(actions_to_create)
            self._update_state()

    def action_generate_actions(self):
        """Réinitialise la procédure depuis la phase 1.
        Supprime toutes les actions non réalisées et repart de zéro."""
        for record in self:
            if not record.procedure_id:
                raise UserError(_(
                    "Veuillez sélectionner une procédure avant de générer les actions."
                ))
            # Supprimer uniquement les actions non encore réalisées
            record.action_ids.filtered(lambda a: a.state != 'done').unlink()
            record.phase_index = 0
            record._planifier_phase(0)
        return True

    def _get_clients_actifs(self):
        """
        Retourne les clients du dossier pour lesquels il reste encore
        des factures à recouvrer.

        Un client est EXCLU si TOUTES ses factures dans ce dossier
        satisfont l'une des conditions suivantes :
          - reste_a_payer == 0 (déjà payée, même sans statut 'recouvre')
          - recouvrement_status == 'recouvre'

        Cela évite de créer des actions pour des factures déjà soldées.
        """
        self.ensure_one()
        clients_actifs = self.env['res.partner']
        for client in self.facture_ids.mapped('client_id'):
            factures_client = self.facture_ids.filtered(
                lambda f, c=client: f.client_id == c
            )
            # Garder le client si au moins 1 facture a encore du reste à payer
            # ET n'est pas marquée recouvrée
            if any(
                f.reste_a_payer > 0 and f.recouvrement_status != 'recouvre'
                for f in factures_client
            ):
                clients_actifs |= client
        return clients_actifs

    def _planifier_phase(self, phase_index):
        """
        Crée les actions pour UNE SEULE phase (phase_index = position 0-based
        dans la liste des templates triés par séquence).

        Règle du cahier de charge :
          - Phase planifiée = 1 action par CLIENT du dossier
          - La date de l'action = date_base + cumul des délais des phases 0..phase_index
          - Après la dernière phase, on ne crée rien (procédure terminée).
        """
        self.ensure_one()
        templates = self.procedure_id.action_template_ids.sorted(
            key=lambda t: (t.sequence, t.id)
        )
        if not templates or phase_index >= len(templates):
            # Toutes les phases sont terminées
            self.phase_index = -1
            self._update_state()
            return

        template = templates[phase_index]
        self.phase_index = phase_index

        # Calcul de la date cumulée depuis la date de base
        base_date = self._get_action_base_date()
        cumul_delay = sum(
            (t.delay or 0) for t in templates[:phase_index + 1]
        )
        action_date = base_date + timedelta(days=cumul_delay)

        # Uniquement les clients avec au moins 1 facture non recouvrée
        clients = self._get_clients_actifs()
        if not clients:
            # Tous les clients sont soldés → procédure terminée
            self.phase_index = -1
            self._update_state()
            return

        actions_to_create = []
        for client in clients:
            actions_to_create.append({
                'name': template.name,
                'recouvrement_id': self.id,
                'client_id': client.id,
                'action_template_id': template.id,
                'action_type': template.action_type,
                'mandatory_date': action_date,
                'comment': template.description or False,
                'responsible_id': self.env.user.id,
            })
        if actions_to_create:
            self.env['recouvrement.action'].create(actions_to_create)

        self._update_state()
        self.message_post(
            body=_(
                "📋 Phase <strong>%(num)s/%(total)s</strong> planifiée : "
                "<em>%(name)s</em> — échéance le %(date)s",
                num=phase_index + 1,
                total=len(templates),
                name=template.name,
                date=action_date.strftime('%d/%m/%Y'),
            ),
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )

    def _check_and_advance_phase(self):
        """
        Appelée après qu'une action est marquée 'done'.
        Vérifie si TOUTES les actions de la phase courante sont terminées.
        Si oui → planifie la phase suivante.
        """
        self.ensure_one()
        if self.phase_index < 0 or self.state in ('solde', 'bloque'):
            return

        templates = self.procedure_id.action_template_ids.sorted(
            key=lambda t: (t.sequence, t.id)
        )
        if not templates:
            return

        # Récupérer le template de la phase courante
        if self.phase_index >= len(templates):
            return
        current_template = templates[self.phase_index]

        # Actions de la phase courante = celles liées à ce template.
        # Règle de comptage par CLIENT :
        #   - Si un client a au moins 1 action 'todo'  → phase pas finie pour lui
        #   - Si toutes ses actions sont 'done' ou 'reporte' ou 'cancel'
        #     ET qu'il a au moins 1 'done'              → phase finie pour lui
        #   - 'reporte' seul (sans aucun 'done')        → on attend encore
        # En résumé : la phase avance quand chaque client a au moins 1 'done'
        # et plus aucun 'todo' dans cette phase.

        phase_actions = self.action_ids.filtered(
            lambda a: a.action_template_id == current_template
        )
        if not phase_actions:
            return

        # Grouper par client
        clients_in_phase = phase_actions.mapped('client_id')
        all_done = True
        for client in clients_in_phase:
            client_actions = phase_actions.filtered(lambda a, c=client: a.client_id == c)

            # Si toutes les factures de ce client ont reste_a_payer=0
            # → on considère ce client comme "terminé" peu importe l'état de ses actions
            factures_client = self.facture_ids.filtered(
                lambda f, c=client: f.client_id == c
            )
            client_solde = all(
                f.reste_a_payer == 0 or f.recouvrement_status == 'recouvre'
                for f in factures_client
            )
            if client_solde:
                # Annuler les éventuelles actions todo/reporte restantes
                pending = client_actions.filtered(lambda a: a.state in ('todo', 'reporte'))
                if pending:
                    pending.write({'state': 'cancel'})
                continue  # ce client ne bloque pas l'avancement

            has_todo = any(a.state == 'todo' for a in client_actions)
            has_done = any(a.state == 'done' for a in client_actions)
            if has_todo or not has_done:
                all_done = False
                break
        if all_done:
            next_index = self.phase_index + 1
            # Vérifier s'il reste encore des clients actifs avant de planifier
            clients_actifs = self._get_clients_actifs()
            if not clients_actifs:
                # Tous recouvrés → terminer la procédure
                self.phase_index = -1
                self._update_state()
                self.message_post(
                    body=_("✅ Toutes les factures du dossier sont recouvrées."),
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )
                return
            if next_index < len(templates):
                self._planifier_phase(next_index)
            else:
                # Dernière phase terminée
                self.phase_index = -1
                self._update_state()
                self.message_post(
                    body=_("✅ Toutes les phases de la procédure sont terminées."),
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )

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
