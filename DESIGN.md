# DESIGN.md — TestPilot SFCC

> Memoria de diseño canónica del **dashboard interno** y de todo material visual (slides, reportes Markdown renderizados). Da **memoria**: tokens, roles visuales, componentes, racional y anti-patrones. El criterio de producto vive en [`PRODUCT.md`](./PRODUCT.md) y lo restringe todo lo de aquí.
>
> Estándar base: [Google `design.md`](https://github.com/google-labs-code/design.md) alineado con [impeccable](https://github.com/pbakaus/impeccable). Linteable con `npx @google/design.md lint DESIGN.md`. Mantenido por el playbook `design-steward` (`.ai/agents/`).

---

> ⚠️ **Realineado 2026-06-03** (branch `rework/storefront-audit-scope`): se agregan la ventana de lenguaje natural, la matriz genérica perfiles×flows, el documento de auditoría de 6 dimensiones, los modos gate/exploratorio y la evidencia por hallazgos (ADR-003). Criterio de producto vigente: `PRODUCT.md` §1 y §6.

## 1. Principios

TestPilot es una **herramienta operativa de ingeniería**, no un producto de marketing. El diseño sirve a dos preguntas: *¿el ingeniero entiende el veredicto en menos de 10 minutos?* y *¿un miembro no-técnico entiende el documento de auditoría sin ayuda?* Siete principios derivados de [`PRODUCT.md`](./PRODUCT.md):

1. **Veredicto antes que decoración.** El semáforo y el "qué hacer" ocupan el lugar de honor. Tablas y gráficos son drill-down.
2. **Dos lectores, una jerarquía.** El ingeniero quiere densidad de señal (datos crudos compactos); Valentina (QA/PM) quiere el resumen legible. Resolución: **resumen en prosa primero, drill-down técnico después** — nunca dos UIs separadas (un reporte, dos lectores — PRODUCT.md §5.2).
3. **El color es semántico, nunca ornamental.** Verde/amarillo/rojo significan estado de gate. No se usan para "dar vida".
4. **Monoespaciado para lo que es dato.** IDs, métricas, HTTP codes, JSON y rutas van en mono — son verificables, no prosa.
5. **Honestidad de estado.** "Calibrando baseline" se ve distinto a "verde". Un run **exploratorio** se ve distinto a un run **gate**. El vacío y la incertidumbre tienen su propio tratamiento visual, no se disfrazan.
6. **Hechos ≠ hipótesis.** Un hallazgo determinista (colector) se presenta como hecho con evidencia; una hipótesis del agente se presenta SIEMPRE como hipótesis con su `confidence` visible — el tratamiento visual los distingue sin leer (P7).
7. **Predicar con el ejemplo.** TestPilot audita accesibilidad WCAG AA de storefronts — su propia UI cumple AA sin excepciones (§6).

## 2. Design tokens

### 2.1 Color

Paleta funcional. Base neutra fría + tres colores de estado + un acento interactivo único. Todos los pares texto/fondo cumplen **WCAG AA (≥4.5:1 en texto normal, ≥3:1 en texto grande/UI)**.

| Token | Valor | Rol |
| :--- | :--- | :--- |
| `--color-bg` | `#0F1419` | Fondo de la app (dark, reduce fatiga en uso prolongado) |
| `--color-surface` | `#1A2027` | Paneles, filas de tabla |
| `--color-surface-raised` | `#222A33` | Modales, drawer de detalle |
| `--color-border` | `#2E3742` | Bordes 1px, separadores |
| `--color-text` | `#E6EAEF` | Texto primario |
| `--color-text-muted` | `#9AA7B4` | Texto secundario, labels (≥4.5:1 sobre `--color-bg`) |
| `--color-status-green` | `#3FB950` | Verde: gate aprobado |
| `--color-status-amber` | `#D29922` | Amarillo: degradación vs baseline |
| `--color-status-red` | `#F85149` | Rojo: fallo funcional |
| `--color-status-neutral` | `#6E7B8A` | Bootstrap / sin baseline / pendiente |
| `--color-accent` | `#2F81F7` | Único color interactivo: links, botón primario, foco |
| `--color-focus-ring` | `#2F81F7` | Anillo de foco (2px, visible en teclado) |

> **Racional:** los tres colores de estado son los héroes visuales del producto y solo aparecen como estado. El acento azul es el **único** color interactivo, para que "clickable" sea inconfundible. La base es dark porque el dashboard se mira muchas veces al día junto a un IDE oscuro.

### 2.2 Tipografía

| Token | Valor | Uso |
| :--- | :--- | :--- |
| `--font-sans` | `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif` | Chrome de la UI, prosa |
| `--font-mono` | `"JetBrains Mono", "SF Mono", "Cascadia Code", monospace` | IDs, métricas, HTTP, JSON, rutas, código de flow |
| `--text-xs` | 12px / 1.4 | Labels, metadata |
| `--text-sm` | 14px / 1.5 | Cuerpo base de tablas |
| `--text-base` | 16px / 1.5 | Cuerpo, prosa |
| `--text-lg` | 20px / 1.3 | Títulos de sección |
| `--text-xl` | 28px / 1.2 | Título de pantalla |
| `--weight-regular` | 400 | Cuerpo |
| `--weight-medium` | 500 | Labels, énfasis |
| `--weight-bold` | 700 | Títulos, veredicto |

> **Racional:** una sola familia sans del sistema (cero costo de carga, look nativo) + una mono para datos. Sin display fonts ni tipografías "de marca": no aporta a un tool interno.

### 2.3 Espaciado, radio, borde, sombra

| Token | Valor | Nota |
| :--- | :--- | :--- |
| `--space-1 … --space-6` | 4 · 8 · 12 · 16 · 24 · 32 px | Escala base 4px |
| `--radius-sm` | 4px | Inputs, badges |
| `--radius-md` | 8px | Paneles, modales |
| `--border-width` | 1px | Único grosor de borde |
| `--shadow` | `0 1px 2px rgba(0,0,0,.4)` | **Única** sombra permitida; solo en modal/drawer |

> **Racional:** sombras casi ausentes. La jerarquía se construye con color de superficie y borde, no con elevación difusa (evita el look "glass/floating" genérico).

## 3. Roles visuales del semáforo

El componente central del producto. Estado = forma + color + texto, nunca color solo (accesibilidad y daltonismo).

| Estado | Color | Glifo | Texto | Cuándo |
| :--- | :--- | :--- | :--- | :--- |
| **Verde** | `--color-status-green` | ● | "Apto para deploy" | Sin errores funcionales y performance dentro de p95 |
| **Amarillo** | `--color-status-amber` | ▲ | "Degradación — revisar" + subtipo | Tres subtipos, siempre visibles como sub-label mono: `performance_regression` · `infrastructure_error` ("infraestructura, no producto") · `human_review` ("requiere revisión humana") |
| **Rojo** | `--color-status-red` | ■ | "Bloqueado — fallo funcional" | Error funcional (HTTP 5xx, elemento faltante, paso fallido) |
| **Neutral** | `--color-status-neutral` | ◌ | "Calibrando baseline (n/14)" | Bootstrap: <14 runs exitosos del par perfil×flow, sin p95 confiable |

> **Racional:** glifos distintos por estado → legible sin color. El estado neutral es de primera clase: el bootstrap silencioso del producto (invariante #4) se ve, no se oculta. El subtipo del amarillo decide la acción del usuario (retry vs revisar vs escalar) — por eso nunca se omite.

**Marca de modo (realineación):** todo run muestra su modo junto al semáforo. `gate` = sin adorno (es el default). `exploratory` = badge `◇ exploratorio` en `--color-status-neutral` + el semáforo se rotula "informativo — no es veredicto de deploy" y **no** usa el texto "Apto para deploy". Un run exploratorio jamás puede confundirse con un gate (C11).

## 4. Componentes

- **Botón primario:** fondo `--color-accent`, texto `#fff`, `--radius-sm`. Uno por pantalla (lanzar run / confirmar y lanzar). Secundarios: borde + texto, sin relleno.
- **Badge de estado:** glifo + label, `--text-xs` mono, color de estado. Usado en filas de historial.
- **Tabla de historial:** filas en `--color-surface`, separador `--color-border`, métricas en `--font-mono` alineadas a la derecha. Hover sutil (sin animación de escala). Columna de modo: badge `◇` en runs exploratorios.
- **Fila de hallazgo:** badge de estado + **chip de dimensión** (§4.1) + paso + URL (mono, truncada con `title`) + links a evidencia (screenshot, entrada de red). Es la unidad de evidencia (principio #3 de PRODUCT.md): **sin evidencia no se renderiza hallazgo**.
- **Bloque de hipótesis (P7):** visualmente distinto del hallazgo — borde punteado `--color-border`, prefijo fijo "Hipótesis del agente", `confidence` visible en mono (`0.62`), y badge `▲ human_review` cuando `requires_human_review=true`. **Nunca** usa los colores de estado como fondo: una hipótesis no es un veredicto.
- **Bloque de métrica:** valor en mono `--text-lg`, label en `--text-xs muted` debajo. Sin ícono decorativo, sin sparkline en MVP.
- **Resumen de red (drill-down):** tabla mono de controllers SFRA (patrón · count · p95 ms, orden desc por p95) + 3 bloques de métrica para CWV (LCP/CLS/TTFB) por perfil + contador de requests fallidos que enlaza al HAR. Vive colapsado bajo cada par perfil×flow.
- **Estado vacío:** texto `muted` + acción sugerida. Nunca ilustración decorativa.
- **Error de validación (JSON Schema gate):** panel rojo con el mensaje descriptivo del schema, en mono. El usuario debe poder copiar el error.

### 4.1 Chips de dimensión de auditoría (realineación)

Las 6 dimensiones tienen identidad **textual con glifo monocromo** — nunca color propio (el color queda reservado al estado §3) ni íconos ilustrativos:

| Dimensión | Chip |
| :--- | :--- |
| Integridad de comercio | `$ comercio` |
| Rendimiento | `~ rendimiento` |
| Correctitud de locale | `@ locale` |
| Accesibilidad | `a11y` |
| Salud del cliente | `! cliente` |
| Integridad de contenido | `# contenido` |

> **Racional:** chips mono `--text-xs` con borde, color `--color-text-muted`. La severidad del hallazgo (info/warning/critical) usa los colores de estado; la dimensión solo etiqueta. Así un hallazgo "critical de locale" se lee en dos tokens sin ambigüedad.

### 4.2 Ventana de lenguaje natural (realineación — entrada principal)

El momento de mayor riesgo de confianza del producto. Tres estados, un solo flujo:

1. **Entrada:** textarea con placeholder de ejemplo real ("revisa la PDP de un producto en oferta y confirma que el descuento se aplique"), contador `n/2000`, selector de modo (gate default · exploratorio con tooltip de qué significa). El editor JSON queda detrás de un toggle "modo avanzado".
2. **Preview (obligatorio, no saltable):** panel con (a) la **explicación en prosa** del traductor ("Voy a recorrer…") como elemento principal, y (b) chips estructurados: flows elegidos, perfiles, productos, modo. El config JSON completo va colapsado debajo. CTA único: "Confirmar y lanzar". Acción secundaria: "Editar instrucción". **Nada se ejecuta sin este paso.**
3. **Ambigüedad / rechazo:** la pregunta de clarificación se muestra como conversación (no como error); el rechazo por catálogo lista los flows disponibles como chips clickeables. Ningún rechazo es un dead-end: siempre ofrece el siguiente paso.

### 4.3 Matriz de ejecución en vivo (realineación — genérica)

- **Filas = perfiles del run · columnas = flows del run** — ambas derivadas del payload, jamás hardcodeadas. Con `full_journey`, las columnas son los flows expandidos de la composición, en su orden.
- **Celda:** glifo + estado (`◌ pending` · `… running` con paso actual en `--text-xs` · `● passed` · `■ failed` · `▲ error`). Los pasos `phase: setup` se distinguen con label `setup` muted.
- La celda completada enlaza al detalle del par perfil×flow. Sin animaciones: el cambio de estado es cambio de color/glifo (`aria-live`).
- La matriz escala: 1 celda (módulo único, 1 perfil) hasta 18 (3 perfiles × 6 flows) sin cambiar de componente.

### 4.4 Documento de auditoría (realineación — el segundo entregable)

- **Orden fijo:** (1) resumen ejecutivo en prosa (lo que lee Valentina) · (2) las 6 dimensiones como secciones, cada una con sus hallazgos (filas de hallazgo §4) · (3) hipótesis del agente (bloques §4) · (4) link al documento Markdown completo (S3).
- Dimensión sin hallazgos muestra "Sin hallazgos" en muted — **presencia explícita**, no se omite la sección (silencio honesto: que no se haya encontrado nada también es información).
- Dimensión no recolectada (colector falló) muestra `◌ no recolectada` — distinto de "sin hallazgos".
- **Degradación del agente:** si `synthesis_available=false`, el resumen ejecutivo se reemplaza por el aviso "Síntesis no disponible — se muestran los hallazgos crudos" en neutral. El documento sigue siendo útil.
- El semáforo NO aparece dentro del documento de auditoría (C10: el veredicto vive arriba, calculado por regla — el documento describe, no juzga).

## 5. Layout

- **Grid:** contenido máximo `1200px` centrado; navegación lateral fija de 2 ítems (Ambientes · Lanzar+Historial).
- **Pantalla Lanzar:** la ventana NL (§4.2) es el elemento principal; al lanzar, transiciona a la matriz en vivo (§4.3) en la misma pantalla.
- **Jerarquía de la pantalla de resultados (orden vertical):** (1) semáforo + veredicto + marca de modo · (2) matriz del run (estado final por celda) · (3) **documento de auditoría** (§4.4) · (4) métricas clave por perfil + resumen de red colapsado · (5) JSON crudo colapsado.
- **Footer global:** `run_id` actual + modo + runs restantes del día (`n/10`) + versión de API (`v2`), en mono `--text-xs muted`. El costo y la versión son siempre visibles (principios de PRODUCT.md §5).
- **Breakpoints:** `≥1024px` (desktop, layout completo) · `<1024px` (la nav lateral colapsa a top-bar; tablas y la matriz hacen scroll horizontal, no se reflujan a tarjetas).

## 6. Accesibilidad (no negociable)

- Contraste **WCAG AA** en todo par texto/fondo (verificar tokens de §2.1).
- Estado **nunca solo por color** — siempre glifo + texto (§3).
- Anillo de foco visible (`--color-focus-ring`, 2px) en navegación por teclado.
- Targets táctiles ≥44px en la top-bar móvil.
- `aria-live` en el panel de resultados en vivo para que el cambio de estado se anuncie.

## 7. Anti-patrones (AI slop — prohibido)

Derivado de "Fixing Visual AI Slop". Si aparece alguno, el `design-steward` lo rechaza:

- ❌ **Gradientes morados / multicolor.** El color es semántico (§3). Fondos planos.
- ❌ **Glass panels / blur / transparencias decorativas.** Jerarquía por superficie + borde (§2.3).
- ❌ **Cards decorativas con sombra flotante.** Una sola sombra, solo en modal/drawer.
- ❌ **Hero vacío con título gigante centrado.** La pantalla abre con datos o con el veredicto.
- ❌ **Métricas ornamentales** (números grandes sin contexto, "+99%" decorativo). Toda métrica enlaza a su evidencia o a su baseline.
- ❌ **Íconos decorativos** que no comunican estado o acción.
- ❌ **Animaciones de entrada / parallax / escala en hover.** Como mucho, transición de color ≤120ms.
- ❌ **Emojis como UI** en el dashboard (sí permitidos en el reporte Markdown si aportan al semáforo: 🟢🟡🔴).
- ❌ **Hipótesis del agente vestida de hecho.** Una hipótesis sin su `confidence` visible, o con fondo de color de estado, es slop de confianza — viola P7 (§4, bloque de hipótesis).
- ❌ **Columnas de flow hardcodeadas.** La matriz que asume "checkout" o exactamente 2 flows es deuda inmediata (RF-29).
- ❌ **Iconografía ilustrativa para las dimensiones.** Las dimensiones usan chips textuales (§4.1); nada de íconos de carrito/lupa/escudo.

## 8. Material derivado (slides, reportes)

Slides de estación y reportes Markdown renderizados a PDF deben aplicar esta misma memoria: paleta de §2.1, mono para datos, **un concepto por slide**, marcar demos con `SIGUE DEMO:`, footer con progreso. El semáforo verde/amarillo/rojo es el motivo visual recurrente. Storyboard fuente: `.hardcore-ai/estacion-6/slides/`.

## 9. Cómo se usa este documento

- **`design-steward`** lo lee **antes** de generar cualquier UI, slide o componente, y justifica cada decisión contra estos tokens.
- Cambios aquí deben pasar el linter: `npx @google/design.md lint DESIGN.md`.
- Un cambio de invariante o audiencia en [`PRODUCT.md`](./PRODUCT.md) obliga a revisar este archivo.

---

*TestPilot SFCC — Hardcore AI Cohorte 2. Última actualización: 2026-06-03 (realineación de alcance: ventana NL, matriz genérica, documento de auditoría, modos, chips de dimensión, principios 2/6/7).*
