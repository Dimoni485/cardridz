import { useState, type FormEvent } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth";
import type { Department, LegalEntity } from "../api/types";
import { ErrorMessage, Modal, PageHeader, Spinner } from "../components/ui";
import { useAsyncData } from "../hooks";

interface EntityForm {
  name: string;
  inn: string;
  notes: string;
  is_active: boolean;
}

const EMPTY_ENTITY: EntityForm = {
  name: "",
  inn: "",
  notes: "",
  is_active: true,
};

interface DepartmentForm {
  legal_entity_id: string;
  name: string;
  room: string;
  is_active: boolean;
}

const EMPTY_DEPARTMENT: DepartmentForm = {
  legal_entity_id: "",
  name: "",
  room: "",
  is_active: true,
};

export function EntitiesPage() {
  const { canEdit } = useAuth();
  const entities = useAsyncData(
    () => api.get<LegalEntity[]>("/legal-entities"),
    [],
  );
  const departments = useAsyncData(
    () => api.get<Department[]>("/departments"),
    [],
  );

  const [entityModalOpen, setEntityModalOpen] = useState(false);
  const [editingEntity, setEditingEntity] = useState<LegalEntity | null>(null);
  const [entityForm, setEntityForm] = useState<EntityForm>(EMPTY_ENTITY);

  const [departmentModalOpen, setDepartmentModalOpen] = useState(false);
  const [editingDepartment, setEditingDepartment] = useState<Department | null>(
    null,
  );
  const [departmentForm, setDepartmentForm] =
    useState<DepartmentForm>(EMPTY_DEPARTMENT);

  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function reload() {
    entities.reload();
    departments.reload();
  }

  function departmentsFor(entityId: number): Department[] {
    return departments.data?.filter((item) => item.legal_entity_id === entityId) ?? [];
  }

  function openCreateEntity() {
    setEditingEntity(null);
    setEntityForm(EMPTY_ENTITY);
    setError(null);
    setEntityModalOpen(true);
  }

  function openEditEntity(entity: LegalEntity) {
    setEditingEntity(entity);
    setEntityForm({
      name: entity.name,
      inn: entity.inn ?? "",
      notes: entity.notes ?? "",
      is_active: entity.is_active,
    });
    setError(null);
    setEntityModalOpen(true);
  }

  async function submitEntity(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    const payload = {
      name: entityForm.name.trim(),
      inn: entityForm.inn.trim() || null,
      notes: entityForm.notes.trim() || null,
      is_active: entityForm.is_active,
    };
    try {
      if (editingEntity) {
        await api.patch(`/legal-entities/${editingEntity.id}`, payload);
      } else {
        await api.post("/legal-entities", payload);
      }
      setEntityModalOpen(false);
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить юрлицо");
    } finally {
      setSaving(false);
    }
  }

  async function deleteEntity(entity: LegalEntity) {
    if (!window.confirm(`Удалить юрлицо «${entity.name}»?`)) return;
    setActionError(null);
    try {
      await api.delete(`/legal-entities/${entity.id}`);
      reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Не удалось удалить юрлицо");
    }
  }

  function openCreateDepartment(entity: LegalEntity) {
    setEditingDepartment(null);
    setDepartmentForm({
      ...EMPTY_DEPARTMENT,
      legal_entity_id: String(entity.id),
    });
    setError(null);
    setDepartmentModalOpen(true);
  }

  function openEditDepartment(department: Department) {
    setEditingDepartment(department);
    setDepartmentForm({
      legal_entity_id: String(department.legal_entity_id),
      name: department.name,
      room: department.room ?? "",
      is_active: department.is_active,
    });
    setError(null);
    setDepartmentModalOpen(true);
  }

  async function submitDepartment(event: FormEvent) {
    event.preventDefault();
    if (!departmentForm.legal_entity_id) {
      setError("Выберите юрлицо");
      return;
    }
    setSaving(true);
    setError(null);
    const payload = {
      legal_entity_id: Number(departmentForm.legal_entity_id),
      name: departmentForm.name.trim(),
      room: departmentForm.room.trim() || null,
      is_active: departmentForm.is_active,
    };
    try {
      if (editingDepartment) {
        await api.patch(`/departments/${editingDepartment.id}`, payload);
      } else {
        await api.post("/departments", payload);
      }
      setDepartmentModalOpen(false);
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить отдел");
    } finally {
      setSaving(false);
    }
  }

  async function deleteDepartment(department: Department) {
    if (!window.confirm(`Удалить отдел «${department.name}»?`)) return;
    setActionError(null);
    try {
      await api.delete(`/departments/${department.id}`);
      reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Не удалось удалить отдел");
    }
  }

  return (
    <div>
      <PageHeader
        title="Юрлица и отделы"
        subtitle="Контрагенты, их подразделения и привязка сотрудников"
        actions={
          canEdit ? (
            <button className="button button-primary" onClick={openCreateEntity}>
              + Добавить юрлицо
            </button>
          ) : undefined
        }
      />

      {actionError && <ErrorMessage message={actionError} />}
      {entities.loading && <Spinner />}
      {entities.error && <ErrorMessage message={entities.error} />}

      {entities.data && !entities.loading && (
        <div className="entity-list">
          {entities.data.length === 0 && (
            <p className="empty-text">
              Юрлица ещё не добавлены. Нажмите «Добавить юрлицо».
            </p>
          )}
          {entities.data.map((entity) => {
            const items = departmentsFor(entity.id);
            return (
              <section className="card entity-card" key={entity.id}>
                <div className="entity-header">
                  <div>
                    <h2>
                      {entity.name}{" "}
                      {!entity.is_active && (
                        <span className="badge badge-inactive badge-inline">
                          неактивно
                        </span>
                      )}
                    </h2>
                    <div className="muted small">
                      {entity.inn ? `ИНН ${entity.inn}` : "ИНН не указан"}
                      {entity.notes ? ` · ${entity.notes}` : ""}
                    </div>
                  </div>
                  {canEdit && (
                    <div className="entity-actions">
                      <button
                        className="button button-small"
                        onClick={() => openCreateDepartment(entity)}
                      >
                        + Отдел
                      </button>
                      <button
                        className="button button-small"
                        onClick={() => openEditEntity(entity)}
                      >
                        Изменить
                      </button>
                      <button
                        className="button button-small button-danger-ghost"
                        onClick={() => deleteEntity(entity)}
                      >
                        Удалить
                      </button>
                    </div>
                  )}
                </div>

                {items.length === 0 ? (
                  <p className="empty-text">У юрлица пока нет отделов.</p>
                ) : (
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Отдел</th>
                        <th>Кабинет</th>
                        <th>Статус</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((department) => (
                        <tr key={department.id}>
                          <td>
                            <strong>{department.name}</strong>
                          </td>
                          <td>{department.room ?? "—"}</td>
                          <td>
                            <span
                              className={`badge ${department.is_active ? "badge-active" : "badge-inactive"}`}
                            >
                              {department.is_active ? "Активен" : "Неактивен"}
                            </span>
                          </td>
                          {canEdit && (
                            <td className="right nowrap">
                              <button
                                className="button button-small"
                                onClick={() => openEditDepartment(department)}
                              >
                                Изменить
                              </button>
                              <button
                                className="button button-small button-danger-ghost"
                                onClick={() => deleteDepartment(department)}
                              >
                                Удалить
                              </button>
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </section>
            );
          })}
        </div>
      )}

      {entityModalOpen && (
        <Modal
          title={editingEntity ? "Редактирование юрлица" : "Новое юрлицо"}
          onClose={() => setEntityModalOpen(false)}
        >
          <form onSubmit={submitEntity} className="form-grid">
            <label className="field field-wide">
              <span>Наименование *</span>
              <input
                value={entityForm.name}
                onChange={(event) =>
                  setEntityForm({ ...entityForm, name: event.target.value })
                }
                required
                placeholder="ООО «Альфа»"
              />
            </label>
            <label className="field">
              <span>ИНН</span>
              <input
                value={entityForm.inn}
                onChange={(event) =>
                  setEntityForm({ ...entityForm, inn: event.target.value })
                }
                maxLength={12}
              />
            </label>
            <label className="field field-checkbox">
              <input
                type="checkbox"
                checked={entityForm.is_active}
                onChange={(event) =>
                  setEntityForm({ ...entityForm, is_active: event.target.checked })
                }
              />
              <span>Активно</span>
            </label>
            <label className="field field-wide">
              <span>Примечание</span>
              <textarea
                rows={2}
                value={entityForm.notes}
                onChange={(event) =>
                  setEntityForm({ ...entityForm, notes: event.target.value })
                }
              />
            </label>
            {error && (
              <div className="field-wide">
                <ErrorMessage message={error} />
              </div>
            )}
            <div className="form-actions field-wide">
              <button
                type="button"
                className="button"
                onClick={() => setEntityModalOpen(false)}
              >
                Отмена
              </button>
              <button className="button button-primary" disabled={saving}>
                {saving ? "Сохранение…" : "Сохранить"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {departmentModalOpen && (
        <Modal
          title={editingDepartment ? "Редактирование отдела" : "Новый отдел"}
          onClose={() => setDepartmentModalOpen(false)}
        >
          <form onSubmit={submitDepartment} className="form-grid">
            <label className="field field-wide">
              <span>Юрлицо *</span>
              <select
                value={departmentForm.legal_entity_id}
                onChange={(event) =>
                  setDepartmentForm({
                    ...departmentForm,
                    legal_entity_id: event.target.value,
                  })
                }
                required
              >
                <option value="">Выберите юрлицо</option>
                {entities.data?.map((entity) => (
                  <option key={entity.id} value={entity.id}>
                    {entity.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field field-wide">
              <span>Название отдела *</span>
              <input
                value={departmentForm.name}
                onChange={(event) =>
                  setDepartmentForm({ ...departmentForm, name: event.target.value })
                }
                required
                placeholder="Бухгалтерия"
              />
            </label>
            <label className="field">
              <span>Номер кабинета</span>
              <input
                value={departmentForm.room}
                onChange={(event) =>
                  setDepartmentForm({ ...departmentForm, room: event.target.value })
                }
                maxLength={50}
                placeholder="каб. 101"
              />
            </label>
            <label className="field field-checkbox">
              <input
                type="checkbox"
                checked={departmentForm.is_active}
                onChange={(event) =>
                  setDepartmentForm({
                    ...departmentForm,
                    is_active: event.target.checked,
                  })
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
              <button
                type="button"
                className="button"
                onClick={() => setDepartmentModalOpen(false)}
              >
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
