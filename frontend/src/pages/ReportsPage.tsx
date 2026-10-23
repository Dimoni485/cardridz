import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type {
  EmployeesReport,
  OperationsReport,
  ServiceReport,
  StockReport,
  UsageReport,
} from "../api/types";
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
  COLOR_LABELS,
  currentMonthIso,
  daysAgoIso,
  formatDate,
  formatMoney,
  KIND_LABELS,
  OPERATION_LABELS,
  recentMonthOptions,
  todayIso,
} from "../utils";

export function ReportsPage() {
  const [dateFrom, setDateFrom] = useState(daysAgoIso(29));
  const [dateTo, setDateTo] = useState(todayIso());
  const [usageMonth, setUsageMonth] = useState(currentMonthIso());
  const monthOptions = recentMonthOptions();

  const [exportOpen, setExportOpen] = useState(false);
  const [exportFrom, setExportFrom] = useState("");
  const [exportTo, setExportTo] = useState("");
  const [exportError, setExportError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const stock = useAsyncData(() => api.get<StockReport>("/reports/stock"), []);
  const employees = useAsyncData(
    () => api.get<EmployeesReport>("/reports/employees"),
    [],
  );
  const operations = useAsyncData(
    () =>
      api.get<OperationsReport>(
        `/reports/operations?date_from=${dateFrom}&date_to=${dateTo}`,
      ),
    [dateFrom, dateTo],
  );
  const usage = useAsyncData(
    () => api.get<UsageReport>(`/reports/usage?month=${usageMonth}`),
    [usageMonth],
  );
  const service = useAsyncData(
    () => api.get<ServiceReport>(`/reports/service?month=${usageMonth}`),
    [usageMonth],
  );

  const maxTypeCount = Math.max(
    1,
    ...(operations.data?.by_type.map((item) => item.count) ?? [1]),
  );
  function openExport() {
    const [year, month] = usageMonth.split("-").map(Number);
    const lastDay = new Date(year, month, 0).getDate();
    setExportFrom(`${usageMonth}-01`);
    setExportTo(`${usageMonth}-${String(lastDay).padStart(2, "0")}`);
    setExportError(null);
    setExportOpen(true);
  }

  async function handleExport(event: React.FormEvent) {
    event.preventDefault();
    if (exportFrom > exportTo) {
      setExportError("Дата начала позже даты окончания");
      return;
    }
    setExporting(true);
    setExportError(null);
    try {
      await api.download(
        `/reports/service-export?date_from=${exportFrom}&date_to=${exportTo}`,
        `cardridz-service-${exportFrom}_${exportTo}.xlsx`,
      );
      setExportOpen(false);
    } catch (err) {
      setExportError(
        err instanceof Error ? err.message : "Не удалось сформировать отчёт",
      );
    } finally {
      setExporting(false);
    }
  }

  const maxDayCount = Math.max(
    1,
    ...(operations.data?.by_day.map((item) => item.count) ?? [1]),
  );

  return (
    <div>
      <PageHeader
        title="Отчёты"
        subtitle="Движение картриджей, остатки по моделям и загрузка сотрудников"
        actions={
          <button className="button print-hide" onClick={() => window.print()}>
            Печать
          </button>
        }
      />

      <div className="toolbar print-hide">
        <label className="inline-field">
          <span>Период с</span>
          <DateField value={dateFrom} onChange={setDateFrom} />
        </label>
        <label className="inline-field">
          <span>по</span>
          <DateField value={dateTo} onChange={setDateTo} />
        </label>
        <button
          className="button"
          onClick={() => {
            setDateFrom(daysAgoIso(29));
            setDateTo(todayIso());
          }}
        >
          Последние 30 дней
        </button>
      </div>

      <section className="card">
        <div className="card-header">
          <h2>Движение за период</h2>
          <span className="muted">
            {formatDate(dateFrom)} — {formatDate(dateTo)}
          </span>
        </div>
        {operations.loading && <Spinner />}
        {operations.error && <ErrorMessage message={operations.error} />}
        {operations.data && (
          <>
            <div className="stat-grid stat-grid-compact">
              <div className="stat-card stat-neutral">
                <span className="stat-label">Операций за период</span>
                <span className="stat-value">{operations.data.total_operations}</span>
              </div>
              <div className="stat-card stat-info">
                <span className="stat-label">Затраты на обслуживание</span>
                <span className="stat-value">
                  {formatMoney(operations.data.total_cost)}
                </span>
              </div>
            </div>

            <div className="report-grid">
              <div>
                <h3>По типам операций</h3>
                {operations.data.by_type.length === 0 && (
                  <p className="empty-text">За выбранный период операций нет.</p>
                )}
                <div className="bar-list">
                  {operations.data.by_type.map((item) => (
                    <div className="bar-row" key={item.type}>
                      <span className="bar-label">{OPERATION_LABELS[item.type]}</span>
                      <div className="bar-track">
                        <div
                          className="bar-fill"
                          style={{ width: `${(item.count / maxTypeCount) * 100}%` }}
                        />
                      </div>
                      <strong className="bar-value">{item.count}</strong>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <h3>По дням</h3>
                {operations.data.by_day.length === 0 ? (
                  <p className="empty-text">Нет данных за период.</p>
                ) : (
                  <div className="chart">
                    {operations.data.by_day.map((item) => (
                      <div
                        className="chart-col"
                        key={item.day}
                        title={`${formatDate(item.day)}: ${item.count}`}
                      >
                        <div
                          className="chart-bar"
                          style={{
                            height: `${Math.max(4, (item.count / maxDayCount) * 130)}px`,
                          }}
                        />
                        <span className="chart-label">
                          {formatDate(item.day).slice(0, 5)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </section>

      <section className="card">
        <div className="card-header">
          <div>
            <h2>Использование по юрлицам и отделам</h2>
            <span className="muted small">
              {usage.data
                ? `${formatDate(usage.data.date_from)} — ${formatDate(usage.data.date_to)}`
                : "Выдачи картриджей и затраты на обслуживание"}
            </span>
          </div>
          <div className="card-header-actions print-hide">
            <label className="inline-field">
              <span>Месяц</span>
              <select
                className="input"
                value={usageMonth}
                onChange={(event) => setUsageMonth(event.target.value)}
              >
                {monthOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <button className="button" onClick={openExport}>
              Выгрузить Excel
            </button>
          </div>
        </div>

        {usage.loading && <Spinner />}
        {usage.error && <ErrorMessage message={usage.error} />}
        {usage.data && (
          <>
            <div className="stat-grid stat-grid-compact">
              <div className="stat-card stat-info">
                <span className="stat-label">Выдано картриджей</span>
                <span className="stat-value">{usage.data.totals.issued_count}</span>
              </div>
              <div className="stat-card stat-indigo">
                <span className="stat-label">Стоимость картриджей</span>
                <span className="stat-value">
                  {formatMoney(usage.data.totals.cartridges_cost)}
                </span>
              </div>
              <div className="stat-card stat-warning">
                <span className="stat-label">Заправка и восстановление</span>
                <span className="stat-value">
                  {formatMoney(usage.data.totals.service_cost)}
                </span>
              </div>
              <div className="stat-card stat-muted">
                <span className="stat-label">Ремонт принтеров</span>
                <span className="stat-value">
                  {formatMoney(usage.data.totals.repair_cost)}
                </span>
              </div>
              <div className="stat-card stat-success">
                <span className="stat-label">Итого затрат</span>
                <span className="stat-value">
                  {formatMoney(usage.data.totals.total_cost)}
                </span>
              </div>
            </div>

            <div className="usage-tables">
              <div>
                <h3>По отделам</h3>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Юрлицо</th>
                      <th>Отдел</th>
                      <th className="center">Выдано</th>
                      <th className="right">Картриджи</th>
                      <th className="right">Обслуживание</th>
                      <th className="right">Ремонт принтеров</th>
                      <th className="right">Итого</th>
                    </tr>
                  </thead>
                  <tbody>
                    {usage.data.rows.length === 0 && (
                      <EmptyRow
                        colSpan={7}
                        text="За выбранный месяц выдач и затрат нет"
                      />
                    )}
                    {usage.data.rows.map((row) => (
                      <tr
                        key={`${row.legal_entity_id}-${row.department_id}`}
                      >
                        <td>{row.legal_entity_name ?? "—"}</td>
                        <td>{row.department_name ?? "—"}</td>
                        <td className="center">{row.issued_count}</td>
                        <td className="right">{formatMoney(row.cartridges_cost)}</td>
                        <td className="right">{formatMoney(row.service_cost)}</td>
                        <td className="right">{formatMoney(row.repair_cost)}</td>
                        <td className="right">
                          <strong>{formatMoney(row.total_cost)}</strong>
                        </td>
                      </tr>
                    ))}
                    {usage.data.rows.length > 0 && (
                      <tr className="table-totals">
                        <td colSpan={2}>Итого</td>
                        <td className="center">{usage.data.totals.issued_count}</td>
                        <td className="right">
                          {formatMoney(usage.data.totals.cartridges_cost)}
                        </td>
                        <td className="right">
                          {formatMoney(usage.data.totals.service_cost)}
                        </td>
                        <td className="right">
                          {formatMoney(usage.data.totals.repair_cost)}
                        </td>
                        <td className="right">
                          {formatMoney(usage.data.totals.total_cost)}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              <div>
                <h3>Итого по юрлицам</h3>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Юрлицо</th>
                      <th className="center">Выдано</th>
                      <th className="right">Итого</th>
                    </tr>
                  </thead>
                  <tbody>
                    {usage.data.by_legal_entity.map((row) => (
                      <tr key={`entity-${row.legal_entity_id}`}>
                        <td>
                          <strong>{row.legal_entity_name ?? "Без юрлица"}</strong>
                          <div className="muted small">
                            картриджи {formatMoney(row.cartridges_cost)}, обслуживание{" "}
                            {formatMoney(row.service_cost)}, ремонт принтеров{" "}
                            {formatMoney(row.repair_cost)}
                          </div>
                        </td>
                        <td className="center">{row.issued_count}</td>
                        <td className="right">
                          <strong>{formatMoney(row.total_cost)}</strong>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </section>

      <section className="card">
        <div className="card-header">
          <div>
            <h2>Сторонние сервисные организации</h2>
            <span className="muted small">
              {service.data
                ? `${formatDate(service.data.date_from)} — ${formatDate(service.data.date_to)}`
                : "Передача на заправку и восстановление"}
            </span>
          </div>
        </div>

        {service.loading && <Spinner />}
        {service.error && <ErrorMessage message={service.error} />}
        {service.data && (
          <>
            <div className="stat-grid stat-grid-compact">
              <div className="stat-card stat-info">
                <span className="stat-label">Отправлено картриджей</span>
                <span className="stat-value">{service.data.totals.sent_count}</span>
              </div>
              <div className="stat-card stat-success">
                <span className="stat-label">Возвращено картриджей</span>
                <span className="stat-value">
                  {service.data.totals.returned_count}
                </span>
              </div>
              <div className="stat-card stat-indigo">
                <span className="stat-label">Отправлено принтеров</span>
                <span className="stat-value">
                  {service.data.totals.printer_sent_count}
                </span>
              </div>
              <div className="stat-card stat-success">
                <span className="stat-label">Возвращено принтеров</span>
                <span className="stat-value">
                  {service.data.totals.printer_returned_count}
                </span>
              </div>
              <div className="stat-card stat-warning">
                <span className="stat-label">Итого затрат</span>
                <span className="stat-value">
                  {formatMoney(
                    service.data.totals.cost + service.data.totals.printer_cost,
                  )}
                </span>
                <span className="stat-hint">
                  картриджи {formatMoney(service.data.totals.cost)}, принтеры{" "}
                  {formatMoney(service.data.totals.printer_cost)}
                </span>
              </div>
              <div className="stat-card stat-muted">
                <span className="stat-label">Сейчас в сервисе</span>
                <span className="stat-value">
                  {service.data.totals.outstanding_count +
                    service.data.totals.printer_outstanding_count}
                </span>
                <span className="stat-hint">
                  картриджи {service.data.totals.outstanding_count}, принтеры{" "}
                  {service.data.totals.printer_outstanding_count}
                </span>
              </div>
            </div>

            <div className="usage-tables service-tables">
              <div>
                <h3>По организациям</h3>
                <table className="table table-compact">
                  <thead>
                    <tr>
                      <th>Организация</th>
                      <th className="center">Картриджи<br />отпр. / возвр.</th>
                      <th className="center">Принтеры<br />отпр. / возвр.</th>
                      <th className="right">Затраты</th>
                      <th className="center">Сейчас<br />картр. / принт.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {service.data.rows.length === 0 && (
                      <EmptyRow
                        colSpan={5}
                        text="За выбранный месяц передач в сервис не было"
                      />
                    )}
                    {service.data.rows.map((row) => (
                      <tr key={`service-${row.provider_id}`}>
                        <td>
                          <strong>{row.provider_name ?? "Без организации"}</strong>
                        </td>
                        <td className="center">
                          {row.sent_count} / {row.returned_count}
                        </td>
                        <td className="center">
                          {row.printer_sent_count} / {row.printer_returned_count}
                        </td>
                        <td className="right">
                          <strong>{formatMoney(row.cost + row.printer_cost)}</strong>
                          <div className="muted small">
                            картриджи {formatMoney(row.cost)}, принтеры{" "}
                            {formatMoney(row.printer_cost)}
                          </div>
                        </td>
                        <td className="center">
                          {row.outstanding_count} / {row.printer_outstanding_count}
                        </td>
                      </tr>
                    ))}
                    {service.data.rows.length > 0 && (
                      <tr className="table-totals">
                        <td>Итого</td>
                        <td className="center">
                          {service.data.totals.sent_count} /{" "}
                          {service.data.totals.returned_count}
                        </td>
                        <td className="center">
                          {service.data.totals.printer_sent_count} /{" "}
                          {service.data.totals.printer_returned_count}
                        </td>
                        <td className="right">
                          {formatMoney(
                            service.data.totals.cost +
                              service.data.totals.printer_cost,
                          )}
                        </td>
                        <td className="center">
                          {service.data.totals.outstanding_count} /{" "}
                          {service.data.totals.printer_outstanding_count}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              <div>
                <h3>Картриджи в сервисе</h3>
                {service.data.outstanding.length === 0 ? (
                  <p className="empty-text">Все картриджи возвращены.</p>
                ) : (
                  <table className="table table-compact">
                    <thead>
                      <tr>
                        <th>Картридж</th>
                        <th>Организация</th>
                        <th>Передан</th>
                        <th>Ожидается</th>
                        <th>Статус</th>
                      </tr>
                    </thead>
                    <tbody>
                      {service.data.outstanding.map((row) => (
                        <tr key={`outstanding-${row.cartridge_id}`}>
                          <td>
                            <Link
                              to={`/cartridges/${row.cartridge_id}`}
                              className="link-strong"
                            >
                              {row.inventory_no}
                            </Link>
                            <div className="muted small">{row.model_name}</div>
                          </td>
                          <td>{row.provider_name ?? "—"}</td>
                          <td className="nowrap">{formatDate(row.service_since)}</td>
                          <td className="nowrap">
                            {formatDate(row.expected_return_date)}
                          </td>
                          <td>
                            {row.overdue ? (
                              <span className="badge badge-overdue">Просрочен</span>
                            ) : (
                              <span className="badge badge-active">В срок</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}

                <h3 className="section-gap">Принтеры в ремонте</h3>
                {service.data.printers_outstanding.length === 0 ? (
                  <p className="empty-text">Все принтеры возвращены.</p>
                ) : (
                  <table className="table table-compact">
                    <thead>
                      <tr>
                        <th>Принтер</th>
                        <th>Организация</th>
                        <th>Передан</th>
                        <th>Ожидается</th>
                        <th>Статус</th>
                      </tr>
                    </thead>
                    <tbody>
                      {service.data.printers_outstanding.map((row) => (
                        <tr key={`printer-outstanding-${row.printer_id}`}>
                          <td>
                            <strong>{row.inventory_no}</strong>
                            <div className="muted small">{row.model_name}</div>
                          </td>
                          <td>{row.provider_name ?? "—"}</td>
                          <td className="nowrap">{formatDate(row.service_since)}</td>
                          <td className="nowrap">
                            {formatDate(row.expected_return_date)}
                          </td>
                          <td>
                            {row.overdue ? (
                              <span className="badge badge-overdue">Просрочен</span>
                            ) : (
                              <span className="badge badge-active">В срок</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </>
        )}
      </section>

      <section className="card">
        <div className="card-header">
          <h2>Остатки по моделям</h2>
          <span className="muted">На текущий момент</span>
        </div>
        {stock.loading && <Spinner />}
        {stock.error && <ErrorMessage message={stock.error} />}
        {stock.data && (
          <table className="table table-compact">
            <thead>
              <tr>
                <th>Модель</th>
                <th>Тип</th>
                <th>Цвет</th>
                <th className="center">Склад</th>
                <th className="center">Выдано</th>
                <th className="center">В принтерах</th>
                <th className="center">Заправка</th>
                <th className="center">Восстановл.</th>
                <th className="center">Списано</th>
                <th className="center">Всего</th>
                <th className="center">Заправок</th>
              </tr>
            </thead>
            <tbody>
              {stock.data.rows.map((row) => (
                <tr key={row.model_id}>
                  <td>
                    <strong>
                      {row.vendor} {row.name}
                    </strong>
                    {row.min_stock > 0 && row.in_stock < row.min_stock && (
                      <div className="text-danger small">
                        Ниже минимума ({row.min_stock})
                      </div>
                    )}
                  </td>
                  <td>{KIND_LABELS[row.kind]}</td>
                  <td>{COLOR_LABELS[row.color]}</td>
                  <td className="center">{row.in_stock}</td>
                  <td className="center">{row.issued}</td>
                  <td className="center">{row.installed}</td>
                  <td className="center">{row.in_refill}</td>
                  <td className="center">{row.in_restore}</td>
                  <td className="center">{row.written_off}</td>
                  <td className="center">
                    <strong>{row.total}</strong>
                  </td>
                  <td className="center">{row.refills}</td>
                </tr>
              ))}
              <tr className="table-totals">
                <td colSpan={3}>Итого</td>
                <td className="center">{stock.data.totals.in_stock}</td>
                <td className="center">{stock.data.totals.issued}</td>
                <td className="center">{stock.data.totals.installed}</td>
                <td className="center">{stock.data.totals.in_refill}</td>
                <td className="center">{stock.data.totals.in_restore}</td>
                <td className="center">{stock.data.totals.written_off}</td>
                <td className="center">{stock.data.totals.total}</td>
                <td className="center">{stock.data.totals.refills}</td>
              </tr>
            </tbody>
          </table>
        )}
      </section>

      <section className="card">
        <div className="card-header">
          <h2>Картриджи по сотрудникам</h2>
          <span className="muted">Выданные и установленные в их кабинетах</span>
        </div>
        {employees.loading && <Spinner />}
        {employees.error && <ErrorMessage message={employees.error} />}
        {employees.data && (
          <table className="table table-compact">
            <thead>
              <tr>
                <th>Сотрудник</th>
                <th>Юрлицо</th>
                <th>Отдел</th>
                <th className="center">Выдано</th>
                <th className="center">В принтерах</th>
                <th className="center">Всего</th>
              </tr>
            </thead>
            <tbody>
              {employees.data.rows.map((row) => (
                <tr key={row.employee_id}>
                  <td>
                    {row.full_name}
                    {!row.is_active && (
                      <span className="badge badge-inactive badge-inline">неактивен</span>
                    )}
                  </td>
                  <td>{row.legal_entity ?? "—"}</td>
                  <td>{row.department ?? "—"}</td>
                  <td className="center">{row.issued}</td>
                  <td className="center">{row.installed_at_printers}</td>
                  <td className="center">
                    <strong>{row.total}</strong>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {exportOpen && (
        <Modal
          title="Выгрузка обслуживания в Excel"
          onClose={() => setExportOpen(false)}
        >
          <form onSubmit={handleExport} className="form-grid">
            <label className="field">
              <span>Период с</span>
              <DateField value={exportFrom} onChange={setExportFrom} />
            </label>
            <label className="field">
              <span>по</span>
              <DateField value={exportTo} onChange={setExportTo} />
            </label>
            <p className="field-wide muted small">
              В отчёт попадают завершённые операции обслуживания: возврат
              с заправки, возврат с восстановления и возврат принтера из ремонта.
              Выгружаются детализация и итоги по юрлицам и отделам.
            </p>
            {exportError && (
              <div className="field-wide">
                <ErrorMessage message={exportError} />
              </div>
            )}
            <div className="form-actions field-wide">
              <button
                type="button"
                className="button"
                onClick={() => setExportOpen(false)}
              >
                Отмена
              </button>
              <button className="button button-primary" disabled={exporting}>
                {exporting ? "Формирование…" : "Скачать .xlsx"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
