# Triage de UAT Cliente

## Alcance

El botón **Validar UAT** registra una validación **no exitosa**. La aprobación
exitosa conserva el circuito anterior y no exige un triage negativo.

Disponible para el Funcional del proyecto, en formulario y Kanban de tareas
Desarrollo en la etapa canónica UAT Cliente.

| Resultado | Tarea original | Nueva tarea | Tratamiento |
| --- | --- | --- | --- |
| Bug | Vuelve a Desarrollo | No | Corrección, deploy y pruebas internas, sin facturación ni consumo contractual |
| Mejora | Permanece en UAT Cliente | Desarrollo en Estimación, independiente | Presupuesto nuevo y doble aprobación |
| Malentendido | Permanece en UAT Cliente | No | Aclaración registrada, sin cambio de código |

Resultado y descripción son obligatorios. Cada registro conserva fecha, autor,
etapas y enlaces en **Historial de eventos**, además del chatter. El informe
de eventos permite filtrar y agrupar por resultado UAT. Eventos, aprobaciones y
evidencias registradas no se pueden alterar o borrar.

## Bug

El wizard devuelve la misma tarea a Desarrollo. Las nuevas horas de Desarrollo,
Deploy y Pruebas durante ese ciclo quedan vinculadas al evento Bug, como internas
no facturables. No se trasladan a otra tarea ni se les asigna una línea comercial.

Se conserva el esfuerzo y costo real, pero se excluyen esas horas de cupos
facturables, tope global, reserva Calyx y bolsas de Configuraciones.
SIGE conserva las horas registradas y las excluye de chargeability.

Al volver a UAT Cliente se cierra el ciclo interno: las nuevas horas consumen
UAT/Soporte de la tarea original, con los controles anteriores. Ningún cambio de
etapa reclasifica horas históricas. Las correcciones adicionales de un parte
antiguo no interno deben registrarse en un parte nuevo durante el ciclo Bug.

## Mejora: operación

1. El Funcional registra **Mejora** y describe el nuevo alcance.
2. Se crea una tarea independiente en Estimación, en el mismo proyecto y cliente.
   Tiene **Tarea de origen UAT**, pero no `parent_id`, estimaciones, checklist
   validado ni línea de venta heredada.
3. Líder Técnico y PM completan sus estimaciones por tramo, según los permisos
   existentes. No se permite cargar horas para preparar la estimación.
4. Un usuario de Ventas con acceso a la tarea utiliza **Cotizar Mejora**:
   selecciona el servicio, precio por unidad y responsable comercial.
   Se crea una nueva cotización con una única línea dedicada, cantidad convertida
   desde las horas estimadas a la unidad de tiempo del producto y reserva UAT
   incluida en ese total. El producto debe tener unidad de medida de tiempo
   y seguimiento `project_only` o `task_in_project`.
   Revisar condiciones, precios e impuestos en Ventas antes de aprobar.
5. Alternativamente, Ventas puede preparar la cotización manualmente y vincular
   su línea mediante **Línea comercial de la Mejora**. Debe ser otra OV, del mismo
   cliente/compañía, con el proyecto de origen indicado explícitamente.
6. El Funcional usa **Aprobación del cliente**, con detalle y evidencia adjunta
   obligatorios.
7. El usuario que figura como responsable comercial de la OV utiliza
   **Aprobar Mejora (Comercial)**. No se reutiliza el grupo Contratos.
8. Ventas confirma la cotización. Sin ambas aprobaciones vigentes se rechaza
   la confirmación; la confirmación no inicia Desarrollo automáticamente.
9. Se habilita el paso a Lista para hacer y luego el workflow habitual.
   La carga de horas usa únicamente el nuevo contrato y sus topes.

Las raíces Calyx generadas al confirmar son contenedores comerciales, no otra
Mejora. No admiten cargas ni subtareas que gasten en paralelo el presupuesto
dedicado. La Mejora conserva su independencia estructural.

Cambiar estimaciones o línea comercial inicia una nueva revisión e invalida
ambas aprobaciones, incluso si se vuelve al valor anterior. Cambios comerciales
relevantes, cambio del comercial o cancelación de la OV también invalidan.
Las nuevas cargas se bloquean; los partes existentes conservan su contrato
histórico y no se vuelven a facturar contra la nueva línea.
Cada línea queda reservada para esa Mejora incluso después de ser reemplazada;
no se libera su contenedor para cargar horas en otra tarea.

No se puede quitar la trazabilidad ni borrar tareas relacionadas: usar archivo.
No se permite trasladar partes hacia o desde una Mejora.

## Malentendido

Registrar la aclaración acordada. Se resuelve el reporte, no la aprobación del
entregable: no se genera tarea, ciclo interno ni cambio de estimaciones.
La tarea queda en UAT Cliente para la validación exitosa posterior.

## Activación

- Instalar `project_task_uat_triage` y actualizar conjuntamente
  `project_hours_request` 15.0.1.2.3 y `project_hours_request_calyx` 15.0.1.0.3.
  Si se usa Configuraciones, actualizar `project_task_config_hierarchy` 15.0.1.0.1.
  Actualizar también `project_contrated_hours` 15.0.3.3.11: su hook evita que
  cotizar una Mejora sobrescriba el importe del alcance original del proyecto.
- Reiniciar los procesos Odoo para cargar los helpers compartidos.
- Verificar que las etapas canónicas Desarrollo, Estimación, UAT Cliente y
  posteriores tienen **Tipo de tarea habilitado = Desarrollo** y que se
  encuentran vinculadas a los proyectos. Los XML de etapas son `noupdate`;
  actualizar un módulo no corrige configuraciones históricas por sí solo.
- Revisar tareas históricas antes de corregir una etapa que haya sido usada
  para Gestión/Funcional. No se cambian automáticamente etapas/tipos históricos.
- Configurar los roles Funcional, PM, Líder Técnico y ejecución en el proyecto.
  El comercial necesita permisos de Ventas y acceso de usuario de Proyectos.
- Verificar reserva UAT activa y cupos en contratos originales Calyx.
- Probar primero en una copia aislada, con cron deshabilitado y correo saliente
  bloqueado. No ejecutar instalación/upgrade sobre una base operativa sin
  autorización.

No se migran ni reclasifican automáticamente horas o reportes anteriores.
No se incluye aprobación portal, generación automática de facturas ni detección
de rechazos en correos externos.

## Validación técnica

Usar el runner nativo de Odoo en una base desechable. Ejemplo con la configuración
del entorno y correo bloqueado:

```sh
odoo -c CONFIGURACION_DE_PRUEBAS -d BASE_DE_PRUEBAS \
  --http-port=0 --max-cron-threads=0 --smtp=127.0.0.1 --smtp-port=1 \
  --stop-after-init --test-enable \
  -u project_task_uat_triage,project_contrated_hours,project_hours_request,project_hours_request_calyx,project_task_config_hierarchy \
  --test-tags /project_task_uat_triage,/project_hours_request,/project_hours_request_calyx,/project_task_config_hierarchy,/project_task_type_workflow,/project_task_description_checklist
```

Si Configuraciones no está instalado, omitirlo de `-u`; el módulo no exige esa
dependencia.

Prueba clave de Bug: con 18 horas no UAT consumidas y 2 reservadas para UAT en un
contrato de 20, registrar 2 Dev + 1 Deploy + 1 Pruebas internas. El esfuerzo total
sube a 22 y el consumo contractual sigue en 18. Luego registrar 1 hora UAT:
el consumo contractual pasa a 19, sin mover el historial.

Los hooks de consumo presupuestario mantienen el comportamiento anterior cuando
el módulo UAT no está instalado. `_get_total_consumed_hours()` conserva el total
real para protecciones estructurales y auditoría.
