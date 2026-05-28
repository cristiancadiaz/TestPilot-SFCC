# Performance Test Instructions — TestPilot SFCC

## Herramientas requeridas

```bash
pip install -e ".[dev]"          # incluye pytest, pytest-benchmark
pip install locust==2.31.0       # load test de la API (no incluido en dev extras)
docker                           # para medir cold start y tamaño de imagen
```

---

## 1. Cold start de imagen Docker (NFR-U0-P1: < 5 s)

Mide el tiempo desde `docker run` hasta primera respuesta 200 en `/health`.

```bash
# Construir la imagen primero
docker build -t testpilot-sfcc:perf-test .

# Medir cold start (requiere /health endpoint en U4)
time docker run --rm \
  -e TESTPILOT_API_KEY=perf-test-key \
  -e LOG_LEVEL=WARNING \
  -p 8000:8000 \
  testpilot-sfcc:perf-test &

# Esperar hasta que /health responda
until curl -sf http://localhost:8000/health; do sleep 0.1; done
# El tiempo total del `time` es el cold start

# Criterio: < 5 s desde docker run hasta primer 200 OK
```

---

## 2. Tamaño de imagen Docker (NFR-U0-P2: < 2 GB)

```bash
docker build -t testpilot-sfcc:perf-test .
docker image inspect testpilot-sfcc:perf-test --format='{{.Size}}' | \
  awk '{printf "Tamaño imagen: %.1f MB\n", $1/1024/1024}'

# Criterio: < 2048 MB (~2 GB)
```

---

## 3. Funciones puras U2 — cálculo de baseline (NFR-U2-P1: < 1 ms)

```bash
pytest tests/test_baseline_perf.py -v --benchmark-only
```

El archivo `tests/test_baseline_perf.py` debe incluir:

```python
# tests/test_baseline_perf.py
import pytest
from src.baseline.baseline_manager import calculate_p95, compute_traffic_light, is_bootstrap_mode
from src.models import RunRecord, TrafficLight
from datetime import datetime, timezone

@pytest.fixture
def ten_runs():
    return [
        RunRecord(
            run_id=f"r{i}", environment_id="staging",
            profile_name="mobile-co", flow_name="checkout-full",
            duration_ms=3000 + i * 100, status="success",
            created_at=datetime.now(timezone.utc),
        )
        for i in range(10)
    ]

def test_calculate_p95_under_1ms(benchmark, ten_runs):
    result = benchmark(calculate_p95, ten_runs)
    assert benchmark.stats["mean"] < 0.001  # < 1 ms
    assert result > 0

def test_compute_traffic_light_under_1ms(benchmark):
    result = benchmark(compute_traffic_light, 3500, 3300, False)
    assert benchmark.stats["mean"] < 0.001
    assert result in list(TrafficLight)

def test_is_bootstrap_mode_under_1ms(benchmark, ten_runs):
    result = benchmark(is_bootstrap_mode, ten_runs)
    assert benchmark.stats["mean"] < 0.001
```

**Criterio:** `benchmark.stats["mean"] < 0.001` s (< 1 ms) para las tres funciones.

---

## 4. U3 Reporter — serialización (NFR-U3-P1/P2/P3)

```bash
pytest tests/test_reporter_perf.py -v --benchmark-only
```

```python
# tests/test_reporter_perf.py
import pytest
from src.reporter.report_generator import generate_report, to_json_dict, to_markdown
# (requiere fixtures con ExecutionReport válido de 6 perfiles)

def test_generate_report_under_500ms(benchmark, sample_profile_results, sample_baseline_store, sample_config, sample_env):
    result = benchmark(
        generate_report,
        sample_profile_results, sample_baseline_store,
        sample_config, "perf-run-001", sample_env,
        started_at=datetime.now(timezone.utc),
    )
    assert benchmark.stats["mean"] < 0.5   # < 500 ms P95 (NFR-U3-P1)

def test_to_json_dict_under_200ms(benchmark, sample_report):
    result = benchmark(to_json_dict, sample_report)
    assert benchmark.stats["mean"] < 0.2   # < 200 ms (NFR-U3-P2)
    assert "ordersCreated" in result

def test_to_markdown_under_50ms(benchmark, sample_report):
    result = benchmark(to_markdown, sample_report)
    assert benchmark.stats["mean"] < 0.05  # < 50 ms (NFR-U3-P3)
    assert result.startswith("#")
```

**Criterios:**

| Función | Umbral |
|---|---|
| `generate_report` (6 perfiles, InMemory) | < 500 ms |
| `to_json_dict` (6 perfiles + jsonschema) | < 200 ms |
| `to_markdown` (6 perfiles × ~15 pasos) | < 50 ms |

---

## 5. API — throughput bajo carga (RNF-07)

Requiere la aplicación corriendo localmente.

```bash
# Terminal 1: levantar la app
uvicorn src.api.main:app --port 8000

# Terminal 2: load test con locust
locust -f tests/locustfile.py \
  --headless \
  --users 5 \
  --spawn-rate 1 \
  --run-time 60s \
  --host http://localhost:8000
```

```python
# tests/locustfile.py
from locust import HttpUser, task, between

VALID_CONFIG = {
    "environment_id": "staging",
    "products": [{"search_term": "camiseta", "validate_variant": False}],
    "flows": ["checkout-full"],
    "profiles": ["mobile-co"],
    "screenshot_on_success": False,
    "screenshot_on_error": True,
}

class TestPilotUser(HttpUser):
    wait_time = between(1, 3)
    headers = {"X-API-Key": "dev-local-key"}

    @task(3)
    def get_health(self):
        self.client.get("/health")

    @task(2)
    def get_latest_run(self):
        self.client.get("/v1/runs/latest", headers=self.headers)

    @task(1)
    def post_run(self):
        # Solo en entorno de test con mocks — no contra SFCC real
        self.client.post("/v1/run", json=VALID_CONFIG, headers=self.headers)
```

**Criterios de load test:**

| Endpoint | Umbral P95 | Tasa de error aceptable |
|---|---|---|
| `GET /health` | < 50 ms | 0% |
| `GET /v1/runs/latest` | < 200 ms | 0% |
| `POST /v1/run` (con mocks) | < 500 ms | < 1% |

---

## 6. Verificación de ausencia de `time.sleep` (RNF-07 — anti-flake)

```bash
# Ningún sleep en código de executor — falla el build si encuentra uno
grep -rn "time\.sleep" src/executor/
# Esperado: sin resultados (exit code 1 si encuentra matches)

# Alternativa con ruff (configurar en pyproject.toml como regla custom)
rg -n "time\.sleep\(" src/executor/
```

**Criterio:** exit code 0 (sin matches). Cualquier `time.sleep` en `src/executor/` es un fallo bloqueante.

---

## Resumen de criterios por NFR

| NFR | Componente | Umbral | Comando de verificación |
|---|---|---|---|
| NFR-U0-P1 | Cold start Docker | < 5 s | `time docker run` + `curl /health` |
| NFR-U0-P2 | Tamaño imagen | < 2 GB | `docker image inspect` |
| NFR-U2-P1 | `calculate_p95` | < 1 ms | `pytest --benchmark-only test_baseline_perf.py` |
| NFR-U3-P1 | `generate_report` | < 500 ms | `pytest --benchmark-only test_reporter_perf.py` |
| NFR-U3-P2 | `to_json_dict` | < 200 ms | ídem |
| NFR-U3-P3 | `to_markdown` | < 50 ms | ídem |
| RNF-07 | Sin `time.sleep` en executor | 0 ocurrencias | `rg "time\.sleep\(" src/executor/` |
| RNF-07 | API P95 bajo carga | < 500 ms | `locust --headless` |
