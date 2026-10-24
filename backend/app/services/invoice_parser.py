"""Разбор PDF-счетов на услуги (заправка/восстановление/ремонт)."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from pypdf import PdfReader

from app.models.enums import InvoiceLineKind

HOMOGLYPHS = str.maketrans("АВСЕНКМОРТХУІЈЅ", "ABCEHKMOPTXYIJS")

TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}

ITEM_RE = re.compile(
    r"^(\d{1,2})\s+(.+?)\s+(\d+)\s+шт\.?\s+([\d'’.,]+)\s+([\d'’.,]+)$"
)
RESTORE_RE = re.compile(r"^Восстановление картриджа\s+(.+)$", re.IGNORECASE)
REFILL_RE = re.compile(r"^Заправка картриджа\s+(.+)$", re.IGNORECASE)
REPAIR_RE = re.compile(r"^Ремонт аппарата\s+(.+)$", re.IGNORECASE)

HP_CODE_RE = re.compile(r"^(CE|CF|CG|CH|CC|CD|CB|C4|C6|Q2)\d", re.IGNORECASE)


class InvoiceParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedLine:
    number: int
    title: str
    kind: InvoiceLineKind
    target_raw: str
    qty: int
    price: Decimal
    total: Decimal


@dataclass
class ParsedInvoice:
    number: str
    issued_at: date
    supplier_name: str
    supplier_inn: str
    buyer_name: str
    buyer_inn: str
    total: Decimal
    vat: Decimal
    vat_rate: Decimal
    lines: list[ParsedLine] = field(default_factory=list)

    @property
    def problems(self) -> list[str]:
        found: list[str] = []
        if not self.lines:
            found.append("В счёте не найдено ни одной позиции")
            return found
        line_sum = sum((line.total for line in self.lines), Decimal("0"))
        if line_sum != self.total:
            found.append(f"Сумма позиций {line_sum} не совпадает с итогом {self.total}")
        for line in self.lines:
            if line.qty * line.price != line.total:
                found.append(
                    f"Позиция {line.number}: {line.qty} × {line.price} ≠ {line.total}"
                )
        return found


def _money(raw: str) -> Decimal:
    return Decimal(re.sub(r"[\s'’]", "", raw).replace(",", "."))


def _join_split_codes(raw: str) -> str:
    return re.sub(r"(?<=\d)\s+(?=[A-ZА-Я]\s*$)", "", raw.strip())


def normalize_code(raw: str) -> str:
    """Убирает кириллические омоглифы в кодах моделей: «СЕ390А» → «CE390A»."""
    parts = []
    for token in raw.split():
        parts.append(token.translate(HOMOGLYPHS) if re.search(r"\d", token) else token)
    return " ".join(parts)


def slug(text: str) -> str:
    out = []
    for ch in text:
        low = ch.lower()
        if low in TRANSLIT:
            out.append(TRANSLIT[low])
        elif ch.isalnum():
            out.append(ch)
        else:
            out.append("-")
    return re.sub(r"-+", "-", "".join(out)).strip("-").upper() or "ITEM"


def vendor_for_cartridge(name: str) -> str:
    if HP_CODE_RE.match(name):
        return "HP"
    if "ricoh" in name.lower():
        return "Ricoh"
    return "Прочее"


def _party(flat: str, label: str, stop: str) -> tuple[str, str]:
    start = flat.index(label) + len(label)
    chunk = flat[start : flat.index(stop, start)]
    inn = re.search(r"ИНН\s*(\d{9,12})", chunk)
    name = re.search(r"«([^»]+)»", chunk) or re.search(r'"([^"]+)"', chunk)
    return (name.group(1).strip() if name else chunk[:100], inn.group(1) if inn else "")


def pdf_to_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:  # noqa: BLE001 - любая ошибка чтения PDF
        raise InvoiceParseError("Не удалось прочитать PDF-файл") from exc


def parse_invoice_pdf(data: bytes) -> ParsedInvoice:
    return parse_invoice_text(pdf_to_text(data))


def parse_invoice_text(text: str) -> ParsedInvoice:
    flat = " ".join(text.split())
    header = re.search(r"Сч[её]т\s*№\s*(\d+)\s*от\s*(\d{2}\.\d{2}\.\d{4})", flat)
    if header is None:
        raise InvoiceParseError("Не удалось найти номер и дату счёта")
    total_match = re.search(r"Итого:\s*([\d'’.,]+)", flat)
    if total_match is None:
        raise InvoiceParseError("Не удалось найти итоговую сумму счёта")
    try:
        supplier_name, supplier_inn = _party(flat, "Поставщик:", "Покупатель:")
        buyer_name, buyer_inn = _party(flat, "Покупатель:", "№ Товар")
    except ValueError as exc:
        raise InvoiceParseError("Не удалось найти поставщика и покупателя") from exc

    vat_match = re.search(
        r"НДС\s*(\d+(?:[.,]\d+)?)\s*%\s*:\s*([\d'’.,]+)", flat
    )
    invoice = ParsedInvoice(
        number=header.group(1),
        issued_at=datetime.strptime(header.group(2), "%d.%m.%Y").date(),
        supplier_name=supplier_name,
        supplier_inn=supplier_inn,
        buyer_name=buyer_name,
        buyer_inn=buyer_inn,
        total=_money(total_match.group(1)),
        vat=_money(vat_match.group(2)) if vat_match else Decimal("0"),
        vat_rate=(
            _money(vat_match.group(1)) if vat_match else Decimal("0")
        ),
    )

    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        match = ITEM_RE.match(line)
        if match is None:
            continue
        num, title, qty, price, total = match.groups()
        title = _join_split_codes(title)

        if repair := REPAIR_RE.match(title):
            kind, target = InvoiceLineKind.REPAIR, repair.group(1).strip()
        elif restore := RESTORE_RE.match(title):
            kind, target = InvoiceLineKind.RESTORE, normalize_code(restore.group(1))
        elif refill := REFILL_RE.match(title):
            kind, target = InvoiceLineKind.REFILL, normalize_code(refill.group(1))
        else:
            raise InvoiceParseError(f"Неизвестный тип позиции: {title}")

        invoice.lines.append(
            ParsedLine(
                number=int(num),
                title=title,
                kind=kind,
                target_raw=target,
                qty=int(qty),
                price=_money(price),
                total=_money(total),
            )
        )

    return invoice
