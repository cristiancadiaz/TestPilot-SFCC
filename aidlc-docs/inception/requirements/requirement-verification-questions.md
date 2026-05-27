# Requirements Clarification — TestPilot SFCC

El PRD en `specs/prd.md` cubre exhaustivamente el problema, personas y scope. Las siguientes preguntas buscan aclarar el **alcance de implementación para esta sesión** y las preferencias técnicas que el PRD deja como TBD.

Por favor responde llenando la letra después de cada `[Answer]:`.

---

## Pregunta 1

¿Cuál es el alcance de implementación para esta sesión con AI-DLC?

A) MVP completo — construir todos los módulos pendientes: executor (Playwright), baseline (DynamoDB), reporter (JSON+MD+semáforo) y classifier (Claude API), más los endpoints GET y la infra AWS CDK

B) Núcleo de ejecución primero — construir solo executor + baseline + reporter en esta sesión (los más críticos para el demo funcional de semana 4); dejar classifier e infra AWS para después

C) Un módulo por vez — empezar solo con el executor (Playwright flows + profiles) como primera unidad de trabajo

D) Deuda técnica + un módulo — resolver primero los gaps técnicos (pyproject.toml, modelo Claude actualizado, SyntheticUserConfig unificada) y luego construir el executor

E) Other (please describe after [Answer]: tag below)

[Answer]: B

> **Recomendación aplicada**: Núcleo de ejecución primero — executor + baseline + reporter cubren el demo funcional de semana 4 sin sobrecargar el sprint con classifier e infra CDK.

---

## Pregunta 2

¿La infraestructura AWS (Step Functions, ECS Fargate, DynamoDB, S3) debe ser implementada como código CDK en esta sesión, o usamos stubs/mocks locales para el MVP?

A) Infraestructura AWS CDK completa — generar los stacks CDK para Step Functions, ECS Fargate, DynamoDB, S3, Secrets Manager y API Gateway

B) Stubs locales primero — implementar la lógica de aplicación con interfaces que simulen AWS (LocalStack o mocks) y dejar el CDK para después

C) Híbrido — implementar DynamoDB y S3 con boto3 real (apuntando a AWS staging), pero Step Functions y ECS como orquestación local en el MVP

D) Other (please describe after [Answer]: tag below)

[Answer]: B

> **Recomendación aplicada**: Stubs locales primero — permite desarrollar y probar toda la lógica de aplicación sin depender de infraestructura AWS. El CDK se agrega en Días 31-60 según el plan del PRD.

---

## Pregunta 3

Para el executor de Playwright, ¿cuál es el entorno de ejecución objetivo para desarrollo/pruebas locales?

A) Docker con imagen oficial de Playwright — `mcr.microsoft.com/playwright/python`, igual al entorno de producción ECS Fargate

B) Playwright instalado directamente en la máquina de desarrollo — `pip install playwright && playwright install chromium`

C) Ambos — el código debe funcionar localmente con Playwright instalado Y en Docker para CI/CD

D) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Pregunta 4

El PRD marca la URL del storefront SFCC staging como dependencia externa (requiere acceso real). Para el desarrollo de los flows Playwright, ¿cómo procedemos?

A) Usar la URL real de staging SFCC de PASH — ya tengo las credenciales y acceso al storefront staging

B) Usar un storefront de demo/sandbox SFCC público para desarrollo inicial, y luego adaptar selectores al staging real de PASH

C) Construir los flows con selectores parametrizados y fixtures de prueba (sin ejecutar contra un storefront real todavía) — validar la arquitectura del código primero

D) Other (please describe after [Answer]: tag below)

[Answer]: C

> **Recomendación aplicada**: Selectores parametrizados sin staging real — construir la arquitectura correcta del executor primero, con datos de prueba locales. Conectar al staging real de PASH es un paso operativo (sprint 0 del PRD) que no debe bloquear la implementación del código.

---

## Pregunta 5

¿Cómo se debe manejar la configuración del proyecto (dependencias, linting)?

A) Crear `pyproject.toml` completo con dependencias, configuración de ruff y mypy — resuelve TD1 de la deuda técnica identificada

B) Crear `requirements.txt` simple con versiones pinned — más rápido, menos configuración

C) Mantener el estado actual sin archivo de dependencias — no es prioridad en esta sesión

D) Other (please describe after [Answer]: tag below)

[Answer]: A

> **Recomendación aplicada**: pyproject.toml completo — es la base para que ruff, mypy y los hooks de AGENTS.md funcionen correctamente. Sin esto, el build Docker no es reproducible y el código no puede ejecutarse en CI.

---

## Pregunta 6

El translator.py usa `claude-3-haiku-20240307` (modelo con fecha que puede quedar deprecated). ¿Actualizamos el modelo?

A) Sí — actualizar a `claude-haiku-4-5-20251001` (latest Haiku disponible) como parte de esta sesión

B) Sí — usar `claude-sonnet-4-6` para traducción y clasificación (más preciso, costo mayor)

C) No — mantener el modelo actual, no es prioridad ahora

D) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Pregunta 7

`SyntheticUserConfig` está definida en dos lugares (`src/api/main.py` y `src/agents/translator.py`). ¿Refactorizamos antes de construir los nuevos módulos?

A) Sí — mover a `src/models.py` compartido antes de agregar nuevos módulos (evita que la duplicación se propague)

B) No — mantener la duplicación por ahora, no reabrir código que funciona a menos que sea necesario

C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Pregunta 8: Extensión de Seguridad

¿Deben aplicarse las reglas de la extensión de seguridad (Security Baseline) como restricciones bloqueantes en este proyecto?

A) Sí — aplicar todas las reglas de SECURITY como restricciones bloqueantes (recomendado para aplicaciones de producción)

B) No — omitir las reglas de SECURITY (adecuado para PoCs, prototipos o proyectos experimentales)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

> **Recomendación aplicada**: Security Baseline sí — TestPilot gestiona credenciales SFCC, ejecuta código sobre un storefront de producción (staging), y tiene un endpoint REST consumido por agentes. Las reglas de seguridad son restricciones bloqueantes adecuadas.

---

## Pregunta 9: Extensión de Property-Based Testing

¿Deben aplicarse las reglas de Property-Based Testing (PBT) como restricciones bloqueantes?

A) Sí — aplicar todas las reglas de PBT (recomendado para proyectos con lógica de negocio, transformaciones de datos o componentes con estado)

B) Parcial — aplicar PBT solo para funciones puras y round-trips de serialización

C) No — omitir las reglas de PBT (adecuado para proyectos CRUD simples o capas de integración delgadas)

X) Other (please describe after [Answer]: tag below)

[Answer]: B

> **Recomendación aplicada**: PBT parcial — el baseline_manager (cálculo p95) y el reporter (lógica del semáforo) tienen lógica matemática pura que se beneficia de PBT. El executor (Playwright) y la API son capas de integración donde PBT no aplica.

---

Por favor responde todas las preguntas llenando la letra después de `[Answer]:` y avísame cuando termines.
