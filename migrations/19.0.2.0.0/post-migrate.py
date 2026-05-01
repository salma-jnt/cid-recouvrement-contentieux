"""
Migration v1 → v2.0.0
======================

Cette migration :
  1. Crée les dossiers multi-factures à partir des dossiers 1:1 existants,
     en regroupant par procédure + date_depot_client.
  2. Convertit chaque encaissement v1 (lié à une facture) en :
     - encaissement v2 client-centric (sans facture_id)
     - + 1 lettrage du montant complet
  3. Migre les recouvrement.appel et recouvrement.email existants vers
     le modèle unifié recouvrement.action.
  4. Initialise statut_interface = 'vert' et mois_upload sur les factures.

À exécuter une seule fois lors de l'upgrade. Idempotent (re-exécutable).
"""
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    _logger.info("Démarrage migration recouvrement_contentieux %s", version)

    env = _get_env(cr)

    _step_1_init_factures(env)
    _step_2_regrouper_dossiers(env)
    _step_3_convertir_encaissements(env)
    _step_4_migrer_appels_emails(env)
    _step_5_recalcul_etats(env)

    _logger.info("Migration terminée avec succès.")


def _get_env(cr):
    from odoo.api import Environment
    from odoo import SUPERUSER_ID
    return Environment(cr, SUPERUSER_ID, {})


# ----------------------------------------------------------------------
# 1. Init des nouveaux champs sur les factures existantes
# ----------------------------------------------------------------------
def _step_1_init_factures(env):
    _logger.info("[1/5] Initialisation des champs facture (mois_upload, statut_interface)")
    cr = env.cr

    # mois_upload basé sur create_date des factures existantes
    cr.execute("""
        UPDATE recouvrement_facture
           SET mois_upload = COALESCE(
                   mois_upload,
                   TO_CHAR(create_date, 'YYYY-MM')
               )
         WHERE mois_upload IS NULL OR mois_upload = '';
    """)

    # statut_interface = vert par défaut
    cr.execute("""
        UPDATE recouvrement_facture
           SET statut_interface = 'vert'
         WHERE statut_interface IS NULL;
    """)

    # Mapping ancien recouvrement_status 'bloque' → 'bloque_juridique'
    cr.execute("""
        UPDATE recouvrement_facture
           SET recouvrement_status = 'bloque_juridique'
         WHERE recouvrement_status = 'bloque';
    """)


# ----------------------------------------------------------------------
# 2. Regroupement des dossiers : 1:1 → 1:N (logique du convoi)
# ----------------------------------------------------------------------
def _step_2_regrouper_dossiers(env):
    _logger.info("[2/5] Regroupement des dossiers en convois multi-factures")
    Recouvrement = env['recouvrement.recouvrement']
    Facture = env['recouvrement.facture']

    # On suppose qu'avant la migration le schéma a déjà été altéré et
    # qu'une colonne 'date_depot_groupe' existe sur recouvrement_recouvrement
    # et 'recouvrement_id' existe sur recouvrement_facture.
    # → Pour chaque (procedure_id, date_depot_client) on crée un dossier
    #   et on rattache toutes les factures correspondantes.

    cr = env.cr
    cr.execute("""
        SELECT DISTINCT
            COALESCE(p.id, NULL) AS procedure_id,
            f.date_depot_client
        FROM recouvrement_facture f
        LEFT JOIN res_partner c ON c.id = f.client_id
        LEFT JOIN recouvrement_client_type ct ON ct.id = c.client_type_id
        LEFT JOIN recouvrement_procedure p ON p.id = ct.procedure_id
        WHERE f.recouvrement_id IS NULL
          AND f.date_depot_client IS NOT NULL
          AND p.id IS NOT NULL
        ORDER BY p.id, f.date_depot_client;
    """)
    groupes = cr.fetchall()
    _logger.info("  → %d groupes (procedure × date_depot_client) détectés", len(groupes))

    for procedure_id, date_depot in groupes:
        if not procedure_id or not date_depot:
            continue

        # Créer le dossier
        dossier = Recouvrement.create({
            'procedure_id': procedure_id,
            'date_depot_groupe': date_depot,
        })

        # Rattacher les factures correspondantes
        cr.execute("""
            UPDATE recouvrement_facture f
               SET recouvrement_id = %s
              FROM res_partner c
              JOIN recouvrement_client_type ct ON ct.id = c.client_type_id
             WHERE f.client_id = c.id
               AND ct.procedure_id = %s
               AND f.date_depot_client = %s
               AND f.recouvrement_id IS NULL;
        """, (dossier.id, procedure_id, date_depot))

    # Forcer la régénération des actions sur tous les dossiers nouvellement créés
    new_dossiers = Recouvrement.search([('action_ids', '=', False)])
    for dossier in new_dossiers:
        try:
            dossier.action_generate_actions()
        except Exception as e:
            _logger.warning("  ⚠ Régénération actions dossier %s : %s", dossier.id, e)


# ----------------------------------------------------------------------
# 3. Encaissements v1 (avec facture_id) → encaissements v2 + lettrage
# ----------------------------------------------------------------------
def _step_3_convertir_encaissements(env):
    _logger.info("[3/5] Conversion des encaissements en client-centric + lettrage")
    cr = env.cr
    Lettrage = env['recouvrement.lettrage']

    # Repérer les encaissements qui ont encore un facture_id (champ legacy)
    cr.execute("""
        SELECT id, facture_id, montant, currency_id
          FROM recouvrement_encaissement
         WHERE facture_id IS NOT NULL;
    """)
    rows = cr.fetchall()
    _logger.info("  → %d encaissements à convertir", len(rows))

    for enc_id, facture_id, montant, currency_id in rows:
        if not facture_id or not montant or montant <= 0:
            continue
        # Fixer le client_id de l'encaissement (s'il était vide ou related)
        cr.execute("""
            UPDATE recouvrement_encaissement
               SET client_id = (SELECT client_id FROM recouvrement_facture WHERE id = %s)
             WHERE id = %s
               AND (client_id IS NULL);
        """, (facture_id, enc_id))

        # Créer un lettrage du montant complet
        try:
            Lettrage.create({
                'encaissement_id': enc_id,
                'facture_id': facture_id,
                'montant_affecte': montant,
                'currency_id': currency_id,
            })
        except Exception as e:
            _logger.warning(
                "  ⚠ Lettrage encaissement %s → facture %s impossible : %s",
                enc_id, facture_id, e,
            )

    # Vider les anciens liens directs après conversion
    cr.execute("""
        UPDATE recouvrement_encaissement
           SET facture_id = NULL
         WHERE facture_id IS NOT NULL;
    """)


# ----------------------------------------------------------------------
# 4. Migrer recouvrement.appel et recouvrement.email vers recouvrement.action
# ----------------------------------------------------------------------
def _step_4_migrer_appels_emails(env):
    _logger.info("[4/5] Migration des appels et emails legacy vers recouvrement.action")
    cr = env.cr
    Action = env['recouvrement.action']

    # 4.a — Appels
    cr.execute("""
        SELECT id, name, facture_id, client_id, date_appel, duree_minutes,
               statut, responsable_id, notes, action_prise, planned_datetime,
               outlook_event_id, outlook_web_link, outlook_sync_state,
               outlook_sync_error, action_template_id
          FROM recouvrement_appel;
    """)
    appels = cr.fetchall() if cr.description else []
    _logger.info("  → %d appels legacy à migrer", len(appels))

    for row in appels:
        (appel_id, name, facture_id, client_id, date_appel, duree, statut,
         responsable_id, notes, action_prise, planned_dt,
         ol_event, ol_link, ol_state, ol_error, template_id) = row

        # Trouver le dossier via la facture
        cr.execute(
            "SELECT recouvrement_id FROM recouvrement_facture WHERE id = %s",
            (facture_id,),
        )
        rec_row = cr.fetchone()
        recouvrement_id = rec_row[0] if rec_row else False
        if not recouvrement_id or not client_id:
            continue

        state_map = {
            'brouillon': 'todo',
            'realise': 'done',
            'non_joignable': 'reporte',
            'rappel_needed': 'reporte',
            'refuse': 'cancel',
        }
        try:
            Action.create({
                'name': name or _('Appel migré'),
                'recouvrement_id': recouvrement_id,
                'client_id': client_id,
                'action_template_id': template_id or False,
                'action_type': 'appel',
                'state': state_map.get(statut, 'todo'),
                'mandatory_date': date_appel.date() if date_appel else False,
                'date_done': date_appel.date() if (date_appel and statut == 'realise') else False,
                'duree_minutes': duree or 0,
                'notes_appel': notes,
                'action_prise': action_prise or 'aucune',
                'responsible_id': responsable_id,
                'planned_datetime': planned_dt,
                'outlook_event_id': ol_event,
                'outlook_web_link': ol_link,
                'outlook_sync_state': ol_state or 'not_synced',
                'outlook_sync_error': ol_error,
            })
        except Exception as e:
            _logger.warning("  ⚠ Migration appel #%s : %s", appel_id, e)

    # 4.b — Emails
    cr.execute("""
        SELECT id, name, facture_id, client_id, date_email, statut,
               responsable_id, destinataire_email, corps_email, modele_utilise,
               date_lecture, planned_datetime, outlook_event_id, outlook_web_link,
               outlook_sync_state, outlook_sync_error, action_template_id
          FROM recouvrement_email;
    """)
    emails = cr.fetchall() if cr.description else []
    _logger.info("  → %d emails legacy à migrer", len(emails))

    for row in emails:
        (email_id, name, facture_id, client_id, date_email, statut,
         responsable_id, destinataire, corps, modele, date_lecture,
         planned_dt, ol_event, ol_link, ol_state, ol_error, template_id) = row

        cr.execute(
            "SELECT recouvrement_id FROM recouvrement_facture WHERE id = %s",
            (facture_id,),
        )
        rec_row = cr.fetchone()
        recouvrement_id = rec_row[0] if rec_row else False
        if not recouvrement_id or not client_id:
            continue

        try:
            Action.create({
                'name': name or _('Email migré'),
                'recouvrement_id': recouvrement_id,
                'client_id': client_id,
                'action_template_id': template_id or False,
                'action_type': 'email',
                'state': 'done' if statut in ('envoye', 'lu', 'reponse') else 'todo',
                'mandatory_date': date_email.date() if date_email else False,
                'date_done': date_email.date() if statut in ('envoye', 'lu', 'reponse') else False,
                'destinataire_email': destinataire,
                'sujet_email': name,
                'corps_email': corps,
                'email_status': statut or 'brouillon',
                'date_envoi': date_email if statut in ('envoye', 'lu', 'reponse') else False,
                'date_lecture': date_lecture,
                'responsible_id': responsable_id,
                'planned_datetime': planned_dt,
                'outlook_event_id': ol_event,
                'outlook_web_link': ol_link,
                'outlook_sync_state': ol_state or 'not_synced',
                'outlook_sync_error': ol_error,
            })
        except Exception as e:
            _logger.warning("  ⚠ Migration email #%s : %s", email_id, e)


# ----------------------------------------------------------------------
# 5. Recalcul des états dérivés
# ----------------------------------------------------------------------
def _step_5_recalcul_etats(env):
    _logger.info("[5/5] Recalcul des états des dossiers")
    Recouvrement = env['recouvrement.recouvrement']
    dossiers = Recouvrement.search([])
    for d in dossiers:
        d._update_state()


def _(s):
    return s
