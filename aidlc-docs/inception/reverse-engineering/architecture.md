# System Architecture — TestPilot SFCC

## System Overview

TestPilot SFCC es un agente interno de testing continuo para storefronts SFCC/SFRA. La arquitectura sigue un patrón de pipeline: ingesta REST → traducción IA → orquestación de ejecución paralela → análisis con baseline → reporte estructurado. El sistema está diseñado para ser consumido tanto por humanos como por agentes downstream de CI/CD.

## Architecture Diagram (Current State — Partially Implemented)

```
CONSUMERS
+------------------+  +--------------------+  +--------------------+
|  Engineer (U1)   |  |  CI/CD Agent (U2)  |  |  Tech Lead (A1)    |
|  POST /v1/run    |  |  GET /v1/runs/     |  |  GET /v1/runs?     |
|  (NL instruction)|  |  latest            |  |  aggregate=daily   |
+--------+---------+  +----------+---------+  +---------+----------+
         |                       |                       |
         +=======================+=======================+
                                 |
                    +------------v-----------+
                    |   MD1 - API Gateway     |  [IMPLEMENTED - partial]
                    |   FastAPI /v1/          |
                    |   POST /v1/run          |
                    |   (GET endpoints TBD)   |
                    +------------+-----------+
                                 |
                    +------------v-----------+
                    |   MD2 - LLM Agent       |  [IMPLEMENTED]
                    |   src/agents/           |
                    |   translator.py         |
                    |   NL -> SyntheticConfig |
                    +------------+-----------+
                                 |
                    +------------v-----------+
                    |   MD3 - Validation      |  [IMPLEMENTED]
                    |   JSON Schema           |
                    |   specs/               |
                    |   synthetic_user_       |
                    |   config.json           |
                    +------------+-----------+
                                 |
                    +============v===========+
                    |   MD4 - Orchestrator    |  [NOT IMPLEMENTED]
                    |   AWS Step Functions    |
                    |   3 profiles x 2 flows  |
                    +===========+============+
                                |
          +--------------------+|+--------------------+
          |                    |||                    |
  +-------v------+   +---------v+------+   +---------v------+
  | mobile/CO    |   | desktop/CO      |   | mobile/MX      |
  | MD5 Executor |   | MD5 Executor    |   | MD5 Executor   |
  | Playwright   |   | Playwright      |   | Playwright     |
  | ECS Fargate  |   | ECS Fargate     |   | ECS Fargate    |
  | [NOT IMPL]   |   | [NOT IMPL]      |   | [NOT IMPL]     |
  +-------+------+   +--------+--------+   +--------+-------+
          |                   |                     |
          +-------------------+---------------------+
                              |
                   +----------v---------+
                   | MD6 - Evidence     |  [NOT IMPLEMENTED]
                   | Screenshots S3     |
                   | (fail + final only)|
                   +----------+---------+
                              |
             +----------------+----------------+
             |                                 |
  +----------v---------+           +----------v---------+
  | MD7 - Classifier   |           | MD7 - Baseline Mgr |
  | src/classifier/    |           | src/baseline/      |
  | Claude API         |           | DynamoDB p95       |
  | [NOT IMPLEMENTED]  |           | [NOT IMPLEMENTED]  |
  +----------+---------+           +----------+---------+
             |                                |
             +----------------+---------------+
                              |
                   +----------v---------+
                   | MD8 - Persistence  |  [NOT IMPLEMENTED]
                   | DynamoDB (runs)    |
                   | S3 (artifacts)     |
                   +----------+---------+
                              |
                   +----------v---------+
                   | MD9 - Reporter     |  [NOT IMPLEMENTED]
                   | src/reporter/      |
                   | JSON + Markdown    |
                   | Slack webhook      |
                   | Traffic Light      |
                   +--------------------+
```

## Component Descriptions

### src/api/ — API Gateway (MD1) [IMPLEMENTED - partial]
- **Purpose**: Punto de entrada REST versionado para el sistema
- **Responsibilities**: Validar requests, serializar/deserializar JSON, retornar respuestas estructuradas
- **Dependencies**: FastAPI, Pydantic, uvicorn
- **Type**: Application
- **Status**: POST /v1/run implementado; GET endpoints pendientes

### src/agents/ — LLM Agent (MD2) [IMPLEMENTED]
- **Purpose**: Traducir lenguaje natural a configuración JSON válida
- **Responsibilities**: Llamar Claude API (claude-3-haiku), parsear respuesta, validar schema, reintentar (max 3)
- **Dependencies**: anthropic SDK, jsonschema, pydantic
- **Type**: Application

### specs/ — Schemas de Contrato (MD3) [IMPLEMENTED]
- **Purpose**: Source of truth del contrato de API entrada/salida
- **Responsibilities**: Catálogo cerrado de flows/profiles, restricciones de email/timeout
- **Dependencies**: JSON Schema draft-07
- **Type**: Model

### src/executor/ — Motor Playwright (MD4+MD5) [NOT IMPLEMENTED]
- **Purpose**: Ejecutar flows de checkout en browsers headless
- **Responsibilities**: Lanzar Playwright, navegar storefront, ejecutar pasos, manejar perfiles
- **Dependencies**: Playwright Python, ECS Fargate
- **Type**: Application

### src/baseline/ — Gestión de Baseline (MD7 parcial) [NOT IMPLEMENTED]
- **Purpose**: Mantener historial de ejecuciones y calcular umbrales dinámicos
- **Responsibilities**: Escritura/lectura DynamoDB, cálculo p95 últimas 10, flag bootstrap
- **Dependencies**: boto3 (DynamoDB)
- **Type**: Application

### src/reporter/ — Generación de Reportes (MD9) [NOT IMPLEMENTED]
- **Purpose**: Producir reporte dual consumible por humanos y agentes
- **Responsibilities**: Calcular semáforo, formatear markdown, emitir JSON versionado, enviar Slack
- **Dependencies**: Slack API
- **Type**: Application

### src/classifier/ — Clasificador de Errores (MD7 parcial) [NOT IMPLEMENTED]
- **Purpose**: Distinguir bugs reales de comportamiento esperado
- **Responsibilities**: Llamar Claude API para clasificación, asignar confianza, escalar a human review
- **Dependencies**: anthropic SDK
- **Type**: Application

### infra/ — AWS CDK (MD4 infraestructura) [NOT IMPLEMENTED]
- **Purpose**: Definir y desplegar infraestructura AWS
- **Responsibilities**: Step Functions, ECS Fargate, DynamoDB tables, S3 bucket, API Gateway, Secrets Manager
- **Dependencies**: AWS CDK Python
- **Type**: Infrastructure

## Data Flow — Happy Path (POST /v1/run)

```
Engineer           API              Translator        Step Functions     Playwright (x3)
    |               |                    |                  |                  |
    |--POST /v1/run->|                   |                  |                  |
    |  {NL prompt}  |                   |                  |                  |
    |               |--translate(prompt)->|                 |                  |
    |               |                    |--Claude API---->|                  |
    |               |                    |<--JSON config---|                  |
    |               |                    |--validate schema|                  |
    |               |<--SyntheticConfig--|                 |                  |
    |               |--startExecution()----------------->  |                  |
    |<-202 Accepted-|                    |                  |--launch browser->|
    |  {testRunId}  |                    |                  |                  |--navigate-->
    |               |                    |                  |                  |--add_to_cart->
    |               |                    |                  |                  |--checkout->
    |               |                    |                  |                  |--decline pay->
    |               |                    |                  |<-step results----|
    |               |                    |                  |--classify(errors)->Claude API
    |               |                    |                  |--compare(p95)-->DynamoDB
    |               |                    |                  |--save(report)-->DynamoDB+S3
    |               |                    |                  |--notify()------>Slack
    |<--Slack notif-|                    |                  |                  |
```

## Integration Points

- **External APIs**:
  - Claude API (Anthropic): traducción NL→config y clasificación de errores
  - Slack Webhook: notificaciones de resultado de runs
  - SFCC Storefront (staging): objetivo de las pruebas Playwright
- **Databases**:
  - DynamoDB: historial de ejecuciones, métricas por paso, baseline p95
  - S3: screenshots (solo fallo + paso final)
- **Third-party Services**:
  - AWS Secrets Manager: credenciales SFCC staging, API keys
  - AWS Step Functions: orquestación de ejecución paralela
  - AWS ECS Fargate: ejecución de containers Playwright

## Infrastructure Components (Planned)

- **CDK Stacks** (infra/ — pendiente):
  - `TestPilotApiStack`: API Gateway + Lambda/ECS para endpoints
  - `TestPilotExecutorStack`: ECS Fargate + Step Functions
  - `TestPilotDataStack`: DynamoDB tables + S3 bucket + Secrets Manager
- **Deployment Model**: Serverless-first — API Gateway + Lambda para REST; ECS Fargate para Playwright
- **Networking**: VPC con subnets privadas para ECS; Secrets Manager sin acceso público
