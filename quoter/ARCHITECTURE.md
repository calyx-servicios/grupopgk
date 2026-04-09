# Arquitectura del Módulo Quoter - Servicios Profesionales

## Fecha: 18/11/2025

---

## Visión General

Este módulo permite gestionar plantillas de servicios profesionales (Impuestos, Auditoría, Payroll) con horas predefinidas según tipo de empresa y nivel de complejidad/riesgo. Estas plantillas se integran con el módulo de ventas de Odoo (`sale.order`).

---

## Modelos Principales

### 1. `quoter.task.template` - Plantillas de Servicios

**Descripción:** Maestro de servicios profesionales con horas configuradas por categoría, tipo de empresa y nivel de complejidad/riesgo.

**Campos Principales:**

#### Información Básica:
- `name`: Nombre del servicio
- `sequence`: Orden de visualización
- `service_category`: Categoría del servicio
  - `taxes`: Impuestos
  - `audit`: Auditoría
  - `payroll`: Payroll
- `description`: Descripción detallada de procedimientos
- `product_id`: Producto asociado para facturación
- `active`: Estado activo/inactivo

#### Horas por Tipo de Empresa - PYME:
- `sme_low_hours`: Complejidad/Riesgo Bajo
- `sme_medium_hours`: Complejidad/Riesgo Medio
- `sme_high_hours`: Complejidad/Riesgo Alto

#### Horas por Tipo de Empresa - Grandes Empresas:
- `ge_low_hours`: Complejidad/Riesgo Bajo
- `ge_medium_hours`: Complejidad/Riesgo Medio
- `ge_high_hours`: Complejidad/Riesgo Alto

#### Horas por Tipo de Empresa - Sociedades del Estado:
- `state_high_hours`: Complejidad/Riesgo Alto (único nivel)

**Método Principal:**
```python
def get_hours_for_config(self, company_type, risk_level):
    """Retorna las horas según configuración de empresa y riesgo"""
```

### 2. `quoter.ipc.index` - Índices IPC

**Descripción:** Histórico de índices de precios al consumidor para actualización de tarifas.

**Campos:**
- `date`: Fecha del índice (primer día del mes)
- `index_value`: Valor del índice IPC
- `notes`: Observaciones

**Métodos:**
- `get_ipc_for_date(target_date)`: Obtener IPC para una fecha
- `calculate_adjustment(from_date, to_date)`: Calcular ajuste entre fechas

---

## Estructura de Vistas

### Vista de Plantillas de Servicios

#### Tree View:
Muestra todas las plantillas con columnas de horas por configuración.

#### Form View:
- **Header**: Nombre, categoría, secuencia, producto asociado
- **Descripción**: Campo de texto para detalles
- **Notebook con 3 páginas dinámicas:**
  1. **Impuestos** (visible solo si `service_category == 'taxes'`)
     - Horas por complejidad (Baja/Media/Alta)
     - Por tipo de empresa (PYME/GE/Estado)
  
  2. **Auditoría** (visible solo si `service_category == 'audit'`)
     - Horas por riesgo (Bajo/Medio/Alto)
     - Por tipo de empresa (PYME/GE/Estado)
  
  3. **Payroll** (visible solo si `service_category == 'payroll'`)
     - Horas por complejidad (Baja/Media/Alta)
     - Por tipo de empresa (PYME/GE/Estado)

#### Search View:
- Filtros por categoría (Impuestos/Auditoría/Payroll)
- Filtro por activo/inactivo
- Agrupación por categoría y producto

---

## Integración con Ventas (`sale.order`)

### Flujo de Trabajo

1. **Configuración Inicial:**
   - Crear plantillas de servicios en "Servicios Profesionales > Plantillas de Servicios"
   - Asociar cada plantilla con un producto vendible
   - Configurar horas según tipo de empresa y nivel

2. **Creación de Cotización:**
   - Crear una orden de venta (`sale.order`)
   - Agregar líneas de productos (`sale.order.line`)
   - Los productos son los asociados a las plantillas de servicios

3. **Cálculo de Horas:**
   - Al seleccionar un producto en `sale.order.line`, se determina:
     - Tipo de empresa del cliente (PYME/GE/Estado)
     - Nivel de complejidad/riesgo del proyecto
   - Se obtienen las horas correspondientes desde `quoter.task.template`
   - Se multiplica por la tarifa del producto

4. **Actualización por IPC:**
   - Usar `quoter.ipc.index` para ajustar precios según inflación
   - Calcular diferencia entre fecha propuesta anterior y actual

### Extensión Futura de sale.order

Para integrar completamente, se recomienda crear campos adicionales en `sale.order`:

```python
# En módulo de extensión
class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    company_type = fields.Selection([
        ('sme', 'PYME'),
        ('large_enterprise', 'Grande Empresa'),
        ('state_company', 'Sociedad del Estado'),
    ], string='Tipo de Empresa')
    
    complexity_level = fields.Selection([
        ('low', 'Bajo'),
        ('medium', 'Medio'),
        ('high', 'Alto'),
    ], string='Nivel de Complejidad/Riesgo')
```

---

## Datos Demo

### Productos Profesionales (`data/pricelist_data.xml`)

10 productos de servicios profesionales:
1. Asistente - $24,458/hora
2. Asistente Experimentado - $28,712/hora
3. Semi Senior - $35,683/hora
4. Acting Senior - $39,228/hora
5. Senior - $44,781/hora
6. Acting Manager - $56,006/hora
7. Manager - $85,072/hora
8. Acting Director - $106,340/hora
9. Director - $119,928/hora
10. Socio - $149,821/hora

### Lista de Precios

- **Nombre**: Tarifa Cotizaciones
- **Moneda**: ARS
- **Items**: 10 (uno por cada producto)

---

## Estructura de Menús

```
Sales
└── Servicios Profesionales
    ├── Plantillas de Servicios (quoter.task.template)
    └── Índices IPC (quoter.ipc.index)
```

---

## Casos de Uso

### Caso 1: Crear Plantilla de Auditoría

```python
# Crear plantilla para "Revisión de Caja y Bancos"
template = env['quoter.task.template'].create({
    'name': 'Revisión de Caja y Bancos',
    'service_category': 'audit',
    'description': 'Procedimientos de auditoría sobre saldos de efectivo y equivalentes',
    'product_id': env.ref('quoter.product_asistente_experimentado').id,
    'sme_low_hours': 4,
    'sme_medium_hours': 6,
    'sme_high_hours': 8,
    'ge_low_hours': 8,
    'ge_medium_hours': 12,
    'ge_high_hours': 16,
    'state_high_hours': 20,
})
```

### Caso 2: Obtener Horas para Cotización

```python
# Cliente: PYME con Riesgo Medio
template = env['quoter.task.template'].browse(1)
hours = template.get_hours_for_config('sme', 'medium')  # Retorna 6 horas
```

### Caso 3: Calcular Ajuste por IPC

```python
ipc_model = env['quoter.ipc.index']
adjustment = ipc_model.calculate_adjustment(
    from_date='2024-01-01',
    to_date='2025-01-01'
)
# Retorna índice de ajuste (ej: 1.25 = 25% de inflación)
```

---

## Archivos del Módulo

### Modelos (2 activos):
- `models/quoter_ipc_index.py`
- `models/quoter_task_template.py`

### Modelos Comentados (no usados):
- `models/quoter_service_config.py`
- `models/quoter_service_product_line.py`

### Vistas (3):
- `views/quoter_ipc_index_views.xml`
- `views/quoter_task_template_views.xml`
- `views/quoter_menu.xml`

### Datos:
- `data/pricelist_data.xml` - Productos y lista de precios

### Seguridad:
- `security/ir.model.access.csv` - Permisos para usuarios y managers

---

## Próximos Pasos

### Fase 1: Extensión de sale.order
- [ ] Crear módulo `quoter_sale` que extienda `sale.order`
- [ ] Agregar campos: `company_type`, `complexity_level`
- [ ] Crear wizard para seleccionar plantillas de servicios
- [ ] Auto-completar horas en `sale.order.line` según configuración

### Fase 2: Reportes
- [ ] Reporte de cotización en PDF
- [ ] Comparación de propuestas con ajuste IPC
- [ ] Dashboard de servicios más cotizados

### Fase 3: Automatización
- [ ] Actualización automática de precios por IPC
- [ ] Alertas de actualización mensual de tarifas
- [ ] Importación masiva de plantillas desde Excel

---

## Ventajas de esta Arquitectura

✅ **Simplicidad**: Solo 2 modelos activos, fácil de mantener
✅ **Flexibilidad**: 3 categorías de servicio independientes
✅ **Integración**: Se conecta naturalmente con sale.order
✅ **Escalabilidad**: Fácil agregar nuevas categorías de servicio
✅ **Mantenibilidad**: Estructura clara y documentada
✅ **Histórico IPC**: Actualización automática de tarifas

---

**Última actualización**: 18/11/2025
