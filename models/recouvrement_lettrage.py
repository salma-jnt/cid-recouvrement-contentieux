"""
Modèle Lettrage — NOUVEAU dans v2.0.0

C'est le pont de répartition entre encaissements et factures, **central**
au moteur financier du chapitre 5 du cahier de charge :

    « Un compteur Reste à allouer s'affiche
      (Montant total de l'encaissement - Montant déjà lettré).
      Au fur et à mesure que l'agent sélectionne des factures à payer,
      le système propose automatiquement d'affecter le montant disponible,
      et le compteur Reste à allouer diminue en temps réel. »

Garde-fous (cahier) :
  - Jamais dépasser le montant restant de la facture
  - Jamais dépasser le reste à allouer de l'encaissement
  - Jamais de montant négatif
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class RecouvrementLettrage(models.Model):
    _name = 'recouvrement.lettrage'
    _description = "Lettrage : pont entre encaissement et facture"
    _order = 'date_lettrage desc, id desc'
    _rec_name = 'display_name'

    encaissement_id = fields.Many2one(
        'recouvrement.encaissement', string='Encaissement',
        required=True, ondelete='cascade', index=True,
    )
    facture_id = fields.Many2one(
        'recouvrement.facture', string='Facture',
        required=True, ondelete='restrict', index=True,
    )
    client_id = fields.Many2one(
        'res.partner', string='Client',
        related='facture_id.client_id', store=True, readonly=True,
    )
    montant_affecte = fields.Monetary(
        string='Montant affecté', required=True,
    )

    # Snapshots au moment du lettrage (audit trail)
    facture_montant_ttc = fields.Monetary(
        string='Montant TTC facture (snapshot)', readonly=True,
    )
    facture_reste_a_payer = fields.Monetary(
        string='Reste à payer avant lettrage (snapshot)', readonly=True,
    )

    date_lettrage = fields.Date(
        string='Date du lettrage',
        default=fields.Date.context_today, required=True,
    )
    currency_id = fields.Many2one(
        'res.currency', string='Devise',
        default=lambda self: self.env.company.currency_id,
    )
    display_name = fields.Char(
        compute='_compute_display_name', store=True,
    )

    # ==================================================================
    # COMPUTES
    # ==================================================================
    @api.depends('encaissement_id.name', 'facture_id.name', 'montant_affecte')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _("%(enc)s → %(fact)s : %(amt)s") % {
                'enc': rec.encaissement_id.name or '',
                'fact': rec.facture_id.name or '',
                'amt': rec.montant_affecte or 0.0,
            }

    # ==================================================================
    # CONTRAINTES
    # ==================================================================
    _sql_constraints = [
        ('montant_positif',
         'CHECK(montant_affecte > 0)',
         "Le montant affecté doit être strictement positif."),
    ]

    @api.constrains('montant_affecte', 'encaissement_id', 'facture_id')
    def _check_caps(self):
        """Vérifie qu'on ne dépasse ni le reste à allouer ni le reste à payer."""
        for lettrage in self:
            # 1) ne pas dépasser le reste à allouer de l'encaissement
            #    (en excluant le présent lettrage du calcul)
            enc = lettrage.encaissement_id
            other_alloue = sum(
                l.montant_affecte for l in enc.lettrage_ids if l.id != lettrage.id
            )
            disponible = (enc.montant or 0.0) - other_alloue
            if lettrage.montant_affecte > disponible + 1e-6:
                raise ValidationError(_(
                    "Encaissement %(enc)s : tentative d'affecter %(asked).2f "
                    "alors que seuls %(avail).2f sont disponibles.",
                    enc=enc.name or '',
                    asked=lettrage.montant_affecte,
                    avail=disponible,
                ))

            # 2) ne pas dépasser le reste à payer de la facture
            fact = lettrage.facture_id
            other_paye = sum(
                l.montant_affecte for l in fact.lettrage_ids if l.id != lettrage.id
            )
            reste = (fact.montant_ttc or 0.0) - other_paye
            if lettrage.montant_affecte > reste + 1e-6:
                raise ValidationError(_(
                    "Facture %(fact)s : tentative d'affecter %(asked).2f "
                    "alors que le reste à payer n'est que de %(reste).2f.",
                    fact=fact.name or '',
                    asked=lettrage.montant_affecte,
                    reste=reste,
                ))

            # 3) cohérence client : encaissement et facture doivent avoir le même client
            if enc.client_id and fact.client_id and enc.client_id != fact.client_id:
                raise ValidationError(_(
                    "Lettrage incohérent : l'encaissement appartient à %(enc_c)s "
                    "et la facture à %(fact_c)s.",
                    enc_c=enc.client_id.display_name,
                    fact_c=fact.client_id.display_name,
                ))

    # ==================================================================
    # CRUD : snapshot + clôture
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        # Snapshot des valeurs au moment du lettrage (audit + reporting)
        for vals in vals_list:
            facture = self.env['recouvrement.facture'].browse(vals['facture_id'])
            vals.setdefault('facture_montant_ttc', facture.montant_ttc or 0.0)
            vals.setdefault('facture_reste_a_payer', facture.reste_a_payer or 0.0)
            vals.setdefault('currency_id', facture.currency_id.id or self.env.company.currency_id.id)
        records = super().create(vals_list)

        # Refresh derived fields + état du dossier
        records._propagate_after_change()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._propagate_after_change()
        return res

    def unlink(self):
        encaissements = self.mapped('encaissement_id')
        factures = self.mapped('facture_id')
        res = super().unlink()
        # Forcer le recompute (Odoo le fait via dependencies, mais on force pour
        # déclencher la mise à jour de l'état du dossier en aval).
        encaissements._compute_alloue()
        encaissements._compute_etat_lettrage()
        for facture in factures:
            if facture.recouvrement_id:
                facture.recouvrement_id._update_state()
        return res

    def _propagate_after_change(self):
        """Met à jour : encaissement (alloué/reste/état) + dossier (état/montants)."""
        encaissements = self.mapped('encaissement_id')
        encaissements._compute_alloue()
        encaissements._compute_etat_lettrage()
        for facture in self.mapped('facture_id'):
            if facture.recouvrement_id:
                facture.recouvrement_id._update_state()
