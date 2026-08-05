# Datos de Demostración - Módulo Quoter

## Archivo: pricelist_data.xml

Este archivo contiene los datos iniciales para el módulo de cotizaciones basados en las tarifas del Excel de auditoría.

### Contenido

#### 1. Productos de Servicios Profesionales (10 productos)

Todos los productos son de tipo `service` con unidad de medida `Hora`:

| Producto | Tarifa Base (ARS) | Descripción |
|----------|-------------------|-------------|
| Asistente | 24,458.00 | Categoría profesional: Asistente |
| Asistente Experimentado | 28,712.00 | Categoría profesional: Asistente Experimentado (AE) |
| Semi Senior | 35,683.00 | Categoría profesional: Semi Senior |
| Acting Senior | 39,228.00 | Categoría profesional: Acting Senior |
| Senior | 44,781.00 | Categoría profesional: Senior (SR) |
| Acting Manager | 56,006.00 | Categoría profesional: Acting Manager |
| Manager | 85,072.00 | Categoría profesional: Manager (GTE) |
| Acting Director | 106,340.00 | Categoría profesional: Acting Director |
| Director | 119,928.00 | Categoría profesional: Director |
| Socio | 149,821.00 | Categoría profesional: Socio |

#### 2. Lista de Precios: "Tarifa Cotizaciones"

- **Nombre**: Tarifa Cotizaciones
- **Moneda**: ARS (Peso Argentino)
- **Estado**: Activa
- **Ámbito**: Multi-compañía

#### 3. Items de Lista de Precios

Cada producto tiene asociado un item en la lista de precios con:
- Precio fijo según tarifa base
- Cantidad mínima: 1
- Método de cálculo: Precio fijo

### Uso en el Módulo

Estos productos y la lista de precios "Tarifa Cotizaciones" se utilizan en:

1. **quoter.service.config**: Seleccionar la lista de precios para calcular honorarios
2. **quoter.service.product.line**: Agregar líneas de productos con horas por categoría profesional
3. **Cálculo automático**: El sistema calcula montos según: `Total Hours × Price from Pricelist`

### Actualización de Tarifas

Las tarifas base en este archivo corresponden a un momento específico. Para actualizar:

1. **Manual**: Editar los precios directamente en Odoo (Sales > Configuration > Pricelists)
2. **Por IPC**: Usar el modelo `quoter.ipc.index` para ajustar automáticamente según inflación
3. **Masivo**: Crear un nuevo archivo XML con tarifas actualizadas

### Notas Importantes

- Las tarifas están en pesos argentinos sin IVA
- Son tarifas por hora de servicio profesional
- Se recomienda actualizar mensualmente según IPC
- Los productos más utilizados son: Asistente Experimentado (AE), Senior (SR), Manager (GTE) y Socio

### Tarifas Más Usadas en Cotizaciones

Según el análisis del Excel, las categorías más utilizadas son:

1. **Asistente Experimentado (AE)**: 28,712.00 - Base para cálculo de horas
2. **Senior (SR)**: 44,781.00 - 50% de horas AE
3. **Manager (GTE)**: 85,072.00 - 30% de horas SR
4. **Socio**: 149,821.00 - 10-20% de horas GTE según riesgo

### Ejemplo de Uso

```python
# Crear una cotización con la lista de precios
service = env['quoter.service.config'].create({
    'name': 'Auditoría EECC 2025',
    'partner_id': partner.id,
    'pricelist_id': env.ref('quoter.pricelist_tarifa_cotizaciones').id,
    'company_type': 'sme',
    'risk_level': 'medium',
})

# Agregar líneas de producto
line = env['quoter.service.product.line'].create({
    'service_id': service.id,
    'product_id': env.ref('quoter.product_asistente_experimentado').id,
    'ae_hours': 100,
    'sr_hours': 50,  # 50% de AE
    'mg_hours': 15,  # 30% de SR
    'partner_hours': 2.25,  # 15% de GTE (riesgo medio)
})

# El sistema calcula automáticamente el monto total
```

### Fuente de Datos

Basado en: **AUDITORIA - Planilla de cotización estandarizada.xlsx**
- Hoja: "Cotización"
- Sección: "Tarifas (Actualizadas con IPC)"
- Fecha base de tarifas: Mes 1 (sin actualización IPC)

---

**Última actualización**: 17/11/2025
