import { useState, type FormEvent } from "react";
import { useAuth } from "../auth";

export function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username.trim(), password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось войти");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-panel">
        <div className="login-brand">
          <span className="brand-mark brand-mark-large">C</span>
          <h1>Cardridz</h1>
          <p>Учёт картриджей, принтеров и расходных материалов</p>
          <ul>
            <li>Склад, выдача и установка картриджей</li>
            <li>Заправка, восстановление и списание</li>
            <li>История операций и отчёты</li>
          </ul>
        </div>
        <div className="login-card">
          <h2>Вход в систему</h2>
          <p className="muted">Введите учётные данные, выданные администратором.</p>
          <form onSubmit={handleSubmit}>
            <label className="field">
              <span>Логин</span>
              <input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
                required
                autoFocus
              />
            </label>
            <label className="field">
              <span>Пароль</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                required
              />
            </label>
            {error && <div className="alert alert-error">{error}</div>}
            <button className="button button-primary button-block" disabled={submitting}>
              {submitting ? "Вход…" : "Войти"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
