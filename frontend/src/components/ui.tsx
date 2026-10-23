import { useEffect, type ReactNode } from "react";
import { createPortal } from "react-dom";
import type { CartridgeStatus, PrinterStatus } from "../api/types";
import {
  PRINTER_STATUS_LABELS,
  STATUS_LABELS,
  statusClass,
} from "../utils";

export function Spinner({ label = "Загрузка…" }: { label?: string }) {
  return (
    <div className="spinner-wrap">
      <div className="spinner" />
      <span>{label}</span>
    </div>
  );
}

export function ErrorMessage({ message }: { message: string }) {
  return <div className="alert alert-error">{message}</div>;
}

export function SuccessMessage({ message }: { message: string }) {
  return <div className="alert alert-success">{message}</div>;
}

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

export function Modal({
  title,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return createPortal(
    <div className="modal-overlay" onMouseDown={onClose}>
      <div
        className={`modal ${wide ? "modal-wide" : ""}`}
        onMouseDown={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="modal-header">
          <h2>{title}</h2>
          <button className="icon-button" onClick={onClose} aria-label="Закрыть">
            ×
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>,
    document.body,
  );
}

export function StatusBadge({ status }: { status: CartridgeStatus }) {
  return <span className={statusClass(status)}>{STATUS_LABELS[status]}</span>;
}

export function PrinterStatusBadge({ status }: { status: PrinterStatus }) {
  return (
    <span className={`badge badge-printer-${status}`}>
      {PRINTER_STATUS_LABELS[status]}
    </span>
  );
}

export function EmptyRow({ colSpan, text = "Нет данных" }: { colSpan: number; text?: string }) {
  return (
    <tr>
      <td colSpan={colSpan} className="empty-cell">
        {text}
      </td>
    </tr>
  );
}
