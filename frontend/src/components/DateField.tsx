import { useEffect, useRef, useState } from "react";

const pad = (value: number) => String(value).padStart(2, "0");

function isoToDisplay(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  return match ? `${match[3]}.${match[2]}.${match[1]}` : "";
}

function displayToIso(text: string): string | null {
  const match = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(text.trim());
  if (!match) return null;
  const [, day, month, year] = match;
  const date = new Date(Number(year), Number(month) - 1, Number(day));
  if (
    date.getFullYear() !== Number(year) ||
    date.getMonth() !== Number(month) - 1 ||
    date.getDate() !== Number(day)
  ) {
    return null;
  }
  return `${year}-${month}-${day}`;
}

function isoToDateTimeDisplay(iso: string): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return `${pad(date.getDate())}.${pad(date.getMonth() + 1)}.${date.getFullYear()} ${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

function displayToDateTimeIso(text: string): string | null {
  const match = /^(\d{2})\.(\d{2})\.(\d{4})(?:\s+(\d{2}):(\d{2}))?$/.exec(
    text.trim(),
  );
  if (!match) return null;
  const [, day, month, year, hours = "00", minutes = "00"] = match;
  const date = new Date(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hours),
    Number(minutes),
  );
  if (
    date.getFullYear() !== Number(year) ||
    date.getMonth() !== Number(month) - 1 ||
    date.getDate() !== Number(day) ||
    date.getHours() !== Number(hours) ||
    date.getMinutes() !== Number(minutes)
  ) {
    return null;
  }
  return date.toISOString();
}

function isoToNativeDate(iso: string): string {
  return /^\d{4}-\d{2}-\d{2}$/.test(iso) ? iso : "";
}

function isoToNativeDateTime(iso: string): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(
    date.getDate(),
  )}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function openNativePicker(input: HTMLInputElement | null) {
  if (!input) return;
  const picker = input as HTMLInputElement & { showPicker?: () => void };
  try {
    if (typeof picker.showPicker === "function") {
      picker.showPicker();
      return;
    }
  } catch {
    // браузер может запретить вызов — используем обычный клик
  }
  input.click();
}

function CalendarIcon() {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  );
}

interface FieldProps {
  value: string;
  onChange: (value: string) => void;
  className?: string;
  id?: string;
}

export function DateField({ value, onChange, className = "", id }: FieldProps) {
  const [text, setText] = useState(isoToDisplay(value));
  const [invalid, setInvalid] = useState(false);
  const nativeRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setText(isoToDisplay(value));
    setInvalid(false);
  }, [value]);

  function handleText(next: string) {
    setText(next);
    if (next.trim() === "") {
      setInvalid(false);
      onChange("");
      return;
    }
    const iso = displayToIso(next);
    if (iso) {
      setInvalid(false);
      onChange(iso);
    } else {
      setInvalid(true);
    }
  }

  function handleBlur() {
    if (text.trim() !== "" && displayToIso(text) === null) {
      setText(isoToDisplay(value));
      setInvalid(false);
    }
  }

  return (
    <div className={`date-field ${className}`.trim()}>
      <input
        id={id}
        className="input"
        type="text"
        inputMode="numeric"
        placeholder="дд.мм.гггг"
        value={text}
        onChange={(event) => handleText(event.target.value)}
        onBlur={handleBlur}
        aria-invalid={invalid || undefined}
      />
      <button
        type="button"
        className="date-picker-button"
        aria-label="Открыть календарь"
        onClick={() => openNativePicker(nativeRef.current)}
      >
        <CalendarIcon />
      </button>
      <input
        ref={nativeRef}
        type="date"
        className="native-picker"
        tabIndex={-1}
        aria-hidden="true"
        value={isoToNativeDate(value)}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}

export function DateTimeField({ value, onChange, className = "", id }: FieldProps) {
  const [text, setText] = useState(isoToDateTimeDisplay(value));
  const [invalid, setInvalid] = useState(false);
  const nativeRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setText(isoToDateTimeDisplay(value));
    setInvalid(false);
  }, [value]);

  function handleText(next: string) {
    setText(next);
    if (next.trim() === "") {
      setInvalid(false);
      onChange("");
      return;
    }
    const iso = displayToDateTimeIso(next);
    if (iso) {
      setInvalid(false);
      onChange(iso);
    } else {
      setInvalid(true);
    }
  }

  function handleBlur() {
    if (text.trim() !== "" && displayToDateTimeIso(text) === null) {
      setText(isoToDateTimeDisplay(value));
      setInvalid(false);
    }
  }

  return (
    <div className={`date-field ${className}`.trim()}>
      <input
        id={id}
        className="input"
        type="text"
        inputMode="numeric"
        placeholder="дд.мм.гггг чч:мм"
        value={text}
        onChange={(event) => handleText(event.target.value)}
        onBlur={handleBlur}
        aria-invalid={invalid || undefined}
      />
      <button
        type="button"
        className="date-picker-button"
        aria-label="Открыть календарь"
        onClick={() => openNativePicker(nativeRef.current)}
      >
        <CalendarIcon />
      </button>
      <input
        ref={nativeRef}
        type="datetime-local"
        className="native-picker"
        tabIndex={-1}
        aria-hidden="true"
        value={isoToNativeDateTime(value)}
        onChange={(event) =>
          onChange(event.target.value ? new Date(event.target.value).toISOString() : "")
        }
      />
    </div>
  );
}
