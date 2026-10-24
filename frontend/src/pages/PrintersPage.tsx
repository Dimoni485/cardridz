import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth";
import type {
  Department,
  Employee,
  PartUnit,
  Printer,
  PrinterModel,
  PrinterRepair,
  PrinterStatus,
  ServiceProvider,
  ServiceResult,
} from "../api/types";
import { DateField, DateTimeField } from "../components/DateField";
import {
  EmptyRow,
  ErrorMessage,
  Modal,
  PageHeader,
  PrinterStatusBadge,
  Spinner,
} from "../components/ui";
import { useAsyncData } from "../hooks";
import {
  formatDate,
  formatDateTime,
  formatMoney,
  PRINTER_STATUS_LABELS,
  SERVICE_RESULT_LABELS,
  todayIso,
} from "../utils";

interface PrinterForm {
  inventory_no: string;
  serial_no: string;
  model_id: string;
  location: string;
  ip_address: string;
  department_id: string;
  employee_id: string;
  status: PrinterStatus;
  notes: string;
}

const EMPTY_FORM: PrinterForm = {
  inventory_no: "",
  serial_no: "",
  model_id: "",
  location: "",
  ip_address: "",
  department_id: "",
  employee_id: "",
  status: "active",
  notes: "",
};

interface SendForm {
  service_provider_id: string;
  sent_at: string;
  expected_return_date: string;
  document_no: string;
  comment: string;
}

const EMPTY_SEND: SendForm = {
  service_provider_id: "",
  sent_at: "",
  expected_return_date: "",
  document_no: "",
  comment: "",
};

interface ReturnForm {
  returned_at: string;
  cost: string;
  result: ServiceResult;
  document_no: string;
  comment: string;
}

const EMPTY_RETURN: ReturnForm = {
  returned_at: "",
  cost: "",
  result: "repaired",
  document_no: "",
  comment: "",
};

export function PrintersPage() {
  const { canEdit } = useAuth();
  const printers = useAsyncData(() => api.get<Printer[]>("/printers"), []);
  const printerModels = useAsyncData(
    () => api.get<PrinterModel[]>("/printer-models"),
    [],
  );
  const employees = useAsyncData(() => api.get<Employee[]>("/employees"), []);
  const departments = useAsyncData(() => api.get<Department[]>("/departments"), []);
  const providers = useAsyncData(
    () => api.get<ServiceProvider[]>("/service-providers?active_only=true"),
    [],
  );

  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Printer | null>(null);
  const [form, setForm] = useState<PrinterForm>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [sendTarget, setSendTarget] = useState<Printer | null>(null);
  const [sendForm, setSendForm] = useState<SendForm>(EMPTY_SEND);
  const [sendError, setSendError] = useState<string | null>(null);

  const [returnTarget, setReturnTarget] = useState<{
    printer: Printer;
    repair: PrinterRepair;
  } | null>(null);
  const [returnForm, setReturnForm] = useState<ReturnForm>(EMPTY_RETURN);
  const [returnError, setReturnError] = useState<string | null>(null);

  const [historyTarget, setHistoryTarget] = useState<Printer | null>(null);
  const [history, setHistory] = useState<PrinterRepair[] | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);

  const [partsTarget, setPartsTarget] = useState<Printer | null>(null);
  const [printerParts, setPrinterParts] = useState<PartUnit[] | null>(null);
  const [partsError, setPartsError] = useState<string | null>(null);

  function openParts(printer: Printer) {
    setPartsTarget(printer);
    setPrinterParts(null);
    setPartsError(null);
    api
      .get<PartUnit[]>(`/part-units?printer_id=${printer.id}&status=installed`)
      .then(setPrinterParts)
      .catch((err: unknown) =>
        setPartsError(
          err instanceof Error ? err.message : "Не удалось загрузить запчасти",
        ),
      );
  }

  function openCreate() {
    setEditing(null);
    setForm({
      ...EMPTY_FORM,
      model_id:
        printerModels.data && printerModels.data.length > 0
          ? String(printerModels.data[0].id)
          : "",
    });
    setError(null);
    setShowForm(true);
  }

  function openEdit(printer: Printer) {
    setEditing(printer);
    setForm({
      inventory_no: printer.inventory_no,
      serial_no: printer.serial_no ?? "",
      model_id: String(printer.model_id),
      location: printer.location ?? "",
      ip_address: printer.ip_address ?? "",
      department_id: printer.department_id ? String(printer.department_id) : "",
      employee_id: printer.employee_id ? String(printer.employee_id) : "",
      status: printer.status,
      notes: printer.notes ?? "",
    });
    setError(null);
    setShowForm(true);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!form.model_id) {
      setError("Выберите модель принтера");
      return;
    }
    setSaving(true);
    setError(null);
    const payload = {
      inventory_no: form.inventory_no.trim(),
      serial_no: form.serial_no.trim() || null,
      model_id: Number(form.model_id),
      location: form.location.trim() || null,
      ip_address: form.ip_address.trim() || null,
      department_id: form.department_id ? Number(form.department_id) : null,
      employee_id: form.employee_id ? Number(form.employee_id) : null,
      status: form.status,
      notes: form.notes.trim() || null,
    };
    try {
      if (editing) {
        await api.patch(`/printers/${editing.id}`, payload);
      } else {
        await api.post("/printers", payload);
      }
      setShowForm(false);
      printers.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить принтер");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(printer: Printer) {
    if (!window.confirm(`Удалить принтер ${printer.inventory_no}?`)) return;
    setListError(null);
    try {
      await api.delete(`/printers/${printer.id}`);
      printers.reload();
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Не удалось удалить принтер");
    }
  }

  function openSend(printer: Printer) {
    setSendTarget(printer);
    setSendForm({
      ...EMPTY_SEND,
      service_provider_id:
        providers.data && providers.data.length > 0
          ? String(providers.data[0].id)
          : "",
    });
    setSendError(null);
  }

  async function submitSend(event: FormEvent) {
    event.preventDefault();
    if (!sendTarget) return;
    setSaving(true);
    setSendError(null);
    try {
      await api.post(`/printers/${sendTarget.id}/repairs`, {
        service_provider_id: Number(sendForm.service_provider_id),
        sent_at: sendForm.sent_at ? new Date(sendForm.sent_at).toISOString() : null,
        expected_return_date: sendForm.expected_return_date || null,
        document_no: sendForm.document_no.trim() || null,
        comment: sendForm.comment.trim() || null,
      });
      setSendTarget(null);
      printers.reload();
    } catch (err) {
      setSendError(err instanceof Error ? err.message : "Не удалось отправить в ремонт");
    } finally {
      setSaving(false);
    }
  }

  async function openReturn(printer: Printer) {
    setListError(null);
    try {
      const repairs = await api.get<PrinterRepair[]>(
        `/printers/${printer.id}/repairs`,
      );
      const openRepair = repairs.find((item) => item.status === "in_service");
      if (!openRepair) {
        setListError("Открытый ремонт не найден. Проверьте историю принтера.");
        return;
      }
      setReturnTarget({ printer, repair: openRepair });
      setReturnForm(EMPTY_RETURN);
      setReturnError(null);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Не удалось загрузить ремонт");
    }
  }

  async function submitReturn(event: FormEvent) {
    event.preventDefault();
    if (!returnTarget) return;
    setSaving(true);
    setReturnError(null);
    try {
      await api.post(
        `/printers/${returnTarget.printer.id}/repairs/${returnTarget.repair.id}/close`,
        {
          returned_at: returnForm.returned_at
            ? new Date(returnForm.returned_at).toISOString()
            : null,
          cost: returnForm.cost ? Number(returnForm.cost) : null,
          result: returnForm.result,
          document_no: returnForm.document_no.trim() || null,
          comment: returnForm.comment.trim() || null,
        },
      );
      setReturnTarget(null);
      printers.reload();
    } catch (err) {
      setReturnError(
        err instanceof Error ? err.message : "Не удалось оформить возврат",
      );
    } finally {
      setSaving(false);
    }
  }

  async function openHistory(printer: Printer) {
    setHistoryTarget(printer);
    setHistory(null);
    setHistoryError(null);
    try {
      const repairs = await api.get<PrinterRepair[]>(
        `/printers/${printer.id}/repairs`,
      );
      setHistory(repairs);
    } catch (err) {
      setHistoryError(
        err instanceof Error ? err.message : "Не удалось загрузить историю",
      );
    }
  }

  return (
    <div>
      <PageHeader
        title="Принтеры"
        subtitle="Парк печатающей техники, ответственные и ремонт в сервисных организациях"
        actions={
          canEdit ? (
            <button className="button button-primary" onClick={openCreate}>
              + Добавить принтер
            </button>
          ) : undefined
        }
      />

      {listError && <ErrorMessage message={listError} />}
      {printers.loading && <Spinner />}
      {printers.error && <ErrorMessage message={printers.error} />}

      {printers.data && !printers.loading && (
        <div className="card table-card">
          <table className="table table-compact printers-table">
            <thead>
              <tr>
                <th>Инв. номер</th>
                <th>Модель</th>
                <th>Отдел</th>
                <th>Расположение</th>
                <th>Ответственный</th>
                <th>Статус</th>
                <th>Сервис</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {printers.data.length === 0 && <EmptyRow colSpan={8} />}
              {printers.data.map((printer) => {
                const overdue = Boolean(
                  printer.expected_return_date &&
                    printer.expected_return_date < todayIso(),
                );
                return (
                  <tr key={printer.id}>
                    <td>
                      <strong>{printer.inventory_no}</strong>
                      {printer.serial_no && (
                        <div className="muted small">S/N {printer.serial_no}</div>
                      )}
                    </td>
                    <td>
                      {printer.model.vendor} {printer.model.name}
                    </td>
                    <td>
                      {printer.department ? (
                        <>
                          <div>{printer.department.name}</div>
                          <div className="muted small">
                            {printer.department.legal_entity.name}
                            {printer.department.room
                              ? ` · ${printer.department.room}`
                              : ""}
                          </div>
                        </>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>{printer.location ?? "—"}</td>
                    <td>{printer.employee?.full_name ?? "—"}</td>
                    <td>
                      <PrinterStatusBadge status={printer.status} />
                    </td>
                    <td>
                      {printer.service_provider ? (
                        <>
                          <div>{printer.service_provider.name}</div>
                          <div className="muted small">
                            с {formatDate(printer.service_since)}
                            {printer.expected_return_date &&
                              ` · до ${formatDate(printer.expected_return_date)}`}
                          </div>
                          {overdue && (
                            <span className="badge badge-overdue">Просрочен</span>
                          )}
                        </>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="right">
                      <div className="row-actions">
                        {canEdit && printer.status === "active" && (
                          <button
                            className="button button-small"
                            onClick={() => openSend(printer)}
                          >
                            В ремонт
                          </button>
                        )}
                        {canEdit && printer.status === "repair" && (
                          <button
                            className="button button-small"
                            onClick={() => openReturn(printer)}
                          >
                            Возврат
                          </button>
                        )}
                        <button
                          className="button button-small"
                          onClick={() => openHistory(printer)}
                        >
                          История
                        </button>
                        <button
                          className="button button-small"
                          onClick={() => openParts(printer)}
                        >
                          Запчасти
                        </button>
                        {canEdit && (
                          <>
                            <button
                              className="button button-small"
                              onClick={() => openEdit(printer)}
                            >
                              Изменить
                            </button>
                            <button
                              className="button button-small button-danger-ghost"
                              onClick={() => handleDelete(printer)}
                            >
                              Удалить
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {showForm && (
        <Modal
          title={editing ? "Редактирование принтера" : "Новый принтер"}
          onClose={() => setShowForm(false)}
          wide
        >
          <form onSubmit={handleSubmit} className="form-grid">
            <label className="field">
              <span>Инвентарный номер *</span>
              <input
                value={form.inventory_no}
                onChange={(event) =>
                  setForm({ ...form, inventory_no: event.target.value })
                }
                required
                placeholder="PRN-007"
              />
            </label>
            <label className="field">
              <span>Серийный номер</span>
              <input
                value={form.serial_no}
                onChange={(event) => setForm({ ...form, serial_no: event.target.value })}
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
                {printerModels.data?.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.vendor} {model.name}
                  </option>
                ))}
              </select>
              {printerModels.data?.length === 0 && (
                <span className="muted small">
                  Справочник пуст — <Link to="/printer-models">добавьте модель принтера</Link>.
                </span>
              )}
            </label>
            <label className="field">
              <span>Расположение</span>
              <input
                value={form.location}
                onChange={(event) => setForm({ ...form, location: event.target.value })}
                placeholder="каб. 101, Бухгалтерия"
              />
            </label>
            <label className="field">
              <span>IP-адрес</span>
              <input
                value={form.ip_address}
                onChange={(event) => setForm({ ...form, ip_address: event.target.value })}
                placeholder="192.168.10.25"
              />
            </label>
            <label className="field">
              <span>Отдел</span>
              <select
                value={form.department_id}
                onChange={(event) =>
                  setForm({ ...form, department_id: event.target.value })
                }
              >
                <option value="">Не назначен</option>
                {departments.data?.map((department) => (
                  <option key={department.id} value={department.id}>
                    {department.legal_entity.name} — {department.name}
                    {department.room ? ` (${department.room})` : ""}
                  </option>
                ))}
              </select>
              {departments.data?.length === 0 && (
                <span className="muted small">
                  Список отделов пуст —{" "}
                  <Link to="/entities">добавьте отделы</Link>.
                </span>
              )}
            </label>
            <label className="field">
              <span>Ответственный</span>
              <select
                value={form.employee_id}
                onChange={(event) =>
                  setForm({ ...form, employee_id: event.target.value })
                }
              >
                <option value="">Не назначен</option>
                {employees.data?.map((employee) => (
                  <option key={employee.id} value={employee.id}>
                    {employee.full_name}
                    {employee.department ? ` — ${employee.department.name}` : ""}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Статус</span>
              <select
                value={form.status}
                onChange={(event) =>
                  setForm({ ...form, status: event.target.value as PrinterStatus })
                }
              >
                {Object.entries(PRINTER_STATUS_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
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

      {sendTarget && (
        <Modal
          title={`Отправить в ремонт: ${sendTarget.inventory_no}`}
          onClose={() => setSendTarget(null)}
        >
          <form onSubmit={submitSend} className="form-grid">
            <label className="field field-wide">
              <span>Сервисная организация *</span>
              <select
                value={sendForm.service_provider_id}
                onChange={(event) =>
                  setSendForm({
                    ...sendForm,
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
            {providers.data?.length === 0 && (
              <p className="field-wide muted small">
                Нет активных сервисных организаций. Добавьте их в разделе
                «Сервисные организации».
              </p>
            )}
            <label className="field">
              <span>Ожидаемая дата возврата</span>
              <DateField
                value={sendForm.expected_return_date}
                onChange={(value) =>
                  setSendForm({ ...sendForm, expected_return_date: value })
                }
              />
            </label>
            <label className="field">
              <span>Номер акта</span>
              <input
                value={sendForm.document_no}
                onChange={(event) =>
                  setSendForm({ ...sendForm, document_no: event.target.value })
                }
              />
            </label>
            <label className="field field-wide">
              <span>Дата отправки</span>
              <DateTimeField
                value={sendForm.sent_at}
                onChange={(value) => setSendForm({ ...sendForm, sent_at: value })}
              />
            </label>
            <label className="field field-wide">
              <span>Неисправность / комментарий</span>
              <textarea
                rows={3}
                value={sendForm.comment}
                onChange={(event) =>
                  setSendForm({ ...sendForm, comment: event.target.value })
                }
              />
            </label>
            {sendError && (
              <div className="field-wide">
                <ErrorMessage message={sendError} />
              </div>
            )}
            <div className="form-actions field-wide">
              <button type="button" className="button" onClick={() => setSendTarget(null)}>
                Отмена
              </button>
              <button className="button button-primary" disabled={saving}>
                {saving ? "Отправка…" : "Отправить в ремонт"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {returnTarget && (
        <Modal
          title={`Возврат из ремонта: ${returnTarget.printer.inventory_no}`}
          onClose={() => setReturnTarget(null)}
        >
          <div className="service-note">
            <div>
              <span>Сервисная организация</span>
              <strong>
                {returnTarget.repair.service_provider?.name ?? "—"}
              </strong>
            </div>
            <div>
              <span>Отправлен</span>
              <strong>{formatDateTime(returnTarget.repair.sent_at)}</strong>
            </div>
            <div>
              <span>Ожидаемый возврат</span>
              <strong>{formatDate(returnTarget.repair.expected_return_date)}</strong>
            </div>
          </div>
          <form onSubmit={submitReturn} className="form-grid">
            <label className="field field-wide">
              <span>Результат *</span>
              <select
                value={returnForm.result}
                onChange={(event) =>
                  setReturnForm({
                    ...returnForm,
                    result: event.target.value as ServiceResult,
                  })
                }
                required
              >
                <option value="repaired">Отремонтирован</option>
                <option value="failed">Не удалось отремонтировать</option>
                <option value="unrepairable">Не подлежит ремонту</option>
                <option value="other">Другое</option>
              </select>
            </label>
            <label className="field">
              <span>Стоимость, ₽</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={returnForm.cost}
                onChange={(event) =>
                  setReturnForm({ ...returnForm, cost: event.target.value })
                }
              />
            </label>
            <label className="field">
              <span>Номер акта</span>
              <input
                value={returnForm.document_no}
                onChange={(event) =>
                  setReturnForm({ ...returnForm, document_no: event.target.value })
                }
              />
            </label>
            <label className="field field-wide">
              <span>Дата возврата</span>
              <DateTimeField
                value={returnForm.returned_at}
                onChange={(value) =>
                  setReturnForm({ ...returnForm, returned_at: value })
                }
              />
            </label>
            <label className="field field-wide">
              <span>Комментарий</span>
              <textarea
                rows={2}
                value={returnForm.comment}
                onChange={(event) =>
                  setReturnForm({ ...returnForm, comment: event.target.value })
                }
              />
            </label>
            {returnError && (
              <div className="field-wide">
                <ErrorMessage message={returnError} />
              </div>
            )}
            <div className="form-actions field-wide">
              <button type="button" className="button" onClick={() => setReturnTarget(null)}>
                Отмена
              </button>
              <button className="button button-primary" disabled={saving}>
                {saving ? "Сохранение…" : "Оформить возврат"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {partsTarget && (
        <Modal
          title={`Запчасти на ${partsTarget.inventory_no}`}
          onClose={() => setPartsTarget(null)}
          wide
        >
          {partsError && <ErrorMessage message={partsError} />}
          {!printerParts && !partsError && <Spinner label="Загрузка запчастей…" />}
          {printerParts && printerParts.length === 0 && (
            <p className="empty-text">На принтере нет установленных запчастей.</p>
          )}
          {printerParts && printerParts.length > 0 && (
            <table className="table">
              <thead>
                <tr>
                  <th>Запчасть</th>
                  <th>Инв. №</th>
                  <th>Установлена</th>
                  <th>Требует замены</th>
                </tr>
              </thead>
              <tbody>
                {printerParts.map((unit) => (
                  <tr key={unit.id}>
                    <td>
                      <Link to={`/parts/${unit.part.id}`}>{unit.part.name}</Link>
                    </td>
                    <td>{unit.inventory_no}</td>
                    <td>{formatDateTime(unit.installed_at)}</td>
                    <td>
                      {unit.needs_replacement ? (
                        <span className="badge badge-invoice-draft">да</span>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="form-actions">
            <Link
              className="button button-primary"
              to={`/part-requests?printer=${partsTarget.id}`}
            >
              Заявка на закупку
            </Link>
            <button className="button" onClick={() => setPartsTarget(null)}>
              Закрыть
            </button>
          </div>
        </Modal>
      )}

      {historyTarget && (
        <Modal
          title={`История ремонтов: ${historyTarget.inventory_no}`}
          onClose={() => setHistoryTarget(null)}
          wide
        >
          {history === null && !historyError && <Spinner />}
          {historyError && <ErrorMessage message={historyError} />}
          {history && history.length === 0 && (
            <p className="empty-text">Ремонтов ещё не было.</p>
          )}
          {history && history.length > 0 && (
            <table className="table table-compact">
              <thead>
                <tr>
                  <th>Отправлен</th>
                  <th>Организация</th>
                  <th>Акт</th>
                  <th>Ожидался</th>
                  <th>Возвращён</th>
                  <th>Результат</th>
                  <th>Стоимость</th>
                  <th>Статус</th>
                </tr>
              </thead>
              <tbody>
                {history.map((repair) => (
                  <tr key={repair.id}>
                    <td className="nowrap">{formatDateTime(repair.sent_at)}</td>
                    <td>{repair.service_provider?.name ?? "—"}</td>
                    <td>{repair.document_no ?? "—"}</td>
                    <td className="nowrap">
                      {formatDate(repair.expected_return_date)}
                    </td>
                    <td className="nowrap">{formatDateTime(repair.returned_at)}</td>
                    <td>
                      {repair.result ? SERVICE_RESULT_LABELS[repair.result] : "—"}
                    </td>
                    <td>{formatMoney(repair.cost)}</td>
                    <td>
                      <span
                        className={`badge ${
                          repair.status === "in_service"
                            ? "badge-in-refill"
                            : "badge-active"
                        }`}
                      >
                        {repair.status === "in_service"
                          ? "В ремонте"
                          : "Возвращён"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Modal>
      )}
    </div>
  );
}
