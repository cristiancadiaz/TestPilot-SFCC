# Build Instructions — TestPilot SFCC

## Prerequisitos

- Python 3.12
- `pip` o `uv`
- (Opcional para Docker) Docker Desktop

## Instalación del entorno de desarrollo

```bash
# Clonar y entrar al directorio
cd F:\Development_Projects\IA\06_testing_sintetico

# Crear virtualenv (recomendado)
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

# Instalar dependencias (incluyendo dev)
pip install -e ".[dev]"

# Instalar browsers de Playwright
playwright install chromium
```

## Variables de entorno requeridas

```bash
# Para executor (POST /v1/run con storefront real)
set ANTHROPIC_API_KEY=sk-ant-...   # Windows
set API_KEY=dev-local-key

# Para screenshots locales (opcional, default: /tmp/testpilot-screenshots)
set SCREENSHOT_DIR=C:\tmp\testpilot-screenshots
```

## Verificación estática (antes de ejecutar tests)

```bash
# Linting + formato
ruff check .
ruff format --check .

# Type checking
mypy src/
```

## Build Docker

```bash
docker build -t testpilot-sfcc:local .

# Ejecutar el servidor en Docker
docker run --rm \
  -e API_KEY=dev-local-key \
  -p 8000:8000 \
  testpilot-sfcc:local
```
