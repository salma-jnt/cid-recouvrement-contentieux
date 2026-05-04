"""
Modèle Action unifiée — refactor v2.0.0

FUSION MAJEURE : remplace 3 modèles précédents
  - recouvrement.action (squelette)
  - recouvrement.appel (modèle séparé, 246 lignes)
  - recouvrement.email (modèle séparé, 320 lignes)

→ un seul modèle recouvrement.action avec champs conditionnels par action_type.

Apports vs v1 :
  + state 'reporte' + méthode action_reporter() (boucle J+1)
  + client_id (Many2one) — cible précise dans le dossier multi-clients
  + action_template_id (Many2one) — traçabilité phase d'origine
  + Champs spécifiques email : destinataire_email, corps_email, pieces_jointes_ids
  + Champs spécifiques appel : duree_minutes, notes_appel, action_prise
  + Logique Outlook centralisée (un seul endroit, plus 2 copies)
  + Logique d'envoi mail centralisée
  + propagation auto du statut_interface_cible vers les factures à la transition de phase
"""
from datetime import timedelta
from email.utils import parseaddr
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class RecouvrementAction(models.Model):
    _name = 'recouvrement.action'
    _description = 'Action de recouvrement (appel, email, courrier...)'
    _order = 'mandatory_date, id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ==================================================================
    # CHAMPS COMMUNS
    # ==================================================================
    name = fields.Char(string='Action', required=True, tracking=True)
    comment = fields.Text(string='Commentaire')

    recouvrement_id = fields.Many2one(
        'recouvrement.recouvrement', string='Dossier de recouvrement',
        required=True, ondelete='cascade', index=True,
    )
    client_id = fields.Many2one(
        'res.partner', string='Client cible', required=True, index=True,
        help="Identifie le client précis ciblé par cette action "
             "à l'intérieur du dossier multi-clients.",
    )
    action_template_id = fields.Many2one(
        'recouvrement.action.template', string="Modèle (phase d'origine)",
        ondelete='set null',
    )
    procedure_id = fields.Many2one(
        'recouvrement.procedure', string='Procédure',
        related='recouvrement_id.procedure_id',
        store=True, readonly=True,
    )
    responsible_id = fields.Many2one(
        'res.users', string='Responsable',
        default=lambda self: self.env.user,
        tracking=True,
    )

    action_type = fields.Selection([
        ('appel', 'Appel'),
        ('email', 'Email'),
        ('courrier', 'Courrier'),
        ('mise_en_demeure', 'Mise en demeure'),
        ('contentieux', 'Contentieux'),
    ], string='Type', required=True, default='appel', index=True)

    priority = fields.Selection([
        ('0', 'Basse'),
        ('1', 'Normale'),
        ('2', 'Haute'),
    ], string='Priorité', default='1')

    state = fields.Selection([
        ('todo', 'À faire'),
        ('done', 'Réalisée'),
        ('reporte', 'Reportée'),
        ('cancel', 'Annulée'),
    ], string='Statut', default='todo', tracking=True, index=True)

    mandatory_date = fields.Date(string='Échéance prévue', index=True)
    date_done = fields.Date(string='Date de réalisation')
    is_overdue = fields.Boolean(
        string='En retard',
        compute='_compute_is_overdue', store=True,
    )

    # ==================================================================
    # CHAMPS SPÉCIFIQUES — APPEL
    # ==================================================================
    duree_minutes = fields.Integer(string='Durée (minutes)')
    notes_appel = fields.Text(string="Notes d'appel")
    action_prise = fields.Selection([
        ('aucune', 'Aucune'),
        ('paiement', 'Promesse de paiement'),
        ('plan_paiement', 'Plan de paiement'),
        ('dialogue', 'Dialogue établi'),
        ('non_joignable', 'Non joignable'),
        ('litige', 'Litige déclaré'),
        ('escalade', 'Escalade'),
    ], string='Action prise (issue)', default='aucune')

    # ==================================================================
    # CHAMPS SPÉCIFIQUES — EMAIL / COURRIER
    # ==================================================================
    destinataire_email = fields.Char(string='Email destinataire')
    corps_email = fields.Html(string="Corps de l'email")
    sujet_email = fields.Char(string="Objet de l'email")
    pieces_jointes_ids = fields.Many2many(
        'ir.attachment', string='Pièces jointes',
    )
    email_status = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('envoye', 'Envoyé'),
        ('lu', 'Lu'),
        ('reponse', 'Réponse reçue'),
        ('erreur', "Erreur d'envoi"),
    ], string='État email', default='brouillon')
    date_envoi = fields.Datetime(string="Date d'envoi")
    date_lecture = fields.Datetime(string='Date de lecture')

    # ==================================================================
    # OUTLOOK (commun aux types appel/email — un seul code)
    # ==================================================================
    planned_datetime = fields.Datetime(string='Date/heure planifiée')
    outlook_event_id = fields.Char(string='Outlook Event ID', copy=False)
    outlook_web_link = fields.Char(string='Lien Outlook', copy=False)
    outlook_sync_state = fields.Selection([
        ('not_synced', 'Non synchronisé'),
        ('synced', 'Synchronisé'),
        ('error', 'Erreur'),
    ], string='Sync Outlook', default='not_synced', copy=False)
    outlook_sync_error = fields.Text(string='Erreur de synchronisation', copy=False)

    # ==================================================================
    # COMPUTES
    # ==================================================================
    @api.depends('state', 'mandatory_date')
    def _compute_is_overdue(self):
        today = fields.Date.today()
        for rec in self:
            rec.is_overdue = bool(
                rec.state in ('todo', 'reporte')
                and rec.mandatory_date
                and rec.mandatory_date < today
            )

    # ==================================================================
    # CRUD
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        # Pré-remplir destinataire_email depuis le client si type email
        for vals in vals_list:
            if vals.get('action_type') in ('email', 'courrier', 'mise_en_demeure'):
                if not vals.get('destinataire_email') and vals.get('client_id'):
                    client = self.env['res.partner'].browse(vals['client_id'])
                    if client.email:
                        vals['destinataire_email'] = client.email
                # Pré-remplir sujet/corps depuis le template si dispo
                if vals.get('action_template_id'):
                    template = self.env['recouvrement.action.template'].browse(
                        vals['action_template_id']
                    )
                    if not vals.get('sujet_email') and template.email_subject_template:
                        vals['sujet_email'] = template.email_subject_template
                    if not vals.get('corps_email') and template.email_body_template:
                        vals['corps_email'] = template.email_body_template
        records = super().create(vals_list)
        records.mapped('recouvrement_id')._update_state()
        return records

    def write(self, vals):
        res = super().write(vals)
        # Mise à jour du dossier
        self.mapped('recouvrement_id')._update_state()

        # Si on change de phase courante (action devient done) → propager statut_interface
        if 'state' in vals and vals['state'] == 'done':
            self._propagate_statut_interface_to_factures()
            # Vérifier avancement de phase
            dossiers = self.mapped('recouvrement_id')
            for dossier in dossiers:
                dossier._check_and_advance_phase()

        # Sync Outlook automatique sur les champs sensibles
        if not self.env.context.get('skip_outlook_sync'):
            watched = {'name', 'planned_datetime', 'responsible_id', 'comment',
                       'corps_email', 'state'}
            if watched.intersection(vals):
                cancelled = self.filtered(
                    lambda r: r.state == 'cancel' and r.outlook_event_id
                )
                if cancelled:
                    cancelled.action_annuler_outlook()
                to_update = self.filtered(
                    lambda r: r.outlook_event_id and r.state != 'cancel'
                              and r.planned_datetime
                )
                if to_update:
                    to_update._sync_with_outlook(auto=True)
        return res

    def unlink(self):
        dossiers = self.mapped('recouvrement_id')
        res = super().unlink()
        dossiers._update_state()
        return res

    # ==================================================================
    # ACTIONS DE WORKFLOW
    # ==================================================================
    def action_done(self):
        for rec in self:
            rec.state = 'done'
            rec.date_done = fields.Date.today()
        self._propagate_statut_interface_to_factures()
        # Vérifier si toutes les actions de la phase sont terminées
        # → planifier automatiquement la phase suivante
        dossiers = self.mapped('recouvrement_id')
        for dossier in dossiers:
            dossier._check_and_advance_phase()
        return True

    def action_reset(self):
        self.write({
            'state': 'todo',
            'date_done': False,
        })
        return True

    def action_cancel(self):
        self.write({'state': 'cancel'})
        return True

    def action_reporter(self, motif=None):
        """
        Boucle de rattrapage J+1 du cahier de charge :
          1. L'action courante passe à 'reporte'
          2. Une nouvelle action en 'todo' est générée à J+1
             (ou demain si pas de date prévue)
          3. Note auto : « Reporté depuis l'action #X »
        """
        for rec in self:
            rec.state = 'reporte'
            base_date = rec.mandatory_date or fields.Date.today()
            new_date = base_date + timedelta(days=1)

            note = _("Reporté depuis l'action #%s (%s)") % (rec.id, rec.name)
            if motif:
                note += "\n" + _("Motif : %s") % motif

            self.create({
                'name': rec.name,
                'recouvrement_id': rec.recouvrement_id.id,
                'client_id': rec.client_id.id,
                'action_template_id': rec.action_template_id.id,
                'action_type': rec.action_type,
                'mandatory_date': new_date,
                'comment': note,
                'responsible_id': rec.responsible_id.id,
                'priority': rec.priority,
                'destinataire_email': rec.destinataire_email,
            })
        return True

    # ==================================================================
    # PROPAGATION VISUELLE (statut_interface)
    # ==================================================================
    def _propagate_statut_interface_to_factures(self):
        """Lorsqu'une action devient 'done', la phase courante du dossier
        change. On copie le statut_interface_cible de la phase courante
        sur toutes les factures du client concerné dans le dossier.
        Si la couleur cible est 'orange' → blocage technique."""
        for action in self:
            if not action.recouvrement_id or not action.client_id:
                continue
            # Trouver la prochaine phase pendante pour ce client
            next_action = action.recouvrement_id.action_ids.filtered(
                lambda a: (
                    a.state in ('todo', 'reporte')
                    and a.client_id == action.client_id
                )
            ).sorted(key=lambda a: (a.mandatory_date or fields.Date.today(), a.id))

            if not next_action:
                continue
            template = next_action[:1].action_template_id
            if not template or not template.statut_interface_cible:
                continue

            color = template.statut_interface_cible
            client_factures = action.recouvrement_id.facture_ids.filtered(
                lambda f: f.client_id == action.client_id
            )
            client_factures.propagate_statut_interface(color)

            # Hook blocage technique : couleur orange
            if color == 'orange':
                client_factures.with_context(
                    recouvrement_import_unlock=True
                ).write({'recouvrement_status': 'bloque_technique'})
                # Notifier le pôle technique via activity
                client_factures._notifier_pole_technique(action)

    # ==================================================================
    # ENVOI EMAIL (centralisé)
    # ==================================================================
    def _validate_email_address(self, email_address, label):
        address = (email_address or '').strip()
        if not address or '@' not in parseaddr(address)[1]:
            raise UserError(_("%s : email invalide ou manquant.") % label)
        return address

    def _get_sender_email(self):
        company = self.env.company
        if company.email:
            return self._validate_email_address(company.email, _("Email société"))
        return self._validate_email_address(
            self.env.user.email, _("Email utilisateur")
        )

    def action_envoyer_email(self):
        """Envoie l'email via le serveur mail Odoo."""
        for rec in self:
            if rec.action_type not in ('email', 'courrier', 'mise_en_demeure'):
                raise UserError(_(
                    "Cette action n'est pas de type email/courrier."
                ))
            try:
                email_from = rec._get_sender_email()
                email_to = rec._validate_email_address(
                    rec.destinataire_email, _("Adresse destinataire"),
                )
                mail_values = {
                    'subject': rec.sujet_email or rec.name,
                    'body_html': rec.corps_email or '',
                    'email_from': email_from,
                    'email_to': email_to,
                    'reply_to': email_from,
                    'model': 'recouvrement.action',
                    'res_id': rec.id,
                    'auto_delete': False,
                }
                if rec.pieces_jointes_ids:
                    mail_values['attachment_ids'] = [
                        (6, 0, rec.pieces_jointes_ids.ids)
                    ]
                mail = self.env['mail.mail'].create(mail_values)
                mail.send(raise_exception=True)

                rec.message_post(
                    body=_("Email envoyé à <strong>%s</strong>") % email_to,
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )
                rec.write({
                    'email_status': 'envoye',
                    'date_envoi': fields.Datetime.now(),
                    'state': 'done',
                    'date_done': fields.Date.today(),
                })
            except Exception as e:
                rec.write({'email_status': 'erreur'})
                _logger.error("Erreur envoi email action #%s : %s", rec.id, e)
                raise UserError(_(
                    "Erreur lors de l'envoi : %s"
                ) % str(e))
        return True

    # ==================================================================
    # OUTLOOK (centralisé — un seul code au lieu de 2 copies)
    # ==================================================================
    def _prepare_outlook_payload(self):
        self.ensure_one()
        if not self.planned_datetime:
            raise UserError(_("Veuillez renseigner la date/heure planifiée."))
        if not self.responsible_id.email:
            raise UserError(_(
                "Le responsable doit avoir un email pour la sync Outlook."
            ))
        start_dt = fields.Datetime.to_datetime(self.planned_datetime)
        end_dt = start_dt + timedelta(minutes=30)

        body_content = self.corps_email if self.action_type in (
            'email', 'courrier', 'mise_en_demeure',
        ) else (self.notes_appel or self.comment or '')

        location = {
            'appel': "Appel client",
            'email': "Relance écrite",
            'courrier': "Courrier",
            'mise_en_demeure': "Mise en demeure",
            'contentieux': "Contentieux",
        }.get(self.action_type, "Action de recouvrement")

        return {
            'subject': self.name or location,
            'body': {'contentType': 'HTML', 'content': body_content or ''},
            'start': {
                'dateTime': start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                'timeZone': 'UTC',
            },
            'location': {'displayName': location},
            'isReminderOn': True,
            'reminderMinutesBeforeStart': 15,
        }

    def _sync_with_outlook(self, auto=False):
        service = self.env['recouvrement.outlook.graph.service']
        for rec in self:
            try:
                payload = rec._prepare_outlook_payload()
                if rec.outlook_event_id:
                    data = service.update_event(
                        rec.responsible_id.email, rec.outlook_event_id, payload,
                    )
                    event_id = data.get('id', rec.outlook_event_id)
                    web_link = data.get('webLink', rec.outlook_web_link)
                else:
                    data = service.create_event(rec.responsible_id.email, payload)
                    event_id = data.get('id')
                    web_link = data.get('webLink')

                rec.with_context(skip_outlook_sync=True).write({
                    'outlook_event_id': event_id,
                    'outlook_web_link': web_link,
                    'outlook_sync_state': 'synced',
                    'outlook_sync_error': False,
                })
            except Exception as err:
                rec.with_context(skip_outlook_sync=True).write({
                    'outlook_sync_state': 'error',
                    'outlook_sync_error': str(err),
                })
                if not auto:
                    raise

    def action_planifier_outlook(self):
        self._sync_with_outlook(auto=False)
        return True

    def action_ouvrir_outlook(self):
        self.ensure_one()
        if not self.outlook_web_link:
            raise UserError(_("Aucun lien Outlook disponible."))
        return {
            'type': 'ir.actions.act_url',
            'url': self.outlook_web_link,
            'target': 'new',
        }

    def action_annuler_outlook(self):
        service = self.env['recouvrement.outlook.graph.service']
        for rec in self:
            if rec.outlook_event_id and rec.responsible_id.email:
                try:
                    service.delete_event(
                        rec.responsible_id.email, rec.outlook_event_id,
                    )
                except Exception as err:
                    rec.with_context(skip_outlook_sync=True).write({
                        'outlook_sync_state': 'error',
                        'outlook_sync_error': str(err),
                    })
                    continue
            rec.with_context(skip_outlook_sync=True).write({
                'outlook_event_id': False,
                'outlook_web_link': False,
                'outlook_sync_state': 'not_synced',
                'outlook_sync_error': False,
            })
        return True