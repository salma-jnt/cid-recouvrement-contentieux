import requests

from odoo import _, models
from odoo.exceptions import UserError


class OutlookGraphService(models.AbstractModel):
    _name = 'recouvrement.outlook.graph.service'
    _description = 'Service Microsoft Graph pour Outlook'

    def _get_graph_config(self):
        params = self.env['ir.config_parameter'].sudo()
        tenant_id = params.get_param('recouvrement.outlook_tenant_id')
        client_id = params.get_param('recouvrement.outlook_client_id')
        client_secret = params.get_param('recouvrement.outlook_client_secret')
        if not all([tenant_id, client_id, client_secret]):
            raise UserError(_("Configuration Outlook manquante. Configurez tenant_id, client_id et client_secret dans Paramètres techniques."))
        return tenant_id, client_id, client_secret

    def get_access_token(self):
        tenant_id, client_id, client_secret = self._get_graph_config()
        token_url = f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'
        payload = {
            'client_id': client_id,
            'client_secret': client_secret,
            'scope': 'https://graph.microsoft.com/.default',
            'grant_type': 'client_credentials',
        }
        response = requests.post(token_url, data=payload, timeout=30)
        if response.status_code != 200:
            raise UserError(_("Impossible d'obtenir un token Microsoft Graph: %s") % response.text)
        return response.json().get('access_token')

    def _headers(self):
        return {
            'Authorization': f'Bearer {self.get_access_token()}',
            'Content-Type': 'application/json',
        }

    def create_event(self, user_email, event_payload):
        url = f'https://graph.microsoft.com/v1.0/users/{user_email}/events'
        response = requests.post(url, headers=self._headers(), json=event_payload, timeout=30)
        if response.status_code not in (200, 201):
            raise UserError(_("Erreur création événement Outlook: %s") % response.text)
        return response.json()

    def update_event(self, user_email, event_id, event_payload):
        url = f'https://graph.microsoft.com/v1.0/users/{user_email}/events/{event_id}'
        response = requests.patch(url, headers=self._headers(), json=event_payload, timeout=30)
        if response.status_code not in (200, 202):
            raise UserError(_("Erreur mise à jour événement Outlook: %s") % response.text)
        if response.text:
            return response.json()
        return {'id': event_id}

    def delete_event(self, user_email, event_id):
        url = f'https://graph.microsoft.com/v1.0/users/{user_email}/events/{event_id}'
        response = requests.delete(url, headers=self._headers(), timeout=30)
        if response.status_code not in (204, 404):
            raise UserError(_("Erreur suppression événement Outlook: %s") % response.text)
        return True