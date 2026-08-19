==================================
Quoter — Cotizador de servicios PGK
==================================

.. |badge_license| image:: https://img.shields.io/badge/licence-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl-3.0-standalone.html

:Versión: ``15.0.6.6.24``
:Estado: Beta
:Licencia: AGPL-3
:Autor: Calyx Servicios S.A.

Cotizador de servicios profesionales para Odoo 15 Community. Extiende
``sale.order`` con un flujo de cotización propio: la orden se divide en
**bloques por área profesional** (Auditoría, TAX, Payroll, BPO, Finanzas…),
cada área calcula **horas por rol** con su propia política de cálculo, las
horas se valorizan contra una lista de precios por rol y el conjunto pasa por
un **circuito de aprobación** (Cotizador → Aprobador → Contratos).

.. contents:: Contenido
   :local:
   :depth: 2


Resumen funcional
=================

Un usuario del perfil *Cotizador* crea una cotización (``is_quotation = True``),
elige el cliente, responde las preguntas estratégicas y selecciona una o varias
**áreas profesionales**. Por cada área seleccionada se crea un **bloque de
cotización** (``quoter.sale.order.area``) con:

* Gerente responsable del área.
* Nivel de complejidad / riesgo y, opcionalmente, rama (tipo de empresa).
* Productos del área, cada uno con horas desglosadas por rol.
* Descuento y recargo porcentual propios del bloque.
* Subtotales y un resumen HTML embebido.

Las horas de cada línea salen de la **configuración del área** (matrices,
fórmulas o tablas en cadena) y se valorizan con los productos técnicos
*Tarifa/h* generados por área × rol. El total de la orden se arma sumando los
bloques, y el PDF interno consolida todo en una matriz por área.

.. note::

   Este README describe el módulo tal como está hoy. Las versiones iniciales
   giraban en torno a ``quoter.service.config`` / ``quoter.service.product.line``;
   esos modelos ya **no se cargan** (ver `Código legado`_).


Conceptos clave
===============

Área profesional (``quoter.professional.area``)
    Unidad de configuración. Define el modo de cálculo de horas, los roles, los
    niveles de complejidad, las ramas, la lista de precios, las secciones y los
    productos cotizables. Su ``sequence`` determina el orden de las pestañas en
    la cotización. El campo ``group_id`` restringe la visibilidad del área (y de
    sus productos) a un grupo de seguridad.

Rol / categoría de recursos (``quoter.area.complexity.range``)
    Columnas de horas del área (Asistente, Senior, Gerente, Socio…). Son
    registros reutilizables entre áreas; el orden lo fija ``sequence``. Cada rol
    de cada área genera automáticamente un producto técnico *Tarifa/h*.

Nivel de complejidad (``quoter.complexity.level``)
    Bajo / Medio / Alto (o riesgo, en Auditoría). Selecciona qué fila de la
    matriz de horas se aplica al bloque. Un área puede renombrar la etiqueta con
    ``complexity_level_custom_label``.

Rama (``quoter.area.branch``)
    Segmentación adicional (p. ej. tipo de empresa) que multiplica las filas de
    las matrices. Si el área no define ramas se usa la rama técnica
    ``quoter.quoter_area_branch_unique`` («Rama única»).

Sección (``quoter.line.separator.tag``)
    Agrupador visual y de color para las líneas del pedido. Los flags
    ``is_employee_subscription`` e ``is_adp`` alimentan el desglose BPA.

Línea de producto del área (``quoter.service.line``)
    Un producto cotizable dentro de un área. Al crearse genera (o enlaza) el
    ``product.template`` correspondiente. Flags relevantes:
    ``is_default_product`` (carga automática), ``manual_load`` (horas por rol
    editables en la cotización), ``manual_total_load`` (total editable, se
    reparte proporcionalmente), ``unify_value`` (horas por rama, sin filas en
    A/B), ``shared_b_calc`` («productos varios»: una sola fila compartida en
    tabla B), ``subtract_in_bpa``.

Bloque de cotización (``quoter.sale.order.area``)
    Instancia de un área dentro de una ``sale.order``. Es el contenedor que ve
    el usuario en la pestaña «Cotización por área».


Modos de cálculo de horas
=========================

El campo ``hour_matrix_mode`` del área define cómo se obtienen las horas por rol
de cada línea de la cotización.

``regular``
    Matriz directa: horas finales por producto × nivel (× rama). Es la más
    simple: lo que se carga en la tabla resultado es lo que se copia a la línea.

``regular_manual``
    Cotización línea a línea: horas y precio unitario cargados a mano por el
    usuario (perfil pensado para Finanzas). Restringido a **un solo nivel de
    complejidad** por área (``_check_regular_manual_single_level``).

``combined``
    Dos tablas encadenadas:

    * **Tabla A** (``quoter.product.level.range.matrix.a``): horas base por rol.
      Formatos: ``normal`` (por rol), ``compact`` (un valor por nivel/rama
      replicado) y ``global`` (un único valor).
    * **Tabla B** (``quoter.product.level.range.matrix.b``): factor por rol.
      ``table_b_kind`` = ``percent`` → ``final = A × (B ÷ 100)``;
      ``multiplier`` → ``final = A × B``; ``formula`` → ``final = A`` (reservado).
    * ``table_b_percent_basis = previous_role`` activa el modo **cascada**: el
      primer rol usa su tabla A y cada rol siguiente aplica su porcentaje sobre
      las horas ya calculadas del rol anterior (mismo nivel y rama).
    * ``table_b_percent_mode`` = ``exact`` fuerza que los porcentajes sumen 100
      en escenarios unificados; ``variable`` lo deja libre.
    * La **salida** se materializa en ``quoter.product.level.range.output``.

    Además hay una capa de reglas para no cargar B celda por celda:
    ``quoter.area.matrix.b.role.rule`` (regla base por rol),
    ``quoter.area.matrix.b.branch.exception`` y
    ``quoter.area.matrix.b.level.exception`` (excepciones por rama o nivel).

``formula``
    Horas por **volumen** (área BPO). Cada producto tiene una
    ``quoter.formula.product.config`` y, por rol, una
    ``quoter.formula.product.config.range`` con plantilla y parámetros
    (``quoter.formula.product.config.param``):

    * ``linear`` → ``horas = (VOLUMEN × minutos_unidad) / 60``
    * ``threshold`` → ``SI(VOLUMEN < umbral; horas_piso_bajo;
      horas_piso + ((VOLUMEN − umbral) × minutos_excedente) / 60)``

    ``tipo_calculo = fija`` ignora la fórmula y usa ``horas_fijas`` por rol.
    El usuario carga el volumen en la línea de la cotización
    (``quoter_formula_volume``).

``formula_chain``
    Tablas por **cantidad de empleados** (``quoter.chain.table``), cada una con
    un tramo ``people_min``–``people_max`` y un ``delta``. Cada celda
    producto × rol (``quoter.chain.table.line``) es ``fixed`` o ``formula``:

    ``valor = valor_de_la_tabla_anterior + nº/delta × (empleados − umbral)``

    La primera tabla admite solo valores fijos; las siguientes heredan la
    configuración de la anterior. Sobre el resultado se aplica el aumento
    porcentual por nivel de complejidad
    (``quoter.area.chain.complexity.increase``).

En todos los modos, ``output_hours_minimum`` del área actúa como **piso**: una
hora calculada por debajo de ese valor se eleva al mínimo (0 = sin ajuste).
La lógica de validación de horas vive centralizada en el modelo abstracto
``quoter.hours.policy``.


Cálculo del precio
==================

El precio no sale del producto de servicio, sino de productos técnicos
generados automáticamente:

1. Al guardar un área, ``_sync_range_rate_products`` crea (o archiva) un
   ``product.template`` por cada rol del área, con
   ``is_quoter_range_rate_product = True``, nombre ``«Área · Rol · Tarifa/h»``,
   tipo servicio y UoM Hora.
2. Esos productos reciben la tarifa horaria mediante las reglas normales de la
   lista de precios (``area.pricelist_id`` y, en su defecto,
   ``order.pricelist_id``).
3. El precio unitario de una línea de cotización es
   ``Σ (horas_del_rol × tarifa_hora_del_rol)``, con ``product_uom_qty = 1``
   (``_quoter_compute_unit_price_from_ranges``).

Los descuentos y recargos del bloque se aplican como factor sobre las tarifas:
``factor = 1 − descuento% + recargo%``. Su efecto neto se materializa en una
línea totalizadora del pedido con el producto técnico
``quoter.product_quoter_area_discount_sum``.

Las plantillas creadas por el cotizador reciben automáticamente un impuesto de
venta al 0 % (``quoter_apply_default_sale_taxes``), preferentemente uno cuyo
nombre contenga «no gravado» / «exento».


Flujo de aprobación
===================

``quoter_workflow_state`` en ``sale.order``:

.. code-block:: text

   en_preparacion ──(Cotizador)──▶ en_aprobacion ──(Aprobador)──▶ aprobado_interno
         ▲                              │                              │
         │                          (rechazo)                    (Contratos)
         │                              │                              ▼
         └───────────────────────── rechazado_cliente ◀──(rechazo)── enviado_cliente
                                                                       │
                                                                (Contratos)
                                                                       ▼
                                                                aprobado_cliente

Permisos por estado (``_compute_quoter_workflow_permissions`` y
``_quoter_validate_workflow_write_access``):

============================ ======================================================
Perfil                       Qué puede hacer
============================ ======================================================
Quoter - Cotizador           Crear y editar contenido **solo** en «En preparación»;
                             enviar a aprobación; retomar tras rechazo de cliente;
                             confirmar el pedido.
Quoter - Aprobador           En «En aprobación» / «Aprobado interno»: editar
                             únicamente ``global_discount_amount`` y
                             ``global_surcharge_amount`` de los bloques. Aprobar
                             internamente o rechazar.
Quoter - Contratos           Solo transiciones: enviar al cliente, registrar
                             aprobación o rechazo del cliente.
============================ ======================================================

``enviado_cliente``, ``aprobado_cliente`` y ``rechazado_cliente`` son **estados
terminales**: ningún perfil puede modificar el registro salvo por las
transiciones del flujo. El rechazo exige motivo y se registra en el chatter
(``quoter.rejection.wizard``).

Detalle de implementación: para el Aprobador restringido, el ``write`` se
**sanea** en lugar de fallar (``_quoter_workflow_sanitize_restricted_vals``),
porque el cliente web arrastra campos ocultos y ecos de líneas que harían
saltar el guard sin que el usuario haya tocado nada.


Seguridad
=========

Grupos definidos en ``security/quoter_groups.xml`` y
``security/quoter_admin_groups.xml``:

===================================== ==========================================
Grupo                                 Uso
===================================== ==========================================
``group_quoter_access``               Grupo base; da el menú y el icono de la
                                      app. Todos los demás lo implican.
``group_quoter_admin``                Configuración maestra: áreas, roles,
                                      niveles, secciones, ramas, tarifas.
``group_quoter_manager``              Puede asignarse como gerente responsable.
``group_quoter_partner``              Puede asignarse como socio.
``group_quoter_cotizador``            Perfil del flujo: prepara cotizaciones.
``group_quoter_aprobador``            Perfil del flujo: aprueba / ajusta %.
``group_quoter_contratos``            Perfil del flujo: envío y cierre.
``group_quoter_tax``                  Visibilidad del área TAX.
``group_quoter_auditoria``            Visibilidad del área Auditoría.
``group_quoter_formula``              Visibilidad del área BPO (modo fórmula).
``group_quoter_payroll``              Visibilidad del área Payroll.
``group_quoter_finanzas``             Visibilidad del área Finanzas
                                      (modo regular manual).
===================================== ==========================================

Reglas de registro:

* Cualquier rol Quoter ve **todas** las cotizaciones profesionales
  (``quoter_rule_sale_order_all_quotations``), en OR con la regla estándar de
  Ventas de «solo mis pedidos».
* Las reglas sobre áreas / líneas / niveles son deliberadamente permisivas
  (``[(1,'=',1)]``): la visibilidad por área se resuelve **en las vistas**
  (pestañas y ``name_search``), porque filtrar por ``group_id`` en ``ir.rule``
  impedía abrir pedidos que referencian áreas de otros equipos.
* ``group_quoter_admin`` tiene acceso completo a ``product.pricelist`` y
  ``product.pricelist.item`` para gestionar tarifas desde el menú Cotizador.

.. warning::

   El grupo **Quoter - Director** está comentado a pedido, pero se conserva la
   definición. Para reactivarlo hay que descomentarlo en
   ``security/quoter_groups.xml`` y volver a agregar sus referencias en
   ``security/quoter_sale_order_access_rules.xml``, ``views/quoter_menu.xml`` y
   ``views/quoter_sale_order_workflow_views.xml``. No se puede comentar con
   ``#`` dentro de un ``eval``: XML normaliza los saltos de línea del atributo y
   el comentario anularía el resto de la expresión.


Líneas de ajuste
================

Sobre cualquier línea de producto se puede crear una **línea de ajuste**
(``quoter_is_adjustment_line``) que suma o resta horas por rol sin tocar la
línea original:

* Requiere observación obligatoria (``quoter.adjustment.note.wizard``).
* Se inserta inmediatamente debajo de su línea padre: la padre se fuerza a
  ``sequence`` impar y el ajuste toma ``sequence + 1``.
* Admite horas negativas, pero se valida que ``base + ajuste ≥ 0`` por rol
  (``_quoter_validate_adjustment_hours_balance``).
* Se contabiliza aparte en los subtotales y en el PDF (fila «Ajuste»).


Resumen general y desglose BPA
==============================

La orden calcula cuatro importes (``_quoter_order_summary_amounts``):

* **Anual (A)** = suma de bloques de áreas TAX + Auditoría.
* **Mensual (B)** = suma de bloques de áreas BPO + Payroll + Finanzas.
* **Proporción mensual** = A ÷ 12.
* **Cuota mensual total** = B + (A ÷ 12).

Si un área no está presente en el pedido, su aporte es 0. Cada bloque genera
además dos resúmenes HTML embebidos: ``area_summary_html`` (horas y tarifas por
rol, con y sin ajuste) y ``bpa_summary_html`` (abono por empleado y ADP, según
los flags de las secciones).


Informe PDF
===========

``reports/quoter_quotation_report.xml`` define el informe interno
**«Cotización interna PGK»** (``quoter.report_quoter_quotation_document``) con
formato de papel propio (``paperformat_quoter_internal``). Incluye:

* Matriz por área (hasta 5 columnas): gerente a cargo, nivel de
  complejidad / riesgo, cantidad de empleados y tipo de empresa según
  corresponda al modo de cada área.
* Preguntas estratégicas con sus adjuntos.
* Presupuesto por bloque: horas por rol, tarifas, valores base y valores
  ajustados por descuento/recargo.
* Recuadro final Anual / Mensual (mismos números que la pestaña «Resumen
  general»).

Dos detalles de infraestructura del informe (``models/ir_actions_report.py``):
se fuerza ``--encoding utf-8`` en wkhtmltopdf y se inyecta el ``<meta charset>``
en el HTML, porque de lo contrario wkhtmltopdf asume Latin-1 y rompe las tildes.

El logo y membrete del PDF salen de la compañía configurada en
``quoter.report_company_id``, no necesariamente de la compañía del pedido.


Instalación
===========

1. Copiar ``quoter`` en el directorio de addons (ya está en el repositorio
   ``grupopgk``).
2. Actualizar la lista de aplicaciones.
3. Instalar **Quoter — Service Configuration**.

Dependencias
------------

``base``, ``web``, ``sale``, ``sale_management``, ``product``, ``stock``,
``sale_order_type`` y ``report_custom``.

.. note::

   ``sale_order_type`` está declarado **después** a propósito: el ``create`` del
   cotizador debe correr antes que el de OCA para dejar ``name = Q…`` antes de
   ``next_by_id`` y no consumir en vano la secuencia del tipo de pedido.


Configuración inicial
=====================

Todo el menú **Cotizador → Configuración** requiere ``group_quoter_admin``.

1. **Ajustes** (``Cotizador → Configuración → Ajustes``): plazo de pago, equipo
   de ventas y compañía del informe PDF por defecto.
2. **Categorías de recursos**: crear los roles (Asistente, Senior, Gerente,
   Socio…) con su secuencia.
3. **Niveles de complejidad**: Bajo / Medio / Alto, con secuencia creciente y
   color.
4. **Ramas** (opcional): solo si el área segmenta por tipo de empresa.
5. **Secciones de cotizador** (opcional): agrupadores de líneas; marcar
   «abono por empleado» / «ADP» si alimentan el desglose BPA.
6. **Áreas profesionales**: por cada área, definir secuencia (orden de
   pestañas), grupo de visibilidad, lista de precios, categoría de productos,
   roles, niveles, ramas y **tipo de tabla de horas**.
7. En la pestaña **Productos** del área, cargar los productos cotizables
   (propios o genéricos reutilizables).
8. En **Vista de matrices**, abrir el editor de tabla, cargar horas / fórmulas y
   volver a cerrarlo. Al cerrar se recalcula y se bloquea la configuración.
9. Cargar las tarifas horarias en la lista de precios del área, sobre los
   productos ``«Área · Rol · Tarifa/h»``.
10. Marcar el área como **Cerrado (en cotizaciones)** para habilitarla en el
    selector de áreas de las cotizaciones.

Bloqueo de configuración
------------------------

El área tiene dos candados independientes:

* ``quoter_config_edit_mode`` — «Abrir / Cerrar editor de tabla». Controla si se
  pueden tocar la política de matrices, las líneas y la matriz de horas.
* ``cerrado`` — habilita el área para elegirla en cotizaciones. Con el área
  cerrada, ``write`` rechaza cambios de ``hour_matrix_mode`` y de niveles de
  complejidad.


Uso
===

1. **Cotizador → Cotizaciones → Nuevo**. La secuencia ``quoter.quotation``
   asigna un número ``Q00001``.
2. Completar cliente, gerente responsable, socio asignado y la pestaña
   **Información estratégica** (competidores, presupuesto, pago actual y
   observaciones; los cuatro campos son obligatorios).
3. Seleccionar las **áreas** de la cotización. Cada área agrega su pestaña en
   **Cotización por área**.
4. En cada bloque: elegir nivel de complejidad (y rama / cantidad de empleados
   según el modo), asignar el gerente del área y cargar productos.

   * **Cargar predeterminados** incorpora los productos marcados como tales.
   * **Agregar múltiples líneas** abre el asistente de carga masiva (si el área
     tiene ``bulk_line_load``).
   * Las horas se completan solas desde la configuración del área; solo son
     editables en los productos marcados ``manual_load`` /
     ``manual_total_load``, en modo ``regular_manual`` y en las líneas de
     ajuste.
5. Revisar subtotales del bloque y el **Resumen general** de la orden.
6. **Enviar a aprobación** → el Aprobador ajusta descuento/recargo y aprueba →
   Contratos envía al cliente y registra la respuesta.
7. Imprimir **Cotización interna PGK** o confirmar el pedido.


Interfaz (assets)
=================

El módulo depende bastante de JavaScript del framework legacy de Odoo 15
(``odoo.define``, ``FormRenderer`` / ``ListRenderer`` / ``FormController``):

============================================ =================================================
Archivo                                      Función
============================================ =================================================
``quoter_area_block_embed.js``               Corazón de la UI: embebe el formulario del bloque
                                             de área dentro del pedido, con sus líneas,
                                             botones y diálogos.
``quoter_area_hours_matrix.js``              Editor de las matrices A / B / salida en el área.
``quoter_formula_matrix.js``                 Editor y vista previa de fórmulas por volumen.
``quoter_chain_matrix.js``                   Editor de las tablas en cadena por empleados.
``quoter_bulk_add_lines.js``                 Asistente de carga masiva de líneas.
``quoter_range_columns.js``                  Columnas de horas por rol en las líneas del pedido.
``quoter_separator_styles.js``               Color y estilo de los separadores de sección.
``quoter_tab_labels.js``                     Etiquetas dinámicas de las pestañas por área.
``quoter_preserve_active_record.js``         Conserva el registro activo al navegar/recargar.
``quoter_matrix.scss``                       Estilos de todas las matrices.
``tax_totals.xml``                           Plantilla QWeb del bloque de totales.
============================================ =================================================

Varios de estos módulos tienen un flag de contingencia al inicio
(``QUOTER_DISABLE_*``) para desactivar el parche sin desinstalar, útil al
diagnosticar errores de bootstrap del cliente web.


Datos incluidos
===============

* ``sequence_data.xml`` — secuencia ``quoter.quotation`` (prefijo ``Q``,
  padding 5, sin compañía).
* ``quoter_branch_data.xml`` — rama técnica «Rama única» (``selectable=False``).
* ``quoter_product_category_data.xml`` — categoría «General (Cotizador)» para
  los productos genéricos.
* ``quoter_product_attribute.xml`` — atributo «Nivel cotización»
  (``create_variant = always``), usado para las variantes por nivel.
* ``pricelist_data.xml`` — categoría «Descuento/Recargo» y producto técnico
  «Descuento/Recargo agrupado (cotizador)».
* ``quoter_formula_view_cleanup.xml`` — borra vistas heredadas de la etapa BPO
  cuyos nombres quedaron en BD.

El módulo **no** trae productos de servicio ni listas de precios de ejemplo:
las tarifas se cargan por instalación.


Migraciones
===========

``migrations/`` contiene scripts *post-migration* que reparan estructuras
creadas por versiones anteriores:

* ``15.0.6.3.2`` y ``15.0.6.3.3`` — eliminan las restricciones UNIQUE previas de
  ``quoter_chain_table_line`` y regeneran las celdas con el esquema
  producto × rol.
* ``15.0.6.3.4`` — repara bases donde las migraciones anteriores quedaron a
  medias (renombres de columnas defensivos).
* ``15.0.6.3.6`` — histórica, sin efecto (``pass``).


Tests
=====

``tests/test_quoter_workflow.py`` cubre el guard del flujo de aprobación:
escritura permitida en «En preparación», bloqueo fuera de ese estado y
transición a «En aprobación».

.. code-block:: bash

   odoo -d <base> -u quoter --test-enable --test-tags /quoter

La cobertura actual es acotada: los modos de cálculo de horas, las matrices y el
cálculo de precios **no** tienen tests automatizados.


Notas técnicas
==============

* **Chatter**: casi todo cambio relevante (campos de cabecera, alta/baja de
  productos, cambios de bloque, transiciones) se registra en el chatter con
  formato «etiqueta: viejo → nuevo». Los helpers están en
  ``models/quoter_chatter.py``; el contexto ``quoter_skip_chatter_log`` lo
  silencia.
* **Contextos de control** usados a lo largo del módulo:
  ``quoter_workflow_transition`` (write limitado a campos de transición),
  ``quoter_confirm_bypass_workflow_lock`` (confirmación del pedido en estados
  terminales), ``quoter_allow_zero_hours`` (salta la validación estricta de
  horas, p. ej. al crear líneas de ajuste).
* **Cantidad fija en 1**: las líneas de cotización siempre llevan
  ``product_uom_qty = 1``; la magnitud está en las horas por rol, no en la
  cantidad.
* **Saneado de comandos**: ``sale.order`` filtra y sanea los comandos O2M de
  ``order_line`` y ``quoter_area_block_ids`` en ``onchange``, ``read`` y
  ``write`` para evitar que los ecos del cliente web pisen datos ya calculados.
* **Persistencia por RPC**: el editor embebido guarda horas, volúmenes y
  ediciones manuales con métodos ``quoter_persist_*_batch`` en
  ``sale.order.line``, sin esperar al guardado del formulario.
* **Validación de horas** centralizada en ``quoter.hours.policy``: horas por rol
  no negativas, suma de la línea no negativa, factores de tabla B estrictamente
  positivos y piso de horas de salida.


Estructura de modelos
=====================

============================================== ==============================================
Modelo                                         Rol
============================================== ==============================================
``quoter.professional.area``                   Área / sector profesional (configuración).
``quoter.area.complexity.range``               Rol / categoría de recursos.
``quoter.complexity.level``                    Nivel de complejidad o riesgo.
``quoter.area.branch``                         Rama (segmentación de matrices).
``quoter.line.separator.tag``                  Sección de cotizador.
``quoter.service.line``                        Producto cotizable dentro de un área.
``quoter.service.line.range.hour``             Horas por rol de un producto del área.
``quoter.service.line.unify.branch.hour``      Horas por rama (productos «unifica valor»).
``quoter.product.level.range``                 Fila producto × nivel × rama.
``quoter.product.level.range.matrix.a``        Tabla A: horas base por rol.
``quoter.product.level.range.matrix.b``        Tabla B: factor por rol.
``quoter.product.level.range.output``          Tabla resultado: horas finales por rol.
``quoter.area.shared.matrix.b``                Factor B compartido («productos varios»).
``quoter.area.matrix.b.role.rule``             Tabla B: regla base por rol.
``quoter.area.matrix.b.branch.exception``      Tabla B: excepción por rama.
``quoter.area.matrix.b.level.exception``       Tabla B: excepción por nivel.
``quoter.formula.product.config``              Configuración por volumen de un producto.
``quoter.formula.product.config.range``        Fórmula u horas fijas por rol.
``quoter.formula.product.config.param``        Parámetro editable de la fórmula.
``quoter.chain.table``                         Tramo por cantidad de empleados.
``quoter.chain.table.line``                    Celda producto × rol de un tramo.
``quoter.chain.table.line.param``              Parámetros ``nº`` y umbral de la celda.
``quoter.area.chain.complexity.increase``      Aumento % por nivel en modo cadena.
``quoter.sale.order.area``                     Bloque de cotización por área en el pedido.
``sale.order.line.range.hour``                 Horas por rol de una línea del pedido.
``quoter.hours.policy``                        Abstracto: validaciones de horas.
``quoter.rejection.wizard``                    Rechazo con motivo.
``quoter.adjustment.note.wizard``              Observación de línea de ajuste.
``quoter.bulk.add.lines.wizard`` (+ ``.line``) Carga masiva de líneas.
``quoter.generic.product.wizard``              Alta de producto genérico.
``quoter.add.generic.to.area.wizard``          Alta de genérico dentro de un área.
============================================== ==============================================

Modelos extendidos: ``sale.order`` (cotización, bloques, flujo, resúmenes,
informe), ``sale.order.line`` (horas por rol, ajustes, fórmula, precio),
``product.template`` / ``product.product`` (productos del cotizador, genéricos y
tarifa/h), ``product.attribute.value`` (enlace a nivel de complejidad),
``ir.actions.report`` (UTF-8 en PDF) y ``res.config.settings``.


Código legado
=============

Se conservan en el árbol pero **no se cargan**:

* ``models/quoter_service_config.py`` y ``models/quoter_service_product_line.py``
  — comentados en ``models/__init__.py``. Eran los modelos de la primera etapa
  (un servicio con horas AE/SR/MG/Partner por línea); su función la cumplen hoy
  ``quoter.professional.area`` + ``quoter.service.line`` + las matrices.
* ``views/quoter_service_config_views.xml`` — no figura en el ``__manifest__``.

También hay campos marcados ``(legacy)`` / ``(obsoleto)`` que se mantienen para
compatibilidad de datos y migración, y cuyos valores ya no intervienen en los
cálculos: ``quoter.formula.product.config.valor_minimo_volumen``,
``horas_si_menor``, ``horas_base_si_mayor``, ``minutos_por_unidad_excedente``,
``minutos_*`` / ``horas_*``; ``quoter.formula.product.config.range.minutos_por_unidad``;
``quoter.chain.table.line.multiplier``; y el alias
``quoter.area.matrix.b.exception``.


Problemas conocidos / hoja de ruta
==================================

* ``table_b_kind = formula`` está declarado pero aún se comporta como
  ``final = A``.
* Cobertura de tests limitada al flujo de aprobación.
* El front-end usa el framework JS legacy de Odoo 15; una migración a versiones
  posteriores obliga a reescribir los assets sobre OWL.


Créditos
========

Desarrollado por **Calyx Servicios S.A.** — https://odoo.calyx-cloud.com.ar/

Mantenimiento
-------------

Agregue su usuario en ``maintainers`` dentro de ``__manifest__.py``
(actualmente contiene el valor de ejemplo ``YourName``).

Licencia
--------

AGPL-3.0 o posterior — https://www.gnu.org/licenses/agpl-3.0.html
