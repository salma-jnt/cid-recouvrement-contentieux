"""Association client ↔ type de client.

Modèle d'association indépendant de res.partner.
Lors de toute modification, synchronise automatiquement
le champ client_type_id du partenaire pour que la logique
de recouvrement continue de fonctionner.
"""
from odoo import api, fields, models


class RecouvrementClientAssignment(models.Model):
    _name = 'recouvrement.client.assignment'
    _description = 'Attribution type de client'
    _order = 'partner_id'

    partner_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True,
        ondelete='cascade',
        index=True,
    )
    client_type_id = fields.Many2one(
        'recouvrement.client.type',
        string='Type de client',
        required=True,
        ondelete='restrict',
    )
    date_attribution = fields.Date(
        string="Date d'attribution",
        default=fields.Date.today,
        readonly=True,
    )
    notes = fields.Text(string='Notes')

    # Champs calculés pour lisibilité dans les vues
    partner_name  = fields.Char(related='partner_id.name',  string='Client',    store=True, readonly=True)
    partner_email = fields.Char(related='partner_id.email', string='Email',     store=True, readonly=True)
    partner_phone = fields.Char(related='partner_id.phone', string='Téléphone', store=True, readonly=True)
    type_name     = fields.Char(related='client_type_id.name', string='Type',   store=True, readonly=True)

    _sql_constraints = [
        ('partner_unique', 'UNIQUE(partner_id)',
         "Un client ne peut avoir qu'un seul type actif à la fois."),
    ]

    # ── Sync vers res.partner.client_type_id ─────────────────────────────────

    def _sync_partner(self):
        for rec in self:
            if rec.partner_id and rec.client_type_id:
                rec.partner_id.sudo().client_type_id = rec.client_type_id

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_partner()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'client_type_id' in vals:
            self._sync_partner()
        return res
