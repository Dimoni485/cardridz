import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth";
import type {
  CartridgeColor,
  CartridgeKind,
  CartridgeModel,
  PrinterModel,
} from "../api/types";
import {
  EmptyRow,
  ErrorMessage,
  Modal,
  PageHeader,
  Spinner,
} from "../components/ui";
import { useAsyncData } from "../hooks";
import { COLOR_LABELS, KIND_LABELS } from "../utils";

interface ModelForm {
  vendor: string;
  name: string;
  kind: CartridgeKind;
  color: CartridgeColor;
  resource_pages: string;
  refillable: boolean;
  min_stock: string;
  notes: string;
  printer_model_ids: number[];
}

const EMPTY_FORM: ModelForm = {
  vendor: "",
  name: "",
  kind: "original",
  color: "black",
  resource_pages: "",
  refillable: true,
  min_stock: "0",
  notes: "",
  printer_model_ids: [],
};

export function ModelsPage() {
  const { canEdit } = useAuth();
  const models = useAsyncData(
    () => api.get<CartridgeModel[]>("/cartridge-models"),
    [],
  );
  const printerModels = useAsyncData(
    () => api.get<PrinterModel[]>("/printer-models"),
    [],
  );

  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<CartridgeModel | null>(null);
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

  function openEdit(model: CartridgeModel) {
    setEditing(model);
    setForm({
      vendor: model.vendor,
      name: model.name,
      kind: model.kind,
      color: model.color,
      resource_pages: model.resource_pages !== null ? String(model.resource_pages) : "",
      refillable: model.refillable,
      min_stock: String(model.min_stock),
      notes: model.notes ?? "",
      printer_model_ids: model.printer_models.map((item) => item.id),
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
      kind: form.kind,
      color: form.color,
      resource_pages: form.resource_pages ? Number(form.resource_pages) : null,
      refillable: form.refillable,
      min_stock: Number(form.min_stock || 0),
      notes: form.notes.trim() || null,
      printer_model_ids: form.printer_model_ids,
    };
    try {
      if (editing) {
        await api.patch(`/cartridge-models/${editing.id}`, payload);
      } else {
        await api.post("/cartridge-models", payload);
      }
      setShowForm(false);
      models.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить модель");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(model: CartridgeModel) {
    if (!window.confirm(`Удалить модель «${model.vendor} ${model.name}»?`)) return;
    setListError(null);
    try {
      await api.delete(`/cartridge-models/${model.id}`);
      models.reload();
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Не удалось удалить модель");
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
        title="Модели картриджей"
        subtitle="Справочник моделей, совместимость с принтерами и минимальный остаток"
        actions={
          canEdit ? (
            <button className="button button-primary" onClick={openCreate}>
              + Добавить модель
            </button>
          ) : undefined
        }
      />

      {listError && <ErrorMessage message={listError} />}

      {models.loading && <Spinner />}
      {models.error && <ErrorMessage message={models.error} />}

      {models.data && !models.loading && (
        <div className="card table-card">
          <table className="table">
            <thead>
              <tr>
                <th>Модель</th>
                <th>Тип / цвет</th>
                <th>Ресурс, стр.</th>
                <th>Заправка</th>
                <th>Мин. остаток</th>
                <th>Совместимость</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {models.data.length === 0 && <EmptyRow colSpan={7} />}
              {models.data.map((model) => (
                <tr key={model.id}>
                  <td>
                    <strong>
                      {model.vendor} {model.name}
                    </strong>
                    {model.notes && <div className="muted small">{model.notes}</div>}
                  </td>
                  <td>
                    {KIND_LABELS[model.kind]}
                    <div className="muted small">{COLOR_LABELS[model.color]}</div>
                  </td>
                  <td>{model.resource_pages ?? "—"}</td>
                  <td>{model.refillable ? "Да" : "Нет"}</td>
                  <td>{model.min_stock}</td>
                  <td className="wrap-cell">
                    {model.printer_models.length === 0
                      ? "—"
                      : model.printer_models
                          .map((item) => `${item.vendor} ${item.name}`)
                          .join(", ")}
                  </td>
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
          title={editing ? "Редактирование модели" : "Новая модель картриджа"}
          onClose={() => setShowForm(false)}
          wide
        >
          <form onSubmit={handleSubmit} className="form-grid">
            <label className="field">
              <span>Производитель *</span>
              <input
                value={form.vendor}
                onChange={(event) => setForm({ ...form, vendor: event.target.value })}
                required
                placeholder="HP"
              />
            </label>
            <label className="field">
              <span>Модель *</span>
              <input
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                required
                placeholder="CF259A"
              />
            </label>
            <label className="field">
              <span>Тип</span>
              <select
                value={form.kind}
                onChange={(event) =>
                  setForm({ ...form, kind: event.target.value as CartridgeKind })
                }
              >
                <option value="original">Оригинал</option>
                <option value="compatible">Совместимый</option>
              </select>
            </label>
            <label className="field">
              <span>Цвет</span>
              <select
                value={form.color}
                onChange={(event) =>
                  setForm({ ...form, color: event.target.value as CartridgeColor })
                }
              >
                {Object.entries(COLOR_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Ресурс, страниц</span>
              <input
                type="number"
                min="0"
                value={form.resource_pages}
                onChange={(event) =>
                  setForm({ ...form, resource_pages: event.target.value })
                }
              />
            </label>
            <label className="field">
              <span>Минимальный остаток</span>
              <input
                type="number"
                min="0"
                value={form.min_stock}
                onChange={(event) => setForm({ ...form, min_stock: event.target.value })}
              />
            </label>
            <label className="field field-checkbox">
              <input
                type="checkbox"
                checked={form.refillable}
                onChange={(event) =>
                  setForm({ ...form, refillable: event.target.checked })
                }
              />
              <span>Подлежит заправке</span>
            </label>
            <label className="field field-wide">
              <span>Примечание</span>
              <textarea
                rows={2}
                value={form.notes}
                onChange={(event) => setForm({ ...form, notes: event.target.value })}
              />
            </label>
            <fieldset className="field field-wide checkbox-group">
              <legend>Совместимые модели принтеров</legend>
              {printerModels.data?.length === 0 && (
                <p className="muted small">
                  Справочник моделей принтеров пуст —{" "}
                  <Link to="/printer-models">добавьте модели принтеров</Link>.
                </p>
              )}
              <div className="checkbox-list">
                {printerModels.data?.map((printerModel) => (
                  <label key={printerModel.id} className="checkbox-item">
                    <input
                      type="checkbox"
                      checked={form.printer_model_ids.includes(printerModel.id)}
                      onChange={() => togglePrinterModel(printerModel.id)}
                    />
                    {printerModel.vendor} {printerModel.name}
                  </label>
                ))}
              </div>
            </fieldset>
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
