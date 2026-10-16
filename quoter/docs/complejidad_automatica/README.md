# Complejidad automática del cotizador (Payroll · Tax · Auditoría)

Documento de traspaso del requerimiento de grupopgk (Odoo 15 community, módulo `quoter`).
Sirve para retomar el desarrollo desde otra máquina o en otra sesión de Claude Code sin
tener que volver a hacer el análisis.

| | |
|---|---|
| Cliente | grupopgk (implementa Calyx) |
| Módulo | `extra-addons/grupopgk/quoter` (no confundir con la copia vieja `extra-addons/quoter`) |
| Rama git | `15.0_staging` |
| Versión del módulo | `15.0.6.9.0` (antes `15.0.6.6.26`) |
| Estado al 2026-10-16 | Desarrollo completo (incluye los cambios de las secciones 10 a 12), probado en `pgk-stg` por tests, shell y UI. **Sin commitear.** |
| Excel de origen | `Nuevo Parametros AUD-PY.xlsx` (no está en el repo; las tablas están en los CSV de esta carpeta) |

Archivos de esta carpeta:

| Archivo | Contenido |
|---|---|
| `README.md` | Este documento |
| `tabla1_convenios_payroll.csv` | Tabla #1: 128 convenios colectivos y su complejidad base |
| `tabla2_sicypyme_topes.csv` | Tabla #2: topes de facturación por industria (Res. SICYPYME 1/2026) |
| `tabla3_horas_auditoria.csv` | Tabla #3: horas por rol de los 3 productos de Auditoría, con los valores del Excel y los que calcula el sistema |

---

## 1. Requerimiento original

### Contexto

Hoy el cotizador elige a mano el nivel de complejidad o riesgo (Bajo/Medio/Alto) en cada área.
El cliente quiere eliminar esa subjetividad: el nivel tiene que salir de datos objetivos
(convenios colectivos, facturación, industria) y el campo tiene que quedar de solo lectura.

**Fuera de alcance:** el motor de cálculo de horas por rol (matrices A/B, `combined`,
`formula`, `formula_chain`), las tablas de horas de Tax y las tarifas o listas de precios.
Solo cambia lo que determina el nivel que alimenta esas matrices, más la limpieza de los
productos de Auditoría.

### Alcance por área (tal como lo pidió el cliente)

**Payroll**
- Catálogo de convenios con su complejidad base (Tabla #1), administrable desde Configuración.
- Campo many2many de convenios en el bloque de Payroll.
- Regla que combina N convenios en una complejidad final (Tabla #5).
- Nivel de solo lectura en todos los estados.

**Auditoría** (la parte más grande)
- Eliminar el campo "primera auditoría" y su lógica.
- Campo numérico obligatorio: facturación del año anterior.
- Reutilizar el campo Rama como "Industria", con 7 valores.
- Tabla de categorización facturación × industria → tamaño (SICYPYME) y su mapeo a nivel.
- Nivel de riesgo de solo lectura y formulario reordenado.
- Archivar los productos de Auditoría existentes, salvo los 3 definidos.
- Cargar la Tabla #3 de horas por rol (3 productos × 4 tamaños × 7 industrias).

**Tax**
- Los mismos dos campos (facturación e industria), debajo del Gerente.
- Reutilizar el cálculo de tamaño de Auditoría y aplicar la Tabla #4 (tamaño → complejidad).
- Nivel de solo lectura. Productos y tablas de horas de Tax sin cambios.

### Checklist original y estado

| Ítem | Estado |
|---|---|
| Payroll: convenios m2m y catálogo (Tabla #1) | ✅ |
| Payroll: regla de combinación de convenios (Tabla #5) | ✅ |
| Payroll: nivel readonly | ✅ |
| Auditoría: quitar "primera auditoría" y su lógica | ✅ |
| Auditoría: campo facturación año anterior | ✅ |
| Auditoría: Rama → Industria (7 valores) | ✅ |
| Auditoría: tabla SICYPYME + mapeo a nivel | ✅ (4 niveles de riesgo, ver decisiones) |
| Auditoría: formulario y nivel readonly | ✅ |
| Auditoría: archivar productos viejos | ✅ |
| Auditoría: cargar Tabla #3 | ✅ |
| Tax: campos facturación e industria | ✅ |
| Tax: mapeo Tabla #4 | ✅ |
| Tax: nivel readonly | ✅ |
| QA / regresión de horas por rol | ✅ técnica (tests, shell, UI). Falta la prueba funcional del cliente |

---

## 2. Tablas del Excel

### Tabla #1: convenios (Payroll)
Ver `tabla1_convenios_payroll.csv`. Son 128 convenios: 42 Baja, 50 Media y 36 Alta.
"Refractarios" viene marcado Media y Alta; el cliente confirmó **Alta**.

### Tabla #2: topes SICYPYME (Auditoría y Tax)
Ver `tabla2_sicypyme_topes.csv`. Importes en ARS de la Resolución N° 1/2026; se actualizan
**anualmente**. Industrias: Construcción, Servicios, Comercio, Industria, Agropecuario,
Bancos y seguros, Minería.
- Minería usa los mismos topes que Industria, y Bancos y seguros los de Servicios. Esas dos
  industrias no existen en la resolución; las agrega el cliente.
- "Mediana" unifica los tramos 1 y 2 de la resolución. Por encima de Mediana es Grande.
- Los topes son inclusivos (`facturación <= tope`).

### Tabla #3: horas por rol (Auditoría)
Ver `tabla3_horas_auditoria.csv`. Son 3 productos × 7 industrias × 4 tamaños × 4 roles.
- Roles del Excel → roles del sistema: AE = AE, SR = MGR, GTE = Gerente, SOCIO = Socio.
- Los valores siguen la cascada que ya tenía configurada el área (`table_b_percent_basis = previous_role`,
  factores B fijos): MGR = 50% de AE, Gerente = 30% de MGR, Socio = 10% de Gerente.
  **Por eso solo se cargan las horas AE (84 valores)**; el resto lo calcula el motor.
- Error del Excel: Auditoría / Construcción / Micro tiene AE = 160. El cliente confirmó **120**,
  que es el valor consistente con SR 60 y total 200.
- La columna TOTAL del Excel difiere en ±1 en varias filas: es redondeo del Excel, no un error de datos.
- El sistema redondea a 0,5 h (el Excel, a horas enteras). Hay 108 de 336 celdas que difieren
  exactamente 0,5; ninguna difiere más. El cliente aceptó decimales de media hora.

### Tabla #4: tamaño → complejidad (Tax)
| Tamaño | Complejidad |
|---|---|
| Micro | Bajo |
| Pequeña | Bajo |
| Mediana | Medio |
| Grande | Alto |

### Tabla #5: regla de convenios (Payroll)
- 0 o 1 convenio: la complejidad de ese convenio. Con 0, **Bajo** (confirmado por el cliente).
  "Fuera de convenio" no cuenta como convenio.
- 2 convenios: como mínimo Medio, salvo que alguno sea Alto (entonces Alto).
- 3 o más: siempre Alto.

### Mapeo de Auditoría (definido con el cliente, no está en el Excel; configurable, ver sección 10)
| Tamaño | Nivel de riesgo |
|---|---|
| Micro | Bajo |
| Pequeña | Medio |
| Mediana | Alto |
| Grande | Muy alto |

---

## 3. Decisiones del cliente (respuestas del funcional)

1. **Auditoría tiene 4 tipos de riesgo** y dependen solo de facturación + industria. Se eligió
   el "punto intermedio": 4 niveles **propios de Auditoría** (no se reutilizan los Bajo/Medio/Alto
   compartidos con Tax y Payroll), con nombres de riesgo (Bajo/Medio/Alto/Muy alto).
   El mapeo tamaño → riesgo es **configurable** (sección 10): el riesgo define las horas.
2. Construcción Micro (Auditoría): AE = 120.
3. Horas con decimales en pasos de 0,5.
4. Refractarios = Alta.
5. Sin convenios = Bajo.
6. SR = MGR y GTE = Gerente.
7. Facturación en ARS, topes inclusivos.
8. `pgk-stg` representa a producción. El desarrollo todavía no se usa en producción y los
   borradores existentes son de prueba (se pueden descartar).

### Supuestos tomados por el desarrollo (pendientes de confirmar)
- Vigencia de la Res. 1/2026 = **2026-01-01**. Se corrige desde Configuración → Topes SICYPYME.
- Sección del cotizador: Auditoría en "Default"; Armado y AXI en "Adicional". Ningún producto
  es predeterminado (`load_default_products` del área ya estaba en False).
- **Mínimo de horas de Auditoría bajado de 1 a 0**, porque la Tabla #3 tiene Socio = 0 h
  en Armado y AXI.
- Nombres de los productos: "Auditoría", "Armado de balance en Excel y Word" y "Cálculo de AXI contable"
  (el template queda como "Servicio profesional Auditoría · <nombre>").

---

## 4. Cómo estaba antes (hallazgos del análisis)

- Hay un único campo de nivel por bloque: `quoter.sale.order.area.complexity_level_id` (m2o a
  `quoter.complexity.level`). En Auditoría la UI y el PDF lo muestran como "Nivel de riesgo"
  (JS `quoter_area_block_embed.js` y `quoter_sale_order_report.py`).
- La Rama es un m2o a `quoter.area.branch` (catálogo) y **forma parte de la clave de horas**:
  `quoter.product.level.range` es único por (producto, nivel, rama). Auditoría usaba
  Pyme/Gran; las demás áreas, "Rama única".
- Modos de horas en stg: TAX = `regular`, Auditoría = `combined` (cascada B `previous_role`),
  PayRoll = `formula_chain` (el nivel suma un % sobre la tabla de la cadena: Bajo 0, Medio +20, Alto +40),
  BPO = `formula` y Finanzas = `regular_manual`.
- Las áreas y los niveles se crearon desde la UI y **no tienen xmlid**. Las áreas se identifican
  por su grupo (`quoter.group_quoter_tax`, `group_quoter_auditoria`, `group_quoter_payroll`).
- Todos los niveles tenían `sequence = 10`. El código decidía "el más alto" por id. Ahora el
  orden sale de `sequence` (Bajo 10, Medio 20, Alto 30; Auditoría 10..40).
- "Primera auditoría" (`sale.order.quoter_is_first_quotation` + related en el bloque) solo forzaba
  el nivel más alto y cargaba productos predeterminados. Se eliminó entero.
- El `write()` del bloque reacciona a `complexity_level_id in vals` para resincronizar líneas y
  horas. Por eso el nivel **no** es un compute almacenado: se deriva en create/write y se escribe
  por el camino normal.

---

## 5. Diseño implementado

### Idea general
Cada área tiene un campo nuevo `complexity_source` ("Determinación del nivel"):

| Valor | Áreas en stg | Cómo se calcula el nivel |
|---|---|---|
| `manual` | BPO, Finanzas | Como antes, lo elige el usuario |
| `labor_agreement` | PayRoll | Tabla #5 sobre los convenios del bloque |
| `company_size` | TAX, Auditoría | Facturación + industria → tamaño (SICYPYME) → nivel (tabla `size_level_ids` del área) |

En `company_size`, si el área usa ramas (Auditoría), la rama del bloque se completa con la
rama vinculada a la industria (`quoter.industry.branch_id`).

### Modelos nuevos (`models/quoter_complexity_source.py`)
- `quoter.labor.agreement`: name (único), `complexity_level_id`, active.
- `quoter.industry`: name, sequence, active, `branch_id`, `threshold_ids`.
  `_quoter_company_size(revenue, date)` devuelve micro/small/medium/large.
- `quoter.sicypyme.threshold`: industry, `date_from` (vigencia), resolution, `micro_max`,
  `small_max`, `medium_max`. Usa el tope vigente a la fecha de la cotización.
- `quoter.area.size.level`: área + tamaño → nivel (Tablas #4 y Auditoría).
- Herencia de `quoter.professional.area`: `complexity_source`, `size_level_ids`,
  `_quoter_level_for_labor_agreements()` (Tabla #5), `_quoter_level_for_company_size()` y
  `action_quoter_recompute_draft_levels()` (sección 10). Restricciones: en `company_size` los
  4 tamaños tienen que tener nivel, y el nivel tiene que ser uno de los del área.

### Bloque (`models/quoter_sale_order_area_complexity.py`)
- Campos: `labor_agreement_ids`, `prev_year_revenue`, `industry_id`, `company_size` (compute
  almacenado), `area_complexity_source` y `company_size_inputs_required`.
- `_quoter_apply_derived_complexity_level()` escribe nivel y rama juntos con el contexto
  `quoter_derived_complexity_level=True` y devuelve los bloques cuyo nivel cambió. Se llama al
  final de `create` y de `write` cuando cambian convenios, facturación, industria, área, nivel o
  rama, y desde `sale.order.write` si cambia `date_order`. Solo actúa sobre cotizaciones con el
  bloque en borrador. **No** se dispara al cambiar la configuración: para eso está el botón de
  recálculo (sección 10).
- Un onchange muestra el nivel calculado antes de guardar.
- En `quoter_sale_order_area.py`, el chequeo de "nivel congelado" se saltea con ese contexto
  (Tax tiene `allow_change_complexity_level = False`).

### Otros cambios
- `quoter_area.py`: campo `output_hours_rounding` ("Redondear horas a múltiplos de"), aplicado en
  `_apply_output_hours_minimum()` **antes** del mínimo. Solo Auditoría lo tiene en 0,5.
- `sale_order.py` / `quoter_sale_order_area.py`: se eliminó toda la lógica de primera auditoría
  (campo, onchange, efectos en create/write, `_quoter_highest_complexity_level`).
- `quoter_sale_order_report.py`: la fila del PDF "Tipo de empresa" ahora se llama "Industria".
- Vistas:
  - `sale_order_views.xml`: campos nuevos debajo del Gerente; nivel readonly si no es manual;
    Rama oculta en `company_size`; aviso "Complete la facturación del año anterior y la industria…".
  - `quoter_complexity_source_views.xml`: menús Configuración → Convenios colectivos, Industrias
    y Topes SICYPYME, más "Determinación del nivel" en el formulario del área.
  - `quoter_service_views.xml`: handle de secuencia en niveles; campo de redondeo en el área.
- Datos (todos `noupdate="1"`, ver sección 12):
  - `data/quoter_complexity_level_data.xml`: Bajo/Medio/Alto compartidos + 4 niveles de Auditoría.
  - `data/quoter_industry_data.xml`: 7 ramas-industria, 7 industrias y topes 2026.
  - `data/quoter_labor_agreement_data.xml`: 128 convenios.
  - `data/quoter_area_complexity_data.xml`: mapeos tamaño → nivel y productos de Auditoría
    (no está en el manifest; lo carga la migración).
- Seguridad: lectura para vendedores y ABM para el gerente de ventas en los 4 modelos nuevos.

### Migraciones
Una sola versión, **`migrations/15.0.6.9.0/`** (reemplaza a las de desarrollo 6.7.0, 6.8.0 y
6.8.2, que solo corrieron en stg):
- **`pre-migration.py`** (solo SQL): asigna xmlid a lo creado desde la UI para que los datos lo
  reutilicen. Vincula las áreas TAX/Auditoría/PayRoll (por grupo), Bajo/Medio/Alto (los que usan
  TAX o PayRoll), las secciones Default/Adicional (por nombre) y, si ya existían, convenios,
  mapeos y productos de Auditoría. También marca Bajo/Medio/Alto como aptos para convenio y les
  pone secuencia 10/20/30.
- **`post-migration.py`** (idempotente):
  1. Si Auditoría no está configurada: archiva los productos anteriores, abre el área
     (`cerrado` y `quoter_config_edit_mode`) y le asigna los 4 niveles, las 7 ramas y
     `matrix_branch_id`.
  2. Carga `data/quoter_area_complexity_data.xml`.
  3. TAX → `company_size`; Auditoría → `company_size`, mínimo 0 y redondeo 0,5;
     PayRoll → `labor_agreement`. Solo si estaban en `manual`.
  4. Carga las horas AE (`AE_HOURS`) solo en los productos de Auditoría que creó el paso 2.
     No se puede usar "ya tiene horas" como criterio: al crearse, la matriz A queda en 1 h.
  5. Valida, recalcula y vuelve a cerrar el área.

  Corre con el contexto `quoter_workflow_transition=True` porque, al cambiar las ramas, el área
  realinea los bloques de cotizaciones ya aprobadas.

Gotchas de la migración de Auditoría (los tres aparecieron al probar):
- El cambio de `branch_ids` y `matrix_branch_id` tiene que ir en el mismo `write` (si no, salta
  "La rama activa debe pertenecer a las ramas definidas").
- `quoter.service.line.separator_tag_id` es obligatorio.
- Un área cerrada (`cerrado`) no deja cambiar `complexity_level_ids`.

### Configuración resultante en stg (área → valor)
- TAX: `company_size`, mapeo de la Tabla #4.
- PayRoll: `labor_agreement`.
- Auditoría:
  - `company_size` con niveles Bajo/Medio/Alto/Muy alto (ids 51 a 54 en stg).
  - Ramas = 7 industrias; rama de la matriz = Construcción.
  - Mínimo 0 y redondeo 0,5.
  - 3 productos activos, cada uno con 28 combinaciones nivel × rama.

---

## 6. Archivos tocados

Nuevos:
- `models/quoter_complexity_source.py`
- `models/quoter_sale_order_area_complexity.py`
- `views/quoter_complexity_source_views.xml`
- `data/quoter_complexity_level_data.xml`, `data/quoter_industry_data.xml`,
  `data/quoter_labor_agreement_data.xml`, `data/quoter_area_complexity_data.xml`
- `migrations/15.0.6.9.0/pre-migration.py` y `post-migration.py`
- `tests/test_quoter_complexity_source.py`
- `docs/complejidad_automatica/*` (esta carpeta)

Modificados: `__manifest__.py`, `models/__init__.py`, `models/quoter_area.py`,
`models/quoter_sale_order_area.py`, `models/quoter_sale_order_report.py`,
`models/quoter_sale_order_workflow.py` (sección 10), `models/sale_order.py`,
`security/ir.model.access.csv`, `tests/__init__.py`, `views/quoter_service_views.xml` y
`views/sale_order_views.xml`.

---

## 7. Entorno y cómo probar

### Entorno local (máquina original)
- Docker: `odoo_15` (Odoo, puerto 8015, debugpy 5615), `db_15` (Postgres 16, puerto 5433) y `pgadmin4_15`.
- Configuración: `odoo_dockerfiles/15_docker/odoo_dockerfiles/odoo_conf/odoo.conf`. En `addons_path`,
  `submodules/ingadhoc/aeroo_reports` tiene que ir **antes** que `submodules/aeroo/aeroo_reports`,
  si no la base no arranca. Si se recrea el contenedor, falta `aeroolib`: instalar el
  `requirements.txt` de `ingadhoc/aeroo_reports`.
- Base: `pgk-stg` (copia de producción). Usuario de prueba `admin` / `admin`.
- Las cotizaciones son de la compañía **Calyx Servicios S.A. (id 3)**: en la UI hay que activar
  esa compañía (cookie/URL `cids=3`).
- Hay un backup previo a la migración de Auditoría en `db_15:/tmp/pgk-stg-pre-audit-20261015.dump`
  (se pierde si se recrea el contenedor).

### Actualizar el módulo
```bash
docker exec odoo_15 python3 /home/calyx/odoo/odoo-bin -c /etc/odoo/odoo.conf -d pgk-stg \
  -u quoter --stop-after-init --no-http
docker restart odoo_15   # el servidor en marcha no recarga el código Python
```
Errores del log que **no** tienen que ver con este desarrollo: `quoter.area.matrix.b.exception has no table`,
`recurrence.period has no table`, menús `menu_quoter_generic_products` inexistentes y adjuntos
faltantes en el filestore de stg.

### Tests
```bash
docker exec odoo_15 python3 /home/calyx/odoo/odoo-bin -c /etc/odoo/odoo.conf -d pgk-stg \
  --test-enable --test-tags /quoter:TestQuoterComplexitySource --stop-after-init --no-http
```
Son 19 tests: regla de convenios, nivel apto para convenio, tamaño por topes y vigencia, derivación en bloques Payroll,
Tax y Auditoría, rama por industria, tamaños que comparten riesgo, completitud del mapeo, nivel
ajeno al área, recálculo de borradores (también sin perfil Cotizador), redondeo y nivel congelado.

Trampas de `pgk-stg` al escribir tests:
- No se pueden crear `res.partner` (`partner_identification_required` exige CUIT): usar
  `env.company.partner_id`.
- No se pueden modificar grupos de usuarios (falta la tabla `project_workflow_scrum_rel`).
- `sale.order.date_of_issue` es NOT NULL.
- El workflow solo deja editar al perfil cotizador: mockear `sale.order._quoter_user_is_cotizador_profile`.
- `test_quoter_workflow` (el test que ya existía) falla en `setUpClass` por el alta de partner;
  no es una regresión.

### Pruebas por UI realizadas (2026-10-16, Playwright + Chromium headless, cotización Q00037, id 8545)
| Área | Caso | Resultado |
|---|---|---|
| Tax | 300 M + Servicios | Micro / Bajo (las 41 h de "Confección DJ IIGG Anual" se verificaron por shell) |
| Tax | 30.000 M | Grande / Alto; 80/40/24/8 = 152 h, $208.000 |
| PayRoll | 0 / 1 Media / 2 / 3 convenios | Bajo / Medio / Medio / Alto; Alto = 1,40 h (+40%) |
| Auditoría | Construcción 700 M | Micro / Bajo; 3 productos = 233 h (200 + 13 + 20) |
| Auditoría | Bancos y seguros 30.000 M | Grande / Muy alto; 824 h (562,5 + 168 + 93,5) |

En la UI los productos se habilitan **después de guardar** el bloque (el nivel aparece antes,
pero `selectable_product_ids` usa el nivel guardado). Ya funcionaba así con el nivel manual.

Para repetir las pruebas por UI sin `sudo`: crear un venv (si falta `python3-venv`, usar
`python3 -m venv --without-pip` + `get-pip.py`), `pip install playwright`,
`playwright install chromium`, y extraer con `apt-get download` + `dpkg -x` las librerías
`libnspr4`, `libnss3` y `libasound2` (apuntar `LD_LIBRARY_PATH` ahí). Odoo deja longpolling
abierto: no esperar `networkidle`, sino la ausencia de `.o_blockUI`.

---

## 8. Pendientes

1. **Commit** (y PR si corresponde) de todo lo anterior.
2. Confirmar con el cliente los supuestos de la sección 3 (vigencia, secciones, mínimo 0).
3. **Error previo, ajeno al requerimiento:** el chatter no registra cambios de campos del bloque
   (nivel, convenios, facturación, industria, gerente, descuento). En
   `QuoterSaleOrderArea.write()` se arma `tracked` antes de escribir, pero
   `_quoter_log_block_changes(tracked)` se llama después y compara el valor nuevo contra sí mismo.
   Viene del commit `e3dc310`. Arreglo propuesto: tomar los valores anteriores antes del `super().write`.
4. Prueba funcional del cliente en stg.
5. **Pase a producción** (confirmado: producción ya tiene `quoter` instalado): actualizar el
   módulo a `15.0.6.9.0`; la migración configura todo sola. El camino se probó con una
   simulación (sección 12).

## 9. Notas para retomar

- Para cambiar el riesgo de un tamaño: Configuración → Riesgo por tamaño de empresa, y después
  "Recalcular cotizaciones en borrador" (ver sección 10).

- Los niveles de Auditoría se llaman igual que los de Tax/Payroll (Bajo/Medio/Alto) pero son
  registros distintos (xmlid `quoter.quoter_complexity_level_audit_*`). En la lista de niveles
  aparecen nombres repetidos.
- El diálogo JS "¿Desea modificar el nivel de riesgo?" (`quoter_area_block_embed.js`) solo se
  dispara con cambios manuales; con el campo en solo lectura ya no aparece.
- Para cambiar topes en el futuro: agregar filas nuevas en Topes SICYPYME con la nueva fecha de
  vigencia, sin editar las anteriores, así las cotizaciones viejas mantienen su tamaño.
- Para cambiar horas de Auditoría: Configuración → Áreas → Auditoría → abrir el editor de tabla
  y cargar las horas AE; MGR, Gerente y Socio salen de la cascada.

---

## 10. Cambio posterior: riesgo configurable por tamaño de empresa (2026-10-16, versión 15.0.6.8.1)

### Pedido
Poder cambiar más adelante qué riesgo corresponde a cada tamaño de empresa (por ejemplo, que
Micro pase de riesgo Bajo a Medio) y que eso defina las horas. Se analizó también configurarlo
por industria × tamaño, pero el cliente prefirió **una tabla por tamaño** (sin sumar la
dimensión industria) y **un botón para recalcular las cotizaciones en borrador**.

### Efecto en las horas
Las horas de Auditoría se buscan por **riesgo × industria**. Si Micro pasa a Medio, una empresa
Micro cotiza con las horas de riesgo Medio de su industria (en la Tabla #3, las de Pequeña).
Ejemplo verificado en la UI, Bancos y seguros Micro: Auditoría pasa de 166,5 h (100/50/15/1,5)
a 250 h (150/75/22,5/2,5). Las horas de un riesgo que ningún tamaño usa siguen cargadas y se
recuperan si se vuelve atrás.

### Implementación
- Se quitó la restricción uno a uno de Auditoría. Ahora:
  - `quoter.professional.area._check_size_levels_complete`: los 4 tamaños con nivel asignado.
  - `quoter.area.size.level._check_level_in_area`: el nivel tiene que ser uno de los del área.
- Menú **Configuración → Riesgo por tamaño de empresa** (`action_quoter_area_size_level`): lista
  editable agrupada por área, sin alta ni baja de filas, con el nivel filtrado a los niveles del área.
- Botón **"Recalcular cotizaciones en borrador"**:
  - En el encabezado de esa lista (aparece al seleccionar filas) y en el formulario del área,
    junto a la tabla.
  - Visible solo para `quoter.group_quoter_admin`.
  - `quoter.professional.area.action_quoter_recompute_draft_levels()` recalcula solo bloques
    `draft` de cotizaciones en `en_preparacion` (estado de venta `draft`/`sent`). No toca las
    que están en aprobación o enviadas.
  - Deja en el chatter "Nivel recalculado por cambio de configuración: X → Y" y muestra una
    notificación con cuántas cotizaciones revisó y cuántas cambiaron.
- Permisos: solo el perfil Cotizador puede editar el contenido en "En preparación". Para que un
  administrador del cotizador sin ese perfil pueda recalcular, se agregó el contexto
  `quoter_recompute_derived_levels`. Lo reconoce
  `sale.order._quoter_workflow_derived_recompute_allowed()`, usado en
  `_quoter_workflow_can_edit_content()` y en `_quoter_validate_workflow_write_access()`, y
  **solo** habilita cotizaciones en preparación.
  - No se usó `quoter_workflow_transition`: con ese contexto `sale.order.write` rechaza todo lo
    que no sea un cambio de estado, y el recálculo escribe en el pedido.
- Aviso en el formulario del área: "El nivel define las horas que se cotizan…".
- Sin migración de datos: el mapeo vigente queda igual (Micro Bajo, Pequeña Medio, Mediana Alto,
  Grande Muy alto en Auditoría; Tabla #4 en Tax).

### Pruebas por UI (Q00037, Auditoría, Bancos y seguros 100 M)
| Paso | Resultado |
|---|---|
| Configurar Micro → Medio (Pequeña también es Medio) | Se guarda sin error |
| Abrir la cotización sin recalcular | Sigue Micro / Bajo, 166,5 h |
| Seleccionar las filas de Auditoría y "Recalcular cotizaciones en borrador" | "Cotizaciones en preparación revisadas: 6. Con cambio de nivel: 1." |
| Abrir la cotización | Micro / Medio, 250 h; chatter "Bajo → Medio" |
| Volver Micro → Bajo y recalcular | Micro / Bajo, 166,5 h (stg quedó como antes) |

---

## 11. Cambio posterior: niveles "Apto para convenio" (2026-10-16, versión 15.0.6.8.2)

### Pedido
Marcar en cada nivel de complejidad si puede usarse en los convenios colectivos. Solo los niveles
marcados se pueden elegir al cargar un convenio. Al terminar las pruebas, dejar marcados los que
ya usan los convenios.

### Implementación (`models/quoter_complexity_source.py`)
- `quoter.complexity.level.labor_agreement_ok` ("Apto para convenio", False por defecto).
- `quoter.labor.agreement.complexity_level_id` filtra a `[('labor_agreement_ok', '=', True)]`
  y tiene una restricción con el mismo criterio (por si se carga por importación o código).
- Un nivel usado por convenios (incluidos los archivados) no puede dejar de ser apto.
- Vistas: interruptor en la lista y casilla en el formulario de niveles; columna "Áreas" en la
  lista para distinguir los Bajo/Medio/Alto de TAX/PayRoll de los de Auditoría.
- Datos: Bajo/Medio/Alto compartidos vienen marcados como aptos en
  `data/quoter_complexity_level_data.xml`; en bases existentes los marca la pre-migración 6.9.0.

### Estado en stg
Aptos: Bajo, Medio y Alto de TAX/PayRoll (ids 2, 3 y 4; los usan los 128 convenios). No aptos:
BPO, Finanzas y los 4 niveles de Auditoría.

### Pruebas por UI
| Caso | Resultado |
|---|---|
| Lista de niveles | Interruptor visible; aptos solo Bajo/Medio/Alto de TAX y PayRoll |
| Nuevo convenio: opciones del nivel | Solo "Bajo", "Medio", "Alto" (los aptos); no aparecen los de Auditoría |
| Desmarcar "Medio" (TAX/PayRoll) | Error: "El nivel «Medio» está asignado a 50 convenios: no puede dejar de ser apto para convenio." |
| Marcar y desmarcar "Finanzas" (sin convenios) | Sin errores |

### Producción
Ver sección 12.

---

## 12. Configuración como archivos de datos (2026-10-16, versión 15.0.6.9.0)

### Pedido
Dejar en archivos de datos `noupdate` todos los registros de configuración que necesita el
requerimiento (convenios, niveles de riesgo, productos de Auditoría, etc.), en lugar de crearlos
desde migraciones.

### Cómo quedó
| Archivo (`noupdate="1"`) | Registros | Carga |
|---|---|---|
| `data/quoter_complexity_level_data.xml` | `quoter_complexity_level_{low,medium,high}` (compartidos, aptos para convenio) y `quoter_complexity_level_audit_{low,medium,high,very_high}` | Manifest |
| `data/quoter_industry_data.xml` | `quoter_area_branch_industry_*` (7), `quoter_industry_*` (7), `quoter_sicypyme_2026_*` (7) | Manifest |
| `data/quoter_labor_agreement_data.xml` | `quoter_labor_agreement_<slug del nombre>` (128) | Manifest |
| `data/quoter_area_complexity_data.xml` | `quoter_area_size_level_{tax,auditoria}_{micro,small,medium,large}` (8) y `quoter_service_line_audit_{audit,balance,axi}` (3) | Post-migración 6.9.0 |

- El último archivo no está en el manifest porque referencia áreas (`quoter_area_tax`,
  `quoter_area_auditoria`) y secciones (`quoter_line_separator_tag_default/additional`) que se
  crean desde la UI. La pre-migración les asigna esos xmlid.
- Las horas AE de la Tabla #3 no pueden ser datos XML (las filas de horas se generan al crear el
  producto y no tienen xmlid). Quedan en `AE_HOURS` de la post-migración.
- Con `noupdate`, una actualización crea lo que falta y nunca pisa lo existente: los cambios que
  se hagan después desde la UI (riesgo por tamaño, niveles de convenios, etc.) se conservan.

### Pruebas
- **stg** (ya configurada, 6.8.2 → 6.9.0): no se creó ni cambió ningún registro (conteos
  idénticos) y se asignaron 147 xmlid (3 áreas, 3 niveles, 2 secciones, 128 convenios, 8 mapeos,
  3 productos). Pasan los 19 tests.
- **Instalación desde cero sobre una copia de producción** (`pgk-prod_pre-neutralize_20260804.dump`,
  restaurada en una base temporal con crons y correo desactivados, y eliminada después): se
  instala sin errores y crea 7 niveles (3 aptos), 128 convenios sobre Bajo/Medio/Alto,
  7 industrias, 7 topes y las ramas.

### Producción
El dump `pgk-prod_pre-neutralize_20260804.dump` no tiene `quoter`, pero el equipo confirmó que
**producción hoy sí lo tiene instalado**: el pase es una actualización a `15.0.6.9.0`.

### Simulación del pase a producción (2026-10-16)
1. Se restauró el backup de stg previo a Auditoría (`db_15:/tmp/pgk-stg-pre-audit-20261015.dump`)
   en una base temporal, con crons y correo desactivados.
2. Se la llevó al estado previo al requerimiento: sin convenios, industrias, topes ni mapeos;
   áreas en `manual`; niveles con secuencia 10; Auditoría con sus 4 productos de prueba y
   ramas Pyme/Gran; módulo en `15.0.6.6.26`.
3. Se actualizó a `15.0.6.9.0`.

Resultado: los conteos y la configuración de las áreas quedaron idénticos a stg; las 336 horas
de Auditoría son iguales celda por celda; los 4 productos viejos quedaron archivados; los 128
convenios tienen xmlid y la distribución 42 / 50 / 36. Pasan los 19 tests. La base se eliminó.

La primera corrida encontró un error real: las horas AE no se cargaban porque la matriz A de
un producto nuevo arranca en 1 h y la migración lo tomaba como "ya cargado". Se corrigió
(paso 4 de la post-migración).
