# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)


def migrate(cr, version):
    """Elimina reglas «Cotizador» y restricción única antes de retirar campos del modelo."""
    cr.execute(
        """
        DELETE FROM product_pricelist_item
        WHERE applied_on = 'quoter'
        """
    )
    cr.execute(
        """
        ALTER TABLE product_pricelist_item
        DROP CONSTRAINT IF EXISTS product_pricelist_item_uniq_quoter_pricelist_range_quoter
        """
    )
