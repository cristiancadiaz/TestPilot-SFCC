# Business Logic Model — MD0 Dashboard Web Interno

## Propósito desde la perspectiva del producto

El Dashboard es la **superficie de operación principal** del sistema. Sin él, TestPilot solo es una API consumible vía `curl` o agentes CI/CD — y eso excluye al ~60% del equipo (PMs, QA manual, líderes técnicos que validan releases sin escribir scripts). El Dashboard convierte a TestPilot en un producto **accionable por personas**, no solo por máquinas.

**Tres outcomes de negocio que materializa el Dashboard:**

1. **Reducir tiempo a decisión "merge/no-merge"** — de 4–8 h (QA manual) a **30 segundos de lectura del semáforo** en la pantalla del PO/Tech Lead.
2. **Aumentar la frecuencia de uso** — al eliminar la fricción CLI, se espera ≥4× más runs/semana en sprint 4.
3. **Auditabilidad y trazabilidad** — el historial filtrable reemplaza el "¿quién testeó este release?" por una vista única consultable por compliance.

---

## Pantallas (5) y responsabilidades

### P1 — Gestión de Ambientes (`/environments`)
**Acción principal:** registrar y editar la configuración de los 3 ambientes (sandbox, development, staging) **una sola vez por ambiente**.

**Datos editables:**
- `environment_id` (read-only tras creación — clave estable)
- `display_name`
- `store_url`
- `env_access_secret_path` (path en Secrets Manager — NO se muestra ni edita el valor)
- `shopper_secret_path` (path en Secrets Manager — NO se muestra ni edita el valor)
- `anti_bot_whitelisted` (boolean)
- `active` (boolean)

**Operaciones soportadas:** Listar / Crear / Editar / Desactivar. **No hay borrado físico** — solo desactivación para preservar trazabilidad histórica de runs.

**Regla de negocio crítica:** los valores reales de las credenciales **nunca pasan por el browser**. El dashboard solo gestiona paths. Los secretos viven exclusivamente en AWS Secrets Manager y son resueltos en el backend al momento de ejecución.

---

### P2 — Lanzamiento de Run (`/runs/new`)
**Acción principal:** configurar y disparar una ejecución de pruebas seleccionando un ambiente registrado.

**Inputs visibles:**
- Selector de `environment_id` (dropdown poblado desde P1, solo ambientes `active=true`)
- Productos a testear (lista de `{search_term, validate_variant}`)
- Flows a ejecutar (checkboxes: `checkout-full`, `checkout-card-declined`)
- Perfiles (checkboxes: `mobile-co`, `desktop-co`, `desktop-ec`)
- Toggle `screenshot_on_success` (default ON en MVP)
- Toggle `screenshot_on_error` (default ON, no editable — invariante de auditoría)

**Vista previa:** muestra el JSON que se enviará a `POST /v1/run` para que el ingeniero verifique antes de lanzar.

**Validaciones cliente:** al menos 1 producto, al menos 1 flow, al menos 1 perfil, ambiente activo.

**Sin credenciales en el payload:** el JSON enviado NO incluye `store_url` ni credenciales — solo `environment_id`. El backend resuelve el resto.

---

### P3 — Vista en Tiempo Real (`/runs/{run_id}/live`)
**Acción principal:** observar la ejecución en curso de un run mientras está corriendo.

**Información mostrada:**
- Encabezado: ambiente, store_url (read-only), timestamp de inicio
- Grilla 3×N: filas = perfiles activos (mobile-co, desktop-co, desktop-ec), columnas = pasos del flow
- Por cada celda: estado actual (`pending` / `running` / `success` / `failed` / `skipped`)
- Por cada perfil: indicador de duración acumulada
- Botón "Cancelar run" (post-MVP — fuera de scope hasta sprint 3)

**Estrategia de actualización:** **polling cada 3 s** contra `GET /v1/runs/{run_id}/status`. Decisión: polling > WebSocket para MVP — más simple, robusto a desconexiones, y la cadencia 3 s es suficiente (los pasos típicos duran 5–30 s).

**Transición automática:** al detectar `state == "completed"` o `state == "failed"`, redirige a `/runs/{run_id}` (P4).

---

### P4 — Detalle de Run (`/runs/{run_id}`)
**Acción principal:** consumir el reporte completo de una ejecución terminada.

**Secciones (orden de lectura):**
1. **Semáforo destacado** (verde/amarillo/rojo) — el primer pixel que ve el usuario.
2. **Banner de auditoría**: "Órdenes creadas: 0" — siempre visible, no colapsable. Si fuera ≠0, banner rojo bloqueante.
3. **Resumen por perfil**: 3 cards (mobile-co, desktop-co, desktop-ec) con duración total, status y semáforo individual.
4. **Tabla de pasos** por perfil y flow, con duración vs baseline p95, status, y miniatura de screenshot.
5. **Galería de screenshots**: ampliable, ordenada por `{perfil}/{flujo}/{paso}-{ok|fail}.png`.
6. **Comparación con baseline**: gráfico de barras p95 vs current por paso (post-MVP si baseline tiene <14 runs).
7. **Acciones**: descargar reporte JSON, descargar reporte Markdown.

**Modo bootstrap:** si `bootstrap_mode=true`, banner azul informativo: *"Sistema en aprendizaje (run X/14 — no se emiten alertas amarillas)"*.

---

### P5 — Historial de Ejecuciones (`/runs`)
**Acción principal:** auditar ejecuciones pasadas y detectar tendencias.

**Filtros disponibles:**
- Rango de fechas (default: últimos 7 días)
- Ambiente (`environment_id`)
- Semáforo (verde / amarillo / rojo / todos)
- Flow (`checkout-full` / `checkout-card-declined` / todos)

**Columnas de la tabla:**
- Fecha/hora (ISO, ordenado desc por default)
- Ambiente
- Semáforo (chip de color)
- Duración total
- Perfiles ejecutados (chips)
- Acción: ver detalle → P4

**Paginación:** server-side, 25 runs por página. Sin scroll infinito (decisión: tabla paginada es más auditable y menos confusa para uso ocasional).

---

## Flujo de usuario crítico (Carolina, Tech Lead — pre-deploy)

```
1. Carolina termina su PR de un cartridge custom.
2. Abre dashboard → P2 "Nuevo Run"
3. Selecciona ambiente = "staging" (ya registrado por Andrés hace 2 meses)
4. Selecciona productos del baseline + ambos flows + 3 perfiles
5. Click "Lanzar" → POST /v1/run → redirige a P3
6. Observa por ~8-12 min cómo avanzan los 3 perfiles en paralelo
7. Al completarse, dashboard la lleva a P4
8. Lee semáforo: VERDE → merge aprobado. AMARILLO → revisa baseline. ROJO → no merge.
9. Si ROJO, descarga JSON, lo adjunta al PR comment, asigna debugging.
```

**Tiempo total de Carolina con el sistema:** ~30 segundos de interacción + ~10 min de espera pasiva (puede hacer otra cosa).

---

## Modelo de datos consumido (read-only desde dashboard)

| Recurso | Endpoint API | Frecuencia |
|---|---|---|
| Lista de ambientes | `GET /v1/environments` | Al cargar P1, P2 |
| Detalle de ambiente | `GET /v1/environments/{id}` | Al editar en P1 |
| Crear/editar ambiente | `POST/PUT /v1/environments` | Acción usuario P1 |
| Lanzar run | `POST /v1/run` | Acción usuario P2 |
| Estado de run en curso | `GET /v1/runs/{id}/status` | Polling 3s en P3 |
| Detalle de run terminado | `GET /v1/runs/{id}` | Al cargar P4 |
| Lista histórica | `GET /v1/runs?filters...` | Al cargar P5 |
| Screenshot individual | `GET /v1/runs/{id}/screenshots/{path}` | Lazy load en P4 |

---

## Decisiones de UX justificadas

| Decisión | Justificación |
|---|---|
| Polling 3 s (no WebSocket) en P3 | Simplicidad operativa, robusto a desconexiones, cadencia suficiente para pasos de 5–30 s |
| No borrado físico de ambientes | Auditoría: runs históricos deben poder mostrar a qué ambiente se ejecutaron, incluso si fue retirado |
| Banner permanente "Órdenes: 0" | Principio P1 (cero contaminación) debe ser visualmente verificable en cada reporte |
| Tabla paginada en historial | Auditabilidad > velocidad de scroll. Uso ocasional, no consumo masivo |
| Sin login multi-usuario en MVP | Equipo de 5–8 personas internas, API key compartida vía variable de entorno del browser (próxima iteración: SSO) |
