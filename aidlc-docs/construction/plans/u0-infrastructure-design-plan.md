# U0 Setup Base — Infrastructure Design Plan

## Unit Context
U0 solo introduce infraestructura a través del Dockerfile. No hay servicios cloud en U0 (stubs en memoria para U2). El Dockerfile es la base de imagen para ejecución local y para ECS Fargate (fases posteriores).

## Plan

- [x] Identificar componentes que requieren infraestructura (solo Dockerfile en U0)
- [x] Determinar imagen base y versión
- [x] Definir estrategia multi-stage build
- [x] Definir usuario no-root (SECURITY-13)
- [x] Documentar variables de entorno requeridas
- [x] Crear infrastructure-design.md
- [x] Crear deployment-architecture.md

## Preguntas / Respuestas

No se requieren preguntas al usuario. La imagen base de Playwright para Python ya está definida en la decisión de stack, y el patrón de Dockerfile para ECS Fargate está establecido en el PRD.
