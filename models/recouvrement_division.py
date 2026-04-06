from odoo import fields, models


class RecouvrementDivision(models.Model):
    _name = 'recouvrement.division'
    _description = 'Division de facturation'

    name = fields.Char(string='Division', required=True)
    code = fields.Char(string='Code division')
    active = fields.Boolean(string='Actif', default=True)
