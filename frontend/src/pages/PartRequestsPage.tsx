import { useState, type FormEvent } from "react";
import { api } from "../api/client";
import type {
  Part,
  PartRequest,
  PartRequestStatus,
  Printer,
} from "../api/types";
import { useAuth } from "../auth";
import { DateField } from "../components/DateField";
import {
  EmptyRow,
  ErrorMessage,
  Modal,
  PageHeader,
  Spinner,
} from "../components/ui";
import { useAsyncData } from "../hooks";
import {
  formatDate,
  formatDateTime,
  PART_REQUEST_STATUS_LABELS,
} from "../utils";

interface RequestLineForm {
  part_id: string;
  qty: string;
}

interface RequestForm {
  printer_id: string;
  needed_by: string;
  comment: string;
  lines: RequestLineForm[];
}

const EMPTY_FORM: RequestForm = {
  printer_id: "",
  needed_by: "",
  comment: "",
  lines: [{ part_id: "", qty: "1" }],
};

export function PartRequestsPage() {
  const { canEdit } = useAuth();
  const [statusFilter, setStatusFilter] = useState<"" | PartRequestStatus>("");
  const requests = useAsyncData(
    () =>
      api.get<PartRequest[]>(
        statusFilter
          ? `/part-requests?status_filter=${statusFilter}`
          : "/part-requests",
      ),
    [statusFilter],
  );
  const printers = useAsyncData(() => api.get<Printer[]>("/printers"), []);
  const parts = useAsyncData(() => api.get<Part[]>("/parts"), []);

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<RequestForm>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [selected, setSelected] = useState<PartRequest | null>(null);

  function openCreate() {
    setForm(EMPTY_FORM);
    setError(null);
    setShowForm(true);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    const lines = form.lines
      .filter((line) => line.part_id)
      .map((line) => ({
        part_id: Number(line.part_id),
        qty: Number(line.qty || 1),
      }));
    if (lines.length === 0) {
      setError("Добавьте хотя бы одну позицию");
      setSaving(false);
      return;
    }
    try {
      await api.post("/part-requests", {
        printer_id: Number(form.printer_id),
        needed_by: form.needed_by || null,
        comment: form.comment.trim() || null,
        lines,
      });
      setShowForm(false);
      requests.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось создать заявку");
    } finally {
      setSaving(false);
    }
  }

  async function act(request: PartRequest, action: string) {
    setListError(null);
    try {
      const updated = await api.post<PartRequest>(
        `/part-requests/${request.id}/${action}`,
      );
      setSelected(updated);
      requests.reload();
    } catch (err) {
      setListError(
        err instanceof Error ? err.message : "Не удалось изменить статус",
      );
    }
  }

  async function removeRequest(request: PartRequest) {
    if (!window.confirm(`Удалить заявку ${request.number}?`)) return;
    setListError(null);
    try {
      await api.delete(`/part-requests/${request.id}`);
      setSelected(null);
      requests.reload();
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Не удалось удалить");
    }
  }

  function updateLine(index: number, patch: Partial<RequestLineForm>) {
    setForm((current) => ({
      ...current,
      lines: current.lines.map((line, position) =>
        position === index ? { ...line, ...patch } : line,
      ),
    }));
  }

  return (
    <div>
      <PageHeader
        title="Заявки на закупку запчастей"
        subtitle="Заявки для конкретного принтера: черновик → отправлена → заказана → получена"
        actions={
          canEdit ? (
            <button className="button button-primary" onClick={openCreate}>
              + Новая заявка
            </button>
          ) : undefined
        }
      />

      <div className="toolbar">
        <select
          className="input"
          value={statusFilter}
          onChange={(event) =>
            setStatusFilter(event.target.value as "" | PartRequestStatus)
          }
        >
          <option value="">Все статусы</option>
          {Object.entries(PART_REQUEST_STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>

      {listError && <ErrorMessage message={listError} />}
      {requests.loading && <Spinner />}
      {requests.error && <ErrorMessage message={requests.error} />}

      {requests.data && !requests.loading && (
        <div className="card table-card">
          <table className="table">
            <thead>
              <tr>
                <th>№</th>
                <th>Принтер</th>
                <th>Позиций</th>
                <th>Нужно к</th>
                <th>Статус</th>
                <th>Создана</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {requests.data.length === 0 && (
                <EmptyRow colSpan={7} text="Заявок пока нет" />
              )}
              {requests.data.map((request) => (
                <tr key={request.id}>
                  <td>{request.number}</td>
                  <td>
                    {request.printer
                      ? `${request.printer.inventory_no} · ${request.printer.model.vendor} ${request.printer.model.name}`
                      : "—"}
                  </td>
                  <td>
                    {request.lines
                      .map((line) => `${line.part.name} × ${line.qty}`)
                      .join(", ")}
                  </td>
                  <td>{formatDate(request.needed_by)}</td>
                  <td>
                    <span className={`badge badge-request-${request.status}`}>
                      {PART_REQUEST_STATUS_LABELS[request.status]}
                    </span>
                  </td>
                  <td>{formatDate(request.created_at)}</td>
                  <td className="entity-actions">
                    <button
                      className="button button-small"
                      onClick={() => setSelected(request)}
                    >
                      Открыть
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showForm && (
        <Modal title="Новая заявка на закупку" onClose={() => setShowForm(false)} wide>
          <form onSubmit={handleSubmit} className="form-grid">
            <label className="field">
              <span>Принтер *</span>
              <select
                value={form.printer_id}
                onChange={(event) =>
                  setForm({ ...form, printer_id: event.target.value })
                }
                required
              >
                <option value="">— выберите принтер —</option>
                {(printers.data ?? []).map((printer) => (
                  <option key={printer.id} value={printer.id}>
                    {printer.inventory_no} · {printer.model.vendor}{" "}
                    {printer.model.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Нужно к дате</span>
              <DateField
                value={form.needed_by}
                onChange={(value) => setForm({ ...form, needed_by: value })}
              />
            </label>
            <label className="field field-wide">
              <span>Комментарий</span>
              <input
                value={form.comment}
                onChange={(event) =>
                  setForm({ ...form, comment: event.target.value })
                }
              />
            </label>

            <div className="field field-wide">
              <span>Позиции</span>
              {form.lines.map((line, index) => (
                <div className="request-line" key={index}>
                  <select
                    value={line.part_id}
                    onChange={(event) =>
                      updateLine(index, { part_id: event.target.value })
                    }
                  >
                    <option value="">— запчасть —</option>
                    {(parts.data ?? []).map((part) => (
                      <option key={part.id} value={part.id}>
                        {part.name}
                        {part.article ? ` (${part.article})` : ""}
                      </option>
                    ))}
                  </select>
                  <input
                    type="number"
                    min={1}
                    value={line.qty}
                    onChange={(event) =>
                      updateLine(index, { qty: event.target.value })
                    }
                  />
                  <button
                    type="button"
                    className="button button-small button-danger-ghost"
                    onClick={() =>
                      setForm((current) => ({
                        ...current,
                        lines: current.lines.filter(
                          (_, position) => position !== index,
                        ),
                      }))
                    }
                    disabled={form.lines.length === 1}
                  >
                    ✕
                  </button>
                </div>
              ))}
              <button
                type="button"
                className="button button-small"
                onClick={() =>
                  setForm((current) => ({
                    ...current,
                    lines: [...current.lines, { part_id: "", qty: "1" }],
                  }))
                }
              >
                + Позиция
              </button>
            </div>

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
                {saving ? "Сохранение…" : "Создать"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {selected && (
        <Modal
          title={`Заявка ${selected.number}`}
          onClose={() => setSelected(null)}
          wide
        >
          <div className="form-grid">
            <div className="field field-wide">
              <strong>
                {selected.printer
                  ? `${selected.printer.inventory_no} · ${selected.printer.model.vendor} ${selected.printer.model.name}`
                  : "Принтер удалён"}
              </strong>
              <div className="muted small">
                Статус: {PART_REQUEST_STATUS_LABELS[selected.status]} · создана{" "}
                {formatDateTime(selected.created_at)}
                {selected.needed_by && ` · нужно к ${formatDate(selected.needed_by)}`}
              </div>
              {selected.comment && (
                <div className="muted small">Комментарий: {selected.comment}</div>
              )}
            </div>
            <table className="table field-wide">
              <thead>
                <tr>
                  <th>Запчасть</th>
                  <th className="right">Кол-во</th>
                  <th>Примечание</th>
                </tr>
              </thead>
              <tbody>
                {selected.lines.map((line) => (
                  <tr key={line.id}>
                    <td>{line.part.name}</td>
                    <td className="right">{line.qty}</td>
                    <td>{line.note ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="form-actions field-wide">
              {canEdit && selected.status === "draft" && (
                <>
                  <button
                    className="button button-primary"
                    onClick={() => act(selected, "submit")}
                  >
                    Отправить
                  </button>
                  <button
                    className="button button-danger-ghost"
                    onClick={() => removeRequest(selected)}
                  >
                    Удалить
                  </button>
                </>
              )}
              {canEdit && selected.status === "submitted" && (
                <button
                  className="button button-primary"
                  onClick={() => act(selected, "order")}
                >
                  Заказать
                </button>
              )}
              {canEdit && selected.status === "ordered" && (
                <button
                  className="button button-primary"
                  onClick={() => act(selected, "receive")}
                >
                  Получена
                </button>
              )}
              {canEdit &&
                !["received", "cancelled"].includes(selected.status) && (
                  <button
                    className="button button-danger-ghost"
                    onClick={() => act(selected, "cancel")}
                  >
                    Отменить
                  </button>
                )}
              <button className="button" onClick={() => setSelected(null)}>
                Закрыть
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
