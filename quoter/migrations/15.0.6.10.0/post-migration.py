# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""La facturación del año anterior y la industria pasan del bloque de área a la cotización.

Cada cotización toma los datos del primer bloque que los tenga completos (orden de los
bloques). Si sus bloques tenían datos distintos, queda en el log: el nivel de esos bloques
no se toca acá y se puede recalcular con «Recalcular cotizaciones en borrador» del área.

Las columnas viejas del bloque quedan en la base sin uso.
"""

import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import column_exists

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Bases sin la complejidad automática (producción en 15.0.6.6.x): no hay nada que copiar.
    if not column_exists(cr, "quoter_sale_order_area", "industry_id"):
        return
    cr.execute(
        """
        SELECT b.order_id
        FROM quoter_sale_order_area b
        WHERE b.industry_id IS NOT NULL OR COALESCE(b.prev_year_revenue, 0) <> 0
        GROUP BY b.order_id
        HAVING COUNT(DISTINCT (COALESCE(b.industry_id, 0), COALESCE(b.prev_year_revenue, 0))) > 1
        """
    )
    conflict_ids = [row[0] for row in cr.fetchall()]
    cr.execute(
        """
        UPDATE sale_order so
        SET quoter_prev_year_revenue = src.prev_year_revenue,
            quoter_industry_id = src.industry_id
        FROM (
            SELECT DISTINCT ON (b.order_id) b.order_id, b.prev_year_revenue, b.industry_id
            FROM quoter_sale_order_area b
            WHERE b.industry_id IS NOT NULL OR COALESCE(b.prev_year_revenue, 0) <> 0
            ORDER BY b.order_id,
                     (b.industry_id IS NULL OR COALESCE(b.prev_year_revenue, 0) = 0),
                     b.sequence,
                     b.id
        ) src
        WHERE so.id = src.order_id
          AND so.quoter_industry_id IS NULL
          AND COALESCE(so.quoter_prev_year_revenue, 0) = 0
        RETURNING so.id
        """
    )
    order_ids = [row[0] for row in cr.fetchall()]
    if not order_ids:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    orders = env["sale.order"].browse(order_ids)
    orders.modified(["quoter_prev_year_revenue", "quoter_industry_id"])
    orders.flush()
    _logger.info(
        "quoter: facturación e industria copiadas del bloque a %s cotizaciones.", len(orders)
    )
    if conflict_ids:
        _logger.warning(
            "quoter: cotizaciones con facturación o industria distinta entre áreas; se tomó "
            "la del primer bloque. Revisar el nivel de: %s",
            ", ".join(env["sale.order"].browse(conflict_ids).mapped("name")),
        )
