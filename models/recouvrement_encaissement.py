from odoo import api, fields, models


class RecouvrementEncaissement(models.Model):
    _name = 'recouvrement.encaissement'
    _description = 'Encaissement de recouvrement'
    _order = 'date_operation desc, id desc'

    name = fields.Char(string='Référence', required=True, default='Nouveau')
    facture_id = fields.Many2one('recouvrement.facture', string='Facture')
    recouvrement_id = fields.Many2one('recouvrement.recouvrement', string='Dossier de recouvrement')
    pole_id = fields.Many2one('hr.department', string='Pôle', related='facture_id.pole_id', store=True, readonly=False)
    code_affaire = fields.Char(string='Code d’affaire', related='facture_id.code_affaire', store=True, readonly=False)
    client_id = fields.Many2one('res.partner', string='Client', related='facture_id.client_id', store=True, readonly=False)
    montant = fields.Monetary(string='Montant', required=True)
    penalite = fields.Monetary(string='Pénalité')
    date_operation = fields.Date(string='Date d’opération', required=True)
    banque = fields.Char(string='Banque')
    observation = fields.Text(string='Observation')
    mode_paiement = fields.Selection([
        ('virement', 'Virement'),
        ('espece', 'Espèces'),
        ('cheque', 'Chèque'),
        ('autre', 'Autre'),
    ], string='Mode de paiement', default='virement')
    currency_id = fields.Many2one('res.currency', string='Devise', default=lambda self: self.env.company.currency_id)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                facture_name = False
                if vals.get('facture_id'):
                    facture = self.env['recouvrement.facture'].browse(vals['facture_id'])
                    facture_name = facture.name
                vals['name'] = facture_name and f"ENC/{facture_name}" or self.env['ir.sequence'].next_by_code('recouvrement.encaissement') or 'ENC'
        return super().create(vals_list)
