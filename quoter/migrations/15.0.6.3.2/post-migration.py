# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)


def _chain_migration_reset_lines(cr):
    """Quita restricción legacy (tabla×rol) y regenera celdas por producto×rol."""
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


def migrate(cr, version):
    cr.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'quoter_chain_table_line'
          AND column_name = 'product_tmpl_id'
        """
    )
    if not cr.fetchone():
        return
    _chain_migration_reset_lines(cr)
    cr.execute(
        """
        SELECT DISTINCT area_id
        FROM quoter_chain_table
        """
    )
    area_ids = [row[0] for row in cr.fetchall() if row[0]]
    if not area_ids:
        return
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    areas = env["quoter.professional.area"].browse(area_ids).filtered(
        lambda a: a.hour_matrix_mode == "formula_chain"
    )
    if areas:
        areas._chain_sync_all_table_lines()
