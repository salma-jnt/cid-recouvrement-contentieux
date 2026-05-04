"""
Migration 19.0.3.0.0 — Ajout phase_index sur recouvrement.recouvrement

Nouvelle logique : planification phase par phase au lieu de tout créer
en une fois. Le champ phase_index indique quelle phase est active.

Pour les dossiers existants :
 - On déduit phase_index depuis les actions existantes (quelle phase
   a le plus grand nombre d'actions todo/reporte).
 - Si toutes les actions sont done → phase_index = -1 (terminé).
 - Si aucune action → phase_index = 0 (départ).
"""


def migrate(cr, version):
    # Ajouter la colonne si elle n'existe pas
    cr.execute("""
        ALTER TABLE recouvrement_recouvrement
        ADD COLUMN IF NOT EXISTS phase_index INTEGER NOT NULL DEFAULT 0;
    """)

    # Pour les dossiers qui ont déjà des actions, calculer le bon index
    # On se base sur la séquence du template de l'action todo la plus ancienne
    cr.execute("""
        UPDATE recouvrement_recouvrement r
        SET phase_index = (
            SELECT COALESCE(
                (
                    -- Index 0-based de la phase courante = rang du template
                    -- de la première action todo/reporte
                    SELECT COUNT(*) - 1
                    FROM recouvrement_action_template t2
                    WHERE t2.procedure_id = r.procedure_id
                      AND (t2.sequence, t2.id) <= (
                          SELECT (t.sequence, t.id)
                          FROM recouvrement_action a
                          JOIN recouvrement_action_template t
                            ON t.id = a.action_template_id
                          WHERE a.recouvrement_id = r.id
                            AND a.state IN ('todo', 'reporte')
                          ORDER BY t.sequence, t.id
                          LIMIT 1
                      )
                ),
                CASE
                    WHEN NOT EXISTS (
                        SELECT 1 FROM recouvrement_action a2
                        WHERE a2.recouvrement_id = r.id
                          AND a2.state IN ('todo', 'reporte')
                    ) AND EXISTS (
                        SELECT 1 FROM recouvrement_action a3
                        WHERE a3.recouvrement_id = r.id
                    ) THEN -1  -- tout est done
                    ELSE 0
                END
            )
        )
        WHERE r.procedure_id IS NOT NULL;
    """)

    cr.execute("SELECT COUNT(*) FROM recouvrement_recouvrement")
    count = cr.fetchone()[0]
    print(f"[migrate 19.0.3.0.0] phase_index initialisé sur {count} dossiers.")