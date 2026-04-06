from odoo import fields, models


class RecouvrementPole(models.Model):
    _name = 'recouvrement.pole'
    _description = 'Pôle de facturation'

    name = fields.Char(string='Pôle', required=True)
    code = fields.Char(string='Code pôle')
    active = fields.Boolean(string='Actif', default=True)
