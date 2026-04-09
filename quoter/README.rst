Quoter - Service Configuration
===============================

Resumen
-------
Este módulo permite configurar servicios cotizables compuestos por líneas de productos y horas por rol (AE, SR, MG, Partner). Calcula automáticamente el total de horas y montos usando la lista de precios seleccionada.

Características
---------------
- Modelo principal ``quoter.service.config`` para definir el servicio y su complejidad.
- Líneas ``quoter.service.product.line`` con desglose de horas por rol y precio unitario desde ``pricelist_id``.
- Cómputo automático de:
  - Horas totales del servicio.
  - Monto total (horas * precio unitario por producto).
- Restricciones:
  - Nombre de servicio único.
  - Horas por rol no negativas.
  - Al menos una hora > 0 por línea de producto.
  - Producto único dentro del mismo servicio.

Instalación
-----------
1. Copiar la carpeta ``quoter`` dentro de su directorio de addons (ya está en el repositorio ``grupopgk``).
2. Actualizar la lista de aplicaciones en Odoo.
3. Instalar el módulo "Quoter - Service Configuration".

Dependencias
------------
- ``base``
- ``sale``
- ``sale_management``
- ``product``

Uso
---
1. Crear un registro de **Service Configuration** indicando: nombre, complejidad, tipo de compañía y lista de precios.
2. Añadir líneas de producto asignando horas por rol.
3. Revisar los totales calculados (horas y monto) en el formulario del servicio.

Notas Técnicas
--------------
- El precio unitario se obtiene con ``pricelist_id.get_product_price`` usando cantidad 1 y la UoM del producto.
- El campo ``total_hours`` de la línea se recalcula con cada cambio en horas individuales.
- Los montos se almacenan para optimizar consultas/reportes.

Créditos
--------
Desarrollado por Calyx Servicios S.A.

Mantenimiento
-------------
Agregue su usuario de mantenimiento en ``maintainers`` dentro de ``__manifest__.py``.

Licencia
--------
AGPL-3.0
