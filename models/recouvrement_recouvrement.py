from odoo import api, fields, models


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
    montant_ttc = fields.Monetary(string='Montant TTC', related='facture_id.montant_ttc', store=True, currency_field='currency_id')
    encaissement_ids = fields.One2many('recouvrement.encaissement', 'recouvrement_id', string='Encaissements')
    montant_encaisse = fields.Monetary(string='Montant encaissé', compute='_compute_montant_encaisse', currency_field='currency_id')
    last_action_date = fields.Date(string='Dernière action', compute='_compute_last_action_date')
    next_action_date = fields.Date(string='Prochaine échéance', compute='_compute_next_action_date')

    @api.depends('encaissement_ids.montant')
    def _compute_montant_encaisse(self):
        for record in self:
            record.montant_encaisse = sum(record.encaissement_ids.mapped('montant'))

    @api.depends('action_ids.mandatory_date', 'action_ids.state')
    def _compute_last_action_date(self):
        for record in self:
            dates = record.action_ids.filtered(lambda a: a.state == 'done').mapped('done_date')
            record.last_action_date = max(dates) if dates else False

    @api.depends('action_ids', 'action_ids.mandatory_date')
    def _compute_next_action_date(self):
        for record in self:
            pending = record.action_ids.filtered(lambda a: a.state in ('todo', 'planned'))
            record.next_action_date = min(pending.mapped('mandatory_date')) if pending else False

    def action_mark_closed(self):
        for record in self:
            record.state = 'closed'
