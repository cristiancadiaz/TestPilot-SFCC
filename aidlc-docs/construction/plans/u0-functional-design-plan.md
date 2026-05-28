# U0 Setup Base — Functional Design Plan

## Unit Context
U0 es setup técnico puro. No tiene lógica de negocio propia: su responsabilidad es establecer los modelos de datos compartidos, la configuración de herramientas, y actualizar código existente para importar desde la fuente canónica.

## Plan

- [x] Analizar unit-of-work.md para U0
- [x] Analizar unit-of-work-story-map.md para RF-01, RF-02, RF-03, RNF-01, RNF-08, RNF-10
- [x] Identificar domain entities (SyntheticUserConfig existente + nuevos modelos)
- [x] Definir business rules de validación
- [x] Documentar reglas no negociables del proyecto
- [x] Crear business-logic-model.md
- [x] Crear business-rules.md
- [x] Crear domain-entities.md

## Preguntas / Respuestas

No se requieren preguntas al usuario: los modelos están definidos en component-methods.md y las restricciones están documentadas en AGENTS.md y el PRD.

## Resultado esperado
- domain-entities.md con todos los modelos Pydantic del sistema
- business-rules.md con invariantes y validaciones
- business-logic-model.md con el flujo de datos entre entidades
