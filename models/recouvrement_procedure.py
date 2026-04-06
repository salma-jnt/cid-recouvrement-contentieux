from odoo import fields, models


class RecouvrementProcedure(models.Model):
    _name = 'recouvrement.procedure'
    _description = 'Procédure de recouvrement'
    _order = 'name'

    name = fields.Char(string='Nom de la procédure', required=True)
    code = fields.Char(string='Code', required=True)
    description = fields.Text(string='Description')
    delay_appel = fields.Integer(string='Délai premier appel (jours)', default=7)
    delay_relance_1 = fields.Integer(string='Délai relance 1 (jours)', default=14)
    delay_relance_2 = fields.Integer(string='Délai relance 2 (jours)', default=21)
    delay_contentieux = fields.Integer(string='Délai contentieux (jours)', default=45)
    action_template_ids = fields.One2many('recouvrement.action.template', 'procedure_id', string='Modèles d’actions')


class RecouvrementActionTemplate(models.Model):
    _name = 'recouvrement.action.template'
    _description = 'Modèle d’action de recouvrement'
    _order = 'sequence'

    procedure_id = fields.Many2one('recouvrement.procedure', string='Procédure', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Séquence', default=10)
    name = fields.Char(string='Nom du modèle', required=True)
    action_type = fields.Selection([
        ('appel', 'Appel'),
        ('relance_1', 'Relance 1'),
        ('relance_2', 'Relance 2'),
        ('mise_en_demeure', 'Mise en demeure'),
        ('contentieux', 'Contentieux'),
    ], string='Type', required=True)
    delay = fields.Integer(string='Délai (jours)', default=7)
    description = fields.Text(string='Description du modèle')
