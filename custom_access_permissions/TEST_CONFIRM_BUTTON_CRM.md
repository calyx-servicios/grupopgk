# Guía de pruebas: Botón Confirmar cotización desde CRM

## Resumen del cambio

El botón **Confirmar** en cotizaciones/presupuestos creados desde el módulo CRM solo es visible para usuarios con **Permisos PGK → Administrador**. Los usuarios con **Perfil Gerente** no pueden verlo ni ejecutarlo.

---

## 1. Actualizar el módulo

```bash
# Desde el directorio del proyecto
docker exec -it odoo-web odoo -c /etc/odoo/odoo.conf -d grupopgk-30012026 -u custom_access_permissions --stop-after-init
```

O desde la interfaz de Odoo:
- **Aplicaciones** → buscar "Custom Access Permissions" → **Actualizar**

---

## 2. Preparación de usuarios de prueba

### Usuario con Perfil Gerente
1. Ir a **Configuración** → **Usuarios y empresas** → **Usuarios**
2. Crear o editar un usuario de ventas
3. En **Permisos PGK**, seleccionar **Perfil Gerente**
4. Guardar

### Usuario con Administrador
1. Crear o editar otro usuario
2. En **Permisos PGK**, seleccionar **Administrador**
3. Guardar

---

## 3. Casos de prueba

### Caso 1: Cotización desde CRM – Usuario Perfil Gerente (debe fallar)

1. Iniciar sesión con el usuario **Perfil Gerente**
2. Ir a **CRM** → **Oportunidades**
3. Abrir una oportunidad existente o crear una nueva
4. Crear una cotización desde la oportunidad:
   - Botón **Nueva cotización** o **Cotización**
5. Completar la cotización (cliente, líneas de producto)
6. **Resultado esperado:** El botón **Confirmar** NO debe ser visible en el encabezado
7. Si se intenta confirmar por otro medio (API, RPC), debe mostrarse el mensaje:
   > "No tiene permisos para confirmar cotizaciones creadas desde CRM. Solo usuarios con perfil Administrador pueden realizar esta acción."

### Caso 2: Cotización desde CRM – Usuario Administrador (debe funcionar)

1. Iniciar sesión con el usuario **Administrador**
2. Ir a **CRM** → **Oportunidades**
3. Abrir una oportunidad
4. Crear una cotización desde la oportunidad
5. Completar la cotización
6. **Resultado esperado:** El botón **Confirmar** SÍ debe ser visible
7. Al hacer clic en **Confirmar**, la cotización debe pasar a estado **Venta**

### Caso 3: Cotización directa (no desde CRM) – Usuario Perfil Gerente (debe funcionar)

1. Iniciar sesión con el usuario **Perfil Gerente**
2. Ir a **Ventas** → **Cotizaciones** → **Nueva**
3. Crear una cotización directamente (sin oportunidad)
4. **Resultado esperado:** El botón **Confirmar** SÍ debe ser visible (comportamiento normal)
5. La confirmación debe funcionar correctamente

### Caso 4: Verificación de protección por API

1. Con usuario **Perfil Gerente**, obtener el ID de una cotización creada desde CRM
2. En shell de Odoo:

```bash
docker exec -it odoo-web odoo shell -d grupopgk-30012026
```

```python
# Dentro del shell
order = env['sale.order'].browse(ID_COTIZACION_CRM)
order.action_confirm()  # Debe lanzar AccessError
```

3. **Resultado esperado:** Se debe lanzar `AccessError` con el mensaje de permisos

---

## 4. Checklist rápido

| # | Escenario | Usuario | Origen | ¿Ve botón? | ¿Puede confirmar? |
|---|-----------|---------|--------|------------|-------------------|
| 1 | Cotización CRM | Perfil Gerente | Oportunidad | No | No |
| 2 | Cotización CRM | Administrador | Oportunidad | Sí | Sí |
| 3 | Cotización directa | Perfil Gerente | Ventas | Sí | Sí |
| 4 | Cotización directa | Administrador | Ventas | Sí | Sí |

---

## 5. Solución de problemas

- **El botón sigue visible para Perfil Gerente en cotizaciones CRM:**  
  Verificar que el módulo se actualizó correctamente y que la cotización tiene `opportunity_id` (creada desde una oportunidad).

- **Error al actualizar el módulo:**  
  Comprobar que `sale_crm` está instalado (el módulo CRM de ventas).
