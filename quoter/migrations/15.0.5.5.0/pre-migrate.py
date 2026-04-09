# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)


def migrate(cr, version):
    # Migra la relación previa quoter_area_complexity_range.area_id
    # hacia la nueva relación many2many quoter_professional_area_range_rel.
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'quoter_area_complexity_range'
              AND column_name = 'area_id'
        )
        """
    )
    if not cr.fetchone()[0]:
        return

    cr.execute(
        """
        CREATE TABLE IF NOT EXISTS quoter_professional_area_range_rel (
            area_id INTEGER NOT NULL,
            range_id INTEGER NOT NULL,
            UNIQUE(area_id, range_id)
        )
        """
    )
    cr.execute(
        """
        INSERT INTO quoter_professional_area_range_rel (area_id, range_id)
        SELECT area_id, id
        FROM quoter_area_complexity_range
        WHERE area_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )
