# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)


def _chain_migration_reset_lines(cr):
    cr.execute(
        """
        ALTER TABLE quoter_chain_table_line
        DROP CONSTRAINT IF EXISTS quoter_chain_table_line_uniq_chain_line_table_range
        """
    )
    cr.execute(
        """
        ALTER TABLE quoter_chain_table_line
        DROP CONSTRAINT IF EXISTS quoter_chain_table_line_uniq_chain_line_table_product_range
        """
    )
    cr.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'quoter_chain_table_line_param'
        """
    )
    if cr.fetchone():
        cr.execute("DELETE FROM quoter_chain_table_line_param")
    cr.execute("DELETE FROM quoter_chain_table_line")


def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    return bool(cr.fetchone())


def _rename_column_safe(cr, table, old_name, new_name):
    """Renombra solo si hace falta; si el ORM ya creó la columna nueva, borra la vieja."""
    has_old = _column_exists(cr, table, old_name)
    has_new = _column_exists(cr, table, new_name)
    if has_new:
        if has_old:
            cr.execute(
                "ALTER TABLE %s DROP COLUMN %s" % (table, old_name)
            )
        return
    if has_old:
        cr.execute(
            "ALTER TABLE %s RENAME COLUMN %s TO %s"
            % (table, old_name, new_name)
        )


def migrate(cr, version):
    _chain_migration_reset_lines(cr)
    _rename_column_safe(
        cr,
        "quoter_professional_area",
        "chain_test_people_count",
        "chain_test_employee_count",
    )
    _rename_column_safe(
        cr,
        "quoter_sale_order_area",
        "chain_people_count",
        "chain_employee_count",
    )
    if not _column_exists(cr, "quoter_chain_table", "delta"):
        cr.execute(
            """
            ALTER TABLE quoter_chain_table
            ADD COLUMN delta integer DEFAULT 1 NOT NULL
            """
        )
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    areas = env["quoter.professional.area"].search(
        [("hour_matrix_mode", "=", "formula_chain")]
    )
    if areas:
        areas._chain_recompute_table_bounds()
        areas._chain_sync_all_table_lines()
