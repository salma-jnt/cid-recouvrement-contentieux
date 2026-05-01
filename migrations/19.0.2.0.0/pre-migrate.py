"""
Pre-migration v1 → v2.0.0
==========================

Ajoute les nouvelles colonnes nécessaires AVANT que les modèles refactorés
ne soient chargés (sinon Odoo va échouer en essayant de lire des colonnes
qu'il pense devoir exister).
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    _logger.info("[Pre-migrate v2.0.0] Ajout des nouvelles colonnes")

    # ------------------------------------------------------------------
    # Facture : nouveaux champs
    # ------------------------------------------------------------------
    _add_column(cr, 'recouvrement_facture', 'mois_upload', 'VARCHAR')
    _add_column(cr, 'recouvrement_facture', 'statut_interface', 'VARCHAR')
    _add_column(cr, 'recouvrement_facture', 'montant_paye', 'NUMERIC')
    _add_column(cr, 'recouvrement_facture', 'reste_a_payer', 'NUMERIC')

    # ------------------------------------------------------------------
    # Dossier : nouveaux champs (la One2many vers facture passe par
    # recouvrement_facture.recouvrement_id qui existe déjà)
    # ------------------------------------------------------------------
    _add_column(cr, 'recouvrement_recouvrement', 'date_depot_groupe', 'DATE')
    _add_column(cr, 'recouvrement_recouvrement', 'nombre_factures', 'INTEGER')
    _add_column(cr, 'recouvrement_recouvrement', 'nombre_clients', 'INTEGER')

    # Renommage state codes : draft→ouvert, open→en_cours, late→en_retard,
    #                        blocked→bloque, closed→solde
    cr.execute("""
        UPDATE recouvrement_recouvrement SET state =
          CASE state
            WHEN 'draft' THEN 'ouvert'
            WHEN 'open' THEN 'en_cours'
            WHEN 'late' THEN 'en_retard'
            WHEN 'blocked' THEN 'bloque'
            WHEN 'closed' THEN 'solde'
            ELSE state
          END
        WHERE state IN ('draft', 'open', 'late', 'blocked', 'closed');
    """)

    # ------------------------------------------------------------------
    # Encaissement : nouveaux champs
    # ------------------------------------------------------------------
    _add_column(cr, 'recouvrement_encaissement', 'montant_alloue', 'NUMERIC')
    _add_column(cr, 'recouvrement_encaissement', 'reste_a_allouer', 'NUMERIC')
    _add_column(cr, 'recouvrement_encaissement', 'etat_lettrage', 'VARCHAR')

    # ------------------------------------------------------------------
    # Action template : nouveau champ statut_interface_cible
    # ------------------------------------------------------------------
    _add_column(cr, 'recouvrement_action_template', 'statut_interface_cible', 'VARCHAR')
    _add_column(cr, 'recouvrement_action_template', 'email_subject_template', 'VARCHAR')
    _add_column(cr, 'recouvrement_action_template', 'email_body_template', 'TEXT')

    # Init du statut cible par défaut sur les anciens templates
    cr.execute("""
        UPDATE recouvrement_action_template
           SET statut_interface_cible = COALESCE(statut_interface_cible, 'vert');
    """)

    # ------------------------------------------------------------------
    # Action : nouveaux champs (avant qu'Odoo charge le modèle unifié)
    # ------------------------------------------------------------------
    _add_column(cr, 'recouvrement_action', 'client_id', 'INTEGER')
    _add_column(cr, 'recouvrement_action', 'action_template_id', 'INTEGER')
    # Champs spécifiques appel
    _add_column(cr, 'recouvrement_action', 'duree_minutes', 'INTEGER')
    _add_column(cr, 'recouvrement_action', 'notes_appel', 'TEXT')
    _add_column(cr, 'recouvrement_action', 'action_prise', 'VARCHAR')
    # Champs spécifiques email
    _add_column(cr, 'recouvrement_action', 'destinataire_email', 'VARCHAR')
    _add_column(cr, 'recouvrement_action', 'sujet_email', 'VARCHAR')
    _add_column(cr, 'recouvrement_action', 'corps_email', 'TEXT')
    _add_column(cr, 'recouvrement_action', 'email_status', 'VARCHAR')
    _add_column(cr, 'recouvrement_action', 'date_envoi', 'TIMESTAMP')
    _add_column(cr, 'recouvrement_action', 'date_lecture', 'TIMESTAMP')
    # Outlook
    _add_column(cr, 'recouvrement_action', 'planned_datetime', 'TIMESTAMP')
    _add_column(cr, 'recouvrement_action', 'outlook_event_id', 'VARCHAR')
    _add_column(cr, 'recouvrement_action', 'outlook_web_link', 'VARCHAR')
    _add_column(cr, 'recouvrement_action', 'outlook_sync_state', 'VARCHAR')
    _add_column(cr, 'recouvrement_action', 'outlook_sync_error', 'TEXT')

    _logger.info("[Pre-migrate v2.0.0] Colonnes ajoutées avec succès.")


def _add_column(cr, table, column, sql_type):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s;
    """, (table, column))
    if not cr.fetchone():
        cr.execute('ALTER TABLE "%s" ADD COLUMN "%s" %s' % (table, column, sql_type))
        _logger.info("  + %s.%s (%s)", table, column, sql_type)
