"""Type de client — RAS (modèle simple, conforme cahier)."""
from odoo import fields, models


class RecouvrementClientType(models.Model):
    _name = 'recouvrement.client.type'
    _description = 'Type de client pour procédure de recouvrement'
    _order = 'name'

    name = fields.Char(string='Type de client', required=True)
    code = fields.Char(string='Code', required=True, index=True)
    description = fields.Text(string='Description')
    procedure_id = fields.Many2one(
        'recouvrement.procedure', string='Procédure par défaut',
        required=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('client_type_code_unique', 'UNIQUE(code)',
         "Le code du type de client doit être unique."),
    ]
