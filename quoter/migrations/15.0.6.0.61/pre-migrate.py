# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Quita la unicidad antigua (tarifa/producto/área/rango) y unifica ítems Cotizador por tarifa+rango."""

import logging

_logger = logging.getLogger(__name__)

OLD_CONSTRAINT = "product_pricelist_item_uniq_quoter_rate_per_range"


def migrate(cr, version):
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'product_pricelist_item'
        )
        """
    )
    if not cr.fetchone()[0]:
        return

    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            WHERE t.relname = 'product_pricelist_item'
              AND c.conname = %s
        )
        """,
        (OLD_CONSTRAINT,),
    )
    if cr.fetchone()[0]:
        _logger.info("quoter pre-migrate: eliminando %s", OLD_CONSTRAINT)
        cr.execute(
            'ALTER TABLE product_pricelist_item DROP CONSTRAINT IF EXISTS "%s"' % OLD_CONSTRAINT
        )

    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'product_pricelist_item'
              AND column_name = 'applied_on'
        )
        """
    )
    if not cr.fetchone()[0]:
        return

    cr.execute(
        """
        UPDATE product_pricelist_item
        SET product_tmpl_id = NULL, product_id = NULL
        WHERE applied_on = 'quoter'
        """
    )

    cr.execute(
        """
        DELETE FROM product_pricelist_item p1
        USING product_pricelist_item p2
        WHERE p1.applied_on = 'quoter'
          AND p2.applied_on = 'quoter'
          AND p1.pricelist_id = p2.pricelist_id
          AND p1.quoter_area_range_id IS NOT NULL
          AND p1.quoter_area_range_id = p2.quoter_area_range_id
          AND p1.id > p2.id
        """
    )
