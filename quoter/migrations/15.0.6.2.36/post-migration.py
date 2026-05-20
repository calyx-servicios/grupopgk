# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Relaja reglas de registro que filtraban por group_id del área.

En instalaciones existentes el XML está en noupdate=1 y no actualiza el dominio;
esta migración alinea la BD con el criterio: lectura de maestros sin bloquear
cotizaciones; la visibilidad por pestaña sigue en las vistas.
"""


def migrate(cr, version):
    domain = "[(1, '=', 1)]"
    cr.execute(
        """
        UPDATE ir_rule AS r
        SET domain_force = %s
        FROM ir_model_data AS d
        WHERE d.module = 'quoter'
          AND d.model = 'ir.rule'
          AND d.name IN (
              'quoter_rule_professional_area_visibility',
              'quoter_rule_service_line_visibility',
              'quoter_rule_service_line_range_hour_visibility',
              'quoter_rule_complexity_level_visibility'
          )
          AND r.id = d.res_id
        """,
        (domain,),
    )
