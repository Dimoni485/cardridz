import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Part, PartInstallation, Printer } from "../api/types";
import { EmptyRow, ErrorMessage, PageHeader, Spinner } from "../components/ui";
import { useAsyncData } from "../hooks";
import { formatDateTime } from "../utils";

export function PartReplacementsPage() {
  const [printerId, setPrinterId] = useState("");
  const [partId, setPartId] = useState("");
  const [openOnly, setOpenOnly] = useState(false);
  const [needsReplacement, setNeedsReplacement] = useState(false);

  const printers = useAsyncData(() => api.get<Printer[]>("/printers"), []);
  const parts = useAsyncData(() => api.get<Part[]>("/parts"), []);

  const installations = useAsyncData(() => {
    const params = new URLSearchParams();
    if (printerId) params.set("printer_id", printerId);
    if (partId) params.set("part_id", partId);
    if (openOnly) params.set("open_only", "true");
    if (needsReplacement) params.set("needs_replacement", "true");
    const suffix = params.toString();
    return api.get<PartInstallation[]>(
      `/part-installations${suffix ? `?${suffix}` : ""}`,
    );
  }, [printerId, partId, openOnly, needsReplacement]);

  return (
    <div>
      <PageHeader
        title="Замены запчастей"
        subtitle="Когда и на каком принтере меняли запчасти; отмеченные «требует замены» — к плановой замене"
      />

      <div className="toolbar">
        <select
          className="input"
          value={printerId}
          onChange={(event) => setPrinterId(event.target.value)}
        >
          <option value="">Все принтеры</option>
          {(printers.data ?? []).map((printer) => (
            <option key={printer.id} value={printer.id}>
              {printer.inventory_no} · {printer.model.vendor}{" "}
              {printer.model.name}
            </option>
          ))}
        </select>
        <select
          className="input"
          value={partId}
          onChange={(event) => setPartId(event.target.value)}
        >
          <option value="">Все запчасти</option>
          {(parts.data ?? []).map((part) => (
            <option key={part.id} value={part.id}>
              {part.name}
            </option>
          ))}
        </select>
        <label className="checkbox-item">
          <input
            type="checkbox"
            checked={openOnly}
            onChange={(event) => setOpenOnly(event.target.checked)}
          />
          <span>Только установленные</span>
        </label>
        <label className="checkbox-item">
          <input
            type="checkbox"
            checked={needsReplacement}
            onChange={(event) => setNeedsReplacement(event.target.checked)}
          />
          <span>Только требующие замены</span>
        </label>
      </div>

      {installations.loading && <Spinner />}
      {installations.error && <ErrorMessage message={installations.error} />}

      {installations.data && !installations.loading && (
        <div className="card table-card">
          <table className="table">
            <thead>
              <tr>
                <th>Запчасть</th>
                <th>Инв. №</th>
                <th>Принтер</th>
                <th>Установлена</th>
                <th>Снята</th>
                <th>Комментарий</th>
                <th>Кто</th>
              </tr>
            </thead>
            <tbody>
              {installations.data.length === 0 && (
                <EmptyRow colSpan={7} text="Замен не найдено" />
              )}
              {installations.data.map((item) => (
                <tr
                  key={item.id}
                  className={item.needs_replacement ? "row-attention" : undefined}
                >
                  <td>
                    <Link to={`/parts/${item.part.id}`}>{item.part.name}</Link>
                    {item.needs_replacement && (
                      <span className="badge badge-invoice-draft part-stock-low">
                        требует замены
                      </span>
                    )}
                  </td>
                  <td>{item.inventory_no}</td>
                  <td>
                    {item.printer
                      ? `${item.printer.inventory_no} · ${item.printer.model.vendor} ${item.printer.model.name}`
                      : "—"}
                  </td>
                  <td>{formatDateTime(item.installed_at)}</td>
                  <td>{formatDateTime(item.removed_at)}</td>
                  <td>{item.comment ?? "—"}</td>
                  <td>{item.user?.full_name ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
