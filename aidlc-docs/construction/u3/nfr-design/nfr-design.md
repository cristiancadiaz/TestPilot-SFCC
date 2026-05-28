# NFR Design — U3 Reporter (2026-05-28)

Patrones concretos para satisfacer los NFR-U3-* y BR-U3-* de la unidad de reporting.

---

## Patrón 1: Schema validation inline en `to_json_dict` (NFR-U3-R3, BR-U3-06)

La validación contra `specs/execution_report.json` ocurre en cada invocación de `to_json_dict` — no es opcional ni desactivable por flag de entorno.

```python
# src/reporter/report_generator.py
import json
from pathlib import Path
import jsonschema
from src.models import ExecutionReport

# Carga lazy al primer uso del módulo — una sola lectura de disco en toda la vida del proceso
_SCHEMA_PATH = Path(__file__).parent.parent.parent / "specs" / "execution_report.json"
_EXECUTION_REPORT_SCHEMA: dict | None = None

def _load_schema() -> dict:
    global _EXECUTION_REPORT_SCHEMA
    if _EXECUTION_REPORT_SCHEMA is None:
        _EXECUTION_REPORT_SCHEMA = json.loads(_SCHEMA_PATH.read_text())
    return _EXECUTION_REPORT_SCHEMA


def to_json_dict(report: ExecutionReport) -> dict:
    """
    Serializa ExecutionReport al formato specs/execution_report.json.
    Valida el output antes de retornar — falla rápido si el modelo Pydantic
    produce algo que no cumple el contrato.
    """
    raw = report.model_dump(mode="json", by_alias=True, exclude_none=True)
    jsonschema.validate(instance=raw, schema=_load_schema())
    return raw
```

**Por qué carga lazy (`_load_schema`):**
- Evita I/O en import time — el módulo se puede importar en tests sin necesidad del archivo en disco.
- El schema se carga una sola vez por proceso — sin penalidad en requests repetidos.

**Por qué `exclude_none=True`:**
- `baseline_comparison` es `None` en modo bootstrap puro — excluirlo mantiene el JSON limpio.
- El schema declara los campos opcionales sin `required` — la validación sigue pasando.

**Trade-off:** `jsonschema.validate` en cada llamada añade ~10–50 ms. Aceptable porque `to_json_dict` se llama una vez por run, no en hot paths. Si post-MVP se necesita más velocidad, compilar el validador con `jsonschema.Draft202012Validator(schema).validate(raw)` precargado.

---

## Patrón 2: `InvariantViolatedError` — propagación no silenciable (NFR-U3-R2, BR-U3-01)

La excepción viaja desde U3 hasta el handler de U4 sin ningún `except` intermedio en U3.

```python
# src/reporter/report_generator.py

class InvariantViolatedError(Exception):
    """Raised when orders_created != 0. Never catch in U3 — let U4 handle it."""
    pass


def generate_report(
    profile_results: list[ProfileResult],
    baseline_store: BaselineStore,
    config: SyntheticUserConfig,
    run_id: str,
    env: ResolvedEnvironment,
    started_at: datetime,
) -> ExecutionReport:
    # BLOQUEANTE — primera línea, sin excepción posible
    violated = [
        pr for pr in profile_results if pr.flow_result.orders_created != 0
    ]
    if violated:
        profiles_str = ", ".join(pr.profile.name for pr in violated)
        raise InvariantViolatedError(
            f"orders_created invariant violated for profiles: {profiles_str}. "
            f"CRITICAL: real orders may have been created."
        )
    # ... resto del proceso
```

**Por qué lista de violadores y no `assert`:**
- `assert` puede desactivarse con `python -O` (optimize flag). `InvariantViolatedError` no.
- La lista de perfiles violadores enriquece el log de U4 para debug post-mortem.

**En U4 (handler):**
```python
# src/api/main.py
from src.reporter.report_generator import InvariantViolatedError

@app.exception_handler(InvariantViolatedError)
async def invariant_violated_handler(request: Request, exc: InvariantViolatedError):
    logger.critical("INVARIANT_VIOLATED: %s", exc, extra={"run_id": run_id})
    # Dispara CloudWatch alarm aquí
    return JSONResponse(
        status_code=500,
        content={"error_code": "invariant_violated", "message": "Critical invariant failure"},
    )
```

---

## Patrón 3: Agregadores deterministas `_worst_traffic_light` y `_bootstrap_mode_global` (BR-U3-04, BR-U3-05, PBT-U3-03, PBT-U3-04)

Dos helpers internos que implementan las reglas de agregación de forma pura y verificable.

```python
# src/reporter/report_generator.py

def _worst_traffic_light(lights: list[TrafficLight]) -> TrafficLight:
    """
    RED > YELLOW > GREEN. Idempotente y asociativo.

    PBT-U3-03: worst([worst(a, b), c]) == worst(a, b, c)
    """
    if TrafficLight.RED in lights:
        return TrafficLight.RED
    if TrafficLight.YELLOW in lights:
        return TrafficLight.YELLOW
    return TrafficLight.GREEN


def _bootstrap_mode_global(profile_results: list[ProfileResult]) -> bool:
    """
    True si CUALQUIER perfil está en bootstrap (OR conservador).

    PBT-U3-04: si al menos uno es True → resultado True.
    Solo si TODOS son False → resultado False.
    """
    return any(
        pr.baseline_comparison.bootstrap_mode
        for pr in profile_results
        if pr.baseline_comparison is not None
    )
```

**Por qué OR y no AND para bootstrap:**
- Un perfil nuevo (`desktop-ec` recién agregado) mantiene el run completo en bootstrap aunque los otros dos perfiles ya tengan historial.
- El operador AND falsamente indicaría "fuera de bootstrap" cuando un perfil aún aprende — generaría alertas no confiables.
- La regla es: si hay incertidumbre en algún perfil, el semáforo del run completo hereda esa incertidumbre.

**Por qué usar `in` sobre un loop explícito en `_worst_traffic_light`:**
- `list.__contains__` hace short-circuit en Python → O(1) en el peor caso encontrado.
- Más legible que `any(l == TrafficLight.RED for l in lights)`.

---

## Patrón 4: Formateo Markdown con helpers puros (BR-U3-07, BR-U3-08, BR-U3-11, NFR-U3-P3)

Los helpers de formato son funciones puras sin I/O, testeables con `assert f(x) == expected`.

```python
# src/reporter/report_generator.py
from src.models import TrafficLight

_EMOJI = {
    TrafficLight.GREEN:  "🟢",
    TrafficLight.YELLOW: "🟡",
    TrafficLight.RED:    "🔴",
}

def _emoji_for_light(light: TrafficLight) -> str:
    return _EMOJI[light]


def _format_duration(ms: int) -> str:
    """
    Convierte milisegundos a string legible en monoespaciado.
    Ejemplos: 890 ms → "890 ms", 45_000 → "45 s", 683_000 → "11 min 23 s"
    """
    if ms < 1_000:
        return f"{ms} ms"
    seconds = ms // 1_000
    if seconds < 60:
        return f"{seconds} s"
    minutes, secs = divmod(seconds, 60)
    return f"{minutes} min {secs} s"


def _relative_to_p95(current_ms: int, p95_ms: int) -> str:
    """
    Retorna porcentaje relativo al p95.
    Si p95_ms == 0, retorna 'sin baseline'.
    """
    if p95_ms == 0:
        return "sin baseline"
    pct = int(current_ms / p95_ms * 100)
    return f"{pct}% (p95={_format_duration(p95_ms)})"


def to_markdown(report: ExecutionReport) -> str:
    """
    Genera Markdown legible en CLI y en Slack sin renderizar.
    BR-U3-07: primera línea = H1 con emoji + run_id + ambiente.
    BR-U3-08: segunda línea = banner de auditoría orders_created=0.
    """
    emoji = _emoji_for_light(report.traffic_light)
    env_upper = report.environment_id.upper()
    lines: list[str] = [
        f"# {emoji} TestPilot Run {report.run_id[:8]} — {env_upper}",
        "",
        f"**Status:** {report.traffic_light.value} • "
        f"**Bootstrap:** {str(report.bootstrap_mode).lower()} • "
        f"**Duración:** {_format_duration(report.duration_ms)}",
        "",
        f"> 🔒 Auditoría: `orders_created = {report.orders_created}`",
        "",
    ]

    # Banner especial para bootstrap
    if report.bootstrap_mode:
        success_count = sum(
            1 for pr in report.profile_results
            if pr.flow_result.status == "success"
        )
        lines += [
            f"ℹ️ Modo aprendizaje ({success_count}/14 runs success — "
            "no se emiten alertas amarillas hasta tener 14 runs)",
            "",
        ]

    # Tabla resumen de perfiles
    lines += [
        "## Resultados por perfil",
        "",
        "| Perfil | Flow | Status | Duración | vs p95 | Semáforo |",
        "|---|---|---|---|---|---|",
    ]
    for pr in report.profile_results:
        p95_str = "sin baseline"
        if pr.baseline_comparison:
            p95_str = _relative_to_p95(pr.flow_result.duration_ms, pr.baseline_comparison.p95_ms)
        lines.append(
            f"| {pr.profile.name} "
            f"| {pr.flow_result.flow_name} "
            f"| {pr.flow_result.status} "
            f"| {_format_duration(pr.flow_result.duration_ms)} "
            f"| {p95_str} "
            f"| {_emoji_for_light(pr.traffic_light)} |"
        )

    return "\n".join(lines)
```

**Por qué `list[str]` + `"\n".join` y no f-string multilínea:**
- Permite añadir secciones condicionales (bootstrap banner) sin `if` dentro de strings.
- Más fácil de testear sección por sección (`"\n".join(lines[:5])` para el header).
- Evita líneas > 120 chars (BR-U3-11).

---

## Patrón 5: Sanitización del output — test de regex (NFR-U3-S1, BR-U3-10)

Test que verifica que ningún output de U3 contiene patrones de credencial.

```python
# tests/test_reporter.py
import re, json

SENSITIVE_PATTERN = re.compile(
    r"password|secret|token|Authorization|Bearer|api_key",
    re.IGNORECASE,
)

def test_json_output_has_no_sensitive_fields(sample_report):
    raw = to_json_dict(sample_report)
    serialized = json.dumps(raw)
    match = SENSITIVE_PATTERN.search(serialized)
    assert match is None, f"Sensitive field found in JSON output: {match.group()!r}"


def test_markdown_output_has_no_sensitive_fields(sample_report):
    md = to_markdown(sample_report)
    match = SENSITIVE_PATTERN.search(md)
    assert match is None, f"Sensitive field found in Markdown output: {match.group()!r}"


def test_markdown_contains_audit_banner(sample_report):
    md = to_markdown(sample_report)
    assert "orders_created = 0" in md


def test_markdown_starts_with_traffic_light_header(sample_report):
    md = to_markdown(sample_report)
    first_line = md.splitlines()[0]
    assert first_line.startswith("# ")
    assert any(emoji in first_line for emoji in ["🟢", "🟡", "🔴"])
```

**Por qué regex sobre el string serializado y no inspección del dict:**
- Cubre el caso donde un campo válido tiene nombre que parece credencial (`api_version`, `token_count`).
- Serializar a string antes de la regex asegura que se detecta incluso en keys anidadas.

---

## Patrón 6: Suite PBT con hypothesis (PBT-U3-01 a 04 — BLOQUEANTE)

```python
# tests/test_reporter_pbt.py
from hypothesis import given, settings
from hypothesis import strategies as st
from src.reporter.report_generator import (
    to_markdown, to_json_dict,
    _worst_traffic_light, _bootstrap_mode_global,
)
from src.models import TrafficLight, ExecutionReport

traffic_light_strategy = st.sampled_from(list(TrafficLight))


# ── PBT-U3-01: to_markdown nunca lanza para input válido ─────────────────────
@given(report=st.from_type(ExecutionReport))
@settings(max_examples=300)
def test_to_markdown_never_raises(report):
    result = to_markdown(report)
    assert isinstance(result, str)
    assert len(result) > 0


# ── PBT-U3-02: to_json_dict siempre valida contra el schema ──────────────────
@given(report=st.from_type(ExecutionReport))
@settings(max_examples=300)
def test_to_json_dict_always_validates(report):
    # Si lanza jsonschema.ValidationError, el test falla — eso es lo esperado
    raw = to_json_dict(report)
    assert raw["ordersCreated"] == 0   # siempre 0 — BR-U3-01


# ── PBT-U3-03: _worst_traffic_light — monotonicidad e idempotencia ────────────
@given(lights=st.lists(traffic_light_strategy, min_size=1, max_size=10))
def test_worst_traffic_light_idempotent(lights):
    result = _worst_traffic_light(lights)
    assert _worst_traffic_light([result]) == result


@given(
    a=st.lists(traffic_light_strategy, min_size=1),
    b=st.lists(traffic_light_strategy, min_size=1),
)
def test_worst_traffic_light_associative(a, b):
    combined = _worst_traffic_light(a + b)
    via_parts = _worst_traffic_light([_worst_traffic_light(a), _worst_traffic_light(b)])
    assert combined == via_parts


@given(lights=st.lists(traffic_light_strategy, min_size=1))
def test_worst_traffic_light_red_dominates(lights):
    with_red = lights + [TrafficLight.RED]
    assert _worst_traffic_light(with_red) == TrafficLight.RED


# ── PBT-U3-04: bootstrap_mode global — conservador (OR) ──────────────────────
@given(report=st.from_type(ExecutionReport))
def test_bootstrap_global_is_conservative(report):
    """Si cualquier perfil está en bootstrap, el global debe ser True."""
    global_bootstrap = report.bootstrap_mode
    any_profile_bootstrap = any(
        pr.baseline_comparison.bootstrap_mode
        for pr in report.profile_results
        if pr.baseline_comparison is not None
    )
    if any_profile_bootstrap:
        assert global_bootstrap is True
```

**Por qué `st.from_type(ExecutionReport)` funciona:**
- Pydantic v2 + hypothesis: `st.from_type` infiere estrategias desde los type hints del modelo.
- Genera instancias con valores válidos para todos los campos — incluyendo enums, listas y opcionales.
- Requiere `hypothesis[cli]` y que los modelos no tengan validadores que rechacen demasiados valores.

**Si `st.from_type` falla para `ExecutionReport`** (por validadores estrictos como `screenshot_on_error=True`), usar `st.builds` con estrategias manuales por campo — el mismo enfoque de U2.

---

## Resumen patrones → NFRs / BRs

| Patrón | NFRs / BRs satisfechos |
|---|---|
| 1. Schema validation inline en `to_json_dict` | NFR-U3-R3, BR-U3-06, NFR-U3-P2 |
| 2. `InvariantViolatedError` no silenciable | NFR-U3-R2, BR-U3-01, RNF-02 |
| 3. `_worst_traffic_light` y `_bootstrap_mode_global` | BR-U3-04, BR-U3-05, PBT-U3-03, PBT-U3-04 |
| 4. Helpers de Markdown puros | BR-U3-07, BR-U3-08, BR-U3-11, NFR-U3-P3 |
| 5. Test de regex sobre output | NFR-U3-S1, BR-U3-10, RNF-03 |
| 6. Suite PBT hypothesis | PBT-U3-01, PBT-U3-02, PBT-U3-03, PBT-U3-04 — BLOQUEANTE |
