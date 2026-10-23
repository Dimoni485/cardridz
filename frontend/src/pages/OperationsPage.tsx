import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Operation, Page } from "../api/types";
import { DateField } from "../components/DateField";
import {
  EmptyRow,
  ErrorMessage,
  PageHeader,
  Spinner,
} from "../components/ui";
import { useAsyncData } from "../hooks";
import {
  daysAgoIso,
  formatDateTime,
  formatMoney,
  OPERATION_LABELS,
  OPERATION_ORDER,
  todayIso,
} from "../utils";

export function OperationsPage() {
  const [typeFilter, setTypeFilter] = useState("");
  const [dateFrom, setDateFrom] = useState(daysAgoIso(29));
  const [dateTo, setDateTo] = useState(todayIso());
  const [page, setPage] = useState(0);
  const limit = 50;

  useEffect(() => {
    setPage(0);
  }, [typeFilter, dateFrom, dateTo]);

  const operations = useAsyncData(() => {
    const params = new URLSearchParams({
      skip: String(page * limit),
      limit: String(limit),
    });
    if (typeFilter) params.set("type", typeFilter);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    return api.get<Page<Operation>>(`/operations?${params.toString()}`);
  }, [typeFilter, dateFrom, dateTo, page]);

  const total = operations.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / limit));

  function resetPeriod() {
    setDateFrom(daysAgoIso(29));
    setDateTo(todayIso());
  }

  return (
    <div>
      <PageHeader
        title="Журнал операций"
        subtitle="Все движения картриджей: приход, выдача, установка, обслуживание, списание"
      />

      <div className="toolbar">
        <select
          className="input"
          value={typeFilter}
          onChange={(event) => setTypeFilter(event.target.value)}
        >
          <option value="">Все операции</option>
          {OPERATION_ORDER.map((type) => (
            <option key={type} value={type}>
              {OPERATION_LABELS[type]}
            </option>
          ))}
        </select>
        <label className="inline-field">
          <span>с</span>
          <DateField value={dateFrom} onChange={setDateFrom} />
        </label>
        <label className="inline-field">
          <span>по</span>
          <DateField value={dateTo} onChange={setDateTo} />
        </label>
        <button className="button" onClick={resetPeriod}>
          Последние 30 дней
        </button>
      </div>

      {operations.loading && <Spinner />}
      {operations.error && <ErrorMessage message={operations.error} />}

      {operations.data && !operations.loading && (
        <>
          <div className="card table-card">
            <table className="table table-compact">
              <thead>
                <tr>
                  <th>Дата</th>
                  <th>Операция</th>
                  <th>Картридж</th>
                  <th>Сотрудник / принтер</th>
                  <th>Юрлицо / отдел</th>
                  <th>Документ</th>
                  <th>Стоимость</th>
                  <th>Комментарий</th>
                </tr>
              </thead>
              <tbody>
                {operations.data.items.length === 0 && <EmptyRow colSpan={8} />}
                {operations.data.items.map((operation) => (
                  <tr key={operation.id}>
                    <td className="nowrap">{formatDateTime(operation.occurred_at)}</td>
                    <td className="nowrap">
                      {OPERATION_LABELS[operation.type]}
                      {operation.service_provider && (
                        <div className="muted small">
                          {operation.service_provider.name}
                        </div>
                      )}
                    </td>
                    <td>
                      <Link
                        to={`/cartridges/${operation.cartridge_id}`}
                        className="link-strong"
                      >
                        {operation.cartridge.inventory_no}
                      </Link>
                      <div className="muted small">
                        {operation.cartridge.model.vendor}{" "}
                        {operation.cartridge.model.name}
                      </div>
                    </td>
                    <td>
                      {operation.employee?.full_name ??
                        (operation.printer
                          ? `${operation.printer.inventory_no} (${operation.printer.location ?? "—"})`
                          : "—")}
                    </td>
                    <td>
                      {operation.legal_entity
                        ? `${operation.legal_entity.name} / ${
                            operation.department?.name ?? "—"
                          }`
                        : "—"}
                    </td>
                    <td>{operation.document_no ?? "—"}</td>
                    <td>{formatMoney(operation.cost)}</td>
                    <td className="wrap-cell">{operation.comment ?? "—"}</td>
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
    </div>
  );
}
