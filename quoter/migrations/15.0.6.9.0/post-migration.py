# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Complejidad automática: configuración de TAX, PayRoll y Auditoría.

Los catálogos (niveles, industrias, topes SICYPYME, convenios) se cargan desde los archivos
de datos del manifest. Acá se hace lo que depende de áreas creadas desde la UI:

- Auditoría: archiva los productos anteriores y deja los 4 niveles de riesgo y las 7
  ramas-industria (reemplazan Pyme / Gran).
- Carga data/quoter_area_complexity_data.xml (mapeos tamaño → nivel y productos de Auditoría).
- Determinación del nivel: PayRoll por convenios; TAX y Auditoría por tamaño de empresa.
- Auditoría: horas sin mínimo, redondeadas a 0,5, y horas AE de la Tabla #3 (MGR, Gerente y
  Socio salen de la cascada B del área: 50 % / 30 % / 10 %).

Es idempotente: en una base ya configurada no cambia nada.
"""

import logging

from odoo import SUPERUSER_ID, api
from odoo.tools import convert_file

_logger = logging.getLogger(__name__)

INDUSTRIES = (
    "construction",
    "services",
    "commerce",
    "industry",
    "agriculture",
    "banking_insurance",
    "mining",
)

AUDIT_SIZE_LEVELS = (
    ("micro", "quoter.quoter_complexity_level_audit_low"),
    ("small", "quoter.quoter_complexity_level_audit_medium"),
    ("medium", "quoter.quoter_complexity_level_audit_high"),
    ("large", "quoter.quoter_complexity_level_audit_very_high"),
)

AUDIT_LINES = (
    ("audit", "quoter.quoter_service_line_audit_audit"),
    ("balance", "quoter.quoter_service_line_audit_balance"),
    ("axi", "quoter.quoter_service_line_audit_axi"),
)

# Tabla #3: horas AE por (producto, industria, tamaño).
# Auditoría / Construcción / Micro: el Excel dice 160; el valor confirmado es 120.
AE_HOURS = {
    ("audit", "construction", "micro"): 120,
    ("audit", "construction", "small"): 200,
    ("audit", "construction", "medium"): 250,
    ("audit", "construction", "large"): 313,
    ("audit", "services", "micro"): 62,
    ("audit", "services", "small"): 93,
    ("audit", "services", "medium"): 140,
    ("audit", "services", "large"): 209,
    ("audit", "commerce", "micro"): 87,
    ("audit", "commerce", "small"): 130,
    ("audit", "commerce", "medium"): 163,
    ("audit", "commerce", "large"): 195,
    ("audit", "industry", "micro"): 82,
    ("audit", "industry", "small"): 123,
    ("audit", "industry", "medium"): 160,
    ("audit", "industry", "large"): 200,
    ("audit", "agriculture", "micro"): 84,
    ("audit", "agriculture", "small"): 126,
    ("audit", "agriculture", "medium"): 189,
    ("audit", "agriculture", "large"): 284,
    ("audit", "banking_insurance", "micro"): 100,
    ("audit", "banking_insurance", "small"): 150,
    ("audit", "banking_insurance", "medium"): 225,
    ("audit", "banking_insurance", "large"): 338,
    ("audit", "mining", "micro"): 84,
    ("audit", "mining", "small"): 126,
    ("audit", "mining", "medium"): 189,
    ("audit", "mining", "large"): 284,
    ("balance", "construction", "micro"): 8,
    ("balance", "construction", "small"): 12,
    ("balance", "construction", "medium"): 16,
    ("balance", "construction", "large"): 20,
    ("balance", "services", "micro"): 6,
    ("balance", "services", "small"): 9,
    ("balance", "services", "medium"): 12,
    ("balance", "services", "large"): 15,
    ("balance", "commerce", "micro"): 8,
    ("balance", "commerce", "small"): 12,
    ("balance", "commerce", "medium"): 16,
    ("balance", "commerce", "large"): 20,
    ("balance", "industry", "micro"): 10,
    ("balance", "industry", "small"): 15,
    ("balance", "industry", "medium"): 20,
    ("balance", "industry", "large"): 25,
    ("balance", "agriculture", "micro"): 12,
    ("balance", "agriculture", "small"): 18,
    ("balance", "agriculture", "medium"): 23,
    ("balance", "agriculture", "large"): 30,
    ("balance", "banking_insurance", "micro"): 40,
    ("balance", "banking_insurance", "small"): 60,
    ("balance", "banking_insurance", "medium"): 78,
    ("balance", "banking_insurance", "large"): 101,
    ("balance", "mining", "micro"): 12,
    ("balance", "mining", "small"): 18,
    ("balance", "mining", "medium"): 23,
    ("balance", "mining", "large"): 30,
    ("axi", "construction", "micro"): 12,
    ("axi", "construction", "small"): 18,
    ("axi", "construction", "medium"): 23,
    ("axi", "construction", "large"): 28,
    ("axi", "services", "micro"): 6,
    ("axi", "services", "small"): 9,
    ("axi", "services", "medium"): 12,
    ("axi", "services", "large"): 15,
    ("axi", "commerce", "micro"): 8,
    ("axi", "commerce", "small"): 12,
    ("axi", "commerce", "medium"): 16,
    ("axi", "commerce", "large"): 20,
    ("axi", "industry", "micro"): 12,
    ("axi", "industry", "small"): 18,
    ("axi", "industry", "medium"): 23,
    ("axi", "industry", "large"): 30,
    ("axi", "agriculture", "micro"): 12,
    ("axi", "agriculture", "small"): 18,
    ("axi", "agriculture", "medium"): 27,
    ("axi", "agriculture", "large"): 41,
    ("axi", "banking_insurance", "micro"): 24,
    ("axi", "banking_insurance", "small"): 36,
    ("axi", "banking_insurance", "medium"): 45,
    ("axi", "banking_insurance", "large"): 56,
    ("axi", "mining", "micro"): 12,
    ("axi", "mining", "small"): 18,
    ("axi", "mining", "medium"): 27,
    ("axi", "mining", "large"): 41,
}


def _industry_by_branch(env):
    return {
        env.ref("quoter.quoter_area_branch_industry_%s" % code).id: code for code in INDUSTRIES
    }


def _prepare_audit_area(env, area):
    """Deja en Auditoría los niveles de riesgo y las ramas-industria antes de cargar los datos."""
    data_lines = env["quoter.service.line"]
    for _key, xmlid in AUDIT_LINES:
        data_lines |= env.ref(xmlid, raise_if_not_found=False) or data_lines
    # Primero se archivan los productos anteriores: así no se les generan matrices
    # para los niveles y ramas nuevos.
    old_lines = area.line_ids - data_lines
    old_lines.mapped("product_tmpl_id").write({"active": False})
    old_lines.write({"active": False})
    area.write({"cerrado": False, "quoter_config_edit_mode": True})
    levels = [env.ref(xmlid) for _size, xmlid in AUDIT_SIZE_LEVELS]
    branches = env["quoter.area.branch"].browse(list(_industry_by_branch(env)))
    area.write(
        {
            "complexity_level_ids": [(6, 0, [level.id for level in levels])],
            # Ramas y rama de la matriz juntas: si no, salta la validación de la rama activa.
            "branch_ids": [(6, 0, branches.ids)],
            "matrix_branch_id": branches[:1].id,
        }
    )


def _load_ae_hours(env, product_keys):
    """Horas AE de la Tabla #3 en los productos de Auditoría indicados.

    Solo para productos recién creados: al crearse, la matriz A queda con un valor por
    defecto (1 h), así que no se puede usar «tiene horas» para saber si ya se cargaron.
    """
    size_by_level = {env.ref(xmlid).id: size for size, xmlid in AUDIT_SIZE_LEVELS}
    industry_by_branch = _industry_by_branch(env)
    LevelRange = env["quoter.product.level.range"]
    for product_key, xmlid in AUDIT_LINES:
        line = env.ref(xmlid, raise_if_not_found=False)
        if not line or product_key not in product_keys:
            continue
        level_ranges = LevelRange.search([("product_tmpl_id", "=", line.product_tmpl_id.id)])
        for level_range in level_ranges:
            size = size_by_level.get(level_range.complexity_level_id.id)
            industry = industry_by_branch.get(level_range.branch_id.id)
            if not size or not industry:
                continue
            hours = float(AE_HOURS[(product_key, industry, size)])
            level_range.matrix_a_ids.write({"hours": hours})
            level_range._recompute_combined_output_hours()


def migrate(cr, version):
    if not version:
        return
    # Al cambiar las ramas el área realinea los bloques de cotizaciones existentes,
    # incluso las cerradas por el workflow.
    env = api.Environment(cr, SUPERUSER_ID, {"quoter_workflow_transition": True})
    tax = env.ref("quoter.quoter_area_tax", raise_if_not_found=False)
    audit = env.ref("quoter.quoter_area_auditoria", raise_if_not_found=False)
    payroll = env.ref("quoter.quoter_area_payroll", raise_if_not_found=False)
    if not (tax and audit):
        _logger.warning(
            "quoter: no se encontraron las áreas TAX y Auditoría; "
            "no se carga data/quoter_area_complexity_data.xml."
        )
    else:
        audit_was_closed = audit.cerrado
        audit_pending = audit.complexity_source != "company_size"
        if audit_pending:
            _prepare_audit_area(env, audit)
        new_products = {
            key for key, xmlid in AUDIT_LINES if not env.ref(xmlid, raise_if_not_found=False)
        }
        convert_file(
            cr,
            "quoter",
            "data/quoter_area_complexity_data.xml",
            {},
            mode="update",
            noupdate=True,
            kind="data",
        )
        env["base"].invalidate_cache()
        if tax.complexity_source == "manual":
            tax.complexity_source = "company_size"
        if audit_pending:
            audit.write(
                {
                    "complexity_source": "company_size",
                    # La Tabla #3 tiene Socio = 0 h: sin mínimo de horas.
                    "output_hours_minimum": 0.0,
                    "output_hours_rounding": 0.5,
                }
            )
        _load_ae_hours(env, new_products)
        if audit_pending:
            audit._quoter_validate_config_before_lock()
            audit._quoter_recompute_after_config_save()
            audit.write({"quoter_config_edit_mode": False, "cerrado": audit_was_closed})
    if payroll and payroll.complexity_source == "manual":
        payroll.complexity_source = "labor_agreement"
