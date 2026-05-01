from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    recouvrement_outlook_tenant_id = fields.Char(
        string='Recouvrement Outlook Tenant ID',
        config_parameter='recouvrement.outlook_tenant_id',
    )
    recouvrement_outlook_client_id = fields.Char(
        string='Recouvrement Outlook Client ID',
        config_parameter='recouvrement.outlook_client_id',
    )
    recouvrement_outlook_client_secret = fields.Char(
        string='Recouvrement Outlook Client Secret',
        config_parameter='recouvrement.outlook_client_secret',
    )
    cid_gemini_api_key = fields.Char(
        string='Clé API Gemini (Google)',
        config_parameter='recouvrement.google_api_key',
        help="Clé API Google Gemini pour activer le chatbot intelligent.",
        password=True,  # 🔐 masque la clé
    )