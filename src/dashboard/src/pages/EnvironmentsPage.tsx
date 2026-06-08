// P1: Environments management
// BR-MD0-04 to BR-MD0-06: input validation
// BR-MD0-01: no credentials in UI
// BR-MD0-13: error banner + retry
// NFR-MD0-U1: keyboard navigation
// NFR-MD0-R3: form keeps values on error

import { useState } from 'react';
import type { EnvironmentConfig } from '@/types/api';
import { apiClient } from '@/api/client';
import type { ApiError } from '@/api/client';
import { useEnvironments } from '@/hooks/useEnvironments';

// Validation regexes (BR-MD0-04 to BR-MD0-06)
const RE_ENV_ID = /^[a-z][a-z0-9_-]{2,31}$/;
const RE_STORE_URL = /^https:\/\/[a-z0-9.-]+(\/.*)?$/;
const RE_SECRET_PATH = /^testpilot\/[a-z][a-z0-9_-]+\/[a-z][a-z0-9_-]+$/;

interface FormState {
  environment_id: string;
  display_name: string;
  store_url: string;
  env_access_secret_path: string;
  shopper_secret_path: string;
  anti_bot_whitelisted: boolean;
}

const EMPTY_FORM: FormState = {
  environment_id: '',
  display_name: '',
  store_url: '',
  env_access_secret_path: '',
  shopper_secret_path: '',
  anti_bot_whitelisted: false,
};

function validateForm(form: FormState, isEdit: boolean): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!isEdit && !RE_ENV_ID.test(form.environment_id)) {
    errors.environment_id =
      'ID inválido: debe iniciar con letra, 3-32 caracteres, solo letras minúsculas, dígitos, guión o guión bajo.';
  }
  if (!form.display_name.trim()) {
    errors.display_name = 'El nombre de visualización es requerido.';
  }
  if (!RE_STORE_URL.test(form.store_url)) {
    errors.store_url = 'URL inválida: debe comenzar con https://.';
  }
  if (!RE_SECRET_PATH.test(form.env_access_secret_path)) {
    errors.env_access_secret_path =
      'Ruta inválida: formato testpilot/<nombre>/<clave>';
  }
  if (!RE_SECRET_PATH.test(form.shopper_secret_path)) {
    errors.shopper_secret_path =
      'Ruta inválida: formato testpilot/<nombre>/<clave>';
  }
  return errors;
}

export function EnvironmentsPage() {
  const { environments, loading, error: loadError, refetch } = useEnvironments();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const isEdit = editingId !== null;

  const openCreate = () => {
    setForm(EMPTY_FORM);
    setFormErrors({});
    setSubmitError(null);
    setCreating(true);
    setEditingId(null);
  };

  const openEdit = (env: EnvironmentConfig) => {
    setForm({
      environment_id: env.environment_id,
      display_name: env.display_name,
      store_url: env.store_url,
      env_access_secret_path: env.env_access_secret_path,
      shopper_secret_path: env.shopper_secret_path,
      anti_bot_whitelisted: env.anti_bot_whitelisted,
    });
    setFormErrors({});
    setSubmitError(null);
    setEditingId(env.environment_id);
    setCreating(false);
  };

  const closeForm = () => {
    setCreating(false);
    setEditingId(null);
    setForm(EMPTY_FORM);
    setFormErrors({});
    setSubmitError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errors = validateForm(form, isEdit);
    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      return;
    }
    if (submitting) return;
    setSubmitting(true);
    setSubmitError(null);

    try {
      if (isEdit) {
        await apiClient.updateEnvironment(editingId!, {
          display_name: form.display_name,
          store_url: form.store_url,
          env_access_secret_path: form.env_access_secret_path,
          shopper_secret_path: form.shopper_secret_path,
          anti_bot_whitelisted: form.anti_bot_whitelisted,
        });
      } else {
        await apiClient.createEnvironment({
          environment_id: form.environment_id,
          display_name: form.display_name,
          store_url: form.store_url,
          env_access_secret_path: form.env_access_secret_path,
          shopper_secret_path: form.shopper_secret_path,
          anti_bot_whitelisted: form.anti_bot_whitelisted,
          active: true,
        });
      }
      refetch();
      closeForm();
    } catch (err) {
      // NFR-MD0-R3: form keeps values; only show error message
      setSubmitError((err as ApiError).message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeactivate = async (id: string) => {
    if (!window.confirm(`¿Desactivar el ambiente ${id}? No se puede eliminar — solo desactivar.`)) return;
    try {
      await apiClient.deactivateEnvironment(id);
      refetch();
    } catch (err) {
      setSubmitError((err as ApiError).message);
    }
  };

  const updateField = (field: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({
      ...prev,
      [field]: field === 'anti_bot_whitelisted' ? e.target.checked : e.target.value,
    }));
    setFormErrors((prev) => ({ ...prev, [field]: '' }));
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Ambientes</h1>
        <button
          onClick={openCreate}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          + Nuevo ambiente
        </button>
      </div>

      {/* Error banner (BR-MD0-13) */}
      {loadError && (
        <div className="bg-red-50 border border-red-200 rounded p-4 flex items-center justify-between">
          <span className="text-red-700">{loadError.message}</span>
          <button
            onClick={refetch}
            className="text-red-600 underline hover:text-red-800"
          >
            Reintentar
          </button>
        </div>
      )}

      {loading && <p className="text-gray-500">Cargando ambientes...</p>}

      {!loading && (
        <div className="space-y-3">
          {environments.map((env) => (
            <div
              key={env.environment_id}
              className="bg-white border border-gray-200 rounded-lg p-4 flex items-center justify-between"
            >
              <div>
                <span className="font-medium text-gray-900">{env.display_name}</span>
                <span className="ml-2 text-sm font-mono text-gray-500">{env.environment_id}</span>
                {!env.active && (
                  <span className="ml-2 text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">
                    inactivo
                  </span>
                )}
                {!env.anti_bot_whitelisted && (
                  <span className="ml-2 text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full">
                    no whitelisted
                  </span>
                )}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => openEdit(env)}
                  className="text-sm text-blue-600 hover:text-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded px-2 py-1"
                >
                  Editar
                </button>
                {env.active && (
                  <button
                    onClick={() => handleDeactivate(env.environment_id)}
                    className="text-sm text-red-600 hover:text-red-800 focus:outline-none focus:ring-2 focus:ring-red-500 rounded px-2 py-1"
                  >
                    Desactivar
                  </button>
                )}
              </div>
            </div>
          ))}
          {environments.length === 0 && (
            <p className="text-gray-500">No hay ambientes configurados.</p>
          )}
        </div>
      )}

      {/* Create/Edit form */}
      {(creating || isEdit) && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-8 w-full max-w-lg space-y-4">
            <h2 className="text-xl font-bold text-gray-900">
              {isEdit ? `Editar: ${editingId}` : 'Nuevo ambiente'}
            </h2>

            {submitError && (
              <div className="bg-red-50 border border-red-200 rounded p-3 text-red-700 text-sm">
                {submitError}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* environment_id — read-only when editing (BR-MD0 invariant) */}
              <label className="block">
                <span className="text-sm font-medium text-gray-700">ID de ambiente</span>
                <input
                  type="text"
                  value={form.environment_id}
                  onChange={updateField('environment_id')}
                  disabled={isEdit}
                  placeholder="staging"
                  className="mt-1 block w-full border rounded px-3 py-2 text-sm disabled:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  aria-describedby={formErrors.environment_id ? 'err-env-id' : undefined}
                />
                {formErrors.environment_id && (
                  <span id="err-env-id" className="text-xs text-red-600">{formErrors.environment_id}</span>
                )}
              </label>

              <label className="block">
                <span className="text-sm font-medium text-gray-700">Nombre de visualización</span>
                <input
                  type="text"
                  value={form.display_name}
                  onChange={updateField('display_name')}
                  placeholder="Staging"
                  className="mt-1 block w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  aria-describedby={formErrors.display_name ? 'err-display' : undefined}
                />
                {formErrors.display_name && (
                  <span id="err-display" className="text-xs text-red-600">{formErrors.display_name}</span>
                )}
              </label>

              <label className="block">
                <span className="text-sm font-medium text-gray-700">URL del storefront (HTTPS)</span>
                <input
                  type="url"
                  value={form.store_url}
                  onChange={updateField('store_url')}
                  placeholder="https://staging.example.shop"
                  className="mt-1 block w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  aria-describedby={formErrors.store_url ? 'err-url' : undefined}
                />
                {formErrors.store_url && (
                  <span id="err-url" className="text-xs text-red-600">{formErrors.store_url}</span>
                )}
              </label>

              <label className="block">
                <span className="text-sm font-medium text-gray-700">Ruta secret env_access</span>
                <input
                  type="text"
                  value={form.env_access_secret_path}
                  onChange={updateField('env_access_secret_path')}
                  placeholder="testpilot/staging/env-access"
                  className="mt-1 block w-full border rounded px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                  aria-describedby={formErrors.env_access_secret_path ? 'err-env-secret' : undefined}
                />
                {formErrors.env_access_secret_path && (
                  <span id="err-env-secret" className="text-xs text-red-600">{formErrors.env_access_secret_path}</span>
                )}
              </label>

              <label className="block">
                <span className="text-sm font-medium text-gray-700">Ruta secret shopper</span>
                <input
                  type="text"
                  value={form.shopper_secret_path}
                  onChange={updateField('shopper_secret_path')}
                  placeholder="testpilot/staging/shopper"
                  className="mt-1 block w-full border rounded px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                  aria-describedby={formErrors.shopper_secret_path ? 'err-shopper' : undefined}
                />
                {formErrors.shopper_secret_path && (
                  <span id="err-shopper" className="text-xs text-red-600">{formErrors.shopper_secret_path}</span>
                )}
              </label>

              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={form.anti_bot_whitelisted}
                  onChange={updateField('anti_bot_whitelisted')}
                  className="rounded focus:ring-2 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700">IP de TestPilot whitelisted en anti-bot</span>
              </label>

              <div className="flex gap-3 pt-2">
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {submitting ? 'Guardando...' : isEdit ? 'Guardar cambios' : 'Crear ambiente'}
                </button>
                <button
                  type="button"
                  onClick={closeForm}
                  className="px-4 py-2 bg-gray-100 text-gray-700 rounded hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-400"
                >
                  Cancelar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
