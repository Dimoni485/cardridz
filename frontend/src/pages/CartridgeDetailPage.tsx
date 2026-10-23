import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth";
import type {
  Cartridge,
  Employee,
  Operation,
  OperationType,
  Printer,
  ServiceProvider,
  ServiceResult,
} from "../api/types";
import { DateField, DateTimeField } from "../components/DateField";
import {
  EmptyRow,
  ErrorMessage,
  Modal,
  PageHeader,
  Spinner,
  StatusBadge,
} from "../components/ui";
import { useAsyncData } from "../hooks";
import {
  formatDate,
  formatDateTime,
  formatMoney,
  OPERATION_LABELS,
  plural,
  SERVICE_RESULT_LABELS,
  STATUS_LABELS,
  todayIso,
} from "../utils";

interface ActionConfig {
  type: Exclude<OperationType, "receipt">;
  label: string;
  employee?: boolean;
  printer?: boolean;
  provider?: boolean;
  expectedReturn?: boolean;
  cost?: boolean;
  document?: boolean;
  result?: boolean;
  danger?: boolean;
}

const ACTIONS: Record<string, ActionConfig[]> = {
  in_stock: [
    { type: "issue", label: "Выдать сотруднику", employee: true },
    { type: "install", label: "Установить в принтер", printer: true },
    {
      type: "send_refill",
      label: "Отправить на заправку",
      provider: true,
      expectedReturn: true,
      document: true,
    },
    {
      type: "send_restore",
      label: "Отправить на восстановление",
      provider: true,
      expectedReturn: true,
      document: true,
    },
    { type: "write_off", label: "Списать", danger: true },
  ],
  issued: [
    { type: "install", label: "Установить в принтер", printer: true },
    { type: "return", label: "Вернуть на склад", employee: true },
    {
      type: "send_refill",
      label: "Отправить на заправку",
      provider: true,
      expectedReturn: true,
      document: true,
    },
    {
      type: "send_restore",
      label: "Отправить на восстановление",
      provider: true,
      expectedReturn: true,
      document: true,
    },
    { type: "write_off", label: "Списать", danger: true },
  ],
  installed: [
    { type: "uninstall", label: "Снять с принтера" },
    { type: "write_off", label: "Списать", danger: true },
  ],
  in_refill: [
    {
      type: "refill_done",
      label: "Вернуть с заправки",
      cost: true,
      document: true,
      result: true,
    },
  ],
  in_restore: [
    {
      type: "restore_done",
      label: "Вернуть с восстановления",
      cost: true,
      document: true,
      result: true,
    },
  ],
  written_off: [],
};

interface ActionForm {
  employee_id: string;
  printer_id: string;
  service_provider_id: string;
  expected_return_date: string;
  result: string;
  cost: string;
  document_no: string;
  comment: string;
  occurred_at: string;
}

const EMPTY_ACTION: ActionForm = {
  employee_id: "",
  printer_id: "",
  service_provider_id: "",
  expected_return_date: "",
  result: "",
  cost: "",
  document_no: "",
  comment: "",
  occurred_at: "",
};

interface EditForm {
  inventory_no: string;
  serial_no: string;
  purchase_price: string;
  purchase_date: string;
  notes: string;
}

export function CartridgeDetailPage() {
  const { canEdit } = useAuth();
  const { id } = useParams<{ id: string }>();
  const cartridgeId = Number(id);

  const cartridge = useAsyncData(
    () => api.get<Cartridge>(`/cartridges/${cartridgeId}`),
    [cartridgeId],
  );
  const operations = useAsyncData(
    () => api.get<Operation[]>(`/cartridges/${cartridgeId}/operations`),
    [cartridgeId],
  );
  const employees = useAsyncData(
    () => api.get<Employee[]>("/employees?active_only=true"),
    [],
  );
  const printers = useAsyncData(
    () => api.get<Printer[]>("/printers?status=active"),
    [],
  );
  const providers = useAsyncData(
    () => api.get<ServiceProvider[]>("/service-providers?active_only=true"),
    [],
  );

  const [action, setAction] = useState<ActionConfig | null>(null);
  const [actionForm, setActionForm] = useState<ActionForm>(EMPTY_ACTION);
  const [actionError, setActionError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [showEdit, setShowEdit] = useState(false);
  const [editForm, setEditForm] = useState<EditForm>({
    inventory_no: "",
    serial_no: "",
    purchase_price: "",
    purchase_date: "",
    notes: "",
  });
  const [editError, setEditError] = useState<string | null>(null);

  const [message, setMessage] = useState<string | null>(null);

  if (!id) return <ErrorMessage message="Картридж не найден" />;
  if (cartridge.loading) return <Spinner />;
  if (cartridge.error) return <ErrorMessage message={cartridge.error} />;
  if (!cartridge.data) return null;

  const data = cartridge.data;
  const availableActions = (ACTIONS[data.status] ?? []).filter(
    (item) => item.type !== "send_refill" || data.model.refillable,
  );
  const inService =
    data.status === "in_refill" || data.status === "in_restore";
  const showResultSelect = Boolean(
    action &&
      (action.result ||
        (action.type === "write_off" && inService)),
  );
  const resultOptions: ServiceResult[] =
    action?.type === "refill_done"
      ? ["refilled", "failed", "other"]
      : action?.type === "restore_done"
        ? ["restored", "failed", "other"]
        : ["unrepairable", "failed", "other"];
  const serviceOverdue = Boolean(
    data.expected_return_date && data.expected_return_date < todayIso(),
  );

  function openAction(config: ActionConfig) {
    const defaultResult =
      config.type === "refill_done"
        ? "refilled"
        : config.type === "restore_done"
          ? "restored"
          : config.type === "write_off" &&
              (data.status === "in_refill" || data.status === "in_restore")
            ? "unrepairable"
            : "";
    setAction(config);
    setActionForm({ ...EMPTY_ACTION, result: defaultResult });
    setActionError(null);
    setMessage(null);
  }

  async function submitAction(event: FormEvent) {
    event.preventDefault();
    if (!action) return;
    setSubmitting(true);
    setActionError(null);
    try {
      await api.post(`/cartridges/${data.id}/operations`, {
        type: action.type,
        employee_id: actionForm.employee_id ? Number(actionForm.employee_id) : null,
        printer_id: actionForm.printer_id ? Number(actionForm.printer_id) : null,
        service_provider_id: actionForm.service_provider_id
          ? Number(actionForm.service_provider_id)
          : null,
        expected_return_date: actionForm.expected_return_date || null,
        result: actionForm.result || null,
        cost: actionForm.cost ? Number(actionForm.cost) : null,
        document_no: actionForm.document_no.trim() || null,
        comment: actionForm.comment.trim() || null,
        occurred_at: actionForm.occurred_at
          ? new Date(actionForm.occurred_at).toISOString()
          : null,
      });
      setAction(null);
      setMessage("Операция выполнена");
      cartridge.reload();
      operations.reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Не удалось выполнить операцию");
    } finally {
      setSubmitting(false);
    }
  }

  function openEdit() {
    setEditForm({
      inventory_no: data.inventory_no,
      serial_no: data.serial_no ?? "",
      purchase_price: data.purchase_price !== null ? String(data.purchase_price) : "",
      purchase_date: data.purchase_date ?? "",
      notes: data.notes ?? "",
    });
    setEditError(null);
    setShowEdit(true);
  }

  async function submitEdit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setEditError(null);
    try {
      await api.patch(`/cartridges/${data.id}`, {
        inventory_no: editForm.inventory_no.trim(),
        serial_no: editForm.serial_no.trim() || null,
        purchase_price: editForm.purchase_price ? Number(editForm.purchase_price) : null,
        purchase_date: editForm.purchase_date || null,
        notes: editForm.notes.trim() || null,
      });
      setShowEdit(false);
      setMessage("Данные картриджа обновлены");
      cartridge.reload();
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "Не удалось сохранить изменения");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <PageHeader
        title={`Картридж ${data.inventory_no}`}
        subtitle={`${data.model.vendor} ${data.model.name}`}
        actions={
          <div className="page-actions">
            <Link to="/cartridges" className="button">
              ← К списку
            </Link>
            {canEdit && (
              <button className="button" onClick={openEdit}>
                Редактировать
              </button>
            )}
          </div>
        }
      />

      {message && <div className="alert alert-success">{message}</div>}

      <div className="detail-grid">
        <section className="card">
          <div className="card-header">
            <h2>Карточка картриджа</h2>
            <StatusBadge status={data.status} />
          </div>
          <dl className="info-grid">
            <div>
              <dt>Инвентарный номер</dt>
              <dd>{data.inventory_no}</dd>
            </div>
            <div>
              <dt>Серийный номер</dt>
              <dd>{data.serial_no ?? "—"}</dd>
            </div>
            <div>
              <dt>Модель</dt>
              <dd>
                {data.model.vendor} {data.model.name}
              </dd>
            </div>
            <div>
              <dt>Тип</dt>
              <dd>{data.model.kind === "original" ? "Оригинал" : "Совместимый"}</dd>
            </div>
            <div>
              <dt>Ответственный сотрудник</dt>
              <dd>{data.employee?.full_name ?? "—"}</dd>
            </div>
            <div>
              <dt>Принтер</dt>
              <dd>
                {data.printer
                  ? `${data.printer.inventory_no} · ${data.printer.location ?? "—"}`
                  : "—"}
              </dd>
            </div>
            {data.service_provider && (
              <>
                <div>
                  <dt>Сервисная организация</dt>
                  <dd>{data.service_provider.name}</dd>
                </div>
                <div>
                  <dt>Передан в сервис</dt>
                  <dd>{formatDate(data.service_since)}</dd>
                </div>
                <div>
                  <dt>Ожидаемый возврат</dt>
                  <dd className={serviceOverdue ? "text-danger" : ""}>
                    {formatDate(data.expected_return_date)}
                    {serviceOverdue ? " · просрочен" : ""}
                  </dd>
                </div>
              </>
            )}
            <div>
              <dt>Стоимость</dt>
              <dd>{formatMoney(data.purchase_price)}</dd>
            </div>
            <div>
              <dt>Дата закупки</dt>
              <dd>{formatDate(data.purchase_date)}</dd>
            </div>
            <div>
              <dt>Заправок</dt>
              <dd>{data.refill_count}</dd>
            </div>
            <div>
              <dt>Принят на учёт</dt>
              <dd>{formatDate(data.created_at)}</dd>
            </div>
            <div className="info-wide">
              <dt>Примечание</dt>
              <dd>{data.notes ?? "—"}</dd>
            </div>
          </dl>
        </section>

        <section className="card">
          <div className="card-header">
            <h2>Доступные действия</h2>
          </div>
          {!canEdit ? (
            <p className="empty-text">
              Учётная запись имеет доступ только для чтения.
            </p>
          ) : availableActions.length === 0 ? (
            <p className="empty-text">
              Картридж списан. Дальнейшие операции недоступны.
            </p>
          ) : (
            <div className="action-list">
              {availableActions.map((config) => (
                <button
                  key={config.type}
                  className={`button button-block ${config.danger ? "button-danger" : ""}`}
                  onClick={() => openAction(config)}
                >
                  {config.label}
                </button>
              ))}
            </div>
          )}
          {data.status === "in_stock" && (
            <p className="muted small">
              Заправка доступна только для моделей с признаком «подлежит заправке».
            </p>
          )}
        </section>
      </div>

      <section className="card">
        <div className="card-header">
          <h2>История операций</h2>
          <span className="muted">
            {operations.data
              ? `${operations.data.length} ${plural(operations.data.length, [
                  "запись",
                  "записи",
                  "записей",
                ])}`
              : ""}
          </span>
        </div>
        {operations.loading && <Spinner />}
        {operations.error && <ErrorMessage message={operations.error} />}
        {operations.data && (
          <table className="table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Операция</th>
                <th>Статус</th>
                <th>Сотрудник / принтер</th>
                <th>Сервис</th>
                <th>Документ</th>
                <th>Стоимость</th>
                <th>Комментарий</th>
                <th>Пользователь</th>
              </tr>
            </thead>
            <tbody>
              {operations.data.length === 0 && <EmptyRow colSpan={9} />}
              {operations.data.map((operation) => (
                <tr key={operation.id}>
                  <td className="nowrap">{formatDateTime(operation.occurred_at)}</td>
                  <td>{OPERATION_LABELS[operation.type]}</td>
                  <td>
                    {operation.from_status
                      ? `${STATUS_LABELS[operation.from_status]} → `
                      : ""}
                    {STATUS_LABELS[operation.to_status]}
                  </td>
                  <td>
                    {operation.employee?.full_name ??
                      (operation.printer
                        ? `${operation.printer.inventory_no} (${operation.printer.location ?? "—"})`
                        : "—")}
                  </td>
                  <td>
                    {operation.service_provider?.name ?? "—"}
                    {operation.result && (
                      <div className="muted small">
                        {SERVICE_RESULT_LABELS[operation.result]}
                      </div>
                    )}
                  </td>
                  <td>{operation.document_no ?? "—"}</td>
                  <td>{formatMoney(operation.cost)}</td>
                  <td className="wrap-cell">{operation.comment ?? "—"}</td>
                  <td>{operation.user?.full_name ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {action && (
        <Modal
          title={action.label}
          onClose={() => setAction(null)}
        >
          <form onSubmit={submitAction} className="form-grid">
            {action.employee && (
              <label className="field field-wide">
                <span>
                  Сотрудник {action.type === "issue" ? "*" : "(необязательно)"}
                </span>
                <select
                  value={actionForm.employee_id}
                  onChange={(event) =>
                    setActionForm({ ...actionForm, employee_id: event.target.value })
                  }
                  required={action.type === "issue"}
                >
                  <option value="">Не указан</option>
                  {employees.data?.map((employee) => (
                    <option key={employee.id} value={employee.id}>
                      {employee.full_name}
                      {employee.department
                        ? ` — ${employee.department.legal_entity.name}, ${employee.department.name}`
                        : ""}
                    </option>
                  ))}
                </select>
              </label>
            )}

            {action.printer && (
              <label className="field field-wide">
                <span>Принтер {action.type === "install" ? "*" : "(необязательно)"}</span>
                <select
                  value={actionForm.printer_id}
                  onChange={(event) =>
                    setActionForm({ ...actionForm, printer_id: event.target.value })
                  }
                  required={action.type === "install"}
                >
                  <option value="">Не указан</option>
                  {printers.data?.map((printer) => (
                    <option key={printer.id} value={printer.id}>
                      {printer.inventory_no} — {printer.model.vendor} {printer.model.name}
                      {printer.location ? ` (${printer.location})` : ""}
                    </option>
                  ))}
                </select>
              </label>
            )}

            {action.provider && (
              <label className="field field-wide">
                <span>Сервисная организация *</span>
                <select
                  value={actionForm.service_provider_id}
                  onChange={(event) =>
                    setActionForm({
                      ...actionForm,
                      service_provider_id: event.target.value,
                    })
                  }
                  required
                >
                  <option value="">Выберите организацию</option>
                  {providers.data?.map((provider) => (
                    <option key={provider.id} value={provider.id}>
                      {provider.name}
                    </option>
                  ))}
                </select>
              </label>
            )}

            {action.provider && providers.data?.length === 0 && (
              <p className="field-wide muted small">
                Нет активных сервисных организаций. Добавьте их в разделе{" "}
                <Link to="/service-providers">«Сервисные организации»</Link>.
              </p>
            )}

            {action.expectedReturn && (
              <label className="field field-wide">
                <span>Ожидаемая дата возврата</span>
                <DateField
                  value={actionForm.expected_return_date}
                  onChange={(value) =>
                    setActionForm({ ...actionForm, expected_return_date: value })
                  }
                />
              </label>
            )}

            {(action.type === "refill_done" || action.type === "restore_done") &&
              data.service_provider && (
                <div className="field field-wide">
                  <span>Сервисная организация</span>
                  <strong>{data.service_provider.name}</strong>
                  {data.expected_return_date && (
                    <div className="muted small">
                      Ожидаемый возврат: {formatDate(data.expected_return_date)}
                    </div>
                  )}
                </div>
              )}

            {showResultSelect && (
              <label className="field field-wide">
                <span>Результат</span>
                <select
                  value={actionForm.result}
                  onChange={(event) =>
                    setActionForm({ ...actionForm, result: event.target.value })
                  }
                >
                  {resultOptions.map((option) => (
                    <option key={option} value={option}>
                      {SERVICE_RESULT_LABELS[option]}
                    </option>
                  ))}
                </select>
              </label>
            )}

            {action.cost && (
              <label className="field">
                <span>Стоимость, ₽</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={actionForm.cost}
                  onChange={(event) =>
                    setActionForm({ ...actionForm, cost: event.target.value })
                  }
                />
              </label>
            )}

            {action.document && (
              <label className="field">
                <span>Номер документа</span>
                <input
                  value={actionForm.document_no}
                  onChange={(event) =>
                    setActionForm({ ...actionForm, document_no: event.target.value })
                  }
                />
              </label>
            )}

            <label className="field field-wide">
              <span>Дата операции</span>
              <DateTimeField
                value={actionForm.occurred_at}
                onChange={(value) =>
                  setActionForm({ ...actionForm, occurred_at: value })
                }
              />
            </label>

            <label className="field field-wide">
              <span>Комментарий</span>
              <textarea
                rows={3}
                value={actionForm.comment}
                onChange={(event) =>
                  setActionForm({ ...actionForm, comment: event.target.value })
                }
              />
            </label>

            {actionError && (
              <div className="field-wide">
                <ErrorMessage message={actionError} />
              </div>
            )}

            <div className="form-actions field-wide">
              <button type="button" className="button" onClick={() => setAction(null)}>
                Отмена
              </button>
              <button
                className={`button ${action.danger ? "button-danger" : "button-primary"}`}
                disabled={submitting}
              >
                {submitting ? "Выполнение…" : "Подтвердить"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {showEdit && (
        <Modal title="Редактирование картриджа" onClose={() => setShowEdit(false)}>
          <form onSubmit={submitEdit} className="form-grid">
            <label className="field">
              <span>Инвентарный номер *</span>
              <input
                value={editForm.inventory_no}
                onChange={(event) =>
                  setEditForm({ ...editForm, inventory_no: event.target.value })
                }
                required
              />
            </label>
            <label className="field">
              <span>Серийный номер</span>
              <input
                value={editForm.serial_no}
                onChange={(event) =>
                  setEditForm({ ...editForm, serial_no: event.target.value })
                }
              />
            </label>
            <label className="field">
              <span>Стоимость, ₽</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={editForm.purchase_price}
                onChange={(event) =>
                  setEditForm({ ...editForm, purchase_price: event.target.value })
                }
              />
            </label>
            <label className="field">
              <span>Дата закупки</span>
              <DateField
                value={editForm.purchase_date}
                onChange={(value) =>
                  setEditForm({ ...editForm, purchase_date: value })
                }
              />
            </label>
            <label className="field field-wide">
              <span>Примечание</span>
              <textarea
                rows={3}
                value={editForm.notes}
                onChange={(event) =>
                  setEditForm({ ...editForm, notes: event.target.value })
                }
              />
            </label>
            {editError && (
              <div className="field-wide">
                <ErrorMessage message={editError} />
              </div>
            )}
            <div className="form-actions field-wide">
              <button type="button" className="button" onClick={() => setShowEdit(false)}>
                Отмена
              </button>
              <button className="button button-primary" disabled={submitting}>
                {submitting ? "Сохранение…" : "Сохранить"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
