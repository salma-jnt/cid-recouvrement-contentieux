"""
Modèle Procédure + Modèle d'action — refactor v2.0.0

Changements vs v1 :
  - Suppression des champs delay_appel, delay_relance_1, delay_relance_2,
    delay_contentieux (redondants avec action_template_ids.delay)
  + statut_interface_cible (vert/orange/rouge/mauve) sur action.template
  - Réduction action_type aux 5 canoniques du cahier
"""
from odoo import api, fields, models, _


class RecouvrementProcedure(models.Model):
    _name = 'recouvrement.procedure'
    _description = 'Procédure / Stratégie de recouvrement'
    _order = 'name'

    name = fields.Char(string='Nom de la procédure', required=True)
    code = fields.Char(string='Code', required=True, index=True)
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)

    action_template_ids = fields.One2many(
        'recouvrement.action.template', 'procedure_id',
        string="Modèles d'actions (phases ordonnées)",
    )
    nb_phases = fields.Integer(
        string='Nombre de phases',
        compute='_compute_nb_phases',
    )

    @api.depends('action_template_ids')
    def _compute_nb_phases(self):
        for rec in self:
            rec.nb_phases = len(rec.action_template_ids)

    _sql_constraints = [
        ('procedure_code_unique', 'UNIQUE(code)',
         "Le code de procédure doit être unique."),
    ]


class RecouvrementActionTemplate(models.Model):
    _name = 'recouvrement.action.template'
    _description = "Modèle d'action / Phase d'une procédure"
    _order = 'procedure_id, sequence, id'

    procedure_id = fields.Many2one(
        'recouvrement.procedure', string='Procédure', required=True,
        ondelete='cascade', index=True,
    )
    sequence = fields.Integer(string='Séquence', default=10)
    name = fields.Char(string='Nom du modèle', required=True)
    description = fields.Text(string='Description du modèle')

    action_type = fields.Selection([
        ('appel', 'Appel'),
        ('email', 'Email'),
        ('courrier', 'Courrier'),
        ('mise_en_demeure', 'Mise en demeure'),
        ('contentieux', 'Contentieux'),
    ], string='Type', required=True, default='appel')

    delay = fields.Integer(
        string="Délai (jours)",
        default=7,
        help="Nombre de jours après la phase précédente "
             "(ou la date de dépôt pour la phase 1).",
    )

    statut_interface_cible = fields.Selection([
        ('vert', 'Vert'),
        ('orange', 'Orange (blocage technique)'),
        ('rouge', 'Rouge'),
        ('mauve', 'Mauve'),
    ], string='Statut visuel cible', default='vert', required=True,
        help="Couleur poussée vers facture.statut_interface "
             "lorsque cette phase devient la phase courante du dossier.",
    )

    # Optionnel : objet/corps email pré-générés pour les phases email
    email_subject_template = fields.Char(string='Objet email (template)')
    email_body_template = fields.Html(string='Corps email (template)')
