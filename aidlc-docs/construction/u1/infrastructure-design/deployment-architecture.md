# Deployment Architecture — U1 Executor Playwright (2026-05-28)

> Para la arquitectura completa del sistema ver: `aidlc-docs/construction/u4/infrastructure-design/deployment-architecture.md`
> Este diagrama focaliza en el scope de U1: ejecución paralela de flows + screenshots.

---

## Diagrama — U1 dentro del ECS task

```mermaid
graph TB
    subgraph "ECS Fargate task — testpilot-sfcc:{sha}"
        U4_CALL["⚙️ U4 API Handler\nPOST /v1/run\nResuelve ResolvedEnvironment\nInvoca run_profiles()"]

        subgraph "U1 Executor — asyncio.gather"
            SEMAPHORE["🔒 BoundedSemaphore\nMAX_CONCURRENT_PROFILES=3"]

            subgraph "Profile 1 — mobile-co"
                P1_CTX["BrowserContext\nlocale=es-CO · mobile\nhttp_credentials=env_access"]
                P1_F1["checkout-full\n_execute_step × N"]
                P1_F2["checkout-card-declined\n_execute_step × N"]
            end

            subgraph "Profile 2 — desktop-co"
                P2_CTX["BrowserContext\nlocale=es-CO · desktop\nhttp_credentials=env_access"]
                P2_F1["checkout-full"]
                P2_F2["checkout-card-declined"]
            end

            subgraph "Profile 3 — desktop-ec"
                P3_CTX["BrowserContext\nlocale=es-EC · desktop\nhttp_credentials=env_access"]
                P3_F1["checkout-full"]
                P3_F2["checkout-card-declined"]
            end
        end

        U2_IN["📊 U2 Baseline\n(siguiente etapa)"]
    end

    subgraph "AWS"
        S3["🪣 S3\ntestpilot-screenshots-*\nPutObject\nSSE-AES256"]
    end

    subgraph "SFCC Storefront (externo)"
        SFCC_ENV["🔐 env_access_auth\nHTTP Basic Auth\n(via BrowserContext)"]
        SFCC_LOGIN["👤 shopper_login\nPágina de login SFCC\n@testpilot.internal"]
        SFCC_FLOW["🛒 Checkout steps\nSearch → PDP → Cart\n→ Checkout → Payment FAIL"]
    end

    U4_CALL -->|"ResolvedEnvironment\n+ SyntheticUserConfig"| SEMAPHORE
    SEMAPHORE --> P1_CTX & P2_CTX & P3_CTX

    P1_CTX --> P1_F1 & P1_F2
    P2_CTX --> P2_F1 & P2_F2
    P3_CTX --> P3_F1 & P3_F2

    P1_F1 & P1_F2 & P2_F1 & P2_F2 & P3_F1 & P3_F2 -->|"HTTPS playwright"| SFCC_ENV
    SFCC_ENV --> SFCC_LOGIN --> SFCC_FLOW

    P1_F1 & P2_F1 & P3_F1 & P1_F2 & P2_F2 & P3_F2 -->|"screenshot fail/final\nPutObject"| S3

    SEMAPHORE -->|"ProfileResult[]\norders_created=0"| U2_IN

    style U4_CALL fill:#f0fdf4,stroke:#16a34a
    style SEMAPHORE fill:#fdf4ff,stroke:#9333ea
    style P1_CTX fill:#fff7ed,stroke:#ea580c
    style P2_CTX fill:#fff7ed,stroke:#ea580c
    style P3_CTX fill:#fff7ed,stroke:#ea580c
    style P1_F1 fill:#fef9c3,stroke:#ca8a04
    style P1_F2 fill:#fef9c3,stroke:#ca8a04
    style P2_F1 fill:#fef9c3,stroke:#ca8a04
    style P2_F2 fill:#fef9c3,stroke:#ca8a04
    style P3_F1 fill:#fef9c3,stroke:#ca8a04
    style P3_F2 fill:#fef9c3,stroke:#ca8a04
    style S3 fill:#fef9c3,stroke:#ca8a04
    style SFCC_ENV fill:#ecfdf5,stroke:#059669
    style SFCC_LOGIN fill:#ecfdf5,stroke:#059669
    style SFCC_FLOW fill:#ecfdf5,stroke:#059669
    style U2_IN fill:#e0f2fe,stroke:#0284c7
```

---

## Diagrama — Ciclo de vida de un BrowserContext

```mermaid
sequenceDiagram
    participant RUNNER as FlowRunner
    participant PW as Playwright
    participant CTX as BrowserContext
    participant SFCC
    participant S3

    RUNNER->>PW: async_playwright().start()
    PW->>RUNNER: playwright instance
    RUNNER->>PW: chromium.launch(headless=True)
    PW->>RUNNER: browser

    RUNNER->>CTX: new_context(locale, user_agent, viewport,\nhttp_credentials=env_access)
    CTX->>RUNNER: context
    RUNNER->>CTX: route("**/*", allowlist_handler)

    loop Por cada flow (checkout-full, checkout-card-declined)
        RUNNER->>CTX: new_page()
        CTX->>RUNNER: page

        RUNNER->>SFCC: goto(store_url) [env_access via http_credentials]
        SFCC-->>RUNNER: 200 OK

        RUNNER->>SFCC: shopper_login (fill + click)
        SFCC-->>RUNNER: login success

        loop Por cada step del flow
            RUNNER->>SFCC: action (click, fill, goto)
            SFCC-->>RUNNER: response
            alt step falla
                RUNNER->>S3: PutObject screenshot-fail.png
            else paso final
                RUNNER->>S3: PutObject screenshot-ok.png
            end
        end

        RUNNER->>CTX: page.close()
    end

    Note over RUNNER,S3: finally — siempre ejecutado
    RUNNER->>PW: browser.close()
    RUNNER->>PW: playwright.stop()
```

---

## Invariantes verificados en U1

| Invariante | Dónde se verifica | Acción si falla |
|---|---|---|
| `orders_created == 0` | `run_profile` — assert antes de retornar | `AssertionError` → capturado por U4, HTTP 500 + CloudWatch alarm |
| `shopper.email.endswith("@testpilot.internal")` | `run_profile` — assert al inicio | `AssertionError` → run abortado |
| `screenshot_on_error is True` | `run_profile` — assert al inicio | `AssertionError` — configuración inválida |
| Sin `time.sleep` en flows | ruff rule + grep en CI | `ruff check` falla el PR |
| `InfrastructureError` en env_access | `_step_env_access` | `ProfileResult(traffic_light=YELLOW)` — no RED |
