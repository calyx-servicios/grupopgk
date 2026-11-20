# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Clasifica las distribuciones ya generadas segun el prefijo de su texto.

Las lineas con el formato anterior ("Porcentaje = ...") no indican la bolsa
de origen y quedan sin tipo: hay que volver a consolidar esos periodos.
"""

PREFIXES = (
    ("gs", "Dist. Gtos. Sector%"),
    ("gg", "Dist. Gtos. Gcia.%"),
    ("gi", "Dist. Gtos. Indirectos%"),
)


def migrate(cr, version):
    if not version:
        return
    for dist_type, prefix in PREFIXES:
        cr.execute(
            """
            UPDATE account_analytic_line
               SET distribution_type = %s
             WHERE consolidation_line
               AND distribution_type IS NULL
               AND name LIKE %s
            """,
            (dist_type, prefix),
        )
        cr.execute(
            """
            UPDATE account_consolidation_data
               SET distribution_type = %s
             WHERE distribution_type IS NULL
               AND description LIKE %s
            """,
            (dist_type, prefix),
        )
