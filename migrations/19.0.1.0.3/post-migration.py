def migrate(cr, version):
    cr.execute("""
        UPDATE recouvrement_appel a
           SET procedure_id = COALESCE(ct.procedure_id, std.id)
          FROM recouvrement_facture f
          JOIN res_partner rp ON rp.id = f.client_id
          LEFT JOIN recouvrement_client_type ct ON ct.id = rp.client_type_id
          CROSS JOIN (SELECT id FROM recouvrement_procedure WHERE code = 'STANDARD' LIMIT 1) std
         WHERE a.facture_id = f.id
           AND (a.procedure_id IS NULL OR a.procedure_id = 0)
    """)

    cr.execute("""
        UPDATE recouvrement_email e
           SET procedure_id = COALESCE(ct.procedure_id, std.id)
          FROM recouvrement_facture f
          JOIN res_partner rp ON rp.id = f.client_id
          LEFT JOIN recouvrement_client_type ct ON ct.id = rp.client_type_id
          CROSS JOIN (SELECT id FROM recouvrement_procedure WHERE code = 'STANDARD' LIMIT 1) std
         WHERE e.facture_id = f.id
           AND (e.procedure_id IS NULL OR e.procedure_id = 0)
    """)
