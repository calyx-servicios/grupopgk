Horas de gestión y reuniones internas
======================================

El módulo ``timesheet_activity_management`` agrega un catálogo administrable,
fecha de actividad, dashboard de consulta y reporte semanal de horas. Instalar
junto con ``timesheet_activity_management_reclassify`` para conservar tipo y
fecha en la reclasificación SIGE. Si está activo el temporizador OCA, instalar
``timesheet_activity_management_timer``. La carga desde Helpdesk queda fuera
del alcance actual.

Configuración inicial
---------------------

1. Asignar ``Administración de horas de gestión`` a quienes administrarán
   tipos y configuración. Este grupo también habilita la consulta.
2. Asignar ``Consulta de horas de gestión`` al Director de Operaciones y a
   las personas autorizadas a consultar el detalle. Los datos se restringen
   a sus compañías permitidas.
3. Revisar los tipos iniciales Gestión y Reunión interna, incluidos en el
   reporte, y Soporte, excluido. El administrador puede ajustar esta propiedad
   y crear otros tipos. Archivar tipos en vez de borrarlos si ya están usados.
4. Crear la configuración de cada compañía, indicar el correo del Director de
   Operaciones y activar el envío semanal una vez validado el ambiente.
5. Enviar un reporte de prueba antes de dar por habilitado el correo. El cron
   diario evalúa el horario local y encola el reporte los lunes a las 08:00 de
   ``America/Argentina/Buenos_Aires``. No envía si la compañía no está
   configurada y activada.

Carga y clasificación
---------------------

Toda carga real con proyecto y horas positivas debe informar Tipo de hora y
Fecha de actividad. La fecha SIGE conserva su comportamiento existente y no
reemplaza a la fecha real de actividad. Para Gestión y Reunión interna, la
descripción debe explicar la actividad; no se aceptan textos vacíos ni ``/``.
Soporte y otros tipos excluidos no exigen una justificación específica.

La clasificación se exige en servidor además de las vistas, incluyendo
importaciones, RPC y ediciones de las dimensiones de la carga. Las líneas
contables, de consolidación y auxiliares de SIGE quedan excluidas. Las tareas,
etapas, límites de horas y controles UAT existentes permanecen activos.

Las líneas históricas no reciben tipo ni fecha inventados. El dashboard incluye
una acción ``Pendientes de completar`` para encontrar datos incompletos. No se
incluyen en una semana hasta contar con su clasificación y fecha de actividad.
Al editar una carga histórica se deben completar los campos obligatorios.

Dashboard y envíos
------------------

El dashboard usa lista, tabla dinámica y gráfico estándar de Odoo. Sus
dimensiones incluyen cliente del proyecto, proyecto/tema, Tipo de hora, PM,
líder técnica y empleado. El filtro Funcionales consulta a los funcionales
actualmente asignados al proyecto: elegir cualquiera de ellos no duplica las
horas. Los responsables y el cliente se presentan según la configuración
actual del proyecto, también para las líneas anteriores.

El correo contiene el total semanal y adjunta un Excel con detalle, horas y
justificación. Los períodos son lunes a domingo anteriores, calculados en la
zona horaria de Argentina, e incluyen cargas guardadas aunque SIGE siga abierto.
Las correcciones posteriores actualizan el dashboard; se puede regenerar y
reenviar una semana desde el menú de administración. Los reenvíos quedan
registrados y no generan rectificaciones automáticas.

El correo se encola en ``mail.mail``; que esté en cola no confirma entrega SMTP.
Los errores de generación quedan registrados en ``Envíos semanales`` y en el
log de Odoo. Los tipos incluidos y los correos se deben probar en una base no
productiva antes de activar el cron.
