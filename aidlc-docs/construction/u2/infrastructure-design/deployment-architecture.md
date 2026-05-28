# Deployment Architecture — U2 Baseline Manager (2026-05-28)

> Para la arquitectura completa del sistema ver: `aidlc-docs/construction/u4/infrastructure-design/deployment-architecture.md`
> Este diagrama focaliza en el scope de U2: cálculo de baseline y decisión de semáforo.

---

## Diagrama — U2 dentro del ECS task (MVP)

```mermaid
graph TB
    subgraph "ECS Fargate task — testpilot-sfcc:{sha}"
        U1_OUT["⚙️ U1 Executor\nProfileResult[]\n(orders_created=0 garantizado)"]

        subgraph "U2 Baseline Manager — src/baseline/"
            STORE["🗃️ InMemoryBaselineStore\n_runs: dict[(env,profile,flow), list]\n_index_by_id: dict[run_id, RunRecord]\n\n⚠️ MVP: datos en RAM\nse resetean con cada deploy"]

            subgraph "Funciones puras (sin I/O)"
                P95["calculate_p95(runs)\n→ int (ms)\ninterpolación lineal\nPBT-02"]
                BOOT["is_bootstrap_mode(runs)\n→ bool\n< 14 success → True\nPBT-03"]
                LIGHT["compute_traffic_light(\n  current_ms, p95_ms, bootstrap\n) → TrafficLight\nPBT-07, PBT-08"]
            end
        end

        U3_IN["📋 U3 Reporter\n(siguiente etapa)"]
    end

    subgraph "AWS — Sprint 3+ (no activo en MVP)"
        DDB["🗄️ DynamoDB\ntestpilot-runs\nGSI: by-env-profile-flow-date\nTTL: 90 días"]
    end

    U1_OUT -->|"por cada ProfileResult\n(env, profile, flow, duration_ms)"| STORE
    STORE -->|"get_last_n_runs(\n  env, profile, flow,\n  n=10, status='success'\n)"| P95
    STORE -->|"get_last_n_runs(\n  n=10, status='success'\n)"| BOOT
    P95 & BOOT -->|"p95_ms, bootstrap"| LIGHT
    LIGHT -->|"TrafficLight"| STORE
    STORE -->|"save_run(RunRecord)"| STORE
    STORE -->|"BaselineComparison[]\n+ TrafficLight[]"| U3_IN
    STORE -.->|"sprint 3+\nPutItem + Query"| DDB

    style U1_OUT fill:#fff7ed,stroke:#ea580c
    style STORE fill:#f0fdf4,stroke:#16a34a
    style P95 fill:#e0f2fe,stroke:#0284c7
    style BOOT fill:#e0f2fe,stroke:#0284c7
    style LIGHT fill:#e0f2fe,stroke:#0284c7
    style U3_IN fill:#fdf4ff,stroke:#9333ea
    style DDB fill:#fef9c3,stroke:#ca8a04
```

---

## Diagrama — Flujo de cálculo por perfil

```mermaid
sequenceDiagram
    participant U4 as U4 Orchestrator
    participant U2 as U2 Baseline
    participant MEM as InMemoryStore
    participant U3 as U3 Reporter

    loop Para cada ProfileResult (6 total: 3 perfiles × 2 flows)
        U4->>U2: calculate(env_id, profile, flow, duration_ms)
        U2->>MEM: get_last_n_runs(env, profile, flow, n=10, status="success")
        MEM-->>U2: list[RunRecord] (0..10 items)

        U2->>U2: bootstrap = is_bootstrap_mode(runs)
        U2->>U2: p95_ms = calculate_p95(runs)
        U2->>U2: light = compute_traffic_light(duration_ms, p95_ms, bootstrap)

        U2->>MEM: save_run(RunRecord{env, profile, flow, duration_ms, status})

        U2-->>U4: BaselineComparison{p95_ms, current_ms, bootstrap, runs_count}\n        + TrafficLight
    end

    U4->>U3: generate_report(profile_results con traffic_lights actualizados)
```

---

## Transición MVP → Sprint 3+ (DynamoDB)

```mermaid
graph LR
    subgraph "MVP"
        INMEM["InMemoryBaselineStore\nsave_run → dict\nget_last_n_runs → list[-n:]"]
    end

    subgraph "Sprint 3+"
        DYNAMO["DynamoDBBaselineStore\nsave_run → PutItem\nget_last_n_runs → GSI Query Limit=10"]
    end

    subgraph "Punto de inyección — U4"
        INJECT["store: BaselineStore =\n  InMemoryBaselineStore()  ← MVP\n  DynamoDBBaselineStore()  ← sprint 3+"]
    end

    INMEM -.->|"swap\n(solo U4 cambia)"| DYNAMO
    INJECT --> INMEM
    INJECT -.-> DYNAMO

    style INMEM fill:#f0fdf4,stroke:#16a34a
    style DYNAMO fill:#fef9c3,stroke:#ca8a04
    style INJECT fill:#fdf4ff,stroke:#9333ea
```

U3 y el resto del sistema no cambian — el Protocol garantiza que el swap es transparente.

---

## Invariantes de U2 verificados en runtime

| Invariante | Verificación | Consecuencia si falla |
|---|---|---|
| `bootstrap=True` nunca produce `YELLOW` | PBT-07 en test suite | Alerta falsa → daña confianza del equipo |
| `current > p95 * 1.5` siempre produce `RED` | PBT-08 en test suite | Regresión no detectada → deploy con bug |
| `calculate_p95([])` retorna `0` | Test unitario | `compute_traffic_light` con `p95=0` → GREEN (safe default) |
| Baseline aislado por `environment_id` | Test de aislamiento | Sandbox contamina staging → falsos positivos |
