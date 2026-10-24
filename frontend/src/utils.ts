import type {
  CartridgeColor,
  CartridgeKind,
  CartridgeStatus,
  InvoiceLineKind,
  InvoiceStatus,
  OperationType,
  PrinterStatus,
  ServiceResult,
} from "./api/types";

export const STATUS_LABELS: Record<CartridgeStatus, string> = {
  in_stock: "На складе",
  issued: "Выдан сотруднику",
  installed: "В принтере",
  in_refill: "На заправке",
  in_restore: "На восстановлении",
  written_off: "Списан",
};

export const STATUS_SHORT_LABELS: Record<CartridgeStatus, string> = {
  in_stock: "На складе",
  issued: "Выдан",
  installed: "В принтере",
  in_refill: "На заправке",
  in_restore: "Восстановление",
  written_off: "Списан",
};

export const OPERATION_LABELS: Record<OperationType, string> = {
  receipt: "Приход",
  issue: "Выдача сотруднику",
  install: "Установка в принтер",
  uninstall: "Снятие с принтера",
  return: "Возврат на склад",
  send_refill: "Отправка на заправку",
  refill_done: "Возврат с заправки",
  send_restore: "Отправка на восстановление",
  restore_done: "Возврат с восстановления",
  write_off: "Списание",
};

export const COLOR_LABELS: Record<CartridgeColor, string> = {
  black: "Чёрный",
  cyan: "Голубой",
  magenta: "Пурпурный",
  yellow: "Жёлтый",
  other: "Другой",
};

export const KIND_LABELS: Record<CartridgeKind, string> = {
  original: "Оригинал",
  compatible: "Совместимый",
};

export const SERVICE_RESULT_LABELS: Record<ServiceResult, string> = {
  refilled: "Заправлен",
  restored: "Восстановлен",
  repaired: "Отремонтирован",
  failed: "Не удалось",
  unrepairable: "Не подлежит восстановлению",
  other: "Другое",
};

export const PRINTER_STATUS_LABELS: Record<PrinterStatus, string> = {
  active: "Работает",
  repair: "В ремонте",
  retired: "Списан",
};

export const INVOICE_STATUS_LABELS: Record<InvoiceStatus, string> = {
  draft: "Черновик",
  applied: "Проведён",
};

export const INVOICE_LINE_KIND_LABELS: Record<InvoiceLineKind, string> = {
  restore: "Восстановление",
  refill: "Заправка",
  repair: "Ремонт аппарата",
};

export const STATUS_ORDER: CartridgeStatus[] = [
  "in_stock",
  "issued",
  "installed",
  "in_refill",
  "in_restore",
  "written_off",
];

export const OPERATION_ORDER: OperationType[] = [
  "receipt",
  "issue",
  "install",
  "uninstall",
  "return",
  "send_refill",
  "refill_done",
  "send_restore",
  "restore_done",
  "write_off",
];

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (dateOnly) {
    return `${dateOnly[3]}.${dateOnly[2]}.${dateOnly[1]}`;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString("ru-RU");
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function localIsoDate(date: Date): string {
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function formatMoney(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatMoneyExact(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export function todayIso(): string {
  return localIsoDate(new Date());
}

export function daysAgoIso(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return localIsoDate(date);
}

export function plural(count: number, forms: [string, string, string]): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return forms[0];
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return forms[1];
  return forms[2];
}

export function currentMonthIso(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export function recentMonthOptions(
  count = 12,
): { value: string; label: string }[] {
  const now = new Date();
  const options: { value: string; label: string }[] = [];
  for (let index = 0; index < count; index += 1) {
    const date = new Date(now.getFullYear(), now.getMonth() - index, 1);
    const value = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
    const label = date
      .toLocaleDateString("ru-RU", { month: "long", year: "numeric" })
      .replace(" г.", "");
    options.push({
      value,
      label: label.charAt(0).toUpperCase() + label.slice(1),
    });
  }
  return options;
}

export function orgName(raw: string): string {
  const trimmed = raw.trim();
  if (/^(ООО|ОАО|ЗАО|ПАО|АО|ИП)\b/i.test(trimmed)) return trimmed;
  return `ООО «${trimmed}»`;
}

export function modelTitle(vendor: string, name: string): string {
  return `${vendor} ${name}`;
}

export function statusClass(status: string): string {
  return `badge badge-${status.replace(/_/g, "-")}`;
}
