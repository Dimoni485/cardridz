import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { Part, PartInstallation, PartUnit, Printer } from "../api/types";
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
  formatDateTime,
  formatMoneyExact,
  PART_KIND_LABELS,
  PART_UNIT_STATUS_LABELS,
  statusClass,
} from "../utils";

interface UnitForm {
  inventory_no: string;
  purchase_price: string;
  purchase_date: string;
  notes: string;
}

const EMPTY_UNIT: UnitForm = {
  inventory_no: "",
  purchase_price: "",
  purchase_date: "",
  notes: "",
};

export function PartDetailPage() {
  const { id } = useParams<{ id: string }>();
  const partId = Number(id);
  const { canEdit } = useAuth();

  const part = useAsyncData(() => api.get<Part>(`/parts/${partId}`), [partId]);
  const units = useAsyncData(
    () => api.get<PartUnit[]>(`/part-units?part_id=${partId}`),
    [partId],
  );
  const history = useAsyncData(
    () => api.get<PartInstallation[]>(`/part-installations?part_id=${partId}`),
    [partId],
  );
  const printers = useAsyncData(() => api.get<Printer[]>("/printers"), []);

  const [error, setError] = useState<string | null>(null);
  const [unitForm, setUnitForm] = useState<UnitForm>(EMPTY_UNIT);
  const [showUnitForm, setShowUnitForm] = useState(false);
  const [installUnit, setInstallUnit] = useState<PartUnit | null>(null);
  const [installPrinterId, setInstallPrinterId] = useState("");
  const [installComment, setInstallComment] = useState("");
  const [removeUnit, setRemoveUnit] = useState<PartUnit | null>(null);
  const [writeOff, setWriteOff] = useState(false);
  const [removeComment, setRemoveComment] = useState("");

  function reload() {
    units.reload();
    history.reload();
    part.reload();
  }

  async function createUnit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await api.post(`/parts/${partId}/units`, {
        inventory_no: unitForm.inventory_no.trim(),
        purchase_price: unitForm.purchase_price
          ? Number(unitForm.purchase_price)
          : null,
        purchase_date: unitForm.purchase_date || null,
        notes: unitForm.notes.trim() || null,
      });
      setShowUnitForm(false);
      setUnitForm(EMPTY_UNIT);
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось добавить");
    }
  }

  async function install(event: FormEvent) {
    event.preventDefault();
    if (!installUnit) return;
    setError(null);
    try {
      await api.post(`/part-units/${installUnit.id}/install`, {
        printer_id: Number(installPrinterId),
        comment: installComment.trim() || null,
      });
      setInstallUnit(null);
      setInstallPrinterId("");
      setInstallComment("");
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось установить");
    }
  }

  async function remove(event: FormEvent) {
    event.preventDefault();
    if (!removeUnit) return;
    setError(null);
    try {
      await api.post(`/part-units/${removeUnit.id}/remove`, {
        write_off: writeOff,
        comment: removeComment.trim() || null,
      });
      setRemoveUnit(null);
      setWriteOff(false);
      setRemoveComment("");
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось снять");
    }
  }

  async function toggleFlag(unit: PartUnit) {
    setError(null);
    try {
      await api.patch(`/part-units/${unit.id}`, {
        needs_replacement: !unit.needs_replacement,
      });
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось изменить");
    }
  }

  async function deleteUnit(unit: PartUnit) {
    if (!window.confirm(`Удалить запчасть ${unit.inventory_no}?`)) return;
    setError(null);
    try {
      await api.delete(`/part-units/${unit.id}`);
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось удалить");
    }
  }

  if (part.loading) return <Spinner label="Загрузка запчасти…" />;
  if (part.error) return <ErrorMessage message={part.error} />;
  if (!part.data) return null;
  const data = part.data;

  return (
    <div>
      <PageHeader
        title={data.name}
        subtitle={`${PART_KIND_LABELS[data.kind]}${data.vendor ? ` · ${data.vendor}` : ""}${data.article ? ` · арт. ${data.article}` : ""}`}
        actions={
          <>
            <Link className="button" to="/parts">
              ← К списку
            </Link>
            {canEdit && (
              <button
                className="button button-primary"
                onClick={() => setShowUnitForm(true)}
              >
                + Добавить на склад
              </button>
            )}
          </>
        }
      />

      {error && <ErrorMessage message={error} />}

      <div className="invoice-summary">
        <span>
          На складе: {data.units_in_stock} (минимум {data.min_stock})
        </span>
        <span>Установлено: {data.units_installed}</span>
        <span>Всего: {data.units_total}</span>
        {data.needs_replacement > 0 && (
          <span className="badge badge-invoice-draft">
            требует замены: {data.needs_replacement}
          </span>
        )}
        <span>
          Совместимость:{" "}
          {data.printer_models.length
            ? data.printer_models
                .map((model) => `${model.vendor} ${model.name}`)
                .join(", ")
            : "не указана"}
        </span>
      </div>

      <div className="card table-card">
        <div className="card-header">
          <h2>Единицы учёта</h2>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>Инв. №</th>
              <th>Статус</th>
              <th>Принтер</th>
              <th>Установлена</th>
              <th>Цена</th>
              <th>Требует замены</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {units.data?.length === 0 && (
              <EmptyRow colSpan={7} text="Нет единиц учёта" />
            )}
            {(units.data ?? []).map((unit) => (
              <tr key={unit.id}>
                <td>{unit.inventory_no}</td>
                <td>
                  <span className={statusClass("in-stock")}>
                    {PART_UNIT_STATUS_LABELS[unit.status]}
                  </span>
                </td>
                <td>
                  {unit.printer
                    ? `${unit.printer.inventory_no} · ${unit.printer.model.vendor} ${unit.printer.model.name}`
                    : "—"}
                </td>
                <td>{formatDateTime(unit.installed_at)}</td>
                <td>{formatMoneyExact(unit.purchase_price)}</td>
                <td>
                  {unit.needs_replacement ? (
                    <span className="badge badge-invoice-draft">да</span>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="entity-actions">
                  {canEdit && unit.status === "in_stock" && (
                    <button
                      className="button button-small"
                      onClick={() => {
                        setInstallUnit(unit);
                        setInstallPrinterId("");
                        setInstallComment("");
                      }}
                    >
                      Установить
                    </button>
                  )}
                  {canEdit && unit.status === "installed" && (
                    <>
                      <button
                        className="button button-small"
                        onClick={() => toggleFlag(unit)}
                      >
                        {unit.needs_replacement
                          ? "Снять флаг"
                          : "Требует замены"}
                      </button>
                      <button
                        className="button button-small button-danger-ghost"
                        onClick={() => {
                          setRemoveUnit(unit);
                          setWriteOff(false);
                          setRemoveComment("");
                        }}
                      >
                        Снять
                      </button>
                    </>
                  )}
                  {canEdit && unit.status !== "installed" && (
                    <button
                      className="button button-small button-danger-ghost"
                      onClick={() => deleteUnit(unit)}
                    >
                      Удалить
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card table-card">
        <div className="card-header">
          <h2>История замен</h2>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>Принтер</th>
              <th>Инв. №</th>
              <th>Установлена</th>
              <th>Снята</th>
              <th>Комментарий</th>
              <th>Кто</th>
            </tr>
          </thead>
          <tbody>
            {history.data?.length === 0 && (
              <EmptyRow colSpan={6} text="Замен ещё не было" />
            )}
            {(history.data ?? []).map((item) => (
              <tr key={item.id}>
                <td>
                  {item.printer
                    ? `${item.printer.inventory_no} · ${item.printer.model.vendor} ${item.printer.model.name}`
                    : "—"}
                </td>
                <td>{item.inventory_no}</td>
                <td>{formatDateTime(item.installed_at)}</td>
                <td>{formatDateTime(item.removed_at)}</td>
                <td>{item.comment ?? "—"}</td>
                <td>{item.user?.full_name ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showUnitForm && (
        <Modal title="Новая единица запчасти" onClose={() => setShowUnitForm(false)}>
          <form onSubmit={createUnit} className="form-grid">
            <label className="field field-wide">
              <span>Инвентарный номер *</span>
              <input
                value={unitForm.inventory_no}
                onChange={(event) =>
                  setUnitForm({ ...unitForm, inventory_no: event.target.value })
                }
                required
              />
            </label>
            <label className="field">
              <span>Цена, ₽</span>
              <input
                type="number"
                step="0.01"
                min={0}
                value={unitForm.purchase_price}
                onChange={(event) =>
                  setUnitForm({ ...unitForm, purchase_price: event.target.value })
                }
              />
            </label>
            <label className="field">
              <span>Дата закупки</span>
              <DateField
                value={unitForm.purchase_date}
                onChange={(value) =>
                  setUnitForm({ ...unitForm, purchase_date: value })
                }
              />
            </label>
            <label className="field field-wide">
              <span>Примечание</span>
              <textarea
                rows={2}
                value={unitForm.notes}
                onChange={(event) =>
                  setUnitForm({ ...unitForm, notes: event.target.value })
                }
              />
            </label>
            <div className="form-actions field-wide">
              <button
                type="button"
                className="button"
                onClick={() => setShowUnitForm(false)}
              >
                Отмена
              </button>
              <button className="button button-primary">Добавить</button>
            </div>
          </form>
        </Modal>
      )}

      {installUnit && (
        <Modal
          title={`Установка ${installUnit.inventory_no}`}
          onClose={() => setInstallUnit(null)}
        >
          <form onSubmit={install} className="form-grid">
            <label className="field field-wide">
              <span>Принтер *</span>
              <select
                value={installPrinterId}
                onChange={(event) => setInstallPrinterId(event.target.value)}
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
            <label className="field field-wide">
              <span>Комментарий</span>
              <input
                value={installComment}
                onChange={(event) => setInstallComment(event.target.value)}
              />
            </label>
            <div className="form-actions field-wide">
              <button
                type="button"
                className="button"
                onClick={() => setInstallUnit(null)}
              >
                Отмена
              </button>
              <button className="button button-primary">Установить</button>
            </div>
          </form>
        </Modal>
      )}

      {removeUnit && (
        <Modal
          title={`Снять ${removeUnit.inventory_no}`}
          onClose={() => setRemoveUnit(null)}
        >
          <form onSubmit={remove} className="form-grid">
            <label className="field field-checkbox field-wide">
              <input
                type="checkbox"
                checked={writeOff}
                onChange={(event) => setWriteOff(event.target.checked)}
              />
              <span>Списать (изношена)</span>
            </label>
            <label className="field field-wide">
              <span>Комментарий</span>
              <input
                value={removeComment}
                onChange={(event) => setRemoveComment(event.target.value)}
              />
            </label>
            <div className="form-actions field-wide">
              <button
                type="button"
                className="button"
                onClick={() => setRemoveUnit(null)}
              >
                Отмена
              </button>
              <button className="button button-primary">Снять</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
