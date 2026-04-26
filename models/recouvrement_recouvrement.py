from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class Recouvrement(models.Model):
    _name = 'recouvrement.recouvrement'
    _description = 'Dossier de recouvrement'
    _order = 'prochaine_echeance asc, id desc'

    name = fields.Char(string='Titre', required=True, default='Nouveau recouvrement')
    facture_ids = fields.One2many('recouvrement.facture', 'recouvrement_id', string='Factures regroupées')
    client_id = fields.Many2one('res.partner', string='Client', compute='_compute_client_id', store=True, readonly=True)
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
    date_depot_client = fields.Date(string='Date de depot chez le client', compute='_compute_date_depot_client', store=True)
    date_echeance = fields.Date(string='Date echeance')
    prochaine_echeance = fields.Date(string='Prochaine echeance', compute='_compute_prochaine_echeance', store=True)
    action_ids = fields.One2many('recouvrement.action', 'recouvrement_id', string='Actions')
    montant_ttc = fields.Monetary(string='Montant TTC', compute='_compute_montant_ttc', store=True, currency_field='currency_id')
    encaissement_ids = fields.One2many('recouvrement.encaissement', 'recouvrement_id', string='Encaissements')
    montant_encaisse = fields.Monetary(string='Montant encaisse', compute='_compute_montant_encaisse', currency_field='currency_id')
    reste_a_recouvrer = fields.Monetary(string='Reste a recouvrer', compute='_compute_reste_a_recouvrer', store=True, currency_field='currency_id')
    last_action_date = fields.Date(string='Derniere action', compute='_compute_last_action_date', store=True)
    next_action_date = fields.Date(string='Prochaine echeance technique', compute='_compute_next_action_date', store=True)
    nb_factures = fields.Integer(string='Nb factures', compute='_compute_nb_factures', store=True)
    responsable_id = fields.Many2one('res.users', string='Responsable', compute='_compute_prochaine_action_info', store=True)
    prochaine_action = fields.Char(string='Prochaine action', compute='_compute_prochaine_action_info', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('date_echeance'):
                # Use first facture as reference for default date and procedure
                facture_ids = vals.get('facture_ids', [])
                if facture_ids and isinstance(facture_ids[0], (list, tuple)) and len(facture_ids[0]) > 0:
                    first_facture_id = facture_ids[0][2]['id'] if isinstance(facture_ids[0][2], dict) else facture_ids[0][2]
                    facture = self.env['recouvrement.facture'].browse(first_facture_id)
                    vals['date_echeance'] = facture.date_facture or facture.date_depot_client
                    if not vals.get('procedure_id') and facture.client_id.client_type_id.procedure_id:
                        vals['procedure_id'] = facture.client_id.client_type_id.procedure_id.id
        records = super().create(vals_list)
        for record in records:
            if record.name == 'Nouveau recouvrement' and record.facture_ids:
                first_facture = record.facture_ids[0]
                record.name = _('Recouvrement %s') % (first_facture.name or record.id)
            if record.procedure_id and not record.action_ids:
                record.action_generate_actions()
            elif record.state != 'blocked':
                record._update_state_from_actions()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {'procedure_id', 'facture_ids'} & set(vals):
            for record in self:
                if record.procedure_id and not record.action_ids:
                    record.action_generate_actions()
                elif record.state != 'blocked':
                    record._update_state_from_actions()
        return res

    @api.depends('facture_ids.client_id')
    def _compute_client_id(self):
        """Client is the common client from all factures (must be the same)."""
        for record in self:
            if record.facture_ids:
                clients = record.facture_ids.mapped('client_id')
                # Use first facture's client or compute from all if they match
                record.client_id = clients[0] if clients else False
            else:
                record.client_id = False

    @api.depends('facture_ids.date_depot_client')
    def _compute_date_depot_client(self):
        """Use first facture's deposit date."""
        for record in self:
            record.date_depot_client = record.facture_ids[0].date_depot_client if record.facture_ids else False

    @api.depends('facture_ids.montant_ttc')
    def _compute_montant_ttc(self):
        """Sum total amount from all grouped factures."""
        for record in self:
            record.montant_ttc = sum(record.facture_ids.mapped('montant_ttc'))
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

    @api.depends('facture_ids')
    def _compute_nb_factures(self):
        """Count grouped factures."""
        for record in self:
            record.nb_factures = len(record.facture_ids)

    @api.depends('action_ids.state', 'action_ids.name', 'action_ids.mandatory_date', 'action_ids.responsible_id')
    def _compute_prochaine_action_info(self):
        for record in self:
            pending = record.action_ids.filtered(lambda a: a.state == 'todo').sorted(
                key=lambda a: (a.mandatory_date or fields.Date.context_today(record), a.id)
            )
            next_action = pending[:1]
            if next_action:
                action = next_action[0]
                record.responsable_id = action.responsible_id
                if action.mandatory_date:
                    record.prochaine_action = '%s - %s' % (action.name or '', action.mandatory_date)
                else:
                    record.prochaine_action = action.name or False
            else:
                record.responsable_id = False
                record.prochaine_action = False

    def _get_action_base_date(self):
        self.ensure_one()
        return self.date_depot_client or (self.facture_ids[0].date_facture if self.facture_ids else False) or fields.Date.context_today(self)

    def _update_state_from_actions(self):
        today = fields.Date.context_today(self)
        facture_status_map = {
            'draft': 'normal',
            'open': 'precontentieux',
            'late': 'contentieux',
            'blocked': 'bloque',
            'closed': 'recouvre',
        }
        for record in self:
            if record.state == 'blocked':
                for facture in record.facture_ids:
                    facture.recouvrement_status = facture_status_map.get(record.state, 'normal')
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

            for facture in record.facture_ids:
                facture.recouvrement_status = facture_status_map.get(record.state, 'normal')

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
            for facture in record.facture_ids:
                facture.recouvrement_status = 'recouvre'

    @api.model
    def find_or_create_dossier(self, facture, procedure_id, date_echeance):
        """Find existing dossier matching criteria or create new one.
        Criteria: same client + date_echeance + procedure
        """
        # Find matching dossier with same procedure, date_echeance, and client
        matching = self.search([
            ('procedure_id', '=', procedure_id),
            ('date_echeance', '=', date_echeance),
            ('facture_ids.client_id', '=', facture.client_id.id),
        ], limit=1)
        
        if matching:
            # Add facture to existing dossier
            matching.facture_ids = [(4, facture.id)]
            return matching
        else:
            # Create new dossier
            return self.create({
                'procedure_id': procedure_id,
                'date_echeance': date_echeance,
                'facture_ids': [(6, 0, [facture.id])],
            })
