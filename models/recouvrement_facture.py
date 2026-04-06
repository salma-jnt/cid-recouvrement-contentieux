from odoo import fields, models


class RecouvrementFacture(models.Model):
    _name = 'recouvrement.facture'
    _description = 'Facture de recouvrement'
    _order = 'date_depot_client desc, name'

    name = fields.Char(string='Référence facture', required=True, index=True)
    facture_type = fields.Selection([
        ('standard', 'Facture standard'),
        ('proforma', 'Facture proforma'),
        ('groupement', 'Facture en groupement'),
        ('autre', 'Autre type'),
    ], string='Type de facture', required=True, default='standard')
    client_id = fields.Many2one('res.partner', string='Client', required=True)
    date_facture = fields.Date(string='Date de la facture')
    date_signature = fields.Date(string='Date de signature')
    date_depot_client = fields.Date(string='Date de dépôt chez le client')
    montant_ttc = fields.Monetary(string='Montant TTC')
    montant_ht = fields.Monetary(string='Montant HT')
    reference_justificatif = fields.Char(string='Référence justificatif')
    division = fields.Char(string='Division')
    pole = fields.Char(string='Pôle')
    code_affaire = fields.Char(string='Code affaire')
    nature = fields.Char(string='Nature')
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('imported', 'Importée'),
        ('validated', 'Validée'),
    ], string='Statut', default='draft')
    currency_id = fields.Many2one('res.currency', string='Devise', default=lambda self: self.env.company.currency_id)
    recouvrement_id = fields.Many2one('recouvrement.recouvrement', string='Recouvrement associé')


class RecouvrementEncaissement(models.Model):
    _name = 'recouvrement.encaissement'
    _description = 'Encaissement de recouvrement'

    name = fields.Char(string='Référence', required=True)
    facture_id = fields.Many2one('recouvrement.facture', string='Facture', required=True)
    recouvrement_id = fields.Many2one('recouvrement.recouvrement', string='Dossier de recouvrement')
    montant = fields.Monetary(string='Montant encaissé', required=True)
    date_encaissement = fields.Date(string='Date d’encaissement', required=True)
    mode_paiement = fields.Selection([
        ('virement', 'Virement'),
        ('espece', 'Espèces'),
        ('cheque', 'Chèque'),
        ('autre', 'Autre'),
    ], string='Mode de paiement', default='virement')
    currency_id = fields.Many2one('res.currency', string='Devise', default=lambda self: self.env.company.currency_id)
