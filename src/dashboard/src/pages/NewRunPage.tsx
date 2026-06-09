// P2: Launch new run
// BR-MD0-01: payload NEVER includes store_url or credentials
// BR-MD0-07: validations before submit
// NFR-MD0-R2: idempotent submit (Pattern 6 nfr-design.md)
// capture_intermediate_screenshots is ALWAYS false (const, ADR-003) — NOT shown in UI
// INVARIANT: schema_version must be 'v2'; no legacy hyphenated names

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type {
  FlowName,
  ProfileName,
  RunMode,
  ProductItem,
  SyntheticUserConfig,
} from '@/types/api';
import { FLOW_NAMES, PROFILE_NAMES } from '@/types/api';
import { apiClient } from '@/api/client';
import type { ApiError } from '@/api/client';
import { useEnvironments } from '@/hooks/useEnvironments';

const FLOW_LABELS: Record<FlowName, string> = {
  checkout_full: 'Checkout completo',
  checkout_card_declined: 'Checkout (tarjeta declinada)',
  search_and_filter: 'Búsqueda y filtros',
  browse_discounted_products: 'Navegación productos con descuento',
  pdp_validation: 'Validación PDP',
  cart_review: 'Revisión de carrito',
  full_journey: 'Recorrido completo (full_journey)',
};

const PROFILE_LABELS: Record<ProfileName, string> = {
  mobile_co: 'Móvil Colombia',
  desktop_co: 'Escritorio Colombia',
  desktop_ec: 'Escritorio Ecuador',
};

export function NewRunPage() {
  const navigate = useNavigate();
  const { activeEnvironments, loading: envsLoading } = useEnvironments();

  const [environmentId, setEnvironmentId] = useState('');
  const [selectedFlows, setSelectedFlows] = useState<Set<FlowName>>(new Set());
  const [selectedProfiles, setSelectedProfiles] = useState<Set<ProfileName>>(new Set());
  const [mode, setMode] = useState<RunMode>('gate');
  const [products, setProducts] = useState<ProductItem[]>([
    { search_term: '', validate_variant: true },
  ]);
  const [timeoutSeconds, setTimeoutSeconds] = useState<number>(180);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [formErrors, setFormErrors] = useState<string[]>([]);

  // --- Validation ---
  function validate(): string[] {
    const errors: string[] = [];
    if (!environmentId) errors.push('Selecciona un ambiente activo.');
    if (products.filter((p) => p.search_term.trim().length >= 2).length === 0) {
      errors.push('Agrega al menos un producto con término de búsqueda (mín. 2 caracteres).');
    }
    if (selectedFlows.size === 0) errors.push('Selecciona al menos un flow.');
    if (selectedProfiles.size === 0) errors.push('Selecciona al menos un perfil.');
    const env = activeEnvironments.find((e) => e.environment_id === environmentId);
    if (environmentId && !env) errors.push('El ambiente seleccionado no está activo.');
    return errors;
  }

  // --- Build payload (BR-MD0-01: NO store_url, NO credentials) ---
  function buildPayload(): SyntheticUserConfig {
    const config: SyntheticUserConfig = {
      schema_version: 'v2',
      environment_id: environmentId,
      flows: Array.from(selectedFlows),
      mode,
      profiles: Array.from(selectedProfiles),
      products: products
        .filter((p) => p.search_term.trim().length >= 2)
        .map((p) => ({ search_term: p.search_term.trim(), validate_variant: p.validate_variant })),
    };
    if (timeoutSeconds !== 180) {
      config.options = {
        timeout_seconds: timeoutSeconds,
        capture_intermediate_screenshots: false, // INVARIANT
      };
    }
    // Verify: payload contains NO store_url, NO credentials
    // (TypeScript type system already enforces this)
    return config;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errors = validate();
    if (errors.length > 0) {
      setFormErrors(errors);
      return;
    }
    if (submitting) return; // idempotence guard (NFR-MD0-R2)
    setSubmitting(true);
    setSubmitError(null);
    setFormErrors([]);

    try {
      const payload = buildPayload();
      const result = await apiClient.launchRun(payload);
      // On success, navigate to live view — submitting stays true (page replaced)
      navigate(`/runs/${result.run_id}/live`);
    } catch (err) {
      setSubmitError((err as ApiError).message);
      setSubmitting(false); // allow retry
    }
  };

  const toggleFlow = (flow: FlowName) => {
    setSelectedFlows((prev) => {
      const next = new Set(prev);
      if (next.has(flow)) next.delete(flow);
      else next.add(flow);
      return next;
    });
  };

  const toggleProfile = (profile: ProfileName) => {
    setSelectedProfiles((prev) => {
      const next = new Set(prev);
      if (next.has(profile)) next.delete(profile);
      else next.add(profile);
      return next;
    });
  };

  const addProduct = () =>
    setProducts((prev) => [...prev, { search_term: '', validate_variant: true }]);

  const updateProduct = (idx: number, field: keyof ProductItem, value: string | boolean) => {
    setProducts((prev) => prev.map((p, i) => (i === idx ? { ...p, [field]: value } : p)));
  };

  const removeProduct = (idx: number) =>
    setProducts((prev) => prev.filter((_, i) => i !== idx));

  const payload = buildPayload();
  const isValid = validate().length === 0;

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900">Lanzar nuevo run</h1>

      {submitError && (
        <div className="bg-red-50 border border-red-200 rounded p-4 text-red-700">
          {submitError}
        </div>
      )}

      {formErrors.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded p-4">
          <ul className="list-disc list-inside text-yellow-800 text-sm space-y-1">
            {formErrors.map((err, i) => (
              <li key={i}>{err}</li>
            ))}
          </ul>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Ambiente */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Ambiente <span className="text-red-500">*</span>
          </label>
          <select
            value={environmentId}
            onChange={(e) => setEnvironmentId(e.target.value)}
            disabled={envsLoading}
            className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            aria-label="Seleccionar ambiente"
          >
            <option value="">-- Selecciona un ambiente activo --</option>
            {activeEnvironments.map((env) => (
              <option key={env.environment_id} value={env.environment_id}>
                {env.display_name} ({env.environment_id})
              </option>
            ))}
          </select>
        </div>

        {/* Modo */}
        <div>
          <span className="block text-sm font-medium text-gray-700 mb-2">Modo</span>
          <div className="flex gap-4">
            {(['gate', 'exploratory'] as RunMode[]).map((m) => (
              <label key={m} className="flex items-start gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="mode"
                  value={m}
                  checked={mode === m}
                  onChange={() => setMode(m)}
                  className="mt-1"
                />
                <div>
                  <span className="text-sm font-medium text-gray-900">{m}</span>
                  <p className="text-xs text-gray-500">
                    {m === 'gate'
                      ? 'Determinista, entra al baseline, veredicto de deploy.'
                      : 'Descubrimiento/auditoría ad-hoc. No entra al baseline ni cuenta como deploy-safe.'}
                  </p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Flows */}
        <div>
          <span className="block text-sm font-medium text-gray-700 mb-2">
            Flows <span className="text-red-500">*</span>
          </span>
          <div className="space-y-2">
            {FLOW_NAMES.map((flow) => (
              <label key={flow} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  value={flow}
                  checked={selectedFlows.has(flow)}
                  onChange={() => toggleFlow(flow)}
                  className="rounded focus:ring-2 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-800">
                  <span className="font-mono text-xs text-gray-500 mr-2">{flow}</span>
                  {FLOW_LABELS[flow]}
                </span>
              </label>
            ))}
          </div>
        </div>

        {/* Profiles */}
        <div>
          <span className="block text-sm font-medium text-gray-700 mb-2">
            Perfiles <span className="text-red-500">*</span>
          </span>
          <div className="flex gap-6">
            {PROFILE_NAMES.map((profile) => (
              <label key={profile} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  value={profile}
                  checked={selectedProfiles.has(profile)}
                  onChange={() => toggleProfile(profile)}
                  className="rounded focus:ring-2 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-800">
                  <span className="font-mono text-xs text-gray-500">{profile}</span>
                  <span className="ml-1">{PROFILE_LABELS[profile]}</span>
                </span>
              </label>
            ))}
          </div>
        </div>

        {/* Products */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="block text-sm font-medium text-gray-700">
              Productos <span className="text-red-500">*</span>
            </span>
            <button
              type="button"
              onClick={addProduct}
              className="text-sm text-blue-600 hover:text-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded px-2 py-1"
            >
              + Agregar producto
            </button>
          </div>
          <div className="space-y-3">
            {products.map((product, idx) => (
              <div key={idx} className="flex items-center gap-3 bg-gray-50 rounded p-3">
                <input
                  type="text"
                  value={product.search_term}
                  onChange={(e) => updateProduct(idx, 'search_term', e.target.value)}
                  placeholder="Término de búsqueda (ej: camisa roja)"
                  minLength={2}
                  maxLength={128}
                  className="flex-1 border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  aria-label={`Término de búsqueda del producto ${idx + 1}`}
                />
                <label className="flex items-center gap-1.5 text-sm text-gray-700 shrink-0">
                  <input
                    type="checkbox"
                    checked={product.validate_variant ?? true}
                    onChange={(e) => updateProduct(idx, 'validate_variant', e.target.checked)}
                    className="rounded focus:ring-2 focus:ring-blue-500"
                    aria-label={`Validar variante del producto ${idx + 1}`}
                  />
                  Validar variante
                </label>
                {products.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeProduct(idx)}
                    className="text-red-500 hover:text-red-700 text-sm focus:outline-none focus:ring-2 focus:ring-red-500 rounded px-1"
                    aria-label={`Eliminar producto ${idx + 1}`}
                  >
                    ✕
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Timeout */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Timeout por flow (segundos)
          </label>
          <input
            type="number"
            value={timeoutSeconds}
            onChange={(e) => setTimeoutSeconds(Number(e.target.value))}
            min={30}
            max={600}
            className="w-32 border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <span className="ml-2 text-xs text-gray-400">Rango: 30–600 s. Default: 180 s.</span>
        </div>

        {/* JSON preview */}
        <div>
          <span className="block text-sm font-medium text-gray-700 mb-2">
            Vista previa del payload (verificar antes de enviar)
          </span>
          <pre className="bg-gray-900 text-green-300 rounded p-4 text-xs overflow-x-auto">
            {JSON.stringify(payload, null, 2)}
          </pre>
          <p className="text-xs text-gray-400 mt-1">
            Este JSON es lo que se enviará a POST /v1/run. No contiene credenciales ni store_url.
          </p>
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={submitting || !isValid}
          className="px-6 py-3 bg-blue-600 text-white font-medium rounded hover:bg-blue-700 disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
          aria-disabled={submitting || !isValid}
        >
          {submitting ? 'Lanzando...' : 'Lanzar Run'}
        </button>
      </form>
    </div>
  );
}
