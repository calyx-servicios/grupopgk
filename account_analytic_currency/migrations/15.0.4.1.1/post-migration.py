# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """`_compute_currency_id` sacaba la moneda del comprobante (`move_id`) o
    de `company_id` (Many2many, ambiguo entre varias empresas), aunque el
    importe de la línea siempre queda en la moneda de una única empresa real.

    Solo cambiaron dos ramas de la fórmula (comprobante y horas); la rama
    restante (`company_id` M2M) sigue igual y no necesita backfill.

    Se hace por SQL directo contra las tablas fuente, no vía recompute del
    ORM: `account_move_line.company_id` es en si mismo un related+store
    (`move_id.company_id`), y encadenar el recompute de un related sobre otro
    related en el mismo flush masivo no garantiza el orden de resolución
    (confirmado: recalculando de a un registro por vez con el ORM, las
    líneas de Adaly con comprobante quedaban con la moneda de otra empresa).
    Leyendo el dato ya persistido en la tabla fuente se evita el problema.
    """
    cr.execute("""
        UPDATE account_analytic_line aal
           SET currency_id = comp.currency_id
          FROM account_move_line aml
          JOIN account_move am ON am.id = aml.move_id
          JOIN res_company comp ON comp.id = am.company_id
         WHERE aal.move_id = aml.id
           AND aal.currency_id IS DISTINCT FROM comp.currency_id
    """)
    _logger.info("Moneda recalculada en %s líneas con comprobante.", cr.rowcount)

    cr.execute("""
        UPDATE account_analytic_line aal
           SET currency_id = comp.currency_id
          FROM hr_employee emp
          JOIN res_company comp ON comp.id = emp.company_id
         WHERE aal.employee_id = emp.id
           AND aal.move_id IS NULL
           AND aal.currency_id IS DISTINCT FROM comp.currency_id
    """)
    _logger.info("Moneda recalculada en %s líneas de horas.", cr.rowcount)
