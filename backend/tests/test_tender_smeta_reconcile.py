"""Tests for indicative smeta JSON reconciliation after LLM output."""

from __future__ import annotations

from app.services.tender.tender_smeta_reconcile import reconcile_smeta_llm_output


def test_reconcile_duplicate_line_totals_scaled_to_direct_cost() -> None:
    """Same absurd line total on each row should scale down to match stated direct cost."""
    out = reconcile_smeta_llm_output(
        {
            "estimated_direct_cost_rub": 1_008_000,
            "suggested_overhead_rub": 100_000,
            "estimated_total_cost_rub": 1_108_000,
            "suggested_minimum_bid_rub": 950_000,
            "row_estimates": [
                {"name": "A", "line_total_rub": 804_000},
                {"name": "B", "line_total_rub": 804_000},
                {"name": "C", "line_total_rub": 804_000},
            ],
        }
    )
    rows = out["row_estimates"]
    assert len(rows) == 3
    for r in rows:
        assert r["line_total_rub"] == 336_000.0
    assert out["estimated_direct_cost_rub"] == 1_008_000.0
    assert out["estimated_total_cost_rub"] == 1_108_000.0
    assert out["suggested_minimum_bid_rub"] >= out["estimated_total_cost_rub"]


def test_reconcile_quantity_times_unit_sets_line_total() -> None:
    """Per-row q×unit overrides inconsistent line_total_rub."""
    out = reconcile_smeta_llm_output(
        {
            "estimated_direct_cost_rub": 999_999,
            "suggested_overhead_rub": 0,
            "row_estimates": [
                {"name": "A", "quantity": 2, "unit_cost_assumption_rub": 1500, "line_total_rub": 1},
                {"name": "B", "quantity": 1, "unit_cost_assumption_rub": 500, "line_total_rub": 1},
            ],
        }
    )
    assert out["row_estimates"][0]["line_total_rub"] == 3000.0
    assert out["row_estimates"][1]["line_total_rub"] == 500.0
    assert out["estimated_direct_cost_rub"] == 3500.0


def test_clamp_minimum_bid_not_below_total() -> None:
    out = reconcile_smeta_llm_output(
        {
            "estimated_direct_cost_rub": 100_000,
            "suggested_overhead_rub": 10_000,
            "estimated_total_cost_rub": 110_000,
            "suggested_minimum_bid_rub": 50_000,
            "row_estimates": [],
        }
    )
    assert out["suggested_minimum_bid_rub"] == 110_000.0
