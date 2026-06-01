# Business Overview — TestPilot SFCC

## Business Context Diagram

```
+------------------------------------------------------------------+
|                         PASH Engineering Team                     |
|   (3-7 devs, >=2 deploys/month on SFCC storefronts in LatAm)     |
+---------------------------+--------------------------------------+
                            |
                   POST /v1/run (NL instruction)
                            |
                            v
+------------------------------------------------------------------+
|                      TestPilot SFCC                               |
|                                                                   |
|  NL Prompt  -->  [Claude API: Translator]                         |
|                         |                                         |
|                         v                                         |
|                  [SyntheticUserConfig]                            |
|                   (validated JSON)                                |
|                         |                                         |
|        +----------------+----------------+                        |
|        |                |                |                        |
|   mobile/CO       desktop/CO        desktop/EC                   |
|        |                |                |                        |
|   [Playwright   [Playwright        [Playwright                    |
|   checkout_full  checkout_full      checkout_full]               |
|   checkout_dec]  checkout_dec]      checkout_dec]                |
|        |                |                |                        |
|        +----------------+----------------+                        |
|                         |                                         |
|               [Claude API: Classifier]                            |
|                         |                                         |
|               [Baseline p95 DynamoDB]                            |
|                         |                                         |
|          JSON Report + Markdown + Traffic Light                   |
+---------------------------+--------------------------------------+
                            |
              +-------------+-------------+
              |                           |
    [Human Engineer]           [CI/CD Agent / downstream agents]
    (30-min deploy decision)   (GET /v1/runs/latest -> auto-approve)
```

## Business Description

- **Business Description**: TestPilot SFCC es una plataforma interna de PASH que automatiza el ciclo de QA de storefronts Salesforce Commerce Cloud (SFRA). Simula usuarios sintéticos ejecutando flujos críticos de checkout mediante Playwright, orquestados por IA (Claude API), y entrega reportes estructurados consumibles por humanos y agentes de CI/CD. Reemplaza 4–8 horas de QA manual por release con una decisión deploy-gate documentada en menos de 30 minutos.

- **Business Transactions**:
  1. **POST /v1/run** — El ingeniero o agente CI/CD envía instrucción NL; el sistema traduce, valida, ejecuta en paralelo los 3 perfiles × 2 flows, clasifica resultados y devuelve reporte con semáforo.
  2. **GET /v1/runs/{run_id}** — Consulta de resultado de una ejecución específica por su UUID.
  3. **GET /v1/runs/latest** — El agente CI/CD consulta el último resultado sin lanzar nueva ejecución; aprueba merge si verde + edad < 4h.
  4. **GET /v1/runs?aggregate=daily** — El Tech Lead consulta el historial diario de ejecuciones para decisiones de planning.
  5. **Bootstrap Baseline** — Las primeras 14 ejecuciones construyen el baseline p95; el semáforo no emite amarillo durante este período.
  6. **Human Review Workflow** — Cuando el clasificador tiene baja confianza (< 0.7), crea ticket con 3 opciones (expected/bug/not-sure); la respuesta del ingeniero alimenta el dataset de groundtruth.

- **Business Dictionary**:
  | Término | Significado |
  |---------|-------------|
  | `SyntheticUserConfig` | Contrato JSON de entrada: environment_id, products[], flows[], profiles[], screenshot flags, testRunId. Sin credenciales. |
  | `ExecutionReport` | Contrato JSON de salida: trafficLight, steps, durationMs, baselineComparison |
  | `trafficLight` | Semáforo green/yellow/red: resumen de salud de la ejecución |
  | `checkout_full` | Flow: search → PDP → cart → checkout (pago falla en último paso) |
  | `checkout_card_declined` | Flow: mismo camino, tarjeta rechazada explícitamente al final |
  | `bootstrap mode` | Período de primeras 14 ejecuciones sin alertas amarillas |
  | `p95` | Percentil 95 de las últimas 10 ejecuciones por paso/perfil/flow |
  | `@testpilot.internal` | Dominio obligatorio para todos los emails de shopper sintético — definido en Secrets Manager como shopper_credentials, nunca en el payload. |
  | `groundtruth` | Dataset etiquetado (expected/bug) que entrena/evalúa el clasificador |

## Component Level Business Descriptions

### src/agents/translator.py
- **Purpose**: Traducir instrucciones en lenguaje natural a configuración JSON válida para usuarios sintéticos
- **Responsibilities**: Llamar Claude API, parsear respuesta JSON, validar contra JSON Schema, traducir NL a SyntheticUserConfig validado; ya NO asigna email ni storefrontUrl — el ambiente se especifica vía environment_id, reintentar hasta 3 veces

### src/api/main.py
- **Purpose**: Punto de entrada REST para ingenieros y agentes downstream
- **Responsibilities**: Exponer POST /v1/run con validación Pydantic, retornar 202 Accepted con testRunId, retornar 422 con errores descriptivos

### specs/synthetic_user_config.json
- **Purpose**: Contrato de entrada — source of truth del schema de configuración
- **Responsibilities**: Definir catálogo cerrado de flows y profiles, patrón de email, rango de timeout

### specs/execution_report.schema.json
- **Purpose**: Contrato de salida — source of truth del schema de reporte
- **Responsibilities**: Definir estructura del reporte con semáforo, steps, baselineComparison con bootstrapMode

### (Pendiente) src/executor/
- **Purpose**: Ejecutar flows Playwright sobre perfiles sintéticos
- **Responsibilities**: Controlar browser, ejecutar pasos, capturar screenshots en fallo + paso final

### (Pendiente) src/reporter/
- **Purpose**: Generar reporte dual JSON + Markdown + semáforo
- **Responsibilities**: Calcular semáforo basado en baseline, formatear reporte para consumo humano y programático

### (Pendiente) src/baseline/
- **Purpose**: Gestionar historial de ejecuciones y calcular umbrales p95
- **Responsibilities**: Escribir/leer DynamoDB, calcular p95 últimas 10 ejecuciones, manejar período bootstrap

### (Pendiente) src/classifier/
- **Purpose**: Clasificar errores de ejecución vía Claude API
- **Responsibilities**: Distinguir bug real vs comportamiento esperado, asignar confianza, escalar a human review si confianza < 0.7
