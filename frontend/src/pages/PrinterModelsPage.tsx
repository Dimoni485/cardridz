import { useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { PrinterModel } from "../api/types";
import {
  EmptyRow,
  ErrorMessage,
  Modal,
  PageHeader,
  Spinner,
} from "../components/ui";
import { useAsyncData, useDebouncedValue } from "../hooks";
import { useAuth } from "../auth";

interface ModelForm {
  vendor: string;
  name: string;
  notes: string;
}

const EMPTY_FORM: ModelForm = { vendor: "", name: "", notes: "" };

export function PrinterModelsPage() {
  const { canEdit } = useAuth();
  const [query, setQuery] = useState("");
  const search = useDebouncedValue(query, 300);
  const models = useAsyncData(
    () =>
      api.get<PrinterModel[]>(
        `/printer-models?q=${encodeURIComponent(search.trim())}`,
      ),
    [search],
  );

  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<PrinterModel | null>(null);
  const [form, setForm] = useState<ModelForm>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setError(null);
    setShowForm(true);
  }

  function openEdit(model: PrinterModel) {
    setEditing(model);
    setForm({
      vendor: model.vendor,
      name: model.name,
      notes: model.notes ?? "",
    });
    setError(null);
    setShowForm(true);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    const payload = {
      vendor: form.vendor.trim(),
      name: form.name.trim(),
      notes: form.notes.trim() || null,
    };
    try {
      if (editing) {
        await api.patch(`/printer-models/${editing.id}`, payload);
      } else {
        await api.post("/printer-models", payload);
      }
      setShowForm(false);
      models.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить модель");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(model: PrinterModel) {
    if (!window.confirm(`Удалить модель «${model.vendor} ${model.name}»?`)) return;
    setListError(null);
    try {
      await api.delete(`/printer-models/${model.id}`);
      models.reload();
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Не удалось удалить модель");
    }
  }

  return (
    <div>
      <PageHeader
        title="Модели принтеров"
        subtitle="Справочник моделей печатающей техники"
        actions={
          canEdit ? (
            <button className="button button-primary" onClick={openCreate}>
              + Добавить модель
            </button>
          ) : undefined
        }
      />

      <div className="toolbar">
        <input
          className="input toolbar-search"
          placeholder="Поиск по производителю или модели"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>

      {listError && <ErrorMessage message={listError} />}
      {models.loading && <Spinner />}
      {models.error && <ErrorMessage message={models.error} />}

      {models.data && !models.loading && (
        <div className="card table-card">
          <table className="table">
            <thead>
              <tr>
                <th>Производитель</th>
                <th>Модель</th>
                <th>Примечание</th>
                {canEdit && <th />}
              </tr>
            </thead>
            <tbody>
              {models.data.length === 0 && (
                <EmptyRow colSpan={canEdit ? 4 : 3} text="Модели принтеров не найдены" />
              )}
              {models.data.map((model) => (
                <tr key={model.id}>
                  <td>{model.vendor}</td>
                  <td>
                    <strong>{model.name}</strong>
                  </td>
                  <td>{model.notes ?? "—"}</td>
                  {canEdit && (
                    <td className="right nowrap">
                      <button
                        className="button button-small"
                        onClick={() => openEdit(model)}
                      >
                        Изменить
                      </button>
                      <button
                        className="button button-small button-danger-ghost"
                        onClick={() => handleDelete(model)}
                      >
                        Удалить
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showForm && (
        <Modal
          title={editing ? "Редактирование модели принтера" : "Новая модель принтера"}
          onClose={() => setShowForm(false)}
        >
          <form onSubmit={handleSubmit} className="form-grid">
            <label className="field">
              <span>Производитель *</span>
              <input
                className="input"
                value={form.vendor}
                onChange={(event) => setForm({ ...form, vendor: event.target.value })}
                required
                maxLength={100}
                placeholder="HP"
              />
            </label>
            <label className="field">
              <span>Модель *</span>
              <input
                className="input"
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                required
                maxLength={150}
                placeholder="LaserJet Pro M404dn"
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
            {error && (
              <div className="field-wide">
                <ErrorMessage message={error} />
              </div>
            )}
            <div className="form-actions field-wide">
              <button
                type="button"
                className="button button-ghost"
                onClick={() => setShowForm(false)}
              >
                Отмена
              </button>
              <button
                type="submit"
                className="button button-primary"
                disabled={saving}
              >
                {saving ? "Сохранение…" : "Сохранить"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
