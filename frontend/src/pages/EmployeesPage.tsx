import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth";
import type { Department, Employee, LegalEntity } from "../api/types";
import {
  EmptyRow,
  ErrorMessage,
  Modal,
  PageHeader,
  Spinner,
} from "../components/ui";
import { useAsyncData } from "../hooks";

interface EmployeeForm {
  full_name: string;
  department_id: string;
  position: string;
  email: string;
  phone: string;
  is_active: boolean;
}

const EMPTY_FORM: EmployeeForm = {
  full_name: "",
  department_id: "",
  position: "",
  email: "",
  phone: "",
  is_active: true,
};

export function EmployeesPage() {
  const { canEdit } = useAuth();
  const [query, setQuery] = useState("");
  const employees = useAsyncData(
    () => api.get<Employee[]>(`/employees?q=${encodeURIComponent(query.trim())}`),
    [query],
  );
  const entities = useAsyncData(() => api.get<LegalEntity[]>("/legal-entities"), []);
  const departments = useAsyncData(() => api.get<Department[]>("/departments"), []);

  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Employee | null>(null);
  const [form, setForm] = useState<EmployeeForm>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const departmentsByEntity = (entityId: number) =>
    departments.data?.filter((item) => item.legal_entity_id === entityId) ?? [];

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setError(null);
    setShowForm(true);
  }

  function openEdit(employee: Employee) {
    setEditing(employee);
    setForm({
      full_name: employee.full_name,
      department_id: employee.department_id ? String(employee.department_id) : "",
      position: employee.position ?? "",
      email: employee.email ?? "",
      phone: employee.phone ?? "",
      is_active: employee.is_active,
    });
    setError(null);
    setShowForm(true);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    const payload = {
      full_name: form.full_name.trim(),
      department_id: form.department_id ? Number(form.department_id) : null,
      position: form.position.trim() || null,
      email: form.email.trim() || null,
      phone: form.phone.trim() || null,
      is_active: form.is_active,
    };
    try {
      if (editing) {
        await api.patch(`/employees/${editing.id}`, payload);
      } else {
        await api.post("/employees", payload);
      }
      setShowForm(false);
      employees.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить сотрудника");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(employee: Employee) {
    if (!window.confirm(`Удалить сотрудника «${employee.full_name}»?`)) return;
    setListError(null);
    try {
      await api.delete(`/employees/${employee.id}`);
      employees.reload();
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Не удалось удалить сотрудника");
    }
  }

  return (
    <div>
      <PageHeader
        title="Сотрудники"
        subtitle="Получатели картриджей и ответственные за технику"
        actions={
          canEdit ? (
            <button className="button button-primary" onClick={openCreate}>
              + Добавить сотрудника
            </button>
          ) : undefined
        }
      />

      <div className="toolbar">
        <input
          className="input toolbar-search"
          placeholder="Поиск по ФИО, юрлицу, отделу или должности"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>

      {listError && <ErrorMessage message={listError} />}
      {employees.loading && <Spinner />}
      {employees.error && <ErrorMessage message={employees.error} />}

      {employees.data && !employees.loading && (
        <div className="card table-card">
          <table className="table">
            <thead>
              <tr>
                <th>ФИО</th>
                <th>Юрлицо</th>
                <th>Отдел</th>
                <th>Должность</th>
                <th>Контакты</th>
                <th>Статус</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {employees.data.length === 0 && <EmptyRow colSpan={7} />}
              {employees.data.map((employee) => (
                <tr key={employee.id}>
                  <td>
                    <strong>{employee.full_name}</strong>
                  </td>
                  <td>{employee.department?.legal_entity.name ?? "—"}</td>
                  <td>
                    {employee.department?.name ?? "—"}
                    {employee.department?.room && (
                      <div className="muted small">{employee.department.room}</div>
                    )}
                  </td>
                  <td>{employee.position ?? "—"}</td>
                  <td>
                    {employee.email ?? "—"}
                    {employee.phone && (
                      <div className="muted small">{employee.phone}</div>
                    )}
                  </td>
                  <td>
                    <span
                      className={`badge ${employee.is_active ? "badge-active" : "badge-inactive"}`}
                    >
                      {employee.is_active ? "Активен" : "Деактивирован"}
                    </span>
                  </td>
                  {canEdit && (
                    <td className="right nowrap">
                      <button
                        className="button button-small"
                        onClick={() => openEdit(employee)}
                      >
                        Изменить
                      </button>
                      <button
                        className="button button-small button-danger-ghost"
                        onClick={() => handleDelete(employee)}
                      >
                        Удалить
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showForm && (
        <Modal
          title={editing ? "Редактирование сотрудника" : "Новый сотрудник"}
          onClose={() => setShowForm(false)}
        >
          <form onSubmit={handleSubmit} className="form-grid">
            <label className="field field-wide">
              <span>ФИО *</span>
              <input
                value={form.full_name}
                onChange={(event) => setForm({ ...form, full_name: event.target.value })}
                required
                placeholder="Иванов Иван Иванович"
              />
            </label>
            <label className="field field-wide">
              <span>Юрлицо и отдел</span>
              <select
                value={form.department_id}
                onChange={(event) =>
                  setForm({ ...form, department_id: event.target.value })
                }
              >
                <option value="">Не указан</option>
                {entities.data?.map((entity) => (
                  <optgroup key={entity.id} label={entity.name}>
                    {departmentsByEntity(entity.id).map((department) => (
                      <option key={department.id} value={department.id}>
                        {department.room
                          ? `${department.name} — ${department.room}`
                          : department.name}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </label>
            {entities.data?.length === 0 && (
              <p className="field-wide muted small">
                Сначала добавьте юрлицо и отдел в разделе{" "}
                <Link to="/entities">«Юрлица и отделы»</Link>.
              </p>
            )}
            <label className="field">
              <span>Должность</span>
              <input
                value={form.position}
                onChange={(event) => setForm({ ...form, position: event.target.value })}
              />
            </label>
            <label className="field">
              <span>Email</span>
              <input
                type="email"
                value={form.email}
                onChange={(event) => setForm({ ...form, email: event.target.value })}
              />
            </label>
            <label className="field">
              <span>Телефон</span>
              <input
                value={form.phone}
                onChange={(event) => setForm({ ...form, phone: event.target.value })}
              />
            </label>
            <label className="field field-checkbox">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(event) =>
                  setForm({ ...form, is_active: event.target.checked })
                }
              />
              <span>Активен</span>
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
    </div>
  );
}
