"""Heuristic extraction of bill-of-works rows from tab-separated tender text.

Used when the LLM returns an empty ``bill_of_works`` but XLSX/DOCX/PDF text still
contains table-like lines (e.g. local estimate / локальная смета).

Russian local estimates often have columns: №, code, name, unit, quantity, unit price,
total — taking the rightmost number as ``quantity`` mis-attributes totals in rubles.
This module detects header rows when possible and pairs unit+quantity columns; it also
filters out titles, labour-cost breakdown rows, and metadata.
"""

from __future__ import annotations

import re
from typing import Any

_MAX_ROWS = 400
_MIN_NAME_LEN = 6

# Typical construction / estimate units (not rubles / hours codes as primary UOM).
_UOM_PATTERN = re.compile(
    r"^[\s]*("
    r"м[²2³3]?|м3|м\^3|шт|т(?:\s|$)|кг|компл|комплект|"
    r"п\.?\s*м|пог\.?\s*м|набор|100\s*м[²2]|100м[²2]|"
    r"ед\.?|мес|чел\.?-?ч|чел-?ч|маш\.?-?ч"
    r")[\s]*$",
    re.IGNORECASE,
)


def _looks_like_uom(s: str) -> bool:
    """True if cell looks like a work measure unit, not currency or a code title."""
    t = (s or "").strip().lower().replace(" ", "")
    if not t or len(t) > 24:
        return False
    if "руб" in t or "тыс" in t:
        return False
    if "%" in t:
        return False
    return bool(_UOM_PATTERN.match(t.strip()))


def _looks_like_quantity(s: str) -> bool:
    t = s.strip().replace(" ", "").replace(",", ".")
    if not t:
        return False
    if re.match(r"^\d{1,2}\.\d{1,2}\.\d{2,4}", t):
        return False
    return bool(re.match(r"^-?[\d.]+(?:[eE][+-]?\d+)?$", t))


def _safe_float(s: str) -> float | None:
    if not _looks_like_quantity(s):
        return None
    try:
        return float(s.strip().replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def _is_header_line(parts: list[str]) -> bool:
    joined = " ".join(parts).lower()
    if "наимен" in joined and ("кол" in joined or "объем" in joined or "объём" in joined):
        return True
    if "наимен" in joined and ("ед" in joined and "изм" in joined):
        return True
    if "шифр" in joined and "наимен" in joined:
        return True
    if "позиц" in joined and "наимен" in joined:
        return True
    if parts and parts[0].strip().lower() in ("№", "п/п", "пп", "n", "no", "номер"):
        if "наимен" in joined or "наим" in joined:
            return True
    return False


def _parse_header_column_indices(parts: list[str]) -> dict[str, int]:
    """Map logical columns to indices from a detected header row."""
    out: dict[str, int] = {}
    for i, raw in enumerate(parts):
        low = raw.strip().lower()
        if "наимен" in low:
            out["name"] = i
        if ("ед" in low and "изм" in low) or low in ("ед.изм.", "ед. изм.", "ед.изм"):
            out["unit"] = i
        if "колич" in low or "объем" in low or "объём" in low:
            out["qty"] = i
        if low in ("№", "п/п", "пп", "номер", "n") or low.startswith("№"):
            out["pos"] = i
        if "цена" in low and "един" in low:
            out["unit_price"] = i
        if "стоим" in low or ("сумм" in low and "всего" in low):
            out["total"] = i
    return out


def _row_from_header_map(parts: list[str], m: dict[str, int]) -> dict[str, str] | None:
    """Build one bill row using header-derived column indices."""
    ni, qi = m.get("name"), m.get("qty")
    if ni is None or qi is None:
        return None
    if ni >= len(parts) or qi >= len(parts):
        return None
    name = parts[ni].strip()
    qty_s = parts[qi].strip()
    if not name or not _looks_like_quantity(qty_s):
        return None
    pos = parts[m["pos"]].strip() if "pos" in m and m["pos"] < len(parts) else ""
    unit = parts[m["unit"]].strip() if "unit" in m and m["unit"] < len(parts) else ""
    remarks = ""
    return {"position": pos, "name": name, "unit": unit, "quantity": qty_s, "remarks": remarks}


def _clean_remarks(name: str, remarks: str) -> str:
    """Drop remarks that duplicate the name or are empty."""
    r = (remarks or "").strip()
    if not r:
        return ""
    n = name.strip()
    if r == n:
        return ""
    if n and (r.startswith(n) or n.startswith(r)) and abs(len(r) - len(n)) < 4:
        return ""
    # Drop tail that is only price/total numbers (common after qty in local estimates).
    compact = r.replace("\t", " ").strip()
    if re.fullmatch(r"[\d\s.,−\-]+", compact) and any(c.isdigit() for c in compact):
        return ""
    return r


def _is_junk_estimate_row(row: dict[str, str]) -> bool:
    """Filter metadata, section banners, labour-cost lines, and mis-parsed totals."""
    name = (row.get("name") or "").strip()
    unit = (row.get("unit") or "").strip()
    qty_s = (row.get("quantity") or "").strip()
    low = name.lower()
    ulow = unit.lower()

    if len(name) < _MIN_NAME_LEN:
        return True
    if any(
        x in low
        for x in (
            "составлен",
            "уровне цен",
            "тыс.руб",
            "тыс руб",
            "локальн-смет",
            "локальная смета",
            "подготовлен",
        )
    ):
        return True
    if re.search(r"\d{2}\.\d{2}\.\d{4}", name):
        return True
    if "средства на оплату труда" in low:
        return True
    if re.match(r"^от\(?зт", low.replace(" ", "")) or "отм(зт" in low.replace(" ", ""):
        return True
    if "заработная плата" in low and "рабоч" in low:
        return True
    if ulow and ("руб" in ulow or "тыс" in ulow):
        return True
    # Section titles without real UOM
    if len(name) < 55 and any(
        x in low for x in ("строительных работ", "монтажных работ", "демонтажных работ")
    ):
        if not unit or not _looks_like_uom(unit):
            return True
    qf = _safe_float(qty_s)
    if qf is not None:
        # Very small decimals often are cost shares or indices, not m2/m3 counts — drop if UOM missing
        if abs(qf) < 0.001:
            return True
        # Large values with non-UOM unit are likely ruble totals misread as qty
        if abs(qf) >= 500_000 and not _looks_like_uom(unit):
            return True
        if abs(qf) >= 10_000_000:
            return True
    # Require plausible unit for numeric-heavy rows (skip labour % rows)
    if unit and not _looks_like_uom(unit):
        if "чел" not in ulow and "маш" not in ulow:
            if qf is not None and 0 < abs(qf) < 1000:
                pass
            else:
                return True
    return False


def _row_fallback_uom_qty_pair(parts: list[str]) -> dict[str, str] | None:
    """Find leftmost (unit, quantity) pair where unit looks like construction UOM."""
    if len(parts) < 3:
        return None
    if _is_header_line(parts):
        return None

    if len(parts) == 3:
        a, b, c = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if _looks_like_uom(b) and _looks_like_quantity(c) and len(a) >= _MIN_NAME_LEN:
            return {
                "position": "",
                "name": a,
                "unit": b,
                "quantity": c,
                "remarks": "",
            }
        return None

    best: tuple[int, int, int] | None = None
    for i in range(1, len(parts) - 1):
        u, q = parts[i].strip(), parts[i + 1].strip()
        if not _looks_like_uom(u) or not _looks_like_quantity(q):
            continue
        qf = _safe_float(q)
        if qf is None:
            continue
        if abs(qf) > 5_000_000:
            continue
        if best is None or i < best[0]:
            best = (i, i, i + 1)

    if best is None:
        return None

    i_u, _, i_q = best
    unit = parts[i_u].strip()
    qty = parts[i_q].strip()
    middle = [parts[j].strip() for j in range(1, i_u) if parts[j].strip()]
    name = max(middle, key=len) if middle else ""
    if len(name) < _MIN_NAME_LEN:
        return None
    pos = parts[0].strip()
    if len(pos) > 28:
        pos = ""
    tail = [parts[j].strip() for j in range(i_q + 1, len(parts)) if parts[j].strip()]
    remarks = _clean_remarks(name, "\t".join(tail))
    return {"position": pos, "name": name, "unit": unit, "quantity": qty, "remarks": remarks}


def extract_bill_of_works_heuristic(text: str) -> tuple[list[dict[str, str]], str]:
    """Parse tab-separated lines into bill rows. Returns (rows, short note for humans)."""
    if not text or len(text.strip()) < 50:
        return [], "too_short"

    rows: list[dict[str, str]] = []
    header_map: dict[str, int] | None = None

    for line in text.splitlines():
        if "\t" not in line:
            header_map = None
            continue
        parts = [p.strip() for p in line.split("\t")]
        while parts and not parts[-1]:
            parts.pop()
        if len(parts) < 3:
            continue

        if _is_header_line(parts):
            header_map = _parse_header_column_indices(parts)
            if "name" not in header_map or "qty" not in header_map:
                header_map = None
            continue

        row: dict[str, str] | None = None
        if header_map:
            row = _row_from_header_map(parts, header_map)
        if row is None:
            row = _row_fallback_uom_qty_pair(parts)

        if row and not _is_junk_estimate_row(row):
            rows.append(row)
            if len(rows) >= _MAX_ROWS:
                break

    if not rows:
        return [], "no_tabular_rows"

    note = f"heuristic:{len(rows)}_rows_from_tabs"
    return rows, note


def merge_bill_rows_llm_and_heuristic(
    llm_rows: list[Any],
    heuristic_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Prefer a richer LLM table; if the model returns few rows, use tabular heuristic when it yields more."""
    normalized_llm = [_normalize_llm_row(r) for r in llm_rows if isinstance(r, dict)]
    normalized_llm = [r for r in normalized_llm if r and (r.get("name") or "").strip()]
    if not heuristic_rows:
        return normalized_llm
    if len(normalized_llm) >= 2 and len(normalized_llm) >= len(heuristic_rows):
        return normalized_llm
    if len(heuristic_rows) > len(normalized_llm):
        return heuristic_rows
    return normalized_llm or heuristic_rows


def _normalize_llm_row(row: dict[str, Any]) -> dict[str, str] | None:
    """Map varied JSON keys to position/name/unit/quantity/remarks."""
    if not isinstance(row, dict):
        return None

    def find_val(*candidates: str) -> str:
        for c in candidates:
            cl = c.lower()
            for k, v in row.items():
                if not isinstance(k, str):
                    continue
                kl = k.lower().replace(" ", "_")
                if kl == cl or kl.replace("_", "") == cl.replace("_", ""):
                    if v is None:
                        return ""
                    return str(v).strip()
        return ""

    name = find_val("name", "наименование", "title", "наименование_работ", "work_name")
    pos = find_val("position", "pos", "№", "номер", "позиция", "no")
    unit = find_val("unit", "ед", "ед_изм", "uom")
    qty = find_val("quantity", "количество", "кол_во", "объем", "объём", "qty")
    remarks = find_val("remarks", "примечание", "note", "комментарий")

    if not name and not qty:
        return None
    remarks = _clean_remarks(name or "—", remarks)
    return {
        "position": pos,
        "name": name or "—",
        "unit": unit,
        "quantity": qty,
        "remarks": remarks,
    }
