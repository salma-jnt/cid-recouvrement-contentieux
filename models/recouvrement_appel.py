from odoo import api, fields, models
from odoo.exceptions import UserError
from datetime import datetime, timedelta


class RecouvrementAppel(models.Model):
    _name = 'recouvrement.appel'
    _description = 'Appel de relance'
    _order = 'date_appel desc'

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
    date_appel = fields.Datetime(
        string='Date de l\'appel',
        default=fields.Datetime.now,
        required=True
    )
    duree_minutes = fields.Integer(string='Durée (minutes)')
    statut = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('realise', 'Réalisé'),
        ('non_joignable', 'Non joignable'),
        ('rappel_needed', 'Rappel nécessaire'),
        ('refuse', 'Refusé'),
    ], string='Statut', default='brouillon')
    
    responsable_id = fields.Many2one(
        'res.users',
        string='Responsable',
        default=lambda self: self.env.user
    )
    notes = fields.Text(string='Notes')
    
    # Suivi
    action_prise = fields.Selection([
        ('aucune', 'Aucune'),
        ('paiement', 'Paiement convenu'),
        ('plan_paiement', 'Plan de paiement'),
        ('dialogue', 'Dialogue établi'),
        ('escalade', 'Escalade'),
    ], string='Action prise', default='aucune')
    
    date_prochain_appel = fields.Datetime(string='Date prochain appel')
    planned_datetime = fields.Datetime(string='Date/heure planifiee')
    planned_duration = fields.Integer(string='Duree planifiee (minutes)', default=30)

    outlook_event_id = fields.Char(string='Outlook Event ID', copy=False)
    outlook_web_link = fields.Char(string='Lien Outlook', copy=False)
    outlook_sync_state = fields.Selection([
        ('not_synced', 'Non synchronise'),
        ('synced', 'Synchronise'),
        ('error', 'Erreur'),
    ], string='Statut synchronisation', default='not_synced', copy=False)
    outlook_sync_error = fields.Text(string='Erreur de synchronisation', copy=False)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('statut') == 'realise' and not vals.get('duree_minutes'):
                vals['duree_minutes'] = 5
        return super().create(vals_list)

    def action_marquer_realise(self):
        self.write({'statut': 'realise'})

    def action_marquer_non_joignable(self):
        self.write({'statut': 'non_joignable'})

    def action_planifier_rappel(self):
        return {
            'name': 'Planifier un rappel',
            'type': 'ir.actions.act_window',
            'res_model': 'recouvrement.appel',
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
        end_dt = start_dt + timedelta(minutes=self.planned_duration or 30)
        return {
            'subject': self.name or 'Relance client',
            'body': {
                'contentType': 'HTML',
                'content': (self.notes or ''),
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
                'displayName': 'Relance client',
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
        res = super().write(vals)
        if self.env.context.get('skip_outlook_sync'):
            return res

        watched_fields = {'name', 'planned_datetime', 'planned_duration', 'responsable_id', 'notes', 'statut'}
        if watched_fields.intersection(vals):
            cancelled = self.filtered(lambda r: r.statut == 'refuse' and r.outlook_event_id)
            if cancelled:
                cancelled.action_annuler_outlook()

            to_update = self.filtered(lambda r: r.outlook_event_id and r.statut != 'refuse' and r.planned_datetime)
            if to_update:
                to_update._sync_with_outlook(auto=True)
        return res
