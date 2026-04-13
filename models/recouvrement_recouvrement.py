from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class Recouvrement(models.Model):
    _name = 'recouvrement.recouvrement'
    _description = 'Dossier de recouvrement'
    _order = 'prochaine_echeance asc, id desc'

    name = fields.Char(string='Titre', required=True, default='Nouveau recouvrement')
    facture_id = fields.Many2one('recouvrement.facture', string='Facture', required=True)
    client_id = fields.Many2one('res.partner', string='Client', related='facture_id.client_id', store=True, readonly=False)
    procedure_id = fields.Many2one('recouvrement.procedure', string='Procédure de recouvrement')
    phase_courante = fields.Char(string='Phase courante', compute='_compute_phase_courante', store=True)
    state = fields.Selection([
        ('draft', 'Normal'),
        ('open', 'Précontentieux'),
        ('late', 'Contentieux'),
        ('blocked', 'Bloqué'),
        ('closed', 'Recouvré'),
    ], string='Statut', default='draft')
    motif_blocage = fields.Text(string='Motif de blocage')
    currency_id = fields.Many2one('res.currency', string='Devise', default=lambda self: self.env.company.currency_id)
    date_depot_client = fields.Date(string='Date de dépôt chez le client', related='facture_id.date_depot_client', store=True)
    date_echeance = fields.Date(string='Date d’échéance')
    prochaine_echeance = fields.Date(string='Prochaine échéance', compute='_compute_prochaine_echeance', store=True)
    action_ids = fields.One2many('recouvrement.action', 'recouvrement_id', string='Actions')
    montant_ttc = fields.Monetary(string='Montant TTC', related='facture_id.montant_ttc', store=True, currency_field='currency_id')
    encaissement_ids = fields.One2many('recouvrement.encaissement', 'recouvrement_id', string='Encaissements')
    montant_encaisse = fields.Monetary(string='Montant encaissé', compute='_compute_montant_encaisse', currency_field='currency_id')
    reste_a_recouvrer = fields.Monetary(string='Reste à recouvrer', compute='_compute_reste_a_recouvrer', store=True, currency_field='currency_id')
    last_action_date = fields.Date(string='Dernière action', compute='_compute_last_action_date', store=True)
    next_action_date = fields.Date(string='Prochaine échéance technique', compute='_compute_next_action_date', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('facture_id') and not vals.get('date_echeance'):
                facture = self.env['recouvrement.facture'].browse(vals['facture_id'])
                vals['date_echeance'] = facture.date_facture or facture.date_depot_client
        records = super().create(vals_list)
        for record in records:
            if record.name == 'Nouveau recouvrement' and record.facture_id:
                record.name = _('Recouvrement %s') % (record.facture_id.name or record.id)
            if record.procedure_id and not record.action_ids:
                record.action_generate_actions()
            elif record.state != 'blocked':
                record._update_state_from_actions()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {'procedure_id', 'facture_id'} & set(vals):
            for record in self:
                if record.procedure_id and not record.action_ids:
                    record.action_generate_actions()
                elif record.state != 'blocked':
                    record._update_state_from_actions()
        return res

    @api.depends('action_ids.mandatory_date', 'action_ids.state', 'procedure_id', 'state')
    def _compute_phase_courante(self):
        for record in self:
            if record.state == 'blocked':
                record.phase_courante = 'Bloqué'
                continue
            if record.state == 'closed':
                record.phase_courante = 'Recouvré / encaissé'
                continue
            pending = record.action_ids.filtered(lambda a: a.state == 'todo').sorted(
                key=lambda a: (a.mandatory_date or fields.Date.context_today(record), a.id)
            )
            record.phase_courante = pending[:1].name if pending else (record.procedure_id.name or 'Suivi')

    @api.depends('encaissement_ids.montant')
    def _compute_montant_encaisse(self):
        for record in self:
            record.montant_encaisse = sum(record.encaissement_ids.mapped('montant'))

    @api.depends('montant_ttc', 'montant_encaisse')
    def _compute_reste_a_recouvrer(self):
        for record in self:
            record.reste_a_recouvrer = max((record.montant_ttc or 0.0) - (record.montant_encaisse or 0.0), 0.0)

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

    @api.depends('next_action_date', 'date_echeance')
    def _compute_prochaine_echeance(self):
        for record in self:
            record.prochaine_echeance = record.next_action_date or record.date_echeance

    def _get_action_base_date(self):
        self.ensure_one()
        return self.date_depot_client or self.facture_id.date_facture or fields.Date.context_today(self)

    def _update_state_from_actions(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.state == 'blocked':
                continue
            pending = record.action_ids.filtered(lambda a: a.state == 'todo')
            overdue = pending.filtered(lambda a: a.mandatory_date and a.mandatory_date < today)
            done_actions = record.action_ids.filtered(lambda a: a.state == 'done')

            if not record.action_ids:
                record.state = 'draft'
            elif overdue:
                record.state = 'late'
            elif pending:
                record.state = 'open'
            elif done_actions or record.reste_a_recouvrer <= 0:
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
