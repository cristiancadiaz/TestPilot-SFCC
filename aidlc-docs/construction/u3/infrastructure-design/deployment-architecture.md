# Deployment Architecture — U3 Reporter (2026-05-28)

> Para la arquitectura completa del sistema ver: `aidlc-docs/construction/u4/infrastructure-design/deployment-architecture.md`
> Este diagrama focaliza en el scope de U3: generación del reporte y serialización del contrato.

---

## Diagrama — U3 dentro del ECS task

```mermaid
graph TB
    subgraph "ECS Fargate task — testpilot-sfcc:{sha}"

        U2_OUT["📊 U2 Baseline\nBaselineComparison[]\nTrafficLight[] actualizados\nen cada ProfileResult"]

        subgraph "U3 Reporter — src/reporter/report_generator.py"

            INVARIANT["🔒 Validación invariante\nassert orders_created == 0\n→ InvariantViolatedError si falla"]

            subgraph "generate_report()"
                WORST["_worst_traffic_light()\nRED > YELLOW > GREEN"]
                BOOTSTRAP["_bootstrap_mode_global()\nOR conservador"]
                BUILD["Construir ExecutionReport\nrun_id · environment_id\nstarted_at · finished_at\nduration_ms · orders_created=0"]
            end

            subgraph "Serialización"
                JSON_OUT["to_json_dict(report)\nmodel_dump(by_alias=True)\njsonschema.validate()"]
                MD_OUT["to_markdown(report)\nH1 + semáforo\nbanner orders=0\ntabla por perfil"]
            end

            SCHEMA["📄 specs/execution_report.json\n(archivo local en imagen Docker)\ncontrato additionalProperties:false"]
        end

        U4_RESP["⚙️ U4 API Handler\nHTTP 200 ExecutionReport\nJSON + Markdown"]
        U4_ERR["⚠️ U4 Exception Handler\nInvariantViolatedError\n→ HTTP 500 + CloudWatch CRÍTICO"]
    end

    subgraph "Consumidores del reporte"
        CAROLINA["👤 Carolina\nlee Markdown\nen Slack / CLI"]
        CICD["🤖 Agente CI/CD\nconsume JSON\n/v1/run response"]
        DASHBOARD["🖥️ MD0 Dashboard\nrenderiza ExecutionReport\nvía GET /v1/runs/{id}"]
    end

    U2_OUT -->|"ProfileResult[]\ncon traffic_lights"| INVARIANT
    INVARIANT -->|"ok"| WORST & BOOTSTRAP
    INVARIANT -->|"violado"| U4_ERR
    WORST & BOOTSTRAP --> BUILD
    BUILD --> JSON_OUT & MD_OUT
    JSON_OUT -->|"valida contra"| SCHEMA
    SCHEMA -->|"válido"| U4_RESP
    MD_OUT --> U4_RESP
    U4_RESP --> CAROLINA & CICD & DASHBOARD

    style U2_OUT fill:#fff7ed,stroke:#ea580c
    style INVARIANT fill:#fef2f2,stroke:#dc2626
    style WORST fill:#e0f2fe,stroke:#0284c7
    style BOOTSTRAP fill:#e0f2fe,stroke:#0284c7
    style BUILD fill:#f0fdf4,stroke:#16a34a
    style JSON_OUT fill:#fef9c3,stroke:#ca8a04
    style MD_OUT fill:#fef9c3,stroke:#ca8a04
    style SCHEMA fill:#f1f5f9,stroke:#64748b
    style U4_RESP fill:#f0fdf4,stroke:#16a34a
    style U4_ERR fill:#fef2f2,stroke:#dc2626
    style CAROLINA fill:#e0f2fe,stroke:#0284c7
    style CICD fill:#f0fdf4,stroke:#16a34a
    style DASHBOARD fill:#e0f2fe,stroke:#0284c7
```

---

## Diagrama — Flujo interno de `generate_report`

```mermaid
sequenceDiagram
    participant U4 as U4 Orchestrator
    participant U3 as U3 Reporter
    participant U2 as BaselineStore
    participant SCHEMA as execution_report.json

    U4->>U3: generate_report(profile_results, baseline_store, config, run_id, env, started_at)

    U3->>U3: assert orders_created == 0 (todos los perfiles)
    Note over U3: InvariantViolatedError si falla → propagada a U4

    loop Por cada ProfileResult (6 total)
        U3->>U2: get_last_n_runs(env_id, profile, flow, n=10, status="success")
        U2-->>U3: list[RunRecord]
        U3->>U3: p95 = calculate_p95(runs)
        U3->>U3: bootstrap = is_bootstrap_mode(runs)
        U3->>U3: light = compute_traffic_light(duration_ms, p95, bootstrap)
        U3->>U2: save_run(RunRecord{...})
    end

    U3->>U3: overall_light = _worst_traffic_light(lights)
    U3->>U3: overall_bootstrap = _bootstrap_mode_global(profile_results)
    U3->>U3: build ExecutionReport(...)
    U3-->>U4: ExecutionReport

    U4->>U3: to_json_dict(report)
    U3->>SCHEMA: jsonschema.validate(raw_dict)
    SCHEMA-->>U3: valid ✅
    U3-->>U4: dict (camelCase, exclude_none)

    U4->>U3: to_markdown(report)
    U3-->>U4: str (Markdown)

    U4-->>U4: HTTP 200 {json_report, markdown_report}
```

---

## Garantías de contrato que U3 provee a sus consumidores

| Consumidor | Garantía | Mecanismo |
|---|---|---|
| Agente CI/CD (JSON) | Siempre conforme a `specs/execution_report.json` | `jsonschema.validate` en cada call — falla rápido si no |
| Carolina (Markdown) | Primera línea siempre `# {emoji} TestPilot Run…` | BR-U3-07 + PBT-U3-01 |
| MD0 Dashboard (JSON) | `orders_created` siempre visible y siempre `0` | BR-U3-01 + NFR-U3-S2 |
| Cualquier consumidor | Sin credenciales ni PII en el output | NFR-U3-S1 + test regex |
| U4 (excepciones) | `InvariantViolatedError` nunca silenciada en U3 | NFR-U3-R2 — solo U4 la captura |
