import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth";
import type { Cartridge, CartridgeModel, Page } from "../api/types";
import { DateField } from "../components/DateField";
import {
  EmptyRow,
  ErrorMessage,
  Modal,
  PageHeader,
  Spinner,
  StatusBadge,
} from "../components/ui";
import { useAsyncData, useDebouncedValue } from "../hooks";
import {
  formatDate,
  formatMoney,
  STATUS_LABELS,
  STATUS_ORDER,
} from "../utils";

interface CreateForm {
  inventory_no: string;
  model_id: string;
  serial_no: string;
  purchase_price: string;
  purchase_date: string;
  notes: string;
  comment: string;
}

const EMPTY_FORM: CreateForm = {
  inventory_no: "",
  model_id: "",
  serial_no: "",
  purchase_price: "",
  purchase_date: "",
  notes: "",
  comment: "",
};

export function CartridgesPage() {
  const { canEdit } = useAuth();
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebouncedValue(query);
  const [status, setStatus] = useState("");
  const [modelId, setModelId] = useState("");
  const [page, setPage] = useState(0);
  const limit = 20;

  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<CreateForm>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setPage(0);
  }, [debouncedQuery, status, modelId]);

  const models = useAsyncData(
    () => api.get<CartridgeModel[]>("/cartridge-models"),
    [],
  );

  const list = useAsyncData(() => {
    const params = new URLSearchParams({
      skip: String(page * limit),
      limit: String(limit),
    });
    if (debouncedQuery.trim()) params.set("q", debouncedQuery.trim());
    if (status) params.set("status", status);
    if (modelId) params.set("model_id", modelId);
    return api.get<Page<Cartridge>>(`/cartridges?${params.toString()}`);
  }, [debouncedQuery, status, modelId, page]);

  function openCreate() {
    setForm({
      ...EMPTY_FORM,
      model_id: models.data && models.data.length > 0 ? String(models.data[0].id) : "",
    });
    setFormError(null);
    setShowCreate(true);
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    if (!form.model_id) {
      setFormError("Выберите модель картриджа");
      return;
    }
    setSaving(true);
    try {
      await api.post<Cartridge>("/cartridges", {
        inventory_no: form.inventory_no.trim(),
        model_id: Number(form.model_id),
        serial_no: form.serial_no.trim() || null,
        purchase_price: form.purchase_price ? Number(form.purchase_price) : null,
        purchase_date: form.purchase_date || null,
        notes: form.notes.trim() || null,
        comment: form.comment.trim() || null,
      });
      setShowCreate(false);
      list.reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Не удалось создать картридж");
    } finally {
      setSaving(false);
    }
  }

  const total = list.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / limit));

  return (
    <div>
      <PageHeader
        title="Картриджи"
        subtitle="Учёт экземпляров: склад, выдача, установка, обслуживание"
        actions={
          canEdit ? (
            <button className="button button-primary" onClick={openCreate}>
              + Добавить картридж
            </button>
          ) : undefined
        }
      />

      <div className="toolbar">
        <input
          className="input toolbar-search"
          placeholder="Поиск по номеру, серийному номеру или модели"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <select
          className="input"
          value={status}
          onChange={(event) => setStatus(event.target.value)}
        >
          <option value="">Все статусы</option>
          {STATUS_ORDER.map((item) => (
            <option key={item} value={item}>
              {STATUS_LABELS[item]}
            </option>
          ))}
        </select>
        <select
          className="input"
          value={modelId}
          onChange={(event) => setModelId(event.target.value)}
        >
          <option value="">Все модели</option>
          {models.data?.map((model) => (
            <option key={model.id} value={model.id}>
              {model.vendor} {model.name}
            </option>
          ))}
        </select>
      </div>

      {list.loading && <Spinner />}
      {list.error && <ErrorMessage message={list.error} />}

      {list.data && !list.loading && (
        <>
          <div className="card table-card">
            <table className="table">
              <thead>
                <tr>
                  <th>№</th>
                  <th>Модель</th>
                  <th>Статус</th>
                  <th>Местонахождение</th>
                  <th>Заправок</th>
                  <th>Стоимость</th>
                  <th>Дата закупки</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {list.data.items.length === 0 && (
                  <EmptyRow colSpan={8} text="Картриджи не найдены" />
                )}
                {list.data.items.map((cartridge) => (
                  <tr key={cartridge.id}>
                    <td className="nowrap">
                      <Link to={`/cartridges/${cartridge.id}`} className="link-strong">
                        {cartridge.inventory_no}
                      </Link>
                      {cartridge.serial_no && (
                        <div className="muted small">S/N {cartridge.serial_no}</div>
                      )}
                    </td>
                    <td>
                      {cartridge.model.vendor} {cartridge.model.name}
                      <div className="muted small">
                        {cartridge.model.kind === "original" ? "Оригинал" : "Совместимый"}
                      </div>
                    </td>
                    <td>
                      <StatusBadge status={cartridge.status} />
                    </td>
                    <td>
                      {cartridge.employee?.full_name ??
                        (cartridge.printer
                          ? `${cartridge.printer.inventory_no} · ${cartridge.printer.location ?? ""}`
                          : "—")}
                    </td>
                    <td className="center">{cartridge.refill_count}</td>
                    <td>{formatMoney(cartridge.purchase_price)}</td>
                    <td className="nowrap">{formatDate(cartridge.purchase_date)}</td>
                    <td className="right">
                      <Link
                        to={`/cartridges/${cartridge.id}`}
                        className="button button-small"
                      >
                        Открыть
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="pagination">
            <span className="muted">
              Всего: {total}. Страница {page + 1} из {totalPages}
            </span>
            <div className="pagination-actions">
              <button
                className="button button-small"
                disabled={page === 0}
                onClick={() => setPage((value) => Math.max(0, value - 1))}
              >
                ← Назад
              </button>
              <button
                className="button button-small"
                disabled={page + 1 >= totalPages}
                onClick={() => setPage((value) => value + 1)}
              >
                Вперёд →
              </button>
            </div>
          </div>
        </>
      )}

      {showCreate && (
        <Modal title="Новый картридж" onClose={() => setShowCreate(false)}>
          <form onSubmit={handleCreate} className="form-grid">
            <label className="field">
              <span>Инвентарный номер *</span>
              <input
                value={form.inventory_no}
                onChange={(event) =>
                  setForm({ ...form, inventory_no: event.target.value })
                }
                required
                placeholder="CRT-0015"
              />
            </label>
            <label className="field">
              <span>Модель *</span>
              <select
                value={form.model_id}
                onChange={(event) => setForm({ ...form, model_id: event.target.value })}
                required
              >
                <option value="">Выберите модель</option>
                {models.data?.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.vendor} {model.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Серийный номер</span>
              <input
                value={form.serial_no}
                onChange={(event) => setForm({ ...form, serial_no: event.target.value })}
              />
            </label>
            <label className="field">
              <span>Стоимость, ₽</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={form.purchase_price}
                onChange={(event) =>
                  setForm({ ...form, purchase_price: event.target.value })
                }
              />
            </label>
            <label className="field">
              <span>Дата закупки</span>
              <DateField
                value={form.purchase_date}
                onChange={(value) => setForm({ ...form, purchase_date: value })}
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
            <label className="field field-wide">
              <span>Комментарий к приходу</span>
              <input
                value={form.comment}
                onChange={(event) => setForm({ ...form, comment: event.target.value })}
                placeholder="Например: накладная № 42"
              />
            </label>
            {formError && (
              <div className="field-wide">
                <ErrorMessage message={formError} />
              </div>
            )}
            <div className="form-actions field-wide">
              <button
                type="button"
                className="button"
                onClick={() => setShowCreate(false)}
              >
                Отмена
              </button>
              <button className="button button-primary" disabled={saving}>
                {saving ? "Сохранение…" : "Добавить"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
