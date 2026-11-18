=======================================
Informe Gestión de Proyectos CALYX
=======================================

Proyectos > Informes > Gestión de Proyectos CALYX. Abre un asistente y genera
un XLSX o CSV con una fila por proyecto de todas las compañías permitidas para
el usuario.

Reutiliza el informe PGK (``project_management_report_pgk``): mismo asistente,
filtros, encabezado, Costos y Dist. Gtos. de la consolidación y generación del
archivo. Este módulo solo define las 35 columnas y agrega las propias de
Tecnología.

Columnas
========
35 columnas. Las de Tecnología salen de la plantilla de exportación
"Contratos_Calyx" (``ir.exports``):

* Área: ``x_area`` (campo de Studio "Area", Many2one a
  ``account.analytic.group``; se exporta el nombre completo). No se usa
  ``service_area_id`` ("Área de servicio"): tiene menos datos y se usa para
  habilitar los campos extra de la ficha (grupo "Odoo"), por eso hay proyectos
  de RPA o Software Factory con área de servicio "Odoo".
* PM: ``x_PM`` (Studio). ``project_manager`` casi no tiene datos.
* Fecha go live original / real: ``expected_go_live_date`` /
  ``real_go_live_date`` (``project_contrated_hours``), de las que se calcula
  Desviación de fecha de entrega. No se usan ``x_date_go_live*`` (Studio).

Si los campos de Studio no existen en la base, las columnas quedan vacías.

Rango de fechas
===============
Igual que el informe PGK para Facturación realizada, Horas facturadas, Tiempo
total del parte de horas, Costos y Dist. Gtos. Con esos valores se recalculan,
con las fórmulas de ``project_contrated_hours``:

* Avance teórico = Tiempo total del parte de horas / Horas contratadas.
* Desvío de avance = Avance real − Avance teórico (0 si no hay avance teórico).
* Desvío de facturación - Calyx = Facturación realizada − Importe total
  proyecto × Avance real.
* % Costos sobre ingresos, Realización, Costos Totales y Margen Bruto.

Avance real, Desvío de horas - Calyx, fechas de go live y Desviación de fecha
de entrega son siempre el valor del proyecto.

Seguridad
=========
Grupo "Informe Gestión de Proyectos CALYX", incluido en Proyecto /
Administrador.
