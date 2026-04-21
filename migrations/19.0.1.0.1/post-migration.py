def migrate(cr, version):
    cr.execute("""
        UPDATE recouvrement_appel a
           SET facture_id = r.facture_id
          FROM recouvrement_recouvrement r
         WHERE a.recouvrement_id = r.id
           AND a.facture_id IS NULL
           AND r.facture_id IS NOT NULL
    """)

    cr.execute("""
        UPDATE recouvrement_email e
           SET facture_id = r.facture_id
          FROM recouvrement_recouvrement r
         WHERE e.recouvrement_id = r.id
           AND e.facture_id IS NULL
           AND r.facture_id IS NOT NULL
    """)
