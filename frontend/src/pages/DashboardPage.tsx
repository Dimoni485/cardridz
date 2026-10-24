import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { PartInstallation, SummaryStats } from "../api/types";
import {
  EmptyRow,
  ErrorMessage,
  PageHeader,
  Spinner,
  StatusBadge,
} from "../components/ui";
import { useAsyncData } from "../hooks";
import {
  formatDateTime,
  formatMoney,
  OPERATION_LABELS,
  STATUS_ORDER,
} from "../utils";

export function DashboardPage() {
  const { data, loading, error } = useAsyncData(
    () => api.get<SummaryStats>("/reports/summary"),
    [],
  );
  const partsAttention = useAsyncData(
    () => api.get<PartInstallation[]>("/part-installations?needs_replacement=true"),
    [],
  );

  if (loading) return <Spinner />;
  if (error) return <ErrorMessage message={error} />;
  if (!data) return null;

  const status = data.by_status;

  return (
    <div>
      <PageHeader
        title="Панель управления"
        subtitle="Сводка по парку картриджей и последние операции"
        actions={
          <Link to="/cartridges" className="button button-primary">
            Перейти к картриджам
          </Link>
        }
      />

      <div className="stat-grid">
        <StatCard label="Всего картриджей" value={data.total_cartridges} tone="neutral" />
        <StatCard label="На складе" value={status.in_stock} tone="success" />
        <StatCard label="Выдано сотрудникам" value={status.issued} tone="info" />
        <StatCard label="В принтерах" value={status.installed} tone="indigo" />
        <StatCard
          label="На обслуживании"
          value={status.in_refill + status.in_restore}
          hint={`заправка: ${status.in_refill}, восстановление: ${status.in_restore}`}
          tone="warning"
        />
        <StatCard label="Списано" value={status.written_off} tone="muted" />
      </div>

      <div className="meta-line">
        <span>Моделей картриджей: <strong>{data.total_models}</strong></span>
        <span>Принтеров: <strong>{data.total_printers}</strong></span>
        <span>Сотрудников: <strong>{data.total_employees}</strong></span>
      </div>

      <div className="dashboard-grid">
        <section className="card">
          <div className="card-header">
            <h2>Требуется пополнение</h2>
            <span className="muted">Остаток ниже минимального</span>
          </div>
          {data.low_stock.length === 0 ? (
            <p className="empty-text">Все модели в достаточном количестве.</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Модель</th>
                  <th>На складе</th>
                  <th>Минимум</th>
                  <th>Не хватает</th>
                </tr>
              </thead>
              <tbody>
                {data.low_stock.map((item) => (
                  <tr key={item.model_id}>
                    <td>
                      <Link to="/models" className="link-strong">
                        {item.vendor} {item.name}
                      </Link>
                    </td>
                    <td className="text-danger">{item.in_stock}</td>
                    <td>{item.min_stock}</td>
                    <td>{item.shortage}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="card">
          <div className="card-header">
            <h2>Статусы картриджей</h2>
          </div>
          <div className="status-list">
            {STATUS_ORDER.map((key) => (
              <div key={key} className="status-row">
                <StatusBadge status={key} />
                <strong>{status[key]}</strong>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="card">
        <div className="card-header">
          <h2>Последние операции</h2>
          <Link to="/operations" className="link">
            Все операции →
          </Link>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>Дата</th>
              <th>Операция</th>
              <th>Картридж</th>
              <th>Контрагент</th>
              <th>Стоимость</th>
              <th>Пользователь</th>
            </tr>
          </thead>
          <tbody>
            {data.recent_operations.length === 0 && <EmptyRow colSpan={6} />}
            {data.recent_operations.map((operation) => (
              <tr key={operation.id}>
                <td className="nowrap">{formatDateTime(operation.occurred_at)}</td>
                <td>{OPERATION_LABELS[operation.type]}</td>
                <td>
                  <Link to={`/cartridges/${operation.cartridge_id}`} className="link-strong">
                    {operation.cartridge.inventory_no}
                  </Link>
                  <div className="muted small">
                    {operation.cartridge.model.vendor} {operation.cartridge.model.name}
                  </div>
                </td>
                <td>
                  {operation.employee?.full_name ??
                    (operation.printer
                      ? `${operation.printer.inventory_no} (${operation.printer.location ?? "—"})`
                      : "—")}
                </td>
                <td>{formatMoney(operation.cost)}</td>
                <td>{operation.user?.full_name ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <div className="card-header">
          <h2>Запчасти к замене</h2>
          <Link className="button button-small" to="/replacements?needs_replacement=true">
            Все замены
          </Link>
        </div>
        {(partsAttention.data ?? []).length === 0 ? (
          <p className="empty-text">Нет запчастей, отмеченных «требует замены».</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Запчасть</th>
                <th>Принтер</th>
                <th>Установлена</th>
              </tr>
            </thead>
            <tbody>
              {(partsAttention.data ?? []).map((item) => (
                <tr key={item.id}>
                  <td>
                    <Link to={`/parts/${item.part.id}`}>{item.part.name}</Link>
                    <span className="muted small"> · {item.inventory_no}</span>
                  </td>
                  <td>
                    {item.printer
                      ? `${item.printer.inventory_no} · ${item.printer.model.vendor} ${item.printer.model.name}`
                      : "—"}
                  </td>
                  <td>{formatDateTime(item.installed_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

function StatCard({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: number;
  hint?: string;
  tone: "neutral" | "success" | "info" | "indigo" | "warning" | "muted";
}) {
  return (
    <div className={`stat-card stat-${tone}`}>
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
      {hint && <span className="stat-hint">{hint}</span>}
    </div>
  );
}
