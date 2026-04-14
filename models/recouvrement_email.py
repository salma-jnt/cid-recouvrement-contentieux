from odoo import api, fields, models
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class RecouvrementEmail(models.Model):
    _name = 'recouvrement.email'
    _description = 'Email de relance'
    _order = 'date_email desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

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
    destinataire_email = fields.Char(
        string='Email destinataire',
        required=True
    )
    
    date_email = fields.Datetime(
        string='Date d\'envoi',
        default=fields.Datetime.now,
        required=True
    )
    statut = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('envoye', 'Envoyé'),
        ('lu', 'Lu'),
        ('reponse', 'Réponse reçue'),
        ('erreur', 'Erreur d\'envoi'),
    ], string='Statut', default='brouillon', tracking=True)
    
    responsable_id = fields.Many2one(
        'res.users',
        string='Responsable',
        default=lambda self: self.env.user
    )
    
    # Contenu
    corps_email = fields.Html(string='Contenu de l\'email', required=True)
    modele_utilise = fields.Selection([
        ('rappel_standard', 'Rappel standard'),
        ('mise_en_demeure', 'Mise en demeure'),
        ('plan_paiement', 'Proposition plan de paiement'),
        ('relance_urgent', 'Relance urgente'),
    ], string='Modèle utilisé')
    
    # Tracking
    date_lecture = fields.Datetime(string='Date de lecture')
    date_reponse = fields.Datetime(string='Date de réponse')
    contenu_reponse = fields.Text(string='Contenu de la réponse')
    
    # Pièces jointes (optionnel)
    pieces_jointes_ids = fields.Many2many(
        'ir.attachment',
        string='Pièces jointes'
    )
    
    def action_envoyer_email(self):
        """Envoyer l'email via SMTP"""
        try:
            # Utiliser le service email d'Odoo avec les paramètres SMTP
            email_from = self.env['ir.config_parameter'].sudo().get_param(
                'mail.default_from', 
                default=self.env.user.email
            )
            
            if not email_from or '@' not in email_from:
                raise UserError('L\'adresse email par défaut n\'est pas configurée.')
            
            # Créer le message
            mail_values = {
                'subject': self.name,
                'body_html': self.corps_email,
                'email_from': email_from,
                'email_to': self.destinataire_email,
                'model': 'recouvrement.email',
                'res_id': self.id,
                'auto_delete': False,
            }
            
            # Ajouter les pièces jointes si présentes
            if self.pieces_jointes_ids:
                mail_values['attachment_ids'] = [(6, 0, self.pieces_jointes_ids.ids)]
            
            # Créer et envoyer le mail
            mail = self.env['mail.mail'].create(mail_values)
            mail.send()
            
            self.write({
                'statut': 'envoye',
                'date_email': fields.Datetime.now()
            })
            
            _logger.info(f'Email de relance envoyé: {self.name} à {self.destinataire_email}')
            
        except Exception as e:
            self.write({'statut': 'erreur'})
            _logger.error(f'Erreur lors de l\'envoi de l\'email: {str(e)}')
            raise UserError(f'Erreur lors de l\'envoi de l\'email: {str(e)}')

    def action_envoyer_brouillon(self):
        """Passer du statut brouillon à envoyer"""
        if self.statut != 'brouillon':
            raise UserError('Seuls les brouillons peuvent être envoyés.')
        self.action_envoyer_email()

    def action_marquer_lu(self):
        """Marquer l'email comme lu (manuel, pour suivi)"""
        self.write({
            'statut': 'lu',
            'date_lecture': fields.Datetime.now()
        })

    def action_ajouter_reponse(self):
        """Ajouter une réponse reçue"""
        return {
            'name': 'Ajouter une réponse',
            'type': 'ir.actions.act_window',
            'res_model': 'recouvrement.email',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
