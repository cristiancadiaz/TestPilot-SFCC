# Business Rules — U0 Setup Base (actualizado 2026-05-24)

## BR-U0-01: SyntheticUserConfig sin credenciales
La clase `SyntheticUserConfig` en `src/models.py` NO debe contener campos `email`, `password`, `username`, `secret`, ni similares. Solo `environment_id`, `products`, `flows`, `profiles`, `screenshot_on_*`.

**Verificación:** test introspecciona los fields del modelo y rechaza nombres prohibidos.

**Razón:** las credenciales se resuelven en backend desde Secrets Manager — nunca viajan en request/response.

---

## BR-U0-02: Email del shopper restringido a dominio interno
La validación de que `ShopperCredentials.email` termina en `@testpilot.internal` **NO** vive en el modelo Pydantic (porque al cargar de Secrets Manager queremos validar formato, no dominio). Vive en `src/executor/runner.py` como assertion antes de ejecutar el flow.

**Verificación:** test en U1 confirma que un email sin `@testpilot.internal` lanza `AssertionError`.

**Razón:** principio P1 (cero contaminación) — un email real podría disparar mailings reales del SFCC.

---

## BR-U0-03: Credenciales nunca en `repr()` ni `__str__()`
Los modelos `EnvironmentAccessCredentials` y `ShopperCredentials` deben tener `password` con `Field(repr=False)` y `__str__` que redacte el password.

**Verificación:** `assert "password" not in str(creds)` y `assert "***" in str(creds)`.

**Razón:** SECURITY-10 — un `logger.info(creds)` no debe filtrar passwords.

---

## BR-U0-04: SyntheticUserConfig.screenshot_on_error invariante
El campo `screenshot_on_error` debe ser `True` siempre. Validador Pydantic rechaza `False`.

**Razón:** invariante de auditoría — si algo falla, debe haber evidencia visual.

---

## BR-U0-05: HTTPS obligatorio en store_url
`EnvironmentConfig.store_url` debe ser HTTPS. HTTP plano rechazado.

**Razón:** SECURITY-07 — la sesión del shopper viaja por HTTPS o no viaja.

---

## BR-U0-06: Versiones pinned, no rangos
`pyproject.toml` debe usar `==` (pinning exacto) para TODAS las dependencias. No `^`, `~`, ni `>=`.

**Verificación:** lint custom o `pip-audit --strict` en CI.

**Razón:** RNF-10 reproducibilidad — el reporte del miércoles debe usar la misma cadena de dependencias que el del lunes.

---

## BR-U0-07: Modelo Claude actualizado
La constante `CLAUDE_MODEL` en `src/agents/translator.py` debe ser `claude-haiku-4-5-20251001` (la versión current confirmada por memoria del proyecto).

**Verificación:** test importa la constante y compara con valor esperado.

**Razón:** evitar deuda silenciosa (translator usaba modelo deprecado en versión anterior).

---

## BR-U0-08: Imagen Docker con tag semántico
El `FROM` del Dockerfile no debe usar `:latest`. Tags semánticos (`:v1.48.0-jammy`) obligatorios.

**Razón:** SECURITY-12, reproducibilidad.

---

## BR-U0-09: Usuario no-root en imagen
La imagen Docker debe ejecutar como usuario no-root en `CMD`.

**Razón:** SECURITY-13.

---

## BR-U0-10: .dockerignore excluye sensibles
`.dockerignore` debe incluir: `.env`, `.env.*`, `.git/`, `aidlc-docs/`, `__pycache__/`, `*.pyc`, `node_modules/`, `dist/`.

**Razón:** evita filtrar secrets, evita imágenes infladas, evita confundir build vs runtime.

---

## BR-U0-11: Build dashboard incluido en imagen
La imagen Docker final debe contener `/app/src/dashboard/dist/index.html`. Si falta, el dashboard MD0 no se sirve.

**Verificación:** `docker run --rm <image> ls /app/src/dashboard/dist/index.html`.

---

## BR-U0-12: Sin secrets en código
Ningún archivo bajo `src/`, `tests/`, `specs/`, `Dockerfile`, `pyproject.toml` debe contener:
- API keys reales
- Passwords reales
- Tokens
- Credenciales de cualquier servicio

**Verificación:** scan con `truffleHog` o `gitleaks` en CI antes de cada PR merge.

**Razón:** SECURITY-01.

---

## BR-U0-13: Catálogo cerrado de flows y perfiles
- `flows` solo acepta valores en `Literal["checkout-full", "checkout-card-declined"]`.
- `profiles` solo acepta valores en `Literal["mobile-co", "desktop-co", "desktop-ec"]`.
- `environment_id` solo acepta valores en `Literal["sandbox", "development", "staging"]`.

**Razón:** mantiene el LLM translator en un catálogo cerrado (R4 mitigado), y previene runs accidentales contra entornos productivos.

---

## Trazabilidad a Security Baseline

| BR | Security Baseline |
|---|---|
| BR-U0-01, BR-U0-03 | SECURITY-01, SECURITY-10 |
| BR-U0-02 | Principio P1 (negocio) |
| BR-U0-04 | Invariante de auditoría |
| BR-U0-05 | SECURITY-07 (crypto/TLS) |
| BR-U0-06 | SECURITY-08 (supply chain) |
| BR-U0-08 | SECURITY-12 (image hardening) |
| BR-U0-09 | SECURITY-13 (non-root) |
| BR-U0-10, BR-U0-12 | SECURITY-01 |
| BR-U0-13 | SECURITY-03 (input validation) |

---

## Referencias

- `inception/application-design/error-taxonomy.md` — semántica completa de `status` que U0 modela.
- `inception/application-design/env-vars-catalog.md` — env vars que U0 documenta y que U4 consume.
- `inception/application-design/logging-strategy.md` — política de logging (U0 no instancia loggers, sólo deja preparado el formatter).
