from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    client_type_id = fields.Many2one(
        'recouvrement.client.type',
        string='Type de client',
        help='Type de client utilisé pour définir la procédure de recouvrement.',
    )

    recouvrement_count = fields.Integer(
        string='Nombre de recouvrements',
        compute='_compute_recouvrement_count',
    )

    def _compute_recouvrement_count(self):
        for partner in self:
            partner.recouvrement_count = self.env['recouvrement.recouvrement'].search_count([
                ('client_id', '=', partner.id)
            ])
