"""
Extension res.partner — refactor v2.0.0

Changements :
  + Hook _notifier_pole_technique sur facture (utilisé par action.py)
  + recouvrement_count recalculé via les factures (puisque le dossier est
    désormais multi-clients, compter les dossiers d'un client passe par
    les factures qu'il possède dans ces dossiers)
"""
from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _default_client_type_id(self):
        return self.env.ref(
            'recouvrement_contentieux.type_client_standard',
            raise_if_not_found=False,
        )

    client_type_id = fields.Many2one(
        'recouvrement.client.type',
        string='Type de client (recouvrement)',
        default=_default_client_type_id,
        help="Détermine la procédure de recouvrement à appliquer aux factures "
             "de ce client.",
    )

    recouvrement_count = fields.Integer(
        string='Nb dossiers de recouvrement',
        compute='_compute_recouvrement_count',
    )
    facture_recouvrement_count = fields.Integer(
        string='Nb factures de recouvrement',
        compute='_compute_recouvrement_count',
    )

    def _compute_recouvrement_count(self):
        Facture = self.env['recouvrement.facture']
        for partner in self:
            factures = Facture.search([('client_id', '=', partner.id)])
            partner.facture_recouvrement_count = len(factures)
            partner.recouvrement_count = len(factures.mapped('recouvrement_id'))

    @api.model_create_multi
    def create(self, vals_list):
        default_type = self._default_client_type_id()
        for vals in vals_list:
            if not vals.get('client_type_id') and default_type:
                vals['client_type_id'] = default_type.id
        return super().create(vals_list)


class RecouvrementFactureNotifierMixin(models.Model):
    """Ajoute le hook de notification du pôle technique sur la facture.
    Pas un nouveau modèle — juste une extension de recouvrement.facture."""
    _inherit = 'recouvrement.facture'

    def _notifier_pole_technique(self, action):
        """Crée une activité Odoo pour le pôle technique en cas de blocage orange."""
        for facture in self:
            pole_users = self.env['res.users']
            if facture.pole_id:
                pole_users = self.env['res.users'].search([
                    ('groups_id.name', 'ilike', 'Pole technique'),
                ], limit=5)
            user = pole_users[:1] or self.env.user

            facture.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_("Blocage technique sur facture %s") % facture.name,
                note=_(
                    "Une action de recouvrement a déclenché un blocage technique. "
                    "Action : %(action_name)s — Date prévue : %(date)s.<br/>"
                    "Veuillez résoudre le blocage avant que la procédure puisse continuer."
                ) % {
                    'action_name': action.name,
                    'date': action.mandatory_date or '',
                },
                user_id=user.id,
                date_deadline=fields.Date.today(),
            )
