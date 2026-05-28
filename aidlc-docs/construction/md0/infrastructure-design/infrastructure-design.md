# Infrastructure Design — MD0 Dashboard Web Interno

## Scope
MD0 no introduce servicios cloud nuevos — se sirve como **archivos estáticos desde el mismo proceso FastAPI** (decisión D-MD0-04). La infraestructura cubre:
1. Build pipeline del dashboard
2. Empaquetado dentro de la imagen Docker existente
3. Configuración de FastAPI para servir estáticos
4. Headers de seguridad

---

## 1. Build pipeline del dashboard

### Estructura de archivos
```
src/dashboard/
├── package.json           # dependencies + scripts
├── pnpm-lock.yaml         # lockfile commited
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.ts
├── index.html             # entry point Vite
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/
│   │   └── client.ts
│   ├── components/
│   │   ├── TrafficLight.tsx
│   │   ├── ScreenshotThumbnail.tsx
│   │   └── ...
│   ├── hooks/
│   │   ├── usePolling.ts
│   │   ├── useEnvironments.ts
│   │   └── useRunFilters.ts
│   ├── pages/
│   │   ├── EnvironmentsPage.tsx
│   │   ├── NewRunPage.tsx
│   │   ├── LiveRunPage.tsx
│   │   ├── RunDetailPage.tsx
│   │   └── HistoryPage.tsx
│   └── types/
│       └── api.ts          # interfaces TS proyectadas del backend
└── dist/                  # output del build — NO commited, generado en CI
```

### Scripts npm
```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint src",
    "test": "vitest"
  }
}
```

### Configuración Vite
```typescript
// vite.config.ts
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    sourcemap: false,           // SECURITY-09: no exponer source maps en prod
    rollupOptions: {
      output: { manualChunks: { vendor: ['react', 'react-dom'] } },
    },
  },
  server: {
    proxy: {
      '/v1': 'http://localhost:8000',  // dev: proxy a FastAPI local
    },
  },
});
```

---

## 2. Integración en Dockerfile

El `Dockerfile` existente (definido en U0) se extiende con un **multi-stage build** para evitar incluir Node en la imagen final:

```dockerfile
# ---------- Stage 1: build del dashboard ----------
FROM node:20-alpine AS dashboard-builder
WORKDIR /build
COPY src/dashboard/package.json src/dashboard/pnpm-lock.yaml ./
RUN npm install -g pnpm@9 && pnpm install --frozen-lockfile
COPY src/dashboard/ ./
RUN pnpm run build  # genera ./dist/

# ---------- Stage 2: runtime (Playwright + FastAPI) ----------
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy
WORKDIR /app

# Crear usuario no-root (SECURITY-13)
RUN useradd --create-home --shell /bin/bash appuser

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY src/ src/
COPY specs/ specs/

# Copiar dist/ del builder al runtime
COPY --from=dashboard-builder /build/dist /app/src/dashboard/dist

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Cambios respecto al U0 Dockerfile original:**
- Stage 1 nuevo: instala Node + pnpm, hace build del dashboard.
- Stage 2: igual al U0 anterior + `COPY --from=dashboard-builder` para incluir `dist/`.
- Resultado: imagen final NO contiene Node, sí contiene `dist/` estático.

---

## 3. Configuración FastAPI para servir estáticos

```python
# src/api/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI(title="TestPilot SFCC API", version="1.0.0")

# Endpoints API: definidos primero (prioridad de routing)
app.include_router(api_router, prefix="/v1")

# Dashboard estático: catch-all al final
DASHBOARD_DIR = Path(__file__).parent.parent / "dashboard" / "dist"
if DASHBOARD_DIR.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(DASHBOARD_DIR), html=True),
        name="dashboard",
    )
```

**Comportamiento:**
- `GET /v1/...` → API endpoints (manejados por router)
- `GET /` → `index.html` del dashboard
- `GET /assets/*.js` → archivos estáticos del bundle
- `GET /any-spa-route` → fallback a `index.html` (SPA routing client-side)

**Si `DASHBOARD_DIR` no existe** (ej. en tests unitarios o dev sin build), el mount se omite — la API sigue funcional.

---

## 4. Variables de entorno requeridas

MD0 no introduce variables nuevas — consume el contrato del backend. Las variables que afectan al dashboard indirectamente:

| Variable | Propietario | Uso en MD0 |
|---|---|---|
| `API_KEY` | Backend env var (Secrets Manager → ECS) | El usuario ingresa esta misma key en el modal del dashboard al primer acceso |
| (ninguna en cliente) | — | El dashboard no lee ninguna env var en build time — todas las URLs son relativas (`/v1/...`) |

**Decisión:** sin `.env` para el frontend. Todo lo que necesita en build es estático. La API key se ingresa en runtime via prompt en `sessionStorage`.

---

## 5. Servir CSP headers desde FastAPI

```python
# src/api/middleware.py
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        path = request.url.path
        if path == '/' or path.endswith('.html'):
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "img-src 'self' data: https://*.s3.amazonaws.com; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "connect-src 'self';"
            )
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

# en main.py
app.add_middleware(SecurityHeadersMiddleware)
```

**Cubre:** NFR-MD0-S6, defensa frente a clickjacking, MIME sniffing.

---

## 6. CI pipeline para MD0

Conceptual (no implementado — se documenta para sprint 0 de implementación):

```yaml
# .github/workflows/build.yml (extracto)
jobs:
  dashboard-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - run: corepack enable pnpm
      - run: cd src/dashboard && pnpm install --frozen-lockfile
      - run: cd src/dashboard && pnpm run lint
      - run: cd src/dashboard && pnpm run test
      - run: cd src/dashboard && pnpm audit --audit-level=high  # SECURITY-08

  docker-build:
    needs: [dashboard-test, backend-test]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/build-push-action@v5
        with: { tags: testpilot-sfcc:${{ github.sha }} }
```

---

## 7. Despliegue

**MVP:** ECS Fargate con imagen única `testpilot-sfcc:{sha}` que contiene backend + dashboard.

**Task definition:**
- CPU: 1 vCPU
- RAM: 2 GB (suficiente para FastAPI + Playwright en runs paralelos)
- Puerto: 8000
- Health check: `GET /health` (definido en U4)

**Servicio:**
- 1 task en MVP (single instance — el sistema es interno, baja concurrencia)
- ALB con HTTPS termination + WAF interno
- Acceso restringido a VPN corporativa

**Escalado:** no en MVP. Si crece, escalado por CPU >70% con max 3 tasks.

---

## 8. Compatibilidad con desarrollo local

```bash
# Terminal 1: backend
cd /repo
uvicorn src.api.main:app --reload --port 8000

# Terminal 2: dashboard (con HMR)
cd src/dashboard
pnpm dev
# Vite levanta http://localhost:5173 con proxy a :8000 para /v1
```

**Desarrollo:** Vite dev server + proxy → desarrolladores ven cambios en <500ms.
**Producción:** un solo proceso FastAPI sirve todo.

---

## Resumen de cambios infra MVP

| Componente | Antes (sin MD0) | Después (con MD0) |
|---|---|---|
| Dockerfile | Single-stage Python+Playwright | Multi-stage (Node builder + Python runtime) |
| Tamaño imagen | ~1.5 GB | ~1.5 GB + ~5 MB dashboard (negligible) |
| Build time | ~3 min | ~4 min (build dashboard agrega ~1 min) |
| FastAPI app | Solo API `/v1/*` | API `/v1/*` + estáticos en `/` |
| Secrets/env vars nuevos | — | Ninguno |
| Servicios AWS nuevos | — | Ninguno |
| Headers HTTP nuevos | — | CSP + 3 más |
