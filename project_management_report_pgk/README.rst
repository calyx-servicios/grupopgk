=====================================
Informe Gestión de Proyectos PGK
=====================================

Proyectos > Informes > Gestión de Proyectos PGK. Abre un asistente y genera un
XLSX o CSV con una fila por proyecto de todas las compañías permitidas para el
usuario.

Columnas
========
27 columnas: las 25 de la plantilla "Gestión de Proyectos PGK - Contratos" más
Costos Totales (21) y Margen Bruto (24).

* Costos y Dist. Gtos. Sector / Gcia / Indirectos salen de
  ``account.consolidation.data`` (informe de consolidación), en PES. Solo
  incluyen los períodos ya consolidados. Las distribuciones se identifican por
  ``distribution_type`` (módulo ``consolidation_report`` 15.0.9.4.0): los
  períodos consolidados con versiones anteriores ("Porcentaje = ...") deben
  volver a consolidarse para que aparezcan.
* Costos Totales = Costos + Dist. Sector + Dist. Gcia + Dist. Indirectos.
* Margen Bruto = Facturación realizada − Costos − Dist. Sector − Dist. Gcia.
* Desvío de facturación, % Costos sobre ingresos y Realización se recalculan
  con la Facturación realizada y los Costos del informe.

Rango de fechas
===============
* Facturación realizada / Horas facturadas: fecha del comprobante
  (``invoice_date``; si no tiene, fecha contable). Adaly: períodos de
  consolidación.
* Tiempo total del parte de horas: ``account.analytic.line.date``.
* Costos y distribuciones: períodos de consolidación (mensuales) cuyo mes
  comienza dentro del rango.
* El resto de las columnas es siempre el acumulado total.

Seguridad
=========
Grupo "Informe Gestión de Proyectos PGK", incluido en Proyecto / Administrador.
