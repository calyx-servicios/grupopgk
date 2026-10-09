Reserva UAT/Soporte Calyx
=========================

Alcance
-------

La venta estandar Calyx permite prever horas UAT/Soporte dentro del total
contratado de cada linea de servicio. No agrega horas al total ni modifica
precio, tarifa o importe. No interviene en el Cotizador profesional PGK.

``project_hours_request`` incorpora el quinto cupo operativo
``estimated_uat_support_hours`` por tarea Desarrollo y el segmento
``uat_support`` en los partes de horas. Este modulo conecta esos cupos con
la reserva comercial por raiz contractual, sin alterar las cuatro bolsas
existentes ni las transiciones de estados.

Operacion
---------

1. En el presupuesto Calyx, completar Horas UAT/Soporte en la linea de
   servicio. Debe ser un valor no negativo dentro de las horas contratadas.
2. Confirmar la orden. La raiz recibe una copia contractual de esa prevision,
   independiente de las estimaciones de las subtareas. La prevision cotizada
   queda congelada desde la confirmacion.
3. El PM asigna Horas UAT/Soporte a las tareas Desarrollo cobrables. La suma
   de cupos, incluidos los de tareas archivadas, no puede superar la reserva.
   En Configuraciones los cupos corresponden al nivel 4, no a contenedores.
4. Desde la raiz, el PM pulsa Activar reserva UAT. La activacion valida
   asignaciones, consumo previo, contrato y limites de las ramas.
5. Toda nueva carga en UAT Cliente consume exclusivamente el cupo UAT de
   su tarea. Al agotarse se bloquea: no toma Desarrollo, Pruebas ni Margen.

Durante la preparacion no se admiten nuevas cargas UAT. Las cargas de los
otros estados mantienen los controles existentes. Una vez activa, la reserva
no puede desactivarse ni editarse directamente.

Las tareas muestran cupo, consumo y disponible UAT. La raiz muestra reserva,
asignacion y horas sin asignar. Los cupos son valores propios de cada tarea,
no sumas que sustituyen las estimaciones del padre. Al duplicar una tarea,
el nuevo cupo UAT empieza en cero.

Ejemplo y limites
-----------------

Con 20 horas contratadas y 4 reservadas para UAT, el trabajo no UAT puede
consumir como maximo 16 horas. Dos tareas con cupos UAT de 2 horas pueden
consumir 2 cada una, pero ninguna puede superar su cupo. Las horas UAT sin
asignar siguen reservadas y no se liberan al trabajo normal.

Se conservan el tope global y los controles de la jerarquia. La reserva de
cada actividad de nivel 3 se descuenta de su capacidad no UAT, y la reserva
no asignada tampoco se presta al exceso compartido. Una ampliacion global
existente aumenta la capacidad no UAT, nunca la reserva UAT.

Las correcciones de duracion conservan el tramo historico. Los cambios de
estado no reclasifican horas previas; quitar o falsificar el tramo y trasladar
UAT a otra bolsa se rechaza. Las tareas con consumo no pueden trasladarse
entre contratos ni eliminarse para liberar presupuesto.

Durante UAT tampoco se puede aumentar un parte historico de otro tramo:
las nuevas horas requieren un nuevo parte UAT. Se permite reducir el parte
historico conservando su imputacion original.

Proyectos existentes
--------------------

Las raices existentes comienzan En preparacion, sin inventar una prevision
UAT ni reclasificar partes antiguos. El PM puede completar la reserva de una
raiz que no tiene snapshot UAT de cotizacion, con registro en el chatter.
Despues distribuye cupos y activa la reserva.

El consumo historico sin tramo UAT cuenta como no UAT. Si ya invade la parte
que se desea reservar, la activacion informa el consumo y el tope disponible.
Debe resolverse el presupuesto antes de activar; no se corrige el deficit
reclasificando automaticamente la historia.

Instalacion y actualizacion
------------------------------

Requiere ``project_hours_request`` y ``calyx_sale_project_from_order``.
Es compatible con ``project_task_config_hierarchy`` sin requerir instalar
esa jerarquia para usar reservas en un arbol Calyx ordinario.

Actualizar el nucleo e instalar este puente durante una ventana de
mantenimiento, con backup previo y sustituyendo BASE por la base destino::

   docker compose run --rm --no-deps web odoo \
     -c /etc/odoo/odoo.conf -d BASE \
     -u project_hours_request -i project_hours_request_calyx \
     --stop-after-init --no-http --workers=0 --max-cron-threads=0

Reiniciar el servicio web despues de actualizar. Usar ``-i`` para la primera
instalacion del puente y ``-u`` para actualizaciones posteriores. La funcion
XML del nucleo configura solo el tramo de la etapa canonica UAT Cliente
tanto al instalar como al actualizar, incluso si el workflow es noupdate.

Verificacion
------------

Ejecutar las suites en una copia descartable, nunca en la base operativa::

   docker compose exec -T web odoo \
     -c /etc/odoo/odoo.conf -d grupopgk_uat_test \
     -u project_hours_request,project_hours_request_calyx \
     --test-tags /project_hours_request,/project_hours_request_calyx \
     --stop-after-init --http-port=18069 --longpolling-port=18072 \
     --workers=0 --max-cron-threads=0

Para la combinacion con jerarquia, actualizar y agregar a los filtros
``project_task_config_hierarchy`` y ``calyx_sale_project_from_order``.
Los puertos distintos evitan colision con el servidor activo cuando Odoo
abre HTTP para los tests.

La comprobacion de concurrencia usa cursores reales y commits de fixtures;
solo acepta bases cuyo nombre contiene ``uat_test``. Se ejecuta en Odoo shell::

   from odoo.addons.project_hours_request_calyx.tests.test_uat_reservations import check_concurrent_allocations
   check_concurrent_allocations(env)

Comprueba snapshots desactualizados y reintentos, tanto para asignar cupos
como para cargar horas UAT. Limpia las fixtures al terminar. El bloqueo
actualiza la fila de tarea/raiz para que PostgreSQL REPEATABLE READ detecte
una transaccion concurrente; el reintento vuelve a comprobar el presupuesto.

No incluye soporte posterior fuera de UAT Cliente, ampliaciones UAT ni
inferencia del triage desde descripciones de partes sin tarea.