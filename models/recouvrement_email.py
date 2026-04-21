from email.utils import parseaddr

from odoo import api, fields, models
from odoo.exceptions import UserError
import logging
from datetime import timedelta

_logger = logging.getLogger(__name__)


class RecouvrementEmail(models.Model):
    _name = 'recouvrement.email'
    _description = 'Email de relance'
    _order = 'date_email desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Objet', required=True)
    facture_id = fields.Many2one(
        'recouvrement.facture',
        string='Facture',
        required=True,
        ondelete='cascade'
    )
    client_id = fields.Many2one(
        'res.partner',
        string='Client',
        related='facture_id.client_id',
        readonly=True,
        store=True
    )
    procedure_id = fields.Many2one(
        'recouvrement.procedure',
        string='Procédure',
        compute='_compute_procedure_id',
        readonly=True,
        store=True,
    )
    action_template_id = fields.Many2one(
        'recouvrement.action.template',
        string='Action de procédure',
        domain="[('procedure_id', '=', procedure_id), ('action_type', 'in', ['courrier', 'mise_en_demeure', 'contentieux'])]",
    )
    destinataire_email = fields.Char(
        string='Email destinataire',
        required=True
    )
    
    date_email = fields.Datetime(
        string='Date d\'envoi',
        default=fields.Datetime.now,
        required=True
    )
    statut = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('envoye', 'Envoyé'),
        ('lu', 'Lu'),
        ('reponse', 'Réponse reçue'),
        ('erreur', 'Erreur d\'envoi'),
    ], string='Statut', default='brouillon', tracking=True)
    
    responsable_id = fields.Many2one(
        'res.users',
        string='Responsable',
        default=lambda self: self.env.user
    )
    
    # Contenu
    corps_email = fields.Html(string='Contenu de l\'email', required=True)
    modele_utilise = fields.Selection([
        ('rappel_standard', 'Rappel standard'),
        ('mise_en_demeure', 'Mise en demeure'),
        ('plan_paiement', 'Proposition plan de paiement'),
        ('relance_urgent', 'Relance urgente'),
    ], string='Modèle utilisé', default='rappel_standard')
    
    # Tracking
    date_lecture = fields.Datetime(string='Date de lecture')
    date_reponse = fields.Datetime(string='Date de réponse')
    contenu_reponse = fields.Text(string='Contenu de la réponse')
    
    # Pièces jointes (optionnel)
    pieces_jointes_ids = fields.Many2many(
        'ir.attachment',
        string='Pièces jointes'
    )

    planned_datetime = fields.Datetime(string='Date/heure planifiee')

    outlook_event_id = fields.Char(string='Outlook Event ID', copy=False)
    outlook_web_link = fields.Char(string='Lien Outlook', copy=False)
    outlook_sync_state = fields.Selection([
        ('not_synced', 'Non synchronise'),
        ('synced', 'Synchronise'),
        ('error', 'Erreur'),
    ], string='Statut synchronisation', default='not_synced', copy=False)
    outlook_sync_error = fields.Text(string='Erreur de synchronisation', copy=False)

    @api.model
    def _suggest_action_template_id(self, facture_id):
        facture = self.env['recouvrement.facture'].browse(facture_id)
        procedure = facture.client_id.client_type_id.procedure_id if facture.client_id and facture.client_id.client_type_id else False
        if not procedure:
            procedure = self.env.ref('recouvrement_contentieux.procedure_standard', raise_if_not_found=False)
        if not procedure:
            return False
        template = self.env['recouvrement.action.template'].search([
            ('procedure_id', '=', procedure.id),
            ('action_type', 'in', ['courrier', 'mise_en_demeure', 'contentieux']),
        ], order='sequence, id', limit=1)
        return template.id or False

    @api.depends('facture_id', 'facture_id.client_id', 'facture_id.client_id.client_type_id', 'facture_id.client_id.client_type_id.procedure_id')
    def _compute_procedure_id(self):
        standard_procedure = self.env.ref('recouvrement_contentieux.procedure_standard', raise_if_not_found=False)
        for rec in self:
            procedure = rec.facture_id.client_id.client_type_id.procedure_id if rec.facture_id and rec.facture_id.client_id and rec.facture_id.client_id.client_type_id else False
            rec.procedure_id = procedure or standard_procedure

    @api.onchange('facture_id')
    def _onchange_facture_id_set_action_template(self):
        for rec in self:
            if rec.facture_id:
                rec.action_template_id = rec._suggest_action_template_id(rec.facture_id.id)

    def _validate_email_address(self, email_address, label):
        address = (email_address or '').strip()
        if not address or '@' not in parseaddr(address)[1]:
            raise UserError(f'{label} email invalide ou manquant.')
        return address

    def _get_sender_email(self):
        company_email = self._validate_email_address(self.env.company.email, 'L\'email de la société') if self.env.company.email else ''
        if company_email:
            return company_email
        user_email = self._validate_email_address(self.env.user.email, 'L\'email de l\'utilisateur')
        return user_email
    
    def action_envoyer_email(self):
        """Envoyer l'email via le serveur mail Odoo et l'enregistrer dans le chatter."""
        try:
            self.ensure_one()
            email_from = self._get_sender_email()
            email_to = self._validate_email_address(self.destinataire_email, 'L\'adresse du destinataire')

            mail_values = {
                'subject': self.name,
                'body_html': self.corps_email,
                'email_from': email_from,
                'email_to': email_to,
                'reply_to': email_from,
                'model': 'recouvrement.email',
                'res_id': self.id,
                'auto_delete': False,
            }

            if self.pieces_jointes_ids:
                mail_values['attachment_ids'] = [(6, 0, self.pieces_jointes_ids.ids)]

            mail = self.env['mail.mail'].create(mail_values)
            mail.send(raise_exception=True)

            self.message_post(
                body=(
                    f"Email envoyé à <strong>{email_to}</strong> depuis <strong>{email_from}</strong>."
                ),
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
            
            self.write({
                'statut': 'envoye',
                'date_email': fields.Datetime.now()
            })
            
            _logger.info('Email de relance envoyé: %s à %s', self.name, email_to)
            
        except Exception as e:
            self.write({'statut': 'erreur'})
            _logger.error('Erreur lors de l\'envoi de l\'email: %s', e)
            raise UserError(f'Erreur lors de l\'envoi de l\'email: {str(e)}')

    def action_envoyer_brouillon(self):
        """Passer du statut brouillon à envoyer"""
        if self.statut != 'brouillon':
            raise UserError('Seuls les brouillons peuvent être envoyés.')
        self.action_envoyer_email()

    def action_marquer_lu(self):
        """Marquer l'email comme lu (manuel, pour suivi)"""
        self.write({
            'statut': 'lu',
            'date_lecture': fields.Datetime.now()
        })

    def action_ajouter_reponse(self):
        """Ajouter une réponse reçue"""
        return {
            'name': 'Ajouter une réponse',
            'type': 'ir.actions.act_window',
            'res_model': 'recouvrement.email',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _prepare_outlook_payload(self):
        self.ensure_one()
        if not self.planned_datetime:
            raise UserError('Veuillez renseigner la date/heure planifiee.')
        if not self.responsable_id.email:
            raise UserError('Le responsable doit avoir un email pour la synchronisation Outlook.')

        start_dt = fields.Datetime.to_datetime(self.planned_datetime)
        end_dt = start_dt + timedelta(minutes=30)
        return {
            'subject': self.name or 'Relance ecrite',
            'body': {
                'contentType': 'HTML',
                'content': (self.corps_email or ''),
            },
            'start': {
                'dateTime': start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                'timeZone': 'UTC',
            },
            'location': {
                'displayName': 'Relance ecrite',
            },
            'isReminderOn': True,
            'reminderMinutesBeforeStart': 15,
        }

    def _sync_with_outlook(self, auto=False):
        service = self.env['recouvrement.outlook.graph.service']
        for rec in self:
            try:
                payload = rec._prepare_outlook_payload()
                if rec.outlook_event_id:
                    data = service.update_event(rec.responsable_id.email, rec.outlook_event_id, payload)
                    event_id = data.get('id', rec.outlook_event_id)
                    web_link = data.get('webLink', rec.outlook_web_link)
                else:
                    data = service.create_event(rec.responsable_id.email, payload)
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
            raise UserError('Aucun lien Outlook disponible pour cette relance.')
        return {
            'type': 'ir.actions.act_url',
            'url': self.outlook_web_link,
            'target': 'new',
        }

    def action_annuler_outlook(self):
        service = self.env['recouvrement.outlook.graph.service']
        for rec in self:
            if rec.outlook_event_id and rec.responsable_id.email:
                try:
                    service.delete_event(rec.responsable_id.email, rec.outlook_event_id)
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

    def write(self, vals):
        if vals.get('facture_id') and not vals.get('action_template_id'):
            vals['action_template_id'] = self._suggest_action_template_id(vals['facture_id'])
        res = super().write(vals)
        if self.env.context.get('skip_outlook_sync'):
            return res

        watched_fields = {'name', 'planned_datetime', 'responsable_id', 'corps_email'}
        if watched_fields.intersection(vals):
            to_update = self.filtered(lambda r: r.outlook_event_id and r.planned_datetime)
            if to_update:
                to_update._sync_with_outlook(auto=True)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('facture_id') and not vals.get('action_template_id'):
                vals['action_template_id'] = self._suggest_action_template_id(vals['facture_id'])
            if not vals.get('modele_utilise'):
                vals['modele_utilise'] = 'rappel_standard'
        return super().create(vals_list)
