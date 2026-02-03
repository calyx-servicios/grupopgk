# DMS Employee Auto Classification

Módulo de Odoo 15 que extiende `dms_auto_classification` para proporcionar clasificación automática de documentos de empleados con sistema integrado de firmas digitales.

## Descripción

Este módulo automatiza el proceso de clasificación, almacenamiento y firma de documentos de empleados (como recibos de sueldo), integrándose con el sistema de gestión documental (DMS) y el módulo de firmas digitales OCA.

## Características Principales

### 📁 Clasificación Automática de Documentos
- **Extracción automática de legajo**: Lee el número de legajo desde el nombre del archivo PDF
- **Renombrado inteligente**: Convierte archivos tipo `450.pdf` a `Juan Perez 02-02-2026.pdf`
- **Vinculación con empleados**: Asocia automáticamente documentos con el empleado correspondiente
- **Organización en DMS**: Crea subcarpetas por empleado en directorios tipo attachment
- **Fecha de clasificación**: Permite especificar la fecha del documento para mejor trazabilidad

### ✍️ Sistema de Firmas Digitales
- **Integración con Sign OCA**: Crea solicitudes de firma automáticamente al clasificar documentos
- **Firma digital del empleado**: Campo binario para almacenar la firma del empleado
- **Auto-relleno de firma**: Prellenado automático del canvas de firma con la firma digital guardada
- **Descarga inteligente**: Descarga el PDF firmado si existe, o el original si no
- **Validación de firma**: Verifica que el empleado tenga firma digital antes de permitir firmar
- **Estado de firma**: Seguimiento del estado (borrador, enviado, firmado, cancelado)

### 📋 Gestión de Documentos por Empleado
- **Vista unificada**: Página "Documentos" en la ficha del empleado con todos sus documentos
- **Seguimiento de estado**: Columnas de "Visto" y "Firmado" para tracking
- **Botón de descarga**: Descarga directa desde la lista de documentos
- **Botón de firma**: Visible solo para el empleado asignado cuando el documento está pendiente
- **Historial completo**: Ordenado por fecha de clasificación descendente

### 🔒 Control de Acceso y Seguridad
- **Filtrado automático por usuario**: Los empleados básicos solo ven su propia ficha
- **Permisos granulares**: Integración con grupos de HR (User/Manager)
- **Seguridad en firmas**: Solo el empleado responsable puede firmar su documento
- **Followers automáticos**: Auto-suscripción del empleado a sus solicitudes de firma

### 📊 Reportes
- **Reporte de Control de Firmas**: Export a Excel con listado de documentos y estados de firma
- **Filtros por fecha**: Permite generar reportes por rango de fechas
- **Información detallada**: Incluye empleado, fecha, estado de firma y visualización

## Requisitos

- Odoo 15.0
- `hr` - Recursos Humanos
- `hr_dms_field` - Campo DMS en empleados
- `dms_auto_classification` - Clasificación automática de documentos
- `dms_field_auto_classification` - Clasificación de campos DMS
- `sign_oca` - Sistema de firmas digitales OCA
- `report_xlsx` - Generación de reportes Excel

## Instalación

1. Clonar el repositorio en la carpeta de addons:
```bash
cd /path/to/odoo/addons
```

2. Actualizar la lista de módulos en Odoo:
```
Configuración → Técnico → Base de datos → Actualizar lista de módulos
```

3. Instalar el módulo:
```
Aplicaciones → Buscar "DMS Employee Auto Classification" → Instalar
```

## Configuración

### 1. Configurar Plantilla de Firma Digital

1. Ir a **Firma → Configuración → Plantillas de Firma**
2. Crear o editar una plantilla
3. Configurar los roles y campos de firma necesarios

### 2. Configurar Plantilla de Clasificación DMS

1. Ir a **Documentos → Configuración → Plantillas de Clasificación**
2. Crear una plantilla para documentos de empleados
3. En el campo **Plantilla de Firma**, seleccionar la plantilla creada en el paso anterior
4. Configurar el patrón de extracción de legajo (ej: `(\d+)\.pdf` para archivos tipo `123.pdf`)

### 3. Configurar Firma Digital del Empleado

1. Ir a **Empleados**
2. Abrir la ficha del empleado
3. Ir a la pestaña **Firma digital**
4. Dibujar y guardar la firma digital del empleado

## Uso

### Clasificación de Documentos

1. Preparar archivos PDF con nombre = legajo del empleado (ej: `450.pdf`, `123.pdf`)
2. Ir a **Documentos → Clasificación Automática**
3. Seleccionar los archivos PDF
4. Elegir la plantilla de clasificación configurada
5. Especificar la fecha de clasificación
6. Hacer clic en **Clasificar**

**Resultado:**
- Los archivos se renombran automáticamente (ej: `Juan Perez 02-02-2026.pdf`)
- Se crean en el DMS en la carpeta del empleado correspondiente
- Se genera automáticamente una solicitud de firma para cada documento
- El empleado recibe una notificación para firmar

### Firma de Documentos

**Opción 1: Desde la Ficha del Empleado**
1. El empleado accede a **Empleados → Mi Ficha**
2. Va a la pestaña **Documentos**
3. Localiza el documento pendiente de firma
4. Hace clic en el botón **Firmar**
5. La firma digital se prellenará automáticamente
6. Confirmar la firma

**Opción 2: Desde el Link de Notificación**
1. El empleado recibe un email de notificación
2. Hace clic en el link de firma
3. La firma digital se prellenará automáticamente
4. Confirmar la firma

### Descarga de Documentos

1. Ir a la pestaña **Documentos** en la ficha del empleado
2. Hacer clic en el botón **Descargar** del documento deseado
3. Si el documento está firmado, descarga el PDF con las firmas
4. Si no está firmado, descarga el PDF original
5. El documento se marca automáticamente como "Visto"

### Generar Reporte de Control de Firmas

1. Ir a **Empleados → Reportes → Control de Firmas**
2. Especificar rango de fechas
3. Hacer clic en **Generar Reporte**
4. Se descarga un archivo Excel con:
   - Legajo del empleado
   - Nombre del empleado
   - Fecha del documento
   - Estado de firma
   - Estado de visualización

## Modelos de Datos

### hr.employee.document
Modelo principal que vincula documentos con empleados:
- `employee_id`: Empleado asociado
- `classification_date`: Fecha del documento
- `dms_file_id`: Archivo en el DMS
- `sign_request_id`: Solicitud de firma asociada
- `viewed`: Indica si el documento fue descargado/visto
- `signed`: Indica si el documento está firmado
- `can_sign`: Computed field que indica si el usuario actual puede firmar

### hr.employee (extendido)
Campos añadidos al modelo de empleado:
- `employee_document_ids`: Relación One2many con documentos
- `digital_signature`: Campo binario para la firma digital

### sign.oca.request (extendido)
Mejoras al modelo de solicitudes de firma:
- Override de `search()` y `read_group()` para filtrado por usuario
- Override de `_compute_to_sign()` para cálculo correcto en multi-usuario
- Override de `sign()` con validación de firma digital

### sign.oca.request.signer (extendido)
Mejoras al modelo de firmantes:
- Override de `get_info()` para inyectar firma digital
- Override de `sign()` con validación de firma digital obligatoria

## Ejemplo Completo

### Escenario: Clasificación de Recibos de Sueldo de Enero 2026

**Archivos originales:**
```
450.pdf  → Juan Perez
123.pdf  → Maria Garcia
789.pdf  → Carlos Lopez
```

**Proceso:**
1. Admin ejecuta wizard de clasificación con fecha `31/01/2026`
2. El sistema identifica a los empleados por legajo
3. Renombra archivos:
   - `Juan Perez 31-01-2026.pdf`
   - `Maria Garcia 31-01-2026.pdf`
   - `Carlos Lopez 31-01-2026.pdf`
4. Crea subcarpetas en DMS (si es storage tipo attachment):
   ```
   Recibos/
   ├── Juan Perez/
   │   └── Juan Perez 31-01-2026.pdf
   ├── Maria Garcia/
   │   └── Maria Garcia 31-01-2026.pdf
   └── Carlos Lopez/
       └── Carlos Lopez 31-01-2026.pdf
   ```
5. Genera solicitudes de firma automáticamente
6. Envía notificaciones a cada empleado
7. Los empleados firman con su firma digital prellenada
8. Los PDFs firmados quedan disponibles para descarga

## Soporte

Para reportar bugs o solicitar nuevas características, contactar al equipo de desarrollo en [Grupo PGK](https://www.grupopgk.com.ar/).

## Licencia

AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)

## Créditos

**Autor:** Grupo PGK  
**Mantenedor:** [@Frankofe](https://github.com/Frankofe)  
**Versión:** 15.0.1.6.0
