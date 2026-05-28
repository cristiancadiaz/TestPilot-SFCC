# Deployment Architecture — MD0 Dashboard Web Interno (2026-05-28)

MD0 no introduce servicios AWS propios — se despliega como archivos estáticos dentro del mismo proceso FastAPI del ECS task de U4. Este diagrama muestra los dos entornos: desarrollo local y producción en ECS Fargate.

---

## Diagrama — Producción (ECS Fargate)

```mermaid
graph TB
    subgraph "Usuario final"
        BROWSER["🌐 Browser\n(equipo interno / VPN)"]
    end

    subgraph "AWS — ap-northeast-1 (o región configurada)"
        subgraph "Networking"
            ALB["⚖️ ALB (internal)\nHTTPS :443\nTLS 1.2+ / ACM cert\nWAF core rules"]
        end

        subgraph "ECS Fargate — testpilot-sfcc:{sha}"
            subgraph "FastAPI process :8000"
                ROUTER["🔀 Router\n/v1/* → API handlers\n/ → StaticFiles mount"]
                STATIC["📦 StaticFiles\nsrc/dashboard/dist/\n(bundle React + Vite)"]
                MIDDLEWARE["🛡️ SecurityHeadersMiddleware\nCSP · X-Frame-Options\nX-Content-Type-Options\nReferrer-Policy"]
                API["⚙️ API Handlers\n/v1/run · /v1/runs\n/v1/environments\n/health"]
            end
        end

        subgraph "Almacenamiento (consumido vía API, no directamente por MD0)"
            DDB["🗄️ DynamoDB\ntestpilot-environments\ntestpilot-runs"]
            S3["🪣 S3\ntestpilot-screenshots-*\n(URLs pre-signed para thumbnails)"]
            SM["🔑 Secrets Manager\ntestpilot/*"]
        end

        CW["📊 CloudWatch\nLogs + Métricas"]
    end

    BROWSER -->|"HTTPS GET /\nGET /assets/*.js"| ALB
    BROWSER -->|"HTTPS POST /v1/run\nGET /v1/runs/*"| ALB
    ALB --> MIDDLEWARE
    MIDDLEWARE --> ROUTER
    ROUTER -->|"rutas estáticas"| STATIC
    ROUTER -->|"rutas /v1/*"| API
    API --> DDB
    API --> S3
    API --> SM
    API --> CW

    style BROWSER fill:#e0f2fe,stroke:#0284c7
    style ALB fill:#fef3c7,stroke:#d97706
    style ROUTER fill:#f0fdf4,stroke:#16a34a
    style STATIC fill:#f0fdf4,stroke:#16a34a
    style MIDDLEWARE fill:#fdf4ff,stroke:#9333ea
    style API fill:#f0fdf4,stroke:#16a34a
    style DDB fill:#fff7ed,stroke:#ea580c
    style S3 fill:#fff7ed,stroke:#ea580c
    style SM fill:#fff7ed,stroke:#ea580c
    style CW fill:#f1f5f9,stroke:#64748b
```

---

## Diagrama — Build Pipeline (CI/CD)

```mermaid
graph LR
    subgraph "Repositorio"
        SRC["📁 src/dashboard/\n(React + Vite + TS)"]
        PY["📁 src/ (Python)\n+ specs/ + pyproject.toml"]
    end

    subgraph "GitHub Actions CI"
        TEST_FE["🧪 pnpm test\npnpm lint\npnpm audit"]
        TEST_BE["🧪 pytest\nmypy · ruff\npip-audit"]
        BUILD["🐳 docker build\n--tag testpilot:{sha}"]
    end

    subgraph "Docker multi-stage"
        STAGE1["Stage 1\nnode:20-alpine\npnpm build → dist/"]
        STAGE2["Stage 2\nplaywright/python:v1.48.0\npip install + COPY dist/"]
        IMAGE["📦 Imagen final\n~1.5 GB\n(sin Node, sin node_modules)"]
    end

    subgraph "AWS"
        ECR["🗂️ ECR\ntestpilot-sfcc:{sha}"]
        ECS["🚀 ECS Fargate\nupdate-service → nueva task"]
    end

    SRC --> TEST_FE
    PY --> TEST_BE
    TEST_FE & TEST_BE --> BUILD
    BUILD --> STAGE1
    BUILD --> STAGE2
    STAGE1 -->|"COPY --from dist/"| STAGE2
    STAGE2 --> IMAGE
    IMAGE --> ECR
    ECR --> ECS

    style STAGE1 fill:#fef3c7,stroke:#d97706
    style STAGE2 fill:#e0f2fe,stroke:#0284c7
    style IMAGE fill:#f0fdf4,stroke:#16a34a
    style ECR fill:#fff7ed,stroke:#ea580c
    style ECS fill:#fff7ed,stroke:#ea580c
```

---

## Diagrama — Desarrollo local

```mermaid
graph LR
    subgraph "Máquina del desarrollador"
        subgraph "Terminal 1 — Backend"
            UVICORN["uvicorn src.api.main:app\n--reload --port 8000"]
        end

        subgraph "Terminal 2 — Frontend"
            VITE["pnpm dev\nlocalhost:5173\n(HMR activo)"]
        end

        BROWSER_DEV["🌐 Browser\nlocalhost:5173"]
    end

    BROWSER_DEV -->|"GET /"| VITE
    BROWSER_DEV -->|"GET /v1/* (proxy)\nvite.config proxy → :8000"| UVICORN

    style UVICORN fill:#e0f2fe,stroke:#0284c7
    style VITE fill:#fef3c7,stroke:#d97706
    style BROWSER_DEV fill:#f0fdf4,stroke:#16a34a
```

---

## Routing en FastAPI — orden de resolución

```
Request entrante
│
├── /v1/*           → API handlers (incluidos antes del mount estático)
├── /health         → health check endpoint
├── /               → index.html (SPA entry point)
├── /assets/*.js    → bundle JS/CSS
├── /assets/*.css   → estilos
└── /cualquier-ruta → fallback a index.html (SPA client-side routing)
```

El orden de registro en `main.py` es crítico: los routers `/v1/` se registran **antes** del `StaticFiles` mount para que las rutas de API tengan prioridad sobre el fallback HTML.

---

## Headers de seguridad aplicados (SecurityHeadersMiddleware)

| Header | Valor | Protege contra |
|---|---|---|
| `Content-Security-Policy` | `default-src 'self'; img-src 'self' data: https://*.s3.amazonaws.com; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'` | XSS, data injection |
| `X-Content-Type-Options` | `nosniff` | MIME sniffing |
| `X-Frame-Options` | `DENY` | Clickjacking |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Referrer leakage |

Headers aplicados solo a respuestas HTML (`/` y `*.html`). Las respuestas `/v1/*` JSON no los necesitan.

---

## Notas de despliegue

| Aspecto | Decisión |
|---|---|
| ¿MD0 usa servicios AWS propios? | No — comparte el ECS task de U4 |
| ¿Hay CDN (CloudFront)? | No en MVP — acceso interno via ALB + VPN suficiente |
| ¿Source maps en producción? | No (`sourcemap: false` en vite.config.ts — SECURITY-09) |
| ¿API key expuesta al cliente? | No — se ingresa en runtime via `sessionStorage`, no en build |
| ¿Variables de entorno en build? | No — todas las URLs son relativas (`/v1/...`) |
