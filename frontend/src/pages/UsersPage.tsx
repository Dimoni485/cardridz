import { useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { AdminUser, UserRole } from "../api/types";
import {
  EmptyRow,
  ErrorMessage,
  Modal,
  PageHeader,
  Spinner,
  SuccessMessage,
} from "../components/ui";
import { useAsyncData } from "../hooks";
import { useAuth } from "../auth";
import { ROLE_HINTS, ROLE_LABELS } from "../roles";

interface UserForm {
  username: string;
  full_name: string;
  password: string;
  role: UserRole;
  is_active: boolean;
}

const EMPTY_FORM: UserForm = {
  username: "",
  full_name: "",
  password: "",
  role: "viewer",
  is_active: true,
};

export function UsersPage() {
  const { user: currentUser } = useAuth();
  const users = useAsyncData(() => api.get<AdminUser[]>("/users"), []);

  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<AdminUser | null>(null);
  const [form, setForm] = useState<UserForm>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [passwordUser, setPasswordUser] = useState<AdminUser | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordDone, setPasswordDone] = useState(false);

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setError(null);
    setShowForm(true);
  }

  function openEdit(user: AdminUser) {
    setEditing(user);
    setForm({
      username: user.username,
      full_name: user.full_name,
      password: "",
      role: user.role,
      is_active: user.is_active,
    });
    setError(null);
    setShowForm(true);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (editing) {
        await api.patch(`/users/${editing.id}`, {
          full_name: form.full_name.trim(),
          role: form.role,
          is_active: form.is_active,
        });
      } else {
        await api.post("/users", {
          username: form.username.trim(),
          full_name: form.full_name.trim(),
          password: form.password,
          role: form.role,
          is_active: form.is_active,
        });
      }
      setShowForm(false);
      users.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить пользователя");
    } finally {
      setSaving(false);
    }
  }

  function openPassword(user: AdminUser) {
    setPasswordUser(user);
    setNewPassword("");
    setPasswordError(null);
    setPasswordDone(false);
  }

  async function submitPassword(event: FormEvent) {
    event.preventDefault();
    if (!passwordUser) return;
    setSaving(true);
    setPasswordError(null);
    try {
      await api.post(`/users/${passwordUser.id}/password`, {
        password: newPassword,
      });
      setPasswordDone(true);
    } catch (err) {
      setPasswordError(
        err instanceof Error ? err.message : "Не удалось изменить пароль",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(user: AdminUser) {
    if (!window.confirm(`Удалить пользователя «${user.username}»?`)) return;
    setListError(null);
    try {
      await api.delete(`/users/${user.id}`);
      users.reload();
    } catch (err) {
      setListError(
        err instanceof Error ? err.message : "Не удалось удалить пользователя",
      );
    }
  }

  return (
    <div>
      <PageHeader
        title="Пользователи"
        subtitle="Учётные записи системы и их права доступа"
        actions={
          <button className="button button-primary" onClick={openCreate}>
            + Добавить пользователя
          </button>
        }
      />

      {listError && <ErrorMessage message={listError} />}
      {users.loading && <Spinner />}
      {users.error && <ErrorMessage message={users.error} />}

      {users.data && !users.loading && (
        <div className="card table-card">
          <table className="table">
            <thead>
              <tr>
                <th>Пользователь</th>
                <th>Логин</th>
                <th>Права</th>
                <th>Статус</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {users.data.length === 0 && <EmptyRow colSpan={5} />}
              {users.data.map((user) => {
                const isSelf = user.id === currentUser?.id;
                return (
                  <tr key={user.id}>
                    <td>
                      <strong>{user.full_name}</strong>
                      {isSelf && <div className="muted small">это вы</div>}
                    </td>
                    <td className="mono">{user.username}</td>
                    <td>
                      <span className={`badge badge-role-${user.role}`}>
                        {ROLE_LABELS[user.role]}
                      </span>
                      <div className="muted small">{ROLE_HINTS[user.role]}</div>
                    </td>
                    <td>
                      <span
                        className={`badge ${user.is_active ? "badge-active" : "badge-inactive"}`}
                      >
                        {user.is_active ? "Активен" : "Заблокирован"}
                      </span>
                    </td>
                    <td className="right nowrap">
                      <button
                        className="button button-small"
                        onClick={() => openEdit(user)}
                      >
                        Изменить
                      </button>
                      <button
                        className="button button-small"
                        onClick={() => openPassword(user)}
                      >
                        Пароль
                      </button>
                      <button
                        className="button button-small button-danger-ghost"
                        onClick={() => handleDelete(user)}
                        disabled={isSelf}
                      >
                        Удалить
                      </button>
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
          title={editing ? "Изменение пользователя" : "Новый пользователь"}
          onClose={() => setShowForm(false)}
        >
          <form onSubmit={handleSubmit} className="form-grid">
            <label className="field">
              <span>Логин *</span>
              <input
                className="input"
                value={form.username}
                onChange={(event) =>
                  setForm({ ...form, username: event.target.value })
                }
                required
                minLength={3}
                maxLength={64}
                pattern="[A-Za-z0-9._\-]+"
                title="Латиница, цифры, точка, дефис или подчёркивание"
                disabled={Boolean(editing)}
              />
            </label>
            <label className="field">
              <span>ФИО *</span>
              <input
                className="input"
                value={form.full_name}
                onChange={(event) =>
                  setForm({ ...form, full_name: event.target.value })
                }
                required
                maxLength={150}
              />
            </label>
            {!editing && (
              <label className="field field-wide">
                <span>Пароль * (не менее 8 символов)</span>
                <input
                  className="input"
                  type="password"
                  value={form.password}
                  onChange={(event) =>
                    setForm({ ...form, password: event.target.value })
                  }
                  required
                  minLength={8}
                  maxLength={128}
                  autoComplete="new-password"
                />
              </label>
            )}
            <label className="field">
              <span>Права доступа *</span>
              <select
                className="input"
                value={form.role}
                onChange={(event) =>
                  setForm({ ...form, role: event.target.value as UserRole })
                }
              >
                {(Object.keys(ROLE_LABELS) as UserRole[]).map((role) => (
                  <option key={role} value={role}>
                    {ROLE_LABELS[role]}
                  </option>
                ))}
              </select>
            </label>
            <label className="field field-checkbox">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(event) =>
                  setForm({ ...form, is_active: event.target.checked })
                }
              />
              <span>Доступ разрешён</span>
            </label>
            <div className="muted small field-wide">
              {ROLE_HINTS[form.role]}
            </div>
            {error && (
              <div className="field-wide">
                <ErrorMessage message={error} />
              </div>
            )}
            <div className="form-actions field-wide">
              <button
                type="button"
                className="button button-ghost"
                onClick={() => setShowForm(false)}
              >
                Отмена
              </button>
              <button
                type="submit"
                className="button button-primary"
                disabled={saving}
              >
                {saving ? "Сохранение…" : "Сохранить"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {passwordUser && (
        <Modal
          title={`Новый пароль для «${passwordUser.username}»`}
          onClose={() => setPasswordUser(null)}
        >
          {passwordDone ? (
            <div>
              <SuccessMessage message="Пароль обновлён" />
              <div className="form-actions">
                <button
                  className="button button-primary"
                  onClick={() => setPasswordUser(null)}
                >
                  Готово
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={submitPassword} className="form-grid">
              <label className="field field-wide">
                <span>Пароль * (не менее 8 символов)</span>
                <input
                  className="input"
                  type="password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  required
                  minLength={8}
                  maxLength={128}
                  autoComplete="new-password"
                />
              </label>
              {passwordError && (
                <div className="field-wide">
                  <ErrorMessage message={passwordError} />
                </div>
              )}
              <div className="form-actions field-wide">
                <button
                  type="button"
                  className="button button-ghost"
                  onClick={() => setPasswordUser(null)}
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  className="button button-primary"
                  disabled={saving}
                >
                  {saving ? "Сохранение…" : "Сохранить пароль"}
                </button>
              </div>
            </form>
          )}
        </Modal>
      )}
    </div>
  );
}
