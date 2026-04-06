from odoo import fields, models


class RecouvrementClientType(models.Model):
    _name = 'recouvrement.client.type'
    _description = 'Type de client pour procédure de recouvrement'
    _order = 'name'

    name = fields.Char(string='Type de client', required=True)
    code = fields.Char(string='Code', required=True)
    description = fields.Text(string='Description')
    procedure_id = fields.Many2one('recouvrement.procedure', string='Procédure par défaut')
