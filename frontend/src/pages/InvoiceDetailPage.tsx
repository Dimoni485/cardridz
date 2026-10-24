import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type {
  Cartridge,
  CartridgeModel,
  CartridgeStatus,
  Department,
  Employee,
  Invoice,
  InvoiceApplyResult,
  InvoiceLine,
  InvoiceLineSlot,
  LegalEntity,
  Page,
  Printer,
  ServiceProvider,
} from "../api/types";
import { useAuth } from "../auth";
import { ErrorMessage, PageHeader, Spinner, SuccessMessage } from "../components/ui";
import { useAsyncData } from "../hooks";
import {
  formatDate,
  formatMoneyExact,
  INVOICE_LINE_KIND_LABELS,
  INVOICE_STATUS_LABELS,
  orgName,
  plural,
  STATUS_LABELS,
} from "../utils";

const SERVICE_STATUS_BY_KIND: Record<string, CartridgeStatus> = {
  refill: "in_refill",
  restore: "in_restore",
};

function SlotCartridgeInput({
  slot,
  options,
  listId,
  locked,
  onSelect,
}: {
  slot: InvoiceLineSlot;
  options: Cartridge[];
  listId: string;
  locked: boolean;
  onSelect: (cartridgeId: number | null) => void;
}) {
  const [text, setText] = useState(slot.cartridge?.inventory_no ?? "");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setText(slot.cartridge?.inventory_no ?? "");
    setError(null);
  }, [slot.cartridge?.id]);

  function commit() {
    const value = text.trim();
    if (!value) {
      setError(null);
      if (slot.cartridge) onSelect(null);
      return;
    }
    const found = options.find(
      (item) => item.inventory_no.toLowerCase() === value.toLowerCase(),
    );
    if (!found) {
      setError("не найден или недоступен");
      return;
    }
    setError(null);
    if (found.id !== slot.cartridge?.id) onSelect(found.id);
  }

  return (
    <div className="slot-cartridge">
      <input
        className="input"
        list={listId}
        value={text}
        placeholder="— авто или инв. № —"
        disabled={locked}
        onChange={(event) => {
          setText(event.target.value);
          setError(null);
        }}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            commit();
          }
        }}
      />
      <datalist id={listId}>
        {options.map((item) => (
          <option key={item.id} value={item.inventory_no}>
            {STATUS_LABELS[item.status]}
          </option>
        ))}
      </datalist>
      {error && <span className="slot-error">{error}</span>}
    </div>
  );
}

function LineSlots({
  line,
  departments,
  defaultDepartment,
  locked,
  onPatch,
}: {
  line: InvoiceLine;
  departments: Department[];
  defaultDepartment: string | null;
  locked: boolean;
  onPatch: (slotId: number, payload: Record<string, unknown>) => void;
}) {
  const modelId = line.cartridge_model?.id ?? 0;
  const cartridges = useAsyncData(
    () =>
      modelId
        ? api.get<Page<Cartridge>>(`/cartridges?model_id=${modelId}&limit=200`)
        : Promise.resolve(null),
    [modelId],
  );
  const serviceStatus = SERVICE_STATUS_BY_KIND[line.kind];
  const available = (cartridges.data?.items ?? []).filter(
    (item) => item.status === "in_stock" || item.status === serviceStatus,
  );
  const slots = [...line.slots].sort((left, right) => left.position - right.position);
  const chosen = new Set(
    slots
      .map((slot) => slot.cartridge?.id)
      .filter((value): value is number => typeof value === "number"),
  );
  const defaultLabel = line.department
    ? `как в позиции — ${line.department.name}`
    : defaultDepartment
      ? `как в счёте — ${defaultDepartment}`
      : "по умолчанию";

  return (
    <div className="slot-list">
      <div className="muted small">
        Картриджи позиции ({slots.length}) — сопоставьте каждый
      </div>
      {slots.map((slot) => {
        const options = available.filter(
          (item) => item.id === slot.cartridge?.id || !chosen.has(item.id),
        );
        return (
          <div className="slot-row" key={slot.id}>
            <span className="slot-index">{slot.position}</span>
            <SlotCartridgeInput
              slot={slot}
              options={options}
              listId={`inv-${line.id}-${slot.id}`}
              locked={locked}
              onSelect={(cartridgeId) =>
                onPatch(slot.id, { cartridge_id: cartridgeId })
              }
            />
            <select
              className="input slot-department"
              value={slot.department?.id ?? ""}
              disabled={locked}
              onChange={(event) => {
                const value = event.target.value
                  ? Number(event.target.value)
                  : null;
                if (value === (slot.department?.id ?? null)) return;
                onPatch(slot.id, { department_id: value });
              }}
            >
              <option value="">{defaultLabel}</option>
              {departments.map((department) => (
                <option key={department.id} value={department.id}>
                  {department.name}
                </option>
              ))}
            </select>
          </div>
        );
      })}
      {cartridges.loading && (
        <div className="muted small">Загрузка картриджей…</div>
      )}
      {!cartridges.loading && available.length === 0 && (
        <div className="muted small">
          Свободных картриджей этой модели нет — недостающие будут созданы
          автоматически
        </div>
      )}
    </div>
  );
}

function LineRow({
  line,
  invoice,
  models,
  printers,
  departments,
  defaultDepartment,
  locked,
  onPatch,
  onPatchSlot,
}: {
  line: InvoiceLine;
  invoice: Invoice;
  models: CartridgeModel[];
  printers: Printer[];
  departments: Department[];
  defaultDepartment: string | null;
  locked: boolean;
  onPatch: (payload: Record<string, unknown>) => void;
  onPatchSlot: (slotId: number, payload: Record<string, unknown>) => void;
}) {
  return (
    <tr className={line.skipped ? "row-muted" : undefined}>
      <td>{line.number}</td>
      <td>
        <div>{line.title}</div>
        <div className="muted small">
          {INVOICE_LINE_KIND_LABELS[line.kind]} · код: {line.target_raw} ·{" "}
          {line.qty} {plural(line.qty, ["шт.", "шт.", "шт."])} ×{" "}
          {formatMoneyExact(line.price)}
        </div>
        {line.applied && line.applied_note && (
          <div className="muted small">Проведено: {line.applied_note}</div>
        )}
      </td>
      <td className="right">{formatMoneyExact(line.total)}</td>
      <td className="match-cell">
        {line.applied ? (
          <span className="badge badge-invoice-applied">Проведено</span>
        ) : line.kind === "repair" ? (
          <select
            className="input"
            value={line.printer?.id ?? ""}
            disabled={locked || line.skipped}
            onChange={(event) => {
              const value = event.target.value
                ? Number(event.target.value)
                : null;
              if (value === (line.printer?.id ?? null)) return;
              onPatch({ printer_id: value });
            }}
          >
            <option value="">— выберите принтер —</option>
            {printers.map((printer) => (
              <option key={printer.id} value={printer.id}>
                {printer.inventory_no} · {printer.model.vendor}{" "}
                {printer.model.name}
              </option>
            ))}
          </select>
        ) : (
          <>
            <select
              className="input"
              value={line.cartridge_model?.id ?? ""}
              disabled={locked || line.skipped}
              onChange={(event) => {
                const value = event.target.value
                  ? Number(event.target.value)
                  : null;
                if (value === (line.cartridge_model?.id ?? null)) return;
                onPatch({ cartridge_model_id: value });
              }}
            >
              <option value="">
                — выберите модель —
              </option>
              {models.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.vendor} {model.name}
                </option>
              ))}
            </select>
            {line.cartridge_model && !line.skipped && (
              <LineSlots
                line={line}
                departments={departments}
                defaultDepartment={defaultDepartment}
                locked={locked}
                onPatch={onPatchSlot}
              />
            )}
            {departments.length > 0 && !line.skipped && (
              <div className="line-department">
                <span className="muted small">Подразделение по умолчанию</span>
                <select
                  className="input"
                  value={line.department?.id ?? ""}
                  disabled={locked}
                  onChange={(event) => {
                    const value = event.target.value
                      ? Number(event.target.value)
                      : null;
                    if (value === (line.department?.id ?? null)) return;
                    onPatch({ department_id: value });
                  }}
                >
                  <option value="">
                    {defaultDepartment
                      ? `Как в счёте — ${defaultDepartment}`
                      : "Как в счёте"}
                  </option>
                  {departments.map((department) => (
                    <option key={department.id} value={department.id}>
                      {department.name} · {department.legal_entity.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </>
        )}
      </td>
      <td>
        {invoice.status === "draft" && !line.applied && (
          <input
            type="checkbox"
            checked={line.skipped}
            disabled={locked}
            onChange={(event) => onPatch({ skipped: event.target.checked })}
            aria-label="Пропустить позицию"
          />
        )}
      </td>
    </tr>
  );
}

export function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const invoiceId = Number(id);
  const navigate = useNavigate();
  const { canEdit } = useAuth();

  const invoiceState = useAsyncData(
    () => api.get<Invoice>(`/invoices/${invoiceId}`),
    [invoiceId],
  );
  const models = useAsyncData(
    () => api.get<CartridgeModel[]>("/cartridge-models"),
    [],
  );
  const printers = useAsyncData(() => api.get<Printer[]>("/printers"), []);
  const providers = useAsyncData(
    () => api.get<ServiceProvider[]>("/service-providers"),
    [],
  );
  const entities = useAsyncData(
    () => api.get<LegalEntity[]>("/legal-entities"),
    [],
  );
  const departments = useAsyncData(
    () => api.get<Department[]>("/departments"),
    [],
  );
  const employees = useAsyncData(() => api.get<Employee[]>("/employees"), []);

  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const invoice = invoiceState.data;
  const locked = !canEdit || !invoice || invoice.status !== "draft";

  async function patchHeader(payload: Record<string, unknown>) {
    setError(null);
    setMessage(null);
    try {
      await api.patch(`/invoices/${invoiceId}`, payload);
      invoiceState.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить");
    }
  }

  async function patchLine(lineId: number, payload: Record<string, unknown>) {
    setError(null);
    setMessage(null);
    try {
      await api.patch(`/invoices/${invoiceId}/lines/${lineId}`, payload);
      invoiceState.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить");
    }
  }

  async function autoMatch() {
    if (!invoice) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await api.post<Invoice>(
        `/invoices/${invoice.id}/auto-match`,
      );
      setMessage(
        `Сопоставлено автоматически: ${updated.matched_lines} из ` +
          `${updated.lines.length}. Проверьте модели перед проведением.`,
      );
      invoiceState.reload();
      models.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сопоставить");
    } finally {
      setBusy(false);
    }
  }

  async function patchSlot(
    lineId: number,
    slotId: number,
    payload: Record<string, unknown>,
  ) {
    setError(null);
    setMessage(null);
    try {
      await api.patch(
        `/invoices/${invoiceId}/lines/${lineId}/slots/${slotId}`,
        payload,
      );
      invoiceState.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить");
    }
  }

  async function unapplyInvoice() {
    if (!invoice) return;
    if (
      !window.confirm(
        `Отменить проведение счёта № ${invoice.number}? Операции и ремонты, ` +
          "созданные этим счётом, будут удалены.",
      )
    ) {
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await api.post<Invoice>(`/invoices/${invoice.id}/unapply`);
      setMessage("Проведение отменено — счёт снова в черновике.");
      invoiceState.reload();
      models.reload();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Не удалось отменить проведение",
      );
    } finally {
      setBusy(false);
    }
  }

  async function applyInvoice() {
    if (!invoice) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await api.post<InvoiceApplyResult>(
        `/invoices/${invoice.id}/apply`,
      );
      setMessage(
        `Счёт проведён: операций — ${result.operations_created}, ремонтов — ` +
          `${result.repairs_created}, создано картриджей — ` +
          `${result.cartridges_created}, пропущено позиций — ` +
          `${result.skipped_lines}, стоимость — ` +
          `${formatMoneyExact(result.posted_cost)}.`,
      );
      invoiceState.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось провести счёт");
    } finally {
      setBusy(false);
    }
  }

  async function deleteInvoice() {
    if (!invoice) return;
    if (!window.confirm(`Удалить черновик счёта № ${invoice.number}?`)) return;
    setError(null);
    try {
      await api.delete(`/invoices/${invoice.id}`);
      navigate("/invoices");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось удалить счёт");
    }
  }

  if (invoiceState.loading) return <Spinner label="Загрузка счёта…" />;
  if (invoiceState.error) return <ErrorMessage message={invoiceState.error} />;
  if (!invoice) return null;

  const pending = invoice.lines.filter((line) => !line.skipped && !line.applied);
  const unmatched = pending.filter((line) =>
    line.kind === "repair" ? !line.printer : !line.cartridge_model,
  );
  const canApply = canEdit && invoice.status === "draft" && pending.length > 0 && unmatched.length === 0;

  const allDepartments = departments.data ?? [];
  const departmentOptions = invoice.legal_entity
    ? allDepartments.filter(
        (item) => item.legal_entity.id === invoice.legal_entity?.id,
      )
    : allDepartments;
  const employeeOptions = (employees.data ?? []).filter(
    (item) => !invoice.department || item.department?.id === invoice.department.id,
  );

  return (
    <div>
      <PageHeader
        title={`Счёт № ${invoice.number}`}
        subtitle={`${formatDate(invoice.issued_at)} · ${orgName(invoice.supplier_name)} → ${orgName(invoice.buyer_name)} · ${formatMoneyExact(invoice.total)}`}
        actions={
          <>
            <Link className="button" to="/invoices">
              ← К списку
            </Link>
            {invoice.status === "applied" && canEdit && (
              <button
                className="button button-danger-ghost"
                disabled={busy}
                onClick={unapplyInvoice}
              >
                {busy ? "Отмена…" : "Отменить проведение"}
              </button>
            )}
            {invoice.status === "draft" && canEdit && (
              <>
                <button className="button" disabled={busy} onClick={autoMatch}>
                  Сопоставить автоматически
                </button>
                <button
                  className="button button-primary"
                  disabled={!canApply || busy}
                  onClick={applyInvoice}
                  title={
                    canApply
                      ? "Провести операции по сопоставленным позициям"
                      : "Сопоставьте все позиции или отметьте их как пропущенные"
                  }
                >
                  {busy ? "Проведение…" : "Провести операции"}
                </button>
                <button
                  className="button button-danger-ghost"
                  onClick={deleteInvoice}
                >
                  Удалить черновик
                </button>
              </>
            )}
          </>
        }
      />

      {error && <ErrorMessage message={error} />}
      {message && <SuccessMessage message={message} />}

      <div className="invoice-summary">
        <span className={`badge badge-invoice-${invoice.status}`}>
          {INVOICE_STATUS_LABELS[invoice.status]}
        </span>
        <span>
          Позиций: {invoice.lines.length} · сопоставлено {invoice.matched_lines}
          {invoice.skipped_lines > 0 && ` · пропущено ${invoice.skipped_lines}`}
        </span>
        <span>
          Сумма: {formatMoneyExact(invoice.total)} · НДС {invoice.vat_rate}%:{" "}
          {formatMoneyExact(invoice.vat)} · без НДС:{" "}
          {formatMoneyExact(invoice.total - invoice.vat)}
        </span>
        {invoice.applied_at && (
          <span>Проведён: {formatDate(invoice.applied_at)}</span>
        )}
      </div>

      {unmatched.length > 0 && invoice.status === "draft" && (
        <div className="alert alert-error">
          Не сопоставлены позиции:{" "}
          {unmatched.map((line) => line.number).join(", ")}. Нажмите
          «Сопоставить автоматически» или укажите модель картриджа / принтер
          вручную, либо отметьте позицию как пропущенную.
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <h2>Реквизиты и владелец</h2>
        </div>
        <div className="form-grid">
          <label className="field">
            <span>Сервисная организация</span>
            <select
              className="input"
              value={invoice.service_provider?.id ?? ""}
              disabled={locked}
              onChange={(event) =>
                patchHeader({
                  service_provider_id: event.target.value
                    ? Number(event.target.value)
                    : null,
                })
              }
            >
              <option value="">
                Создать {orgName(invoice.supplier_name)} по ИНН {invoice.supplier_inn}
              </option>
              {(providers.data ?? []).map((provider) => (
                <option key={provider.id} value={provider.id}>
                  {provider.name}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Юрлицо</span>
            <select
              className="input"
              value={invoice.legal_entity?.id ?? ""}
              disabled={locked}
              onChange={(event) =>
                patchHeader({
                  legal_entity_id: event.target.value
                    ? Number(event.target.value)
                    : null,
                  department_id: null,
                  holder_employee_id: null,
                })
              }
            >
              <option value="">
                Создать {orgName(invoice.buyer_name)} по ИНН {invoice.buyer_inn}
              </option>
              {(entities.data ?? []).map((entity) => (
                <option key={entity.id} value={entity.id}>
                  {entity.name}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Подразделение</span>
            <select
              className="input"
              value={invoice.department?.id ?? ""}
              disabled={locked}
              onChange={(event) =>
                patchHeader({
                  department_id: event.target.value
                    ? Number(event.target.value)
                    : null,
                  holder_employee_id: null,
                })
              }
            >
              <option value="">Первое подразделение юрлица</option>
              {departmentOptions.map((department) => (
                <option key={department.id} value={department.id}>
                  {department.name}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Держатель техники (для атрибуции операций)</span>
            <select
              className="input"
              value={invoice.holder_employee?.id ?? ""}
              disabled={locked}
              onChange={(event) =>
                patchHeader({
                  holder_employee_id: event.target.value
                    ? Number(event.target.value)
                    : null,
                })
              }
            >
              <option value="">Первый сотрудник подразделения</option>
              {employeeOptions.map((employee) => (
                <option key={employee.id} value={employee.id}>
                  {employee.full_name}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Отправка в сервис, дней до даты счёта</span>
            <input
              className="input"
              type="number"
              min={0}
              max={365}
              value={invoice.sent_offset_days}
              disabled={locked}
              onChange={(event) =>
                patchHeader({ sent_offset_days: Number(event.target.value) })
              }
            />
          </label>

          <label className="field">
            <span>Стоимость в операциях</span>
            <select
              className="input"
              value={invoice.cost_with_vat ? "gross" : "net"}
              disabled={locked}
              onChange={(event) =>
                patchHeader({ cost_with_vat: event.target.value === "gross" })
              }
            >
              <option value="net">
                Без НДС (цена ÷ {(1 + invoice.vat_rate / 100).toFixed(2)})
              </option>
              <option value="gross">С НДС (как в счёте)</option>
            </select>
          </label>
        </div>
      </div>

      <div className="card table-card invoice-lines">
        <div className="card-header">
          <h2>Позиции счёта</h2>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>№</th>
              <th>Позиция</th>
              <th className="right">Сумма</th>
              <th>Сопоставление</th>
              <th title="Пропустить позицию">—</th>
            </tr>
          </thead>
          <tbody>
            {invoice.lines.map((line) => (
              <LineRow
                key={line.id}
                line={line}
                invoice={invoice}
                models={models.data ?? []}
                printers={printers.data ?? []}
                departments={departmentOptions}
                defaultDepartment={invoice.department?.name ?? null}
                locked={locked}
                onPatch={(payload) => patchLine(line.id, payload)}
                onPatchSlot={(slotId, payload) =>
                  patchSlot(line.id, slotId, payload)
                }
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
