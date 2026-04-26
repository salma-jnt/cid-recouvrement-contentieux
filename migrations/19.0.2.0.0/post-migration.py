# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Migrate Recouvrement model from facture_id (Many2one) to facture_ids (One2many)."""
    # Query all existing recouvrement records with facture_id set
    cr.execute("""
        SELECT id, facture_id FROM recouvrement_recouvrement 
        WHERE facture_id IS NOT NULL
    """)
    
    records = cr.fetchall()
    _logger.info(f"Found {len(records)} recouvrement records to migrate")
    
    # For each record, ensure the facture's recouvrement_id is set correctly
    for record_id, facture_id in records:
        if facture_id:
            # Update facture.recouvrement_id to point to this dossier
            cr.execute("""
                UPDATE recouvrement_facture 
                SET recouvrement_id = %s 
                WHERE id = %s
            """, (record_id, facture_id))
            _logger.info(f"Migrated facture {facture_id} to recouvrement {record_id}")
    
    _logger.info("Migration completed successfully")
