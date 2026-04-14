from odoo import api, fields, models
from datetime import datetime, timedelta


class RecouvrementAppel(models.Model):
    _name = 'recouvrement.appel'
    _description = 'Appel de relance'
    _order = 'date_appel desc'

    name = fields.Char(string='Objet', required=True)
    recouvrement_id = fields.Many2one(
        'recouvrement.recouvrement',
        string='Dossier de recouvrement',
        required=True,
        ondelete='cascade'
    )
    client_id = fields.Many2one(
        'res.partner',
        string='Client',
        related='recouvrement_id.client_id',
        readonly=True,
        store=True
    )
    date_appel = fields.Datetime(
        string='Date de l\'appel',
        default=fields.Datetime.now,
        required=True
    )
    duree_minutes = fields.Integer(string='Durée (minutes)')
    statut = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('realise', 'Réalisé'),
        ('non_joignable', 'Non joignable'),
        ('rappel_needed', 'Rappel nécessaire'),
        ('refuse', 'Refusé'),
    ], string='Statut', default='brouillon')
    
    responsable_id = fields.Many2one(
        'res.users',
        string='Responsable',
        default=lambda self: self.env.user
    )
    notes = fields.Text(string='Notes')
    
    # Suivi
    action_prise = fields.Selection([
        ('aucune', 'Aucune'),
        ('paiement', 'Paiement convenu'),
        ('plan_paiement', 'Plan de paiement'),
        ('dialogue', 'Dialogue établi'),
        ('escalade', 'Escalade'),
    ], string='Action prise', default='aucune')
    
    date_prochain_appel = fields.Datetime(string='Date prochain appel')
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('statut') == 'realise' and not vals.get('duree_minutes'):
                vals['duree_minutes'] = 5
        return super().create(vals_list)

    def action_marquer_realise(self):
        self.write({'statut': 'realise'})

    def action_marquer_non_joignable(self):
        self.write({'statut': 'non_joignable'})

    def action_planifier_rappel(self):
        return {
            'name': 'Planifier un rappel',
            'type': 'ir.actions.act_window',
            'res_model': 'recouvrement.appel',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
