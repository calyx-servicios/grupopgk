# Guía de configuración y uso por método de horas

Documentación del módulo **Quoter** para los métodos de tabla de horas distintos de **Regular** (que ya está documentado por separado).

| Método en sistema | Valor técnico | Uso típico |
|-------------------|---------------|------------|
| Regular manual | `regular_manual` | Finanzas: líneas libres con horas y precio manual |
| Combinada | `combined` | Auditoría y áreas con tablas A × B por rol |
| Fórmula | `formula` | BPO y servicios por volumen × minutos por rol |
| Fórmula en cadena | `formula_chain` | Payroll y tablas según cantidad de empleados |

---

## Antes de empezar (común a todos)

1. **Menú:** Cotizador → Configuración → **Áreas profesionales**.
2. **Crear o abrir el área** y completar datos base:
   - Nombre, secuencia, grupo (visibilidad), lista de precios, categoría de producto.
   - **Roles del área** (`Categorías de recursos`): columnas de horas en cotización (AE, SR, GTE, Socio, etc.).
3. **Pestaña Reglas de tablas:**
   - Elegir **Tipo de tabla de horas** (radio).
   - Definir **Ramas** (opcional). Si no hay ramas, el sistema usa «Rama única».
   - Definir **Secciones de cotizador** (etiquetas separadoras de líneas).
4. **Editor de tabla:** botones **Abrir editor de tabla** / **Cerrar editor de tabla** (gestores). Mientras el editor está cerrado, matrices y productos quedan en solo lectura.
5. **Cerrado:** cuando la configuración está lista, marcar **Cerrado** para permitir usar el área en cotizaciones.
6. **En la cotización (`sale.order`):** cada área aparece como pestaña con un **bloque embebido** (`quoter.sale.order.area`). Guardar el bloque antes de operaciones masivas (carga múltiple, wizards).

Opciones del área que afectan la cotización:

| Campo | Efecto |
|-------|--------|
| **Carga múltiple de líneas** | Muestra «Agregar múltiples líneas» en el bloque |
| **Cargar predeterminados** | Muestra «Cargar predeterminados» y autoload al crear bloque |
| **Redondear el mínimo a** | Horas de salida por debajo del mínimo se elevan a ese valor |

---

## 1. Combinada (`combined`)

Es el método **más amplio**: tablas **A** (base por rol) y **B** (factor o porcentaje), con ramas, niveles de complejidad, unificaciones y excepciones.

### 1.1 Configuración del área

#### Paso 1 — Tipo y política de matrices

En **Reglas de tablas → Política de horas (matrices)**:

1. **Tipo de tabla de horas:** *Combinada*.
2. **Formato tabla A:**
   - *Por rol* — edición completa por rol y nivel.
   - *Unificada por nivel/rama* — un valor por nivel/rama replicado a todos los roles.
   - *Unificada global* — un único valor para toda la tabla A.
3. **Tipo tabla B:**
   - *Porcentaje (sobre A)* — final = A × (B ÷ 100).
   - *Multiplicador* — final = A × B.
4. Si B es porcentaje:
   - **Modo porcentaje B:** exacto (total 100 %) o variable (total libre).
   - **Base del porcentaje B:** sobre tabla A o cascada (cada rol aplica % sobre el rol anterior del mismo nivel/rama).
5. Opciones de unificación (solo combinada):
   - **A: unificar valores por rol** / ocultar columnas repetidas.
   - **A: unificar valores por nivel de complejidad** / ocultar roles repetidos.
   - **B: unificar valores por rol** / ocultar columnas repetidas.
   - **Unificar valores por rama** — habilita «Unifica valor» en productos.
   - **Productos varios en tabla B** — habilita «Productos varios» en cada producto.
6. **Permite cambiar el nivel** — en cotización se puede cambiar el nivel del bloque después de guardado (recalcula todas las líneas).
7. **Redondear el mínimo a** — aplica a horas de la tabla resultado.

#### Paso 2 — Niveles, ramas y secciones

- **Niveles de complejidad:** obligatorios (bajo / medio / alto, etc.). Definen variantes de producto y colores en el pedido.
- **Ramas:** opcionales; segmentan tablas A/B y la cotización.
- **Secciones de cotizador:** etiquetas para agrupar líneas.

#### Paso 3 — Tabla B avanzada (opcional)

En **Tabla B - configuración avanzada**:

- **Reglas base por rol:** factor por defecto, fijo u oculto por rol.
- **Excepciones por nivel:** factor distinto para combinación nivel + rol.
- **Excepciones por rama:** ajustes por rama.

Si **Productos varios en tabla B** está activo, configurar **Factores B compartidos** en el área.

#### Paso 4 — Productos del área

Pestaña **Productos** (con editor abierto):

1. **Agregar producto genérico** o líneas existentes.
2. Por cada producto:
   - **Sección** (separador), **Predeterminado**, **Carga manual** (horas por rol editables en cotización).
   - **Unifica valor** (si ramas unificadas) — horas por rama sin filas propias en A/B.
   - **Productos varios** (si B compartida) — comparte fila B con otros marcados.
3. Botón **Horas por nivel (roles del área)** — define la plantilla de horas por nivel/rama/rol (origen de la tabla resultado para cotización).
4. La sección «Referencia (no alimenta el cotizador)» en el formulario de línea es solo informativa.

#### Paso 5 — Matrices A y B

Pestaña **Vista de matrices**:

- Editar **tabla A** y **tabla B** por producto, nivel, rama y rol.
- Al **Cerrar editor de tabla**, en modo combinado se **recalculan** las matrices resultado.
- El campo **Reglas de tablas** (cabecera) resume: *Combinada · A: … · B: …*.

#### Paso 6 — Cerrar configuración

1. Verificar productos, niveles y matrices.
2. **Cerrar editor de tabla**.
3. Marcar **Cerrado**.

### 1.2 Uso en cotización

1. Crear cotización y abrir la pestaña del área.
2. **Seleccionar nivel del área** (y **rama** si el área usa ramas). Guardar el bloque.
3. Opcional: marcar **Es primera auditoría** (áreas de auditoría) — asigna el nivel de mayor riesgo.
4. **Cargar predeterminados** — incorpora productos marcados como predeterminados.
5. **Agregar múltiples líneas** — si está habilitado en el área.
6. Agregar o quitar productos; las **horas por rol** se calculan desde la plantilla del nivel/rama elegidos (salvo líneas con **carga manual**).
7. **Descuento %** y **Recargo %** del bloque (perfil socio; no aplica en fórmula en cadena).
8. **Ajustes** (gestores): línea de ajuste con horas editables y nota obligatoria.
9. **Resumen por rango** y totales del pie del bloque.

### 1.3 Particularidades combinada

- Cambiar **nivel** o **rama** recalcula horas y precios de las líneas (si «Permite cambiar el nivel» o el bloque aún no está congelado).
- Tras guardar el nivel en cotización normal (no auditoría), el nivel puede **congelarse** (`complexity_level_frozen`).
- Productos con **carga manual**: el usuario edita columnas de horas en la lista del bloque.
- El precio unitario se calcula por lista de precios × horas por rol (productos técnicos tarifa/h por rol).

---

## 2. Fórmula (`formula`)

Horas por rol = función del **volumen** de la línea y parámetros por producto/rol. Típico en áreas del grupo **Fórmula** (ej. BPO).

### 2.1 Configuración del área

#### Paso 1 — Tipo de tabla

En **Reglas de tablas**:

1. **Tipo de tabla de horas:** *Fórmula*.
2. **Niveles de complejidad:** al menos uno (se usa el primero por defecto en cotización; el selector de nivel **no se muestra** en el bloque).
3. **Volumen de prueba (vista fórmula):** solo para la matriz de configuración; **no afecta cotizaciones**.
4. **Redondear el mínimo a** — aplica a horas calculadas.

No aplican tablas A/B ni las opciones de unificación de combinada.

#### Paso 2 — Productos y fórmulas

Pestaña **Productos**:

1. Agregar productos al área.
2. En cada línea, sección **Configuración por volumen (producto)**:
   - **Tipo de cálculo:**
     - *Fórmula* — horas según volumen y parámetros por rol.
     - *Horas fijas* — horas constantes por rol (sin columna volumen en cotización).
   - **Referencia de volumen** — texto guía (ej. «Facturas por mes»). Se muestra en cotización.
   - **Volumen predeterminado** — solo sugerencia en configuración/prueba; en cotización el volumen inicial de línea es **1** (o **0** si horas fijas).
3. **Fórmula por rol del área** — por cada rol:
   - *Lineal* o *Umbral* (plantillas con parámetros numéricos).
   - Activar/desactivar fórmula por rol.
   - Para *Horas fijas*: campo **Horas fijas** por rol.

También se puede editar desde la **Vista de matrices** (matriz fórmula por producto y volumen de prueba).

#### Paso 3 — Vista de matrices (fórmula)

- Matriz por producto: columnas de roles, filas de productos.
- Permite probar fórmulas con el volumen de prueba del área.
- Iconos/enlaces abren el editor de fórmula por celda/rol.

#### Paso 4 — Cerrar configuración

Igual que el resto: cerrar editor y marcar **Cerrado**.

### 2.2 Uso en cotización

1. Abrir pestaña del área. **No hace falta elegir nivel** (se asigna automáticamente).
2. La lista de productos está disponible de inmediato (sin alerta de «seleccione nivel»).
3. **Cargar predeterminados** / **Agregar múltiples líneas** — según flags del área.
4. Por cada línea de producto con fórmula variable:
   - Columna **Referencia** (solo lectura).
   - Columna **Volumen** — editable; recalcula horas y precio al cambiar.
   - El volumen de la línea es **independiente** del volumen de prueba de configuración.
5. Productos con **horas fijas**: sin columna volumen; horas por rol fijas de configuración.
6. Columnas de **horas por rol** y **total** — calculadas (no editables salvo carga manual en producto).
7. **Descuento %** y **Recargo %** del bloque disponibles.

### 2.3 Particularidades fórmula

- Fórmulas **lineales** y por **umbral** usan parámetros por rol (minutos/unidad, pisos, etc.).
- El precio sigue la lista de precios del área × horas por rol.
- Persistencia del volumen: se guarda en `sale.order.line` vía RPC al editar (no depender del volumen de prueba del área).

---

## 3. Fórmula en cadena (`formula_chain`)

Tablas indexadas por **cantidad de empleados**; cada celda puede ser valor fijo o fórmula. El **nivel de complejidad** aplica un **% de aumento** en cadena. Típico en Payroll.

### 3.1 Configuración del área

#### Paso 1 — Tipo de tabla

En **Reglas de tablas**:

1. **Tipo de tabla de horas:** *Fórmula en cadena*.
2. **Roles del área** — columnas de la matriz (como en fórmula).
3. **No** se usan los «Niveles de complejidad» estándar de la pestaña superior para la cadena; en su lugar:

**Cadena: aumento % por nivel de complejidad**

- Agregar filas: **Nivel** + **% de aumento**.
- Solo esos niveles aparecen en cotización y en la vista previa.
- El primer nivel de la tabla es el predeterminado.

4. **Redondear el mínimo a** — aplica a horas de salida.

#### Paso 2 — Tablas por cantidad de empleados

Pestaña **Vista de matrices** (matriz cadena):

1. Crear **tablas** ordenadas por rango de empleados (`people_min` / `people_max`).
2. Por tabla: configurar **máximo de empleados**, **delta** (incremento entre tablas) y celdas por **producto × rol**:
   - Valor **fijo** (horas).
   - **Fórmula** (expresión con cantidad de empleados y parámetros).
3. **Empleados de prueba** y **Nivel de complejidad (prueba)** — solo vista previa en configuración.
4. Navegación por pestañas entre tablas de la cadena.

#### Paso 3 — Productos

Pestaña **Productos**:

- Agregar productos (sin botón «Horas por nivel» de combinada).
- Marcar predeterminados, secciones, carga manual si aplica.
- La configuración de horas vive en las **tablas cadena**, no en plantillas por nivel.

#### Paso 4 — Cerrar configuración

Cerrar editor y marcar **Cerrado**.

### 3.2 Uso en cotización

1. Abrir pestaña del área.
2. Campos del bloque:
   - **Cantidad de empleados** — determina qué tabla de la cadena se usa.
   - **Nivel del área** — solo si hay **más de un** nivel en la tabla de aumento %; si hay uno solo, queda oculto.
3. Guardar el bloque; al cambiar empleados o nivel se **recalculan** horas de todas las líneas.
4. Agregar productos (predeterminados, manual o múltiple).
5. Horas por rol: **solo lectura** (vienen de la tabla activa + % de nivel).
6. **No** hay descuento ni recargo % a nivel de bloque en este método.
7. Vista previa opcional de matriz cadena en cotización (según implementación JS del bloque).

### 3.3 Particularidades fórmula en cadena

- Resolución de tabla: según `chain_employee_count` del bloque y rangos `people_min`/`people_max` de cada tabla.
- Si no hay celda para un producto/rol, la hora es **0**.
- Líneas con **carga manual** en el producto siguen el comportamiento manual del módulo.
- El nivel debe pertenecer a la tabla de aumento % del área (validación al guardar).

---

## 4. Regular manual (`regular_manual`)

Cotización **línea a línea** con **horas y precio unitario editables**. Pensado para **Finanzas** (grupo `quoter_finanzas`).

### 4.1 Configuración del área

#### Paso 1 — Tipo de tabla

En **Reglas de tablas**:

1. **Tipo de tabla de horas:** *Regular manual*.
2. **Niveles de complejidad:** **exactamente uno** (restricción del sistema). Ese nivel se asigna automáticamente al bloque.
3. No hay matrices A/B ni matriz fórmula/cadena en **Vista de matrices**.

#### Paso 2 — Productos

- Agregar productos al área (secciones, predeterminados, etc.).
- **Carga manual** por producto: permite editar horas por rol en cotización.
- No se usa «Horas por nivel» de combinada.

#### Paso 3 — Opciones de cotización

- **Cargar predeterminados:** deshabilitado / no aplica — mensaje explícito para Finanzas.
- **Carga múltiple:** opcional según `bulk_line_load`.

### 4.2 Uso en cotización

1. Abrir pestaña del área — **sin** selector de nivel visible (nivel fijo del área).
2. La lista de líneas está **disponible de inmediato** (no requiere guardar nivel).
3. Agregar productos manualmente línea a línea.
4. Por línea:
   - **Precio unitario** — columna visible y editable (único método con esta columna en lista).
   - **Horas por rol** — editables (según flags de carga manual del producto).
   - **Total horas** — editable si el producto tiene «horas totales manual».
5. El precio puede fijarse manualmente (`regular_manual` usa `price_unit` de la línea, no solo cálculo por tarifas).
6. **Descuento %** y **Recargo %** del bloque disponibles.

### 4.3 Particularidades regular manual

- Un solo nivel de complejidad en configuración.
- No hay recálculo desde plantillas de nivel al cambiar producto (modo manual).
- Ideal para servicios atípicos o montos pactados fuera de matrices estándar.

---

## Resumen comparativo

| Aspecto | Combinada | Fórmula | Fórmula en cadena | Regular manual |
|---------|-----------|---------|-------------------|----------------|
| Niveles en config | Varios | Varios (auto 1.º) | Tabla aumento % | **Uno solo** |
| Nivel en cotización | Obligatorio elegir | Oculto (auto) | Si hay >1 en cadena | Oculto (fijo) |
| Empleados en cotización | — | — | **Cantidad de empleados** | — |
| Columna volumen | — | **Sí** (si fórmula) | — | — |
| Columna precio unitario | No | No | No | **Sí** |
| Matrices en config | A + B | Fórmula por rol | Tablas cadena | — |
| Cargar predeterminados | Sí | Sí | Sí | **No** |
| Descuento/recargo bloque | Sí | Sí | **No** | Sí |
| Permite cambiar nivel | Opción área | N/A | Según niveles cadena | N/A |

---

## Actualización del módulo

Tras cambios en código o vistas:

```bash
cd /ruta/al/proyecto && sudo make update m="quoter"
```

En el navegador, recarga forzada (**Ctrl+Shift+R**) si hay cambios JavaScript (matrices, bloque embebido).

---

*Versión del módulo al redactar: 15.0.6.6.18*
