from odoo import api, fields, models


class RecouvrementAction(models.Model):
    _name = 'recouvrement.action'
    _description = 'Action de recouvrement'
    _order = 'mandatory_date, id'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.mapped('recouvrement_id')._update_state_from_actions()
        return records

    def write(self, vals):
        res = super().write(vals)
        self.mapped('recouvrement_id')._update_state_from_actions()
        return res

    def unlink(self):
        dossiers = self.mapped('recouvrement_id')
        res = super().unlink()
        dossiers._update_state_from_actions()
        return res

    name = fields.Char(string='Action', required=True)
    recouvrement_id = fields.Many2one('recouvrement.recouvrement', string='Dossier de recouvrement', required=True, ondelete='cascade')
    action_type = fields.Selection([
        ('appel', 'Appel'),
        ('relance_1', 'Relance 1'),
        ('relance_2', 'Relance 2'),
        ('mise_en_demeure', 'Mise en demeure'),
        ('contentieux', 'Contentieux'),
    ], string='Type', required=True, default='appel')
    responsible_id = fields.Many2one('res.users', string='Responsable', default=lambda self: self.env.user)
    priority = fields.Selection([
        ('0', 'Basse'),
        ('1', 'Normale'),
        ('2', 'Haute'),
    ], string='Priorité', default='1')
    mandatory_date = fields.Date(string='Échéance')
    date_done = fields.Date(string='Date réalisée')
    done_date = fields.Date(string='Date de suivi', compute='_compute_done_date', store=True)
    is_overdue = fields.Boolean(string='En retard', compute='_compute_is_overdue', store=True)
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

    @api.depends('state', 'mandatory_date')
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for record in self:
            record.is_overdue = bool(record.state == 'todo' and record.mandatory_date and record.mandatory_date < today)

    def action_done(self):
        for record in self:
            record.state = 'done'
            record.date_done = fields.Date.context_today(self)
            record.recouvrement_id._update_state_from_actions()

    def action_reset(self):
        for record in self:
            record.state = 'todo'
            record.date_done = False
            record.recouvrement_id._update_state_from_actions()

    def action_cancel(self):
        for record in self:
            record.state = 'cancel'
            record.date_done = False
            record.recouvrement_id._update_state_from_actions()
