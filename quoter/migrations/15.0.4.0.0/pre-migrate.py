# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Migrar de quoter.service a área + líneas directas (area_id en líneas, pricelist en área)."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'quoter_service'
        )
        """
    )
    if not cr.fetchone()[0]:
        _logger.info("quoter pre-migrate: tabla quoter_service no existe, nada que hacer.")
        return

    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'quoter_service_line'
              AND column_name = 'service_id'
        )
        """
    )
    has_service_fk = cr.fetchone()[0]

    if has_service_fk:
        cr.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'quoter_service_line'
                  AND column_name = 'area_id'
            )
            """
        )
        if not cr.fetchone()[0]:
            cr.execute(
                """
                ALTER TABLE quoter_service_line
                    ADD COLUMN area_id INTEGER
                """
            )
        cr.execute(
            """
            UPDATE quoter_service_line l
            SET area_id = s.area_id
            FROM quoter_service s
            WHERE l.service_id = s.id AND s.area_id IS NOT NULL
            """
        )
        cr.execute(
            """
            SELECT COUNT(*) FROM quoter_service_line
            WHERE area_id IS NULL AND service_id IS NOT NULL
            """
        )
        row = cr.fetchone()
        if row and row[0]:
            _logger.warning(
                "quoter pre-migrate: %s líneas con service_id sin área resuelta.",
                row[0],
            )

    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'product_template'
              AND column_name = 'quoter_service_id'
        )
        """
    )
    if cr.fetchone()[0]:
        cr.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'product_template'
                  AND column_name = 'quoter_area_id'
            )
            """
        )
        if not cr.fetchone()[0]:
            cr.execute(
                """
                ALTER TABLE product_template
                    ADD COLUMN quoter_area_id INTEGER
                """
            )
        cr.execute(
            """
            UPDATE product_template pt
            SET quoter_area_id = s.area_id
            FROM quoter_service s
            WHERE pt.quoter_service_id = s.id AND s.area_id IS NOT NULL
            """
        )

    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'quoter_professional_area'
              AND column_name = 'pricelist_id'
        )
        """
    )
    if not cr.fetchone()[0]:
        cr.execute(
            """
            ALTER TABLE quoter_professional_area
                ADD COLUMN pricelist_id INTEGER
            """
        )
    cr.execute(
        """
        UPDATE quoter_professional_area a
        SET pricelist_id = sub.pricelist_id
        FROM (
            SELECT DISTINCT ON (area_id) area_id, pricelist_id
            FROM quoter_service
            WHERE pricelist_id IS NOT NULL AND area_id IS NOT NULL
            ORDER BY area_id, id DESC
        ) sub
        WHERE a.id = sub.area_id
          AND a.pricelist_id IS NULL
        """
    )

    _logger.info("quoter pre-migrate: datos copiados desde quoter.service donde aplicaba.")
