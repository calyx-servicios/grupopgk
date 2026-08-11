# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

BATCH_SIZE = 5000

# Campos de la línea a recalcular, en el orden en que se los recorre
LINE_FIELDS = ("bussines_group_id", "managment_account_id", "sector_account_id")


def migrate(cr, version):
    """Realinea las agrupaciones que se calculaban con un depends incompleto.

    Tres campos declaraban depender de menos cosas de las que su regla usa, así
    que dejaban de actualizarse cuando cambiaba el maestro. Corregidos los
    depends, Odoo no recalcula lo que ya existe: hay que forzarlo por única vez.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    # el orden importa: las líneas derivan de lo que se corrige arriba
    _realinear_grupos_de_negocio(env)
    _realinear_marca_de_gerencia(cr, env)
    _recalcular_sector_de_cuentas(env)
    _recalcular_agrupaciones_de_lineas(env)


def _recalcular_sector_de_cuentas(env):
    """El sector paso de calcularse en la linea a calcularse en la cuenta.

    Las lineas lo toman de ahi por related, pero eso rige de aca en adelante: lo
    que ya estaba guardado no se refresca solo, asi que igual hay que recorrerlas.
    """
    accounts = env["account.analytic.account"].with_context(active_test=False).search([])
    if not accounts:
        return
    env.add_to_compute(accounts._fields["sector_account_id"], accounts)
    env["base"].flush()
    _logger.info("Sector recalculado en %s cuentas analíticas.", len(accounts))


def _realinear_grupos_de_negocio(env):
    """Son unos pocos registros: se recalculan todos sin filtrar."""
    groups = env["account.analytic.group"].search([])
    if not groups:
        return
    env.add_to_compute(groups._fields["is_business_group"], groups)
    env["base"].flush()
    _logger.info("Marca de grupo de negocio recalculada en %s grupos.", len(groups))


def _realinear_marca_de_gerencia(cr, env):
    """Cuentas cuyo valor guardado no coincide con su propia fórmula."""
    cr.execute("""
        SELECT a.id
        FROM account_analytic_account a
        LEFT JOIN account_analytic_account pa ON pa.id = a.parent_id
        WHERE a.is_management_group <> COALESCE(pa.is_sector_group, false)
    """)
    account_ids = [row[0] for row in cr.fetchall()]
    if not account_ids:
        _logger.info("Marca de gerencia: no hay cuentas desalineadas.")
        return

    # browse en vez de search: entre las desalineadas hay cuentas archivadas.
    accounts = env["account.analytic.account"].browse(account_ids)
    env.add_to_compute(accounts._fields["is_management_group"], accounts)
    env["base"].flush()
    _logger.info("Marca de gerencia realineada en %s cuentas.", len(accounts))


def _recalcular_agrupaciones_de_lineas(env):
    """Las recorre todas: filtrar exigiría replicar la regla del cálculo por
    fuera del sistema, y errarle dejaría líneas sin corregir.
    """
    lines = env["account.analytic.line"].search([])
    if not lines:
        return

    fields = [lines._fields[name] for name in LINE_FIELDS]
    for offset in range(0, len(lines), BATCH_SIZE):
        batch = lines[offset:offset + BATCH_SIZE]
        for field in fields:
            env.add_to_compute(field, batch)
        env["base"].flush()
        # sin esto la caché crece con todas las líneas de la transacción
        env.cache.invalidate()

    _logger.info(
        "Agrupaciones recalculadas en %s líneas analíticas.", len(lines),
    )
