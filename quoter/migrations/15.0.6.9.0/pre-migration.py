# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Asigna xmlid a la configuración creada desde la UI antes de cargar los datos.

Los archivos de datos (noupdate) referencian áreas, niveles y secciones que se crearon desde la
UI y no tienen xmlid. Acá se los vincula por grupo o por nombre para que la carga de datos los
reutilice en lugar de duplicarlos. En bases donde la configuración ya existía (stg, que corrió
las versiones de desarrollo 15.0.6.7.0 a 15.0.6.8.2) también se vinculan los convenios, los
mapeos tamaño → nivel y los productos de Auditoría.

Solo SQL: en la pre-migración todavía no existen las tablas ni columnas nuevas.
"""

import re
import unicodedata

AREAS = (
    ("tax", "group_quoter_tax"),
    ("auditoria", "group_quoter_auditoria"),
    ("payroll", "group_quoter_payroll"),
)
SHARED_LEVELS = (("low", "Bajo", 10), ("medium", "Medio", 20), ("high", "Alto", 30))
SEPARATOR_TAGS = (("default", "Default"), ("additional", "Adicional"))
AUDIT_LINES = (
    ("audit", "Auditoría"),
    ("balance", "Armado de balance en Excel y Word"),
    ("axi", "Cálculo de AXI contable"),
)
SIZES = ("micro", "small", "medium", "large")


def _slug(name):
    """Mismo criterio que los xmlid de data/quoter_labor_agreement_data.xml."""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _table_exists(cr, table):
    cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (table,))
    return bool(cr.fetchone())


def _xmlid_res_id(cr, name):
    cr.execute("SELECT res_id FROM ir_model_data WHERE module = 'quoter' AND name = %s", (name,))
    row = cr.fetchone()
    return row[0] if row else None


def _bind(cr, model, name, res_id):
    if not res_id or _xmlid_res_id(cr, name):
        return
    cr.execute(
        """
        INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date)
        VALUES ('quoter', %s, %s, %s, TRUE, now() AT TIME ZONE 'UTC', now() AT TIME ZONE 'UTC')
        """,
        (name, model, res_id),
    )


def _first_id(cr, query, params):
    cr.execute(query, params)
    row = cr.fetchone()
    return row[0] if row else None


def migrate(cr, version):
    if not version:
        return
    areas = {}
    for key, group in AREAS:
        area_id = _first_id(
            cr,
            "SELECT id FROM quoter_professional_area WHERE group_id = %s ORDER BY id LIMIT 1",
            (_xmlid_res_id(cr, group),),
        )
        if area_id:
            areas[key] = area_id
            _bind(cr, "quoter.professional.area", "quoter_area_%s" % key, area_id)

    # Bajo / Medio / Alto compartidos: los que usan TAX o PayRoll. Se marcan aptos para convenio
    # acá porque los convenios (datos) lo exigen y los niveles existentes no se actualizan.
    cr.execute(
        "ALTER TABLE quoter_complexity_level ADD COLUMN IF NOT EXISTS labor_agreement_ok BOOLEAN"
    )
    shared_areas = tuple(areas[key] for key in ("tax", "payroll") if key in areas)
    for key, name, sequence in SHARED_LEVELS if shared_areas else ():
        level_id = _xmlid_res_id(cr, "quoter_complexity_level_%s" % key) or _first_id(
            cr,
            """
            SELECT l.id FROM quoter_complexity_level l
              JOIN quoter_professional_area_complexity_level_rel r
                ON r.complexity_level_id = l.id
             WHERE r.area_id IN %s AND lower(l.name) = lower(%s)
             ORDER BY l.id LIMIT 1
            """,
            (shared_areas, name),
        )
        if level_id:
            _bind(cr, "quoter.complexity.level", "quoter_complexity_level_%s" % key, level_id)
            cr.execute(
                """
                UPDATE quoter_complexity_level SET sequence = %s, labor_agreement_ok = TRUE
                 WHERE id = %s
                """,
                (sequence, level_id),
            )

    for key, name in SEPARATOR_TAGS:
        tag_id = _first_id(
            cr,
            "SELECT id FROM quoter_line_separator_tag WHERE lower(name) = lower(%s) ORDER BY id",
            (name,),
        )
        _bind(cr, "quoter.line.separator.tag", "quoter_line_separator_tag_%s" % key, tag_id)

    if _table_exists(cr, "quoter_labor_agreement"):
        cr.execute("SELECT id, name FROM quoter_labor_agreement")
        for agreement_id, name in cr.fetchall():
            _bind(cr, "quoter.labor.agreement", "quoter_labor_agreement_%s" % _slug(name), agreement_id)

    if _table_exists(cr, "quoter_area_size_level"):
        for key in ("tax", "auditoria"):
            for size in SIZES:
                row_id = _first_id(
                    cr,
                    """
                    SELECT id FROM quoter_area_size_level
                     WHERE area_id = %s AND company_size = %s
                    """,
                    (areas.get(key), size),
                )
                _bind(cr, "quoter.area.size.level", "quoter_area_size_level_%s_%s" % (key, size), row_id)

    for key, name in AUDIT_LINES if "auditoria" in areas else ():
        line_id = _first_id(
            cr,
            """
            SELECT id FROM quoter_service_line
             WHERE area_id = %s AND name = %s AND active
             ORDER BY id LIMIT 1
            """,
            (areas["auditoria"], name),
        )
        _bind(cr, "quoter.service.line", "quoter_service_line_audit_%s" % key, line_id)
