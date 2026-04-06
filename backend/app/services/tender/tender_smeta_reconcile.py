"""Post-process indicative smeta JSON from the LLM so figures stay internally consistent.

The model may repeat the same ``line_total_rub`` on every row, report row sums that do not
match ``estimated_direct_cost_rub``, or suggest a bid floor below cost. This module
recomputes per-row totals when quantity and unit price are present, rescales rows when
their aggregate clearly disagrees with the stated direct cost, and clamps the minimum bid.
"""

from __future__ import annotations

import math
from typing import Any


def _parse_number(value: Any) -> float | None:
    """Parse a numeric value from LLM output (int, float, or Russian-style decimal string)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        return float(value)
    if isinstance(value, str):
        s = value.replace("\u00a0", " ").replace(" ", "").replace(",", ".").strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _rows_line_sum(rows: list[dict[str, Any]]) -> float:
    total = 0.0
    for r in rows:
        lt = _parse_number(r.get("line_total_rub"))
        if lt is not None and lt >= 0:
            total += lt
    return total


def _all_line_totals_equal(rows: list[dict[str, Any]]) -> bool:
    vals: list[float] = []
    for r in rows:
        lt = _parse_number(r.get("line_total_rub"))
        if lt is None:
            return False
        vals.append(lt)
    if len(vals) < 2:
        return False
    first = vals[0]
    return all(math.isclose(v, first, rel_tol=0.0, abs_tol=0.5) for v in vals)


def reconcile_smeta_llm_output(out: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``out`` with coherent ``row_estimates`` and top-level rub fields.

    Аргументы:
        out: Parsed JSON object from the OpenAI smeta call.

    Возвращает:
        Updated dict safe to persist under ``smeta_calculation``.
    """
    result = dict(out)
    raw_rows = result.get("row_estimates")
    if not isinstance(raw_rows, list) or not raw_rows:
        return _clamp_minimum_bid(result)

    rows: list[dict[str, Any]] = []
    for item in raw_rows:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        q = _parse_number(row.get("quantity"))
        unit = _parse_number(row.get("unit_cost_assumption_rub"))
        if q is not None and unit is not None and q >= 0 and unit >= 0:
            row["line_total_rub"] = round(q * unit, 2)
        rows.append(row)

    if not rows:
        result["row_estimates"] = []
        return _clamp_minimum_bid(result)

    direct_llm = _parse_number(result.get("estimated_direct_cost_rub"))
    line_sum = _rows_line_sum(rows)

    every_row_has_q_u = True
    for r in rows:
        if _parse_number(r.get("quantity")) is None or _parse_number(r.get("unit_cost_assumption_rub")) is None:
            every_row_has_q_u = False
            break

    # Rows all identical (common LLM failure: repeats project total per line): scale to stated direct cost.
    if (
        len(rows) >= 2
        and _all_line_totals_equal(rows)
        and direct_llm is not None
        and direct_llm > 0
        and line_sum > direct_llm * 1.15
    ):
        factor = direct_llm / line_sum if line_sum > 0 else 1.0
        for r in rows:
            lt = _parse_number(r.get("line_total_rub"))
            if lt is not None:
                r["line_total_rub"] = round(lt * factor, 2)
        line_sum = _rows_line_sum(rows)

    # When we cannot trust per-row q×unit for every line, align row sums with LLM direct cost if they drift.
    if (
        not every_row_has_q_u
        and direct_llm is not None
        and direct_llm > 0
        and line_sum > 0
    ):
        denom = max(direct_llm, line_sum, 1.0)
        drift = abs(line_sum - direct_llm) / denom
        if drift > 0.12:
            factor = direct_llm / line_sum
            for r in rows:
                lt = _parse_number(r.get("line_total_rub"))
                if lt is not None:
                    r["line_total_rub"] = round(lt * factor, 2)
            line_sum = _rows_line_sum(rows)

    # Totals: if every row came from q×unit, row sum is authoritative; else use reconciled line_sum.
    if line_sum > 0:
        result["estimated_direct_cost_rub"] = round(line_sum, 2)
        overhead = _parse_number(result.get("suggested_overhead_rub"))
        oh = max(0.0, overhead or 0.0)
        result["estimated_total_cost_rub"] = round(line_sum + oh, 2)
    elif direct_llm is not None:
        oh = max(0.0, _parse_number(result.get("suggested_overhead_rub")) or 0.0)
        result["estimated_total_cost_rub"] = round(direct_llm + oh, 2)

    result["row_estimates"] = rows
    return _clamp_minimum_bid(result)


def _clamp_minimum_bid(out: dict[str, Any]) -> dict[str, Any]:
    """Ensure ``suggested_minimum_bid_rub`` is not below total / direct cost."""
    total = _parse_number(out.get("estimated_total_cost_rub"))
    direct = _parse_number(out.get("estimated_direct_cost_rub"))
    floor_cost = total if total is not None and total > 0 else direct
    bid = _parse_number(out.get("suggested_minimum_bid_rub"))
    if floor_cost is None or floor_cost <= 0 or bid is None:
        return out
    if bid + 0.5 < floor_cost:
        out["suggested_minimum_bid_rub"] = round(floor_cost, 2)
    return out
