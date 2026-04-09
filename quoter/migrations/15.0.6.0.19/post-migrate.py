# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)


def migrate(cr, version):
    """Pasar prefijo COT/ → Q (data con noupdate no actualiza sola)."""
    cr.execute(
        """
        UPDATE ir_sequence
           SET prefix = 'Q'
         WHERE code = 'quoter.quotation'
           AND prefix = 'COT/';
        """
    )
