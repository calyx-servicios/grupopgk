# Manual Usuario - Cotizador y Area TAX

## 1. Objetivo

Este documento resume como usar el cotizador en `sale.order`, en especial para el area `TAX`, y diferencia claramente lo que ya esta implementado de lo que aun esta pendiente.

## 2. Conceptos clave

- **Area profesional**: define una planilla de cotizacion (niveles, rangos, lineas y politica de horas).
- **Etiqueta separadora**: sirve para agrupar y ordenar productos/lineas visualmente.
- **Rangos del area**: franjas usadas para cargar horas por rango.
- **Nivel de complejidad**: nivel activo por area dentro del pedido.
- **Grupo del area**: controla que usuarios ven el area y su pestana.
- **Carga manual**: bandera en linea del cotizador; hoy es dato manual (logica funcional pendiente en pedido).

## 3. Como crear etiquetas separadoras

1. Ir al menu de configuracion de etiquetas separadoras del cotizador.
2. Crear etiqueta con nombre (y color, si aplica).
3. En el area, asignar la etiqueta en cada linea del cotizador.

Uso: solo organiza y agrupa visualmente; no define precios ni horas por si sola.

## 4. Como configurar rangos y area

1. Crear/seleccionar el area profesional.
2. Definir su `secuencia` (1..5) para posicion de pestana.
3. Asociar `rangos del area`.
4. Asociar `niveles de complejidad`.
5. Configurar `grupo de visibilidad` del area (si aplica).
6. Definir politica de horas:
   - Regular
   - Combinada (tabla A + tabla B)
7. Marcar `cerrado` cuando el area ya esta lista para usar en cotizacion.

## 5. Grupos y permisos

- **Quoter - Gerente**:
  - puede editar campos de gerente responsable;
  - puede operar acciones sensibles del cotizador;
  - gestiona ajustes y descuentos/recargos por area.
- **Quoter - Socio**:
  - puede editar el campo socio asignado.
- **Grupo del area (ej. TAX)**:
  - solo usuarios de ese grupo ven la pestana y datos del area.

## 6. Como se maneja el cotizador en sale.order

1. Crear/abrir pedido y marcar cotizacion (`is_quotation`).
2. Seleccionar areas (maximo 5).
3. Completar cabecera:
   - Gerente responsable (filtrado por grupo gerente).
   - Socio asignado (filtrado por grupo socio).
4. Por cada pestana de area:
   - elegir nivel;
   - cargar/editar lineas de productos;
   - ajustar descuento y recargo globales.

### Descuento y Recargo por area

- Se manejan en dos campos separados:
  - **Descuento** (positivo, resta al total)
  - **Recargo** (positivo, suma al total)
- Pueden coexistir ambos.
- Formula por area:
  - `total_area = subtotal_productos + subtotal_ajustes - descuento + recargo`

## 7. Visibilidad de pestanas por area

Las pestanas se muestran cuando:

1. el pedido es cotizacion;
2. existe area en ese slot/secuencia;
3. el usuario pertenece al grupo de visibilidad del area (si el area tiene grupo asignado).

## 8. Productos en area TAX

En el modelo actual, TAX usa la misma base del cotizador por area:

- lineas por producto;
- horas por rango;
- nivel del area;
- ajustes por linea;
- totales por pestana.

La especializacion funcional TAX de la tarjeta (secciones estandar, ajustes, manuales y totales por rol) se considera evolutiva sobre esta base.

## 9. Ajustes de lineas

- Solo el gerente asignado en la `sale.order` (y con grupo gerente) puede crear ajustes.
- La observacion en linea de ajuste es obligatoria.
- El flujo usa asistente para crear ajuste con observacion obligatoria.

## 10. Tabla combinada con porcentajes (aplicable a TAX)

1. En el area, elegir modo de horas `Combinada`.
2. Definir:
   - Tabla A (base)
   - Tabla B tipo `Porcentaje`
3. Resultado:
   - horas finales calculadas desde A y B segun politica configurada.
4. Edicion:
   - controlada por modo editor y permisos del grupo gerente.

## 11. Matriz JS en TAX (como funciona)

La matriz JS del area:

- renderiza niveles y rangos;
- muestra celdas de entrada/salida segun modo regular o combinado;
- respeta bloqueo por permisos y estado de edicion;
- persiste valores mediante metodos backend del area.

## 12. Pendiente de desarrollo (explicito)

Segun definicion funcional TAX, aun quedan items por implementar de forma especifica:

- secciones visuales dedicadas: Estandar / Ajustes / Manuales / Totales por rol;
- item manual `NUEVO - ...` con ingreso libre por rol;
- logica especial de **Consultoria fiscal de rutina** (horas totales y distribucion automatica por % de complejidad);
- ayuda contextual para **Confeccion DJ PH**;
- cierre funcional completo de `manual_load` en `sale.order` (hoy la marca se define manualmente por usuario, pero su comportamiento de negocio aun no esta cerrado).

