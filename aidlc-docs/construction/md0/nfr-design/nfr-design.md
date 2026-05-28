# NFR Design — MD0 Dashboard Web Interno

Patrones concretos para satisfacer los NFR-MD0-* (ver `nfr-requirements.md`).

---

## Patrón 1: Custom hook `usePolling` (NFR-MD0-P2, NFR-MD0-R1)

```typescript
function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  shouldContinue: (data: T) => boolean
): { data: T | null; error: ApiError | null; isPolling: boolean } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [isPolling, setIsPolling] = useState(true);
  const failureCount = useRef(0);

  useEffect(() => {
    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout>;

    const tick = async () => {
      try {
        const result = await fetcher();
        if (cancelled) return;
        setData(result);
        setError(null);
        failureCount.current = 0;
        if (shouldContinue(result)) {
          const jitter = Math.random() * 1000 - 500;
          timeoutId = setTimeout(tick, intervalMs + jitter);
        } else {
          setIsPolling(false);
        }
      } catch (err) {
        failureCount.current += 1;
        if (failureCount.current >= 3) {
          setError(err as ApiError);
          setIsPolling(false);  // pausar tras 3 fallos consecutivos
        } else {
          timeoutId = setTimeout(tick, intervalMs);
        }
      }
    };
    tick();
    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
  }, [intervalMs]);

  return { data, error, isPolling };
}
```

**Por qué este patrón:**
- `cancelled` flag + cleanup → detiene polling al desmontar componente (BR-MD0-11).
- Jitter ±500 ms evita thundering herd (NFR-MD0-P2).
- 3 fallos consecutivos → pausa (NFR-MD0-R1).
- `shouldContinue(data)` → detener al detectar terminal state (BR-MD0-11).

---

## Patrón 2: API client centralizado con autenticación

```typescript
class ApiClient {
  private apiKey: string | null = null;

  constructor() {
    this.apiKey = sessionStorage.getItem('testpilot_api_key');
  }

  setApiKey(key: string): void {
    this.apiKey = key;
    sessionStorage.setItem('testpilot_api_key', key);
  }

  async fetch<T>(path: string, options: RequestInit = {}): Promise<T> {
    if (!this.apiKey) throw new ApiError('no_api_key', 'API key not configured');
    
    const response = await fetch(`/v1${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
        ...options.headers,
      },
    });

    if (response.status === 401) {
      this.apiKey = null;
      sessionStorage.removeItem('testpilot_api_key');
      throw new ApiError('unauthorized', 'API key inválida o expirada');
    }

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new ApiError(
        body.error_code || 'unknown',
        body.message || `HTTP ${response.status}`
      );
    }

    return response.json();
  }
}
```

**Por qué:**
- Un solo lugar maneja `X-API-Key` (NFR-MD0-S3).
- Manejo automático de 401 → flush key + throw (BR-MD0-12).
- Para 5xx, lanza `ApiError` con `error_code` — UI decide qué banner mostrar (NFR-MD0-S4).
- Nunca expone el body crudo de errores 500 a la UI (SECURITY-15).

---

## Patrón 3: Componente `<TrafficLight>` accesible (BR-MD0-17, NFR-MD0-U2)

```tsx
type Color = 'green' | 'yellow' | 'red';

function TrafficLight({ color, size = 'lg', bootstrapMode = false }: Props) {
  const config = {
    green: { bg: 'bg-green-500', text: 'OK', icon: '✓', aria: 'Aprobado' },
    yellow: { bg: 'bg-yellow-500', text: 'Alerta', icon: '⚠', aria: 'Alerta' },
    red:    { bg: 'bg-red-600',    text: 'Fallo', icon: '✗', aria: 'Fallo' },
  }[color];

  const muted = bootstrapMode && color === 'yellow';  // BR-MD0-10

  return (
    <div
      role="status"
      aria-label={config.aria}
      className={cn(
        'flex items-center gap-2 rounded-full px-4 py-2 text-white font-bold',
        muted ? 'bg-gray-400' : config.bg,
        size === 'lg' ? 'h-24 text-3xl' : 'h-8 text-sm'
      )}
    >
      <span aria-hidden="true">{config.icon}</span>
      <span>{config.text}</span>
    </div>
  );
}
```

**Por qué:**
- Triple codificación: color + texto + ícono (NFR-MD0-U2, BR-MD0-17) → accesible a daltónicos.
- `role="status"` + `aria-label` → screen readers anuncian el resultado.
- Tamaño mínimo 96px en `size="lg"` (BR-MD0-08).
- Bootstrap mode: yellow se renderiza gris (BR-MD0-10) — no alarma falsa.

---

## Patrón 4: Renderizado seguro de error strings (NFR-MD0-S7)

```tsx
function StepErrorMessage({ error }: { error: string | null }) {
  if (!error) return null;
  return (
    <div className="text-sm text-red-700 font-mono break-all">
      {/* React escape automático — NUNCA dangerouslySetInnerHTML */}
      {error}
    </div>
  );
}
```

**Regla del proyecto:** ESLint rule `react/no-danger: error` en `eslint.config.js`. Esto previene introducir XSS por accidente al renderizar errores de SFCC que podrían contener HTML.

---

## Patrón 5: Galería de screenshots con lazy load (NFR-MD0-P4)

```tsx
function ScreenshotThumbnail({ url, alt }: Props) {
  const [loaded, setLoaded] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref);  // wrap de IntersectionObserver

  return (
    <div ref={ref} className="aspect-video bg-gray-200">
      {inView && (
        <img
          src={`/v1/screenshots/${url}`}
          alt={alt}
          loading="lazy"
          onLoad={() => setLoaded(true)}
          className={cn('w-full h-full object-cover', !loaded && 'opacity-0')}
        />
      )}
    </div>
  );
}
```

**Por qué:**
- IntersectionObserver via `useInView` → carga solo al entrar al viewport (NFR-MD0-P4).
- `loading="lazy"` nativo como defensa adicional.
- Placeholder gris hasta cargar — evita layout shift.

---

## Patrón 6: Form con submit idempotente (NFR-MD0-R2)

```tsx
function LaunchRunForm() {
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (formData: SyntheticUserConfig) => {
    if (submitting) return;        // doble guard
    setSubmitting(true);
    try {
      const result = await api.fetch<{ run_id: string }>('/run', {
        method: 'POST',
        body: JSON.stringify(formData),
      });
      navigate(`/runs/${result.run_id}/live`);
    } catch (err) {
      showErrorBanner(err);
      setSubmitting(false);        // permitir reintento
    }
    // si éxito, no liberamos submitting — navegación ya ocurrió
  };

  return (
    <form onSubmit={handleSubmit}>
      ...
      <button disabled={submitting}>
        {submitting ? 'Lanzando...' : 'Lanzar Run'}
      </button>
    </form>
  );
}
```

**Por qué:**
- Doble-click no genera dos runs (NFR-MD0-R2).
- Si éxito, navegación a P3 reemplaza la pantalla → `submitting` no se libera.
- Si error, `submitting=false` → user reintenta sin recargar.

---

## Patrón 7: Filtros sincronizados con URL (BR-MD0-16)

```typescript
function useRunFilters() {
  const [searchParams, setSearchParams] = useSearchParams();

  const filters: RunFilters = {
    from: searchParams.get('from') || defaultFrom(),
    to: searchParams.get('to') || defaultTo(),
    environment_id: searchParams.get('env') || undefined,
    traffic_light: searchParams.get('tl') as Color | undefined,
    flow: searchParams.get('flow') || undefined,
  };

  const updateFilter = (key: string, value: string | undefined) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next);
  };

  return { filters, updateFilter };
}
```

**Por qué:**
- URL refleja estado de filtros → compartible, restaurable al refresh (BR-MD0-16).
- Estado vive en URL, no en estado local → no se pierde al navegar y volver.

---

## Patrón 8: Headers de seguridad servidos por FastAPI

El backend (U4) agrega los siguientes headers a las responses de archivos estáticos del dashboard:

```python
from fastapi import Response

@app.middleware("http")
async def add_security_headers(request, call_next):
    response: Response = await call_next(request)
    if request.url.path == '/' or request.url.path.endswith('.html'):
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "img-src 'self' data: https://*.s3.amazonaws.com; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "connect-src 'self';"
        )
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response
```

**Cubre:** NFR-MD0-S6 (CSP), defensa frente a clickjacking (X-Frame-Options), MIME sniffing.

**Nota:** este middleware vive en U4 pero su diseño se especifica aquí porque protege MD0. Ver `construction/u4/nfr-design/nfr-design.md`.

---

## Resumen de patrones → NFRs

| Patrón | NFRs satisfechos |
|---|---|
| 1. `usePolling` | NFR-MD0-P2, NFR-MD0-R1, BR-MD0-11 |
| 2. `ApiClient` | NFR-MD0-S3, NFR-MD0-S4, BR-MD0-12 |
| 3. `<TrafficLight>` | NFR-MD0-U2, BR-MD0-08, BR-MD0-10, BR-MD0-17 |
| 4. Escape automático | NFR-MD0-S7 |
| 5. Lazy load screenshots | NFR-MD0-P4 |
| 6. Submit idempotente | NFR-MD0-R2 |
| 7. URL filters | BR-MD0-16 |
| 8. CSP headers | NFR-MD0-S6 |
