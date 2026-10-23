import { useState, type FormEvent } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth";
import { ROLE_LABELS } from "../roles";
import { ErrorMessage, Modal, SuccessMessage } from "./ui";

interface NavItem {
  to: string;
  label: string;
  icon: string;
  end?: boolean;
  adminOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Панель", icon: "◫", end: true },
  { to: "/cartridges", label: "Картриджи", icon: "▤" },
  { to: "/operations", label: "Журнал операций", icon: "⇄" },
  { to: "/printers", label: "Принтеры", icon: "⎙" },
  { to: "/models", label: "Модели картриджей", icon: "◈" },
  { to: "/printer-models", label: "Модели принтеров", icon: "▦" },
  { to: "/employees", label: "Сотрудники", icon: "◎" },
  { to: "/entities", label: "Юрлица и отделы", icon: "⌂" },
  { to: "/service-providers", label: "Сервисные организации", icon: "⛭" },
  { to: "/reports", label: "Отчёты", icon: "▥" },
  { to: "/users", label: "Пользователи", icon: "☗", adminOnly: true },
  { to: "/help", label: "Помощь", icon: "?" },
];

export function Layout() {
  const { user, logout, canEdit, isAdmin } = useAuth();

  const [showPassword, setShowPassword] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordDone, setPasswordDone] = useState(false);
  const [saving, setSaving] = useState(false);

  function openPassword() {
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setPasswordError(null);
    setPasswordDone(false);
    setShowPassword(true);
  }

  async function submitPassword(event: FormEvent) {
    event.preventDefault();
    setPasswordError(null);
    if (newPassword !== confirmPassword) {
      setPasswordError("Новый пароль и подтверждение не совпадают");
      return;
    }
    setSaving(true);
    try {
      await api.post("/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setPasswordDone(true);
    } catch (err) {
      setPasswordError(err instanceof Error ? err.message : "Не удалось сменить пароль");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">C</span>
          <div>
            <strong>Cardridz</strong>
            <small>учёт картриджей</small>
          </div>
        </div>
        <nav className="nav">
          {NAV_ITEMS.filter((item) => !item.adminOnly || isAdmin).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="user-chip">
            <span className="avatar">{user?.full_name.slice(0, 1) ?? "?"}</span>
            <div>
              <div className="user-name">{user?.full_name}</div>
              <div className="user-login">
                @{user?.username} · {user ? ROLE_LABELS[user.role] : ""}
              </div>
            </div>
          </div>
          <button className="button button-ghost button-block" onClick={openPassword}>
            Сменить пароль
          </button>
          <button className="button button-ghost button-block" onClick={logout}>
            Выйти
          </button>
        </div>
      </aside>
      <main className="content">
        {!canEdit && (
          <div className="readonly-banner">
            Режим только для чтения — изменения данных недоступны для вашей
            учётной записи.
          </div>
        )}
        <Outlet />
      </main>

      {showPassword && (
        <Modal title="Смена пароля" onClose={() => setShowPassword(false)}>
          {passwordDone ? (
            <div>
              <SuccessMessage message="Пароль изменён" />
              <div className="form-actions">
                <button
                  className="button button-primary"
                  onClick={() => setShowPassword(false)}
                >
                  Готово
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={submitPassword} className="form-grid">
              <label className="field field-wide">
                <span>Текущий пароль *</span>
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                  autoComplete="current-password"
                  required
                />
              </label>
              <label className="field field-wide">
                <span>Новый пароль * (минимум 8 символов)</span>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  autoComplete="new-password"
                  minLength={8}
                  required
                />
              </label>
              <label className="field field-wide">
                <span>Повторите новый пароль *</span>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  autoComplete="new-password"
                  minLength={8}
                  required
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
                  className="button"
                  onClick={() => setShowPassword(false)}
                >
                  Отмена
                </button>
                <button className="button button-primary" disabled={saving}>
                  {saving ? "Сохранение…" : "Сменить пароль"}
                </button>
              </div>
            </form>
          )}
        </Modal>
      )}
    </div>
  );
}
