# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)


def migrate(cr, version):
    """Respalda columnas range_N_hours antes de que el ORM las elimine."""
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'quoter_product_level_range'
          AND column_name = 'range_1_hours'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        CREATE TABLE IF NOT EXISTS quoter_mig_plr_hours (
            plr_id integer PRIMARY KEY,
            r1 double precision,
            r2 double precision,
            r3 double precision,
            r4 double precision
        )
        """
    )
    cr.execute("TRUNCATE quoter_mig_plr_hours")
    cr.execute(
        """
        INSERT INTO quoter_mig_plr_hours (plr_id, r1, r2, r3, r4)
        SELECT id, range_1_hours, range_2_hours, range_3_hours, range_4_hours
        FROM quoter_product_level_range
        """
    )
