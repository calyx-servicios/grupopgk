# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Elimina filas line_section de separador: el cotizador usa solo estilos JS."""


def migrate(cr, version):
    cr.execute(
        """
        DELETE FROM sale_order_line
        WHERE display_type = 'line_section'
          AND quoter_separator_section_tag_id IS NOT NULL
        """
    )
