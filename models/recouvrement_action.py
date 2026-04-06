from odoo import api, fields, models


class RecouvrementAction(models.Model):
    _name = 'recouvrement.action'
    _description = 'Action de recouvrement'
    _order = 'mandatory_date, id'

    name = fields.Char(string='Action', required=True)
    recouvrement_id = fields.Many2one('recouvrement.recouvrement', string='Dossier de recouvrement', required=True, ondelete='cascade')
    action_type = fields.Selection([
        ('appel', 'Appel'),
        ('relance_1', 'Relance 1'),
        ('relance_2', 'Relance 2'),
        ('mise_en_demeure', 'Mise en demeure'),
        ('contentieux', 'Contentieux'),
    ], string='Type', required=True, default='appel')
    mandatory_date = fields.Date(string='Échéance')
    date_done = fields.Date(string='Date réalisée')
    done_date = fields.Date(string='Date de suivi', compute='_compute_done_date', store=True)
    state = fields.Selection([
        ('todo', 'À faire'),
        ('done', 'Réalisée'),
        ('cancel', 'Annulée'),
    ], string='Statut', default='todo')
    comment = fields.Text(string='Commentaire')
    procedure_id = fields.Many2one('recouvrement.procedure', string='Procédure liée', related='recouvrement_id.procedure_id', store=True, readonly=True)

    @api.depends('state', 'date_done')
    def _compute_done_date(self):
        for record in self:
            record.done_date = record.date_done if record.state == 'done' else False

    def action_done(self):
        for record in self:
            record.state = 'done'
            record.date_done = fields.Date.context_today(self)

    def action_reset(self):
        for record in self:
            record.state = 'todo'
            record.date_done = False
