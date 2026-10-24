import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Invoice, InvoiceListItem, InvoiceStatus } from "../api/types";
import { useAuth } from "../auth";
import { EmptyRow, ErrorMessage, PageHeader, Spinner } from "../components/ui";
import { useAsyncData } from "../hooks";
import {
  formatDate,
  formatMoneyExact,
  INVOICE_STATUS_LABELS,
  orgName,
  plural,
} from "../utils";

const STATUS_OPTIONS: { value: "" | InvoiceStatus; label: string }[] = [
  { value: "", label: "Все счета" },
  { value: "draft", label: "Черновики" },
  { value: "applied", label: "Проведённые" },
];

export function InvoicesPage() {
  const { canEdit } = useAuth();
  const navigate = useNavigate();
  const fileInput = useRef<HTMLInputElement | null>(null);

  const [statusFilter, setStatusFilter] = useState<"" | InvoiceStatus>("");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const invoices = useAsyncData(
    () =>
      api.get<InvoiceListItem[]>(
        statusFilter ? `/invoices?status_filter=${statusFilter}` : "/invoices",
      ),
    [statusFilter],
  );

  async function handleFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const created = await api.upload<Invoice>("/invoices", file);
      navigate(`/invoices/${created.id}`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Не удалось распознать счёт",
      );
      if (fileInput.current) fileInput.current.value = "";
    } finally {
      setUploading(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Счета на услуги"
        subtitle="Распознавание PDF-счетов и сопоставление позиций с картриджами и принтерами"
        actions={
          canEdit ? (
            <>
              <input
                ref={fileInput}
                type="file"
                accept="application/pdf,.pdf"
                hidden
                onChange={handleFile}
              />
              <button
                className="button button-primary"
                disabled={uploading}
                onClick={() => fileInput.current?.click()}
              >
                {uploading ? "Распознавание…" : "+ Загрузить счёт"}
              </button>
            </>
          ) : undefined
        }
      />

      <div className="toolbar">
        <select
          className="input"
          value={statusFilter}
          onChange={(event) =>
            setStatusFilter(event.target.value as "" | InvoiceStatus)
          }
        >
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {error && <ErrorMessage message={error} />}
      {invoices.loading && <Spinner />}
      {invoices.error && <ErrorMessage message={invoices.error} />}

      {invoices.data && !invoices.loading && (
        <div className="card table-card invoice-list">
          <table className="table">
            <thead>
              <tr>
                <th>Счёт</th>
                <th>Дата</th>
                <th>Поставщик</th>
                <th>Покупатель</th>
                <th>Позиции</th>
                <th className="right">Сумма</th>
                <th>Статус</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {invoices.data.length === 0 && (
                <EmptyRow colSpan={8} text="Счета ещё не загружены" />
              )}
              {invoices.data.map((invoice) => (
                <tr key={invoice.id}>
                  <td>
                    <Link to={`/invoices/${invoice.id}`}>
                      № {invoice.number}
                    </Link>
                  </td>
                  <td>{formatDate(invoice.issued_at)}</td>
                  <td>{orgName(invoice.supplier_name)}</td>
                  <td>{orgName(invoice.buyer_name)}</td>
                  <td>
                    {invoice.lines_matched} из {invoice.lines_total}{" "}
                    {plural(invoice.lines_total, [
                      "позиции",
                      "позиций",
                      "позиций",
                    ])}
                  </td>
                  <td className="right">
                    {formatMoneyExact(invoice.total)}
                  </td>
                  <td>
                    <span className={`badge badge-invoice-${invoice.status}`}>
                      {INVOICE_STATUS_LABELS[invoice.status]}
                    </span>
                  </td>
                  <td className="entity-actions">
                    <Link className="button button-small" to={`/invoices/${invoice.id}`}>
                      Открыть
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
