from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _default_client_type_id(self):
        return self.env.ref('recouvrement_contentieux.type_client_standard', raise_if_not_found=False)

    client_type_id = fields.Many2one(
        'recouvrement.client.type',
        string='Type de client',
        default=_default_client_type_id,
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

    @api.model_create_multi
    def create(self, vals_list):
        default_type = self._default_client_type_id()
        for vals in vals_list:
            if not vals.get('client_type_id') and default_type:
                vals['client_type_id'] = default_type.id
        return super().create(vals_list)
