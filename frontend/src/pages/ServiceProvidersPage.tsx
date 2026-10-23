import { useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { ServiceProvider } from "../api/types";
import {
  EmptyRow,
  ErrorMessage,
  Modal,
  PageHeader,
  Spinner,
} from "../components/ui";
import { useAsyncData } from "../hooks";

interface ProviderForm {
  name: string;
  inn: string;
  contact_person: string;
  phone: string;
  email: string;
  notes: string;
  is_active: boolean;
}

const EMPTY_FORM: ProviderForm = {
  name: "",
  inn: "",
  contact_person: "",
  phone: "",
  email: "",
  notes: "",
  is_active: true,
};

export function ServiceProvidersPage() {
  const [query, setQuery] = useState("");
  const providers = useAsyncData(
    () =>
      api.get<ServiceProvider[]>(
        `/service-providers?q=${encodeURIComponent(query.trim())}`,
      ),
    [query],
  );

  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<ServiceProvider | null>(null);
  const [form, setForm] = useState<ProviderForm>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setError(null);
    setShowForm(true);
  }

  function openEdit(provider: ServiceProvider) {
    setEditing(provider);
    setForm({
      name: provider.name,
      inn: provider.inn ?? "",
      contact_person: provider.contact_person ?? "",
      phone: provider.phone ?? "",
      email: provider.email ?? "",
      notes: provider.notes ?? "",
      is_active: provider.is_active,
    });
    setError(null);
    setShowForm(true);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    const payload = {
      name: form.name.trim(),
      inn: form.inn.trim() || null,
      contact_person: form.contact_person.trim() || null,
      phone: form.phone.trim() || null,
      email: form.email.trim() || null,
      notes: form.notes.trim() || null,
      is_active: form.is_active,
    };
    try {
      if (editing) {
        await api.patch(`/service-providers/${editing.id}`, payload);
      } else {
        await api.post("/service-providers", payload);
      }
      setShowForm(false);
      providers.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить организацию");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(provider: ServiceProvider) {
    if (!window.confirm(`Удалить организацию «${provider.name}»?`)) return;
    setListError(null);
    try {
      await api.delete(`/service-providers/${provider.id}`);
      providers.reload();
    } catch (err) {
      setListError(
        err instanceof Error ? err.message : "Не удалось удалить организацию",
      );
    }
  }

  return (
    <div>
      <PageHeader
        title="Сервисные организации"
        subtitle="Сторонние организации, выполняющие заправку и восстановление картриджей"
        actions={
          <button className="button button-primary" onClick={openCreate}>
            + Добавить организацию
          </button>
        }
      />

      <div className="toolbar">
        <input
          className="input toolbar-search"
          placeholder="Поиск по названию, ИНН или контактному лицу"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>

      {listError && <ErrorMessage message={listError} />}
      {providers.loading && <Spinner />}
      {providers.error && <ErrorMessage message={providers.error} />}

      {providers.data && !providers.loading && (
        <div className="card table-card">
          <table className="table">
            <thead>
              <tr>
                <th>Организация</th>
                <th>ИНН</th>
                <th>Контактное лицо</th>
                <th>Контакты</th>
                <th>Статус</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {providers.data.length === 0 && <EmptyRow colSpan={6} />}
              {providers.data.map((provider) => (
                <tr key={provider.id}>
                  <td>
                    <strong>{provider.name}</strong>
                    {provider.notes && (
                      <div className="muted small">{provider.notes}</div>
                    )}
                  </td>
                  <td>{provider.inn ?? "—"}</td>
                  <td>{provider.contact_person ?? "—"}</td>
                  <td>
                    {provider.phone ?? "—"}
                    {provider.email && (
                      <div className="muted small">{provider.email}</div>
                    )}
                  </td>
                  <td>
                    <span
                      className={`badge ${provider.is_active ? "badge-active" : "badge-inactive"}`}
                    >
                      {provider.is_active ? "Активна" : "Деактивирована"}
                    </span>
                  </td>
                  <td className="right nowrap">
                    <button
                      className="button button-small"
                      onClick={() => openEdit(provider)}
                    >
                      Изменить
                    </button>
                    <button
                      className="button button-small button-danger-ghost"
                      onClick={() => handleDelete(provider)}
                    >
                      Удалить
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showForm && (
        <Modal
          title={editing ? "Редактирование организации" : "Новая сервисная организация"}
          onClose={() => setShowForm(false)}
        >
          <form onSubmit={handleSubmit} className="form-grid">
            <label className="field field-wide">
              <span>Наименование *</span>
              <input
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                required
                placeholder="ООО «РефиллСервис»"
              />
            </label>
            <label className="field">
              <span>ИНН</span>
              <input
                value={form.inn}
                onChange={(event) => setForm({ ...form, inn: event.target.value })}
                maxLength={12}
              />
            </label>
            <label className="field">
              <span>Контактное лицо</span>
              <input
                value={form.contact_person}
                onChange={(event) =>
                  setForm({ ...form, contact_person: event.target.value })
                }
              />
            </label>
            <label className="field">
              <span>Телефон</span>
              <input
                value={form.phone}
                onChange={(event) => setForm({ ...form, phone: event.target.value })}
              />
            </label>
            <label className="field">
              <span>Email</span>
              <input
                type="email"
                value={form.email}
                onChange={(event) => setForm({ ...form, email: event.target.value })}
              />
            </label>
            <label className="field field-wide">
              <span>Примечание</span>
              <textarea
                rows={2}
                value={form.notes}
                onChange={(event) => setForm({ ...form, notes: event.target.value })}
              />
            </label>
            <label className="field field-checkbox">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(event) =>
                  setForm({ ...form, is_active: event.target.checked })
                }
              />
              <span>Активна</span>
            </label>
            {error && (
              <div className="field-wide">
                <ErrorMessage message={error} />
              </div>
            )}
            <div className="form-actions field-wide">
              <button type="button" className="button" onClick={() => setShowForm(false)}>
                Отмена
              </button>
              <button className="button button-primary" disabled={saving}>
                {saving ? "Сохранение…" : "Сохранить"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
