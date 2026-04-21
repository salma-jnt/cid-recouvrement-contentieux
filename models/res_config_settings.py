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
