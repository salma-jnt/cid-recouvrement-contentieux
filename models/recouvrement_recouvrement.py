from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class Recouvrement(models.Model):
    _name = 'recouvrement.recouvrement'
    _description = 'Dossier de recouvrement'
    _order = 'state, date_depot_client desc'

    name = fields.Char(string='Titre', required=True, default='Nouveau recouvrement')
    facture_id = fields.Many2one('recouvrement.facture', string='Facture', required=True)
    client_id = fields.Many2one('res.partner', string='Client', related='facture_id.client_id', store=True, readonly=False)
    procedure_id = fields.Many2one('recouvrement.procedure', string='Procédure de recouvrement')
    date_depot_client = fields.Date(string='Date de dépôt chez le client', related='facture_id.date_depot_client', store=True)
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('open', 'En cours'),
        ('late', 'En retard'),
        ('closed', 'Clôturé'),
    ], string='Statut', default='draft')
    currency_id = fields.Many2one('res.currency', string='Devise', default=lambda self: self.env.company.currency_id)
    action_ids = fields.One2many('recouvrement.action', 'recouvrement_id', string='Actions')
    action_count = fields.Integer(string='Nombre d’actions', compute='_compute_action_count')
    montant_ttc = fields.Monetary(string='Montant TTC', related='facture_id.montant_ttc', store=True, currency_field='currency_id')
    encaissement_ids = fields.One2many('recouvrement.encaissement', 'recouvrement_id', string='Encaissements')
    montant_encaisse = fields.Monetary(string='Montant encaissé', compute='_compute_montant_encaisse', currency_field='currency_id')
    last_action_date = fields.Date(string='Dernière action', compute='_compute_last_action_date')
    next_action_date = fields.Date(string='Prochaine échéance', compute='_compute_next_action_date')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.name == 'Nouveau recouvrement' and record.facture_id:
                record.name = _('Recouvrement %s') % (record.facture_id.name or record.id)
            if record.procedure_id and not record.action_ids:
                record.action_generate_actions()
            else:
                record._update_state_from_actions()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {'procedure_id', 'facture_id'} & set(vals):
            for record in self:
                if record.procedure_id and not record.action_ids:
                    record.action_generate_actions()
                else:
                    record._update_state_from_actions()
        return res

    @api.depends('action_ids')
    def _compute_action_count(self):
        for record in self:
            record.action_count = len(record.action_ids)

    @api.depends('encaissement_ids.montant')
    def _compute_montant_encaisse(self):
        for record in self:
            record.montant_encaisse = sum(record.encaissement_ids.mapped('montant'))

    @api.depends('action_ids.mandatory_date', 'action_ids.state', 'action_ids.done_date')
    def _compute_last_action_date(self):
        for record in self:
            dates = record.action_ids.filtered(lambda a: a.state == 'done').mapped('done_date')
            record.last_action_date = max(dates) if dates else False

    @api.depends('action_ids', 'action_ids.mandatory_date', 'action_ids.state')
    def _compute_next_action_date(self):
        for record in self:
            pending = record.action_ids.filtered(lambda a: a.state == 'todo')
            record.next_action_date = min(pending.mapped('mandatory_date')) if pending else False

    def _get_action_base_date(self):
        self.ensure_one()
        return self.date_depot_client or self.facture_id.date_facture or fields.Date.context_today(self)

    def _update_state_from_actions(self):
        today = fields.Date.context_today(self)
        for record in self:
            pending = record.action_ids.filtered(lambda a: a.state == 'todo')
            overdue = pending.filtered(lambda a: a.mandatory_date and a.mandatory_date < today)
            done_actions = record.action_ids.filtered(lambda a: a.state == 'done')

            if not record.action_ids:
                record.state = 'draft'
            elif overdue:
                record.state = 'late'
            elif pending:
                record.state = 'open'
            elif done_actions:
                record.state = 'closed'
            else:
                record.state = 'draft'

    def action_generate_actions(self):
        action_obj = self.env['recouvrement.action']
        for record in self:
            if not record.procedure_id:
                raise UserError(_('Veuillez sélectionner une procédure de recouvrement avant de générer les actions.'))

            base_date = record._get_action_base_date()
            record.action_ids.filtered(lambda a: a.state != 'done').unlink()

            for template in record.procedure_id.action_template_ids.sorted(key=lambda t: (t.sequence, t.id)):
                action_obj.create({
                    'name': template.name,
                    'recouvrement_id': record.id,
                    'action_type': template.action_type,
                    'mandatory_date': base_date + timedelta(days=template.delay or 0),
                    'comment': template.description or False,
                    'responsible_id': self.env.user.id,
                })

            record._update_state_from_actions()
        return True

    def action_mark_closed(self):
        for record in self:
            record.state = 'closed'
