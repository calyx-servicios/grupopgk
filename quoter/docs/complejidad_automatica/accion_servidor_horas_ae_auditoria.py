# Carga de las horas AE de la Tabla #3 en los 3 productos de Auditoría.
#
# Uso (UAT / producción), con un usuario administrador del cotizador y modo desarrollador:
#   1. Terminar antes los pasos 1 a 6 de la sección "Configuración manual" del README
#      (área Auditoría con sus 4 niveles, las 7 ramas-industria, el riesgo por tamaño y los
#      3 productos creados) y dejar abierto el editor de tabla del área.
#   2. Ajustes → Técnico → Acciones de servidor → Crear:
#        Nombre: "Cotizador: cargar horas AE de Auditoría"
#        Modelo: Acción de servidor (ir.actions.server); con otro modelo Odoo 15 no
#                muestra el botón "Ejecutar". El código no usa el registro, solo env.
#        Acción a realizar: Ejecutar código Python
#      y pegar este archivo completo en "Código Python".
#   3. Guardar y usar el botón "Ejecutar".
#
# Solo carga la hora AE (matriz A); MGR, Gerente y Socio los calcula la cascada del área
# (50 % / 30 % / 10 %). Si se ejecuta dos veces, vuelve a escribir los mismos valores.

# Nombre de cada producto tal como se creó en el área → clave de la tabla.
PRODUCTS = {
    "Auditoría": "audit",
    "Armado de balance en Excel y Word": "balance",
    "Cálculo de AXI contable": "axi",
}

# Tabla #3: horas AE por (producto, industria, tamaño). Auditoría / Construcción / Micro = 120
# (el Excel dice 160 por error; confirmado por el cliente).
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

group = env.ref("quoter.group_quoter_auditoria")
area = env["quoter.professional.area"].search([("group_id", "=", group.id)], limit=1)
if not area:
    raise UserError("No se encontró el área de Auditoría (grupo «Quoter - Auditoría»).")
if not area.quoter_config_edit_mode:
    raise UserError("Abra el editor de tabla del área «%s» antes de cargar las horas." % area.name)

size_by_level = {row.complexity_level_id.id: row.company_size for row in area.size_level_ids}
if len(size_by_level) != 4:
    raise UserError(
        "El área «%s» tiene que tener 4 niveles distintos en «Riesgo por tamaño de empresa»." % area.name
    )
industry_by_branch = {}
for code in ("construction", "services", "commerce", "industry", "agriculture", "banking_insurance", "mining"):
    branch = env.ref("quoter.quoter_industry_%s" % code).branch_id
    if branch not in area.branch_ids:
        raise UserError("La rama «%s» no está asignada al área «%s»." % (branch.name, area.name))
    industry_by_branch[branch.id] = code

loaded = 0
missing = []
for name, product_key in PRODUCTS.items():
    line = area.line_ids.filtered(lambda l: l.name == name)[:1]
    if not line:
        missing.append(name)
        continue
    level_ranges = env["quoter.product.level.range"].search(
        [("product_tmpl_id", "=", line.product_tmpl_id.id)]
    )
    for level_range in level_ranges:
        size = size_by_level.get(level_range.complexity_level_id.id)
        industry = industry_by_branch.get(level_range.branch_id.id)
        if not size or not industry:
            continue
        level_range.matrix_a_ids.write({"hours": float(AE_HOURS[(product_key, industry, size)])})
        level_range._recompute_combined_output_hours()
        loaded += 1
if missing:
    raise UserError("No se encontraron estos productos en el área: %s" % ", ".join(missing))

action = {
    "type": "ir.actions.client",
    "tag": "display_notification",
    "params": {
        "title": "Horas AE de Auditoría",
        "message": "Combinaciones cargadas: %s (esperadas: 84)." % loaded,
        "type": "success" if loaded == 84 else "warning",
        "sticky": True,
    },
}
