import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Part, PartKind, PrinterModel } from "../api/types";
import { useAuth } from "../auth";
import { EmptyRow, ErrorMessage, Modal, PageHeader, Spinner } from "../components/ui";
import { useAsyncData } from "../hooks";
import { PART_KIND_LABELS } from "../utils";

interface PartForm {
  name: string;
  kind: PartKind;
  vendor: string;
  article: string;
  min_stock: string;
  notes: string;
  is_active: boolean;
  printer_model_ids: number[];
}

const EMPTY_FORM: PartForm = {
  name: "",
  kind: "other",
  vendor: "",
  article: "",
  min_stock: "0",
  notes: "",
  is_active: true,
  printer_model_ids: [],
};

export function PartsPage() {
  const { canEdit } = useAuth();
  const [query, setQuery] = useState("");
  const [kindFilter, setKindFilter] = useState<"" | PartKind>("");

  const parts = useAsyncData(() => {
    const params = new URLSearchParams();
    if (query.trim()) params.set("q", query.trim());
    if (kindFilter) params.set("kind", kindFilter);
    const suffix = params.toString();
    return api.get<Part[]>(`/parts${suffix ? `?${suffix}` : ""}`);
  }, [query, kindFilter]);
  const printerModels = useAsyncData(
    () => api.get<PrinterModel[]>("/printer-models"),
    [],
  );

  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Part | null>(null);
  const [form, setForm] = useState<PartForm>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setError(null);
    setShowForm(true);
  }

  function openEdit(part: Part) {
    setEditing(part);
    setForm({
      name: part.name,
      kind: part.kind,
      vendor: part.vendor ?? "",
      article: part.article ?? "",
      min_stock: String(part.min_stock),
      notes: part.notes ?? "",
      is_active: part.is_active,
      printer_model_ids: part.printer_models.map((item) => item.id),
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
      kind: form.kind,
      vendor: form.vendor.trim() || null,
      article: form.article.trim() || null,
      min_stock: Number(form.min_stock || 0),
      notes: form.notes.trim() || null,
      is_active: form.is_active,
      printer_model_ids: form.printer_model_ids,
    };
    try {
      if (editing) {
        await api.patch(`/parts/${editing.id}`, payload);
      } else {
        await api.post("/parts", payload);
      }
      setShowForm(false);
      parts.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить запчасть");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(part: Part) {
    if (!window.confirm(`Удалить запчасть «${part.name}»?`)) return;
    setListError(null);
    try {
      await api.delete(`/parts/${part.id}`);
      parts.reload();
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Не удалось удалить");
    }
  }

  function togglePrinterModel(id: number) {
    setForm((current) => ({
      ...current,
      printer_model_ids: current.printer_model_ids.includes(id)
        ? current.printer_model_ids.filter((item) => item !== id)
        : [...current.printer_model_ids, id],
    }));
  }

  return (
    <div>
      <PageHeader
        title="Запчасти"
        subtitle="Номенклатура запчастей, совместимость с принтерами и остаток на складе"
        actions={
          canEdit ? (
            <button className="button button-primary" onClick={openCreate}>
              + Добавить запчасть
            </button>
          ) : undefined
        }
      />

      <div className="toolbar">
        <input
          className="input toolbar-search"
          placeholder="Поиск по названию, вендору или артикулу"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <select
          className="input"
          value={kindFilter}
          onChange={(event) => setKindFilter(event.target.value as "" | PartKind)}
        >
          <option value="">Все типы</option>
          {Object.entries(PART_KIND_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>

      {listError && <ErrorMessage message={listError} />}
      {parts.loading && <Spinner />}
      {parts.error && <ErrorMessage message={parts.error} />}

      {parts.data && !parts.loading && (
        <div className="card table-card">
          <table className="table">
            <thead>
              <tr>
                <th>Название</th>
                <th>Тип</th>
                <th>Артикул</th>
                <th>Совместимость</th>
                <th className="right">На складе</th>
                <th className="right">Установлено</th>
                <th>Требует замены</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {parts.data.length === 0 && (
                <EmptyRow colSpan={8} text="Запчасти ещё не добавлены" />
              )}
              {parts.data.map((part) => (
                <tr key={part.id}>
                  <td>
                    <Link to={`/parts/${part.id}`}>{part.name}</Link>
                    {part.units_in_stock < part.min_stock && (
                      <span className="badge badge-invoice-draft part-stock-low">
                        ниже минимума
                      </span>
                    )}
                  </td>
                  <td>{PART_KIND_LABELS[part.kind]}</td>
                  <td>{part.article ?? "—"}</td>
                  <td className="part-compat">
                    {part.printer_models.length
                      ? part.printer_models
                          .map((model) => `${model.vendor} ${model.name}`)
                          .join(", ")
                      : "—"}
                  </td>
                  <td className="right">{part.units_in_stock}</td>
                  <td className="right">{part.units_installed}</td>
                  <td>
                    {part.needs_replacement > 0 ? (
                      <span className="badge badge-invoice-draft">
                        {part.needs_replacement}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="entity-actions">
                    <Link className="button button-small" to={`/parts/${part.id}`}>
                      Открыть
                    </Link>
                    {canEdit && (
                      <>
                        <button
                          className="button button-small"
                          onClick={() => openEdit(part)}
                        >
                          Изменить
                        </button>
                        <button
                          className="button button-small button-danger-ghost"
                          onClick={() => handleDelete(part)}
                        >
                          Удалить
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showForm && (
        <Modal
          title={editing ? `Запчасть «${editing.name}»` : "Новая запчасть"}
          onClose={() => setShowForm(false)}
          wide
        >
          <form onSubmit={handleSubmit} className="form-grid">
            <label className="field field-wide">
              <span>Название *</span>
              <input
                value={form.name}
                onChange={(event) =>
                  setForm({ ...form, name: event.target.value })
                }
                required
              />
            </label>
            <label className="field">
              <span>Тип</span>
              <select
                value={form.kind}
                onChange={(event) =>
                  setForm({ ...form, kind: event.target.value as PartKind })
                }
              >
                {Object.entries(PART_KIND_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Минимальный остаток</span>
              <input
                type="number"
                min={0}
                value={form.min_stock}
                onChange={(event) =>
                  setForm({ ...form, min_stock: event.target.value })
                }
              />
            </label>
            <label className="field">
              <span>Вендор</span>
              <input
                value={form.vendor}
                onChange={(event) =>
                  setForm({ ...form, vendor: event.target.value })
                }
              />
            </label>
            <label className="field">
              <span>Артикул</span>
              <input
                value={form.article}
                onChange={(event) =>
                  setForm({ ...form, article: event.target.value })
                }
              />
            </label>
            <label className="field field-wide">
              <span>Совместимые модели принтеров</span>
              <div className="checkbox-list">
                {(printerModels.data ?? []).map((model) => (
                  <label key={model.id} className="checkbox-item">
                    <input
                      type="checkbox"
                      checked={form.printer_model_ids.includes(model.id)}
                      onChange={() => togglePrinterModel(model.id)}
                    />
                    <span>
                      {model.vendor} {model.name}
                    </span>
                  </label>
                ))}
              </div>
            </label>
            <label className="field field-wide">
              <span>Примечание</span>
              <textarea
                rows={2}
                value={form.notes}
                onChange={(event) =>
                  setForm({ ...form, notes: event.target.value })
                }
              />
            </label>
            <label className="field field-checkbox field-wide">
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
              <button
                type="button"
                className="button"
                onClick={() => setShowForm(false)}
              >
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
