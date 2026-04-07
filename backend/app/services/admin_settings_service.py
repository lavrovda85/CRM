"""Service for admin runtime settings (DB overrides + env defaults)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.system_setting import SystemSetting

SCHEDULER_KEY = "task_scheduler"


def _scheduler_defaults() -> dict[str, Any]:
    s = get_settings()
    return {
        "enabled": s.task_scheduler_enabled,
        "cron_minute": s.task_scheduler_cron_minute,
        "cron_hour": s.task_scheduler_cron_hour,
        "cron_day_of_month": s.task_scheduler_cron_day_of_month,
        "cron_month_of_year": s.task_scheduler_cron_month_of_year,
        "cron_day_of_week": s.task_scheduler_cron_day_of_week,
        "title": s.task_scheduler_title,
        "description": s.task_scheduler_description,
        "priority": s.task_scheduler_priority,
        "template_id": s.task_scheduler_template_id,
        "assigned_to": s.task_scheduler_assigned_to,
        "requested_by": s.task_scheduler_requested_by,
        "board_id": s.task_scheduler_board_id,
        "client_id": s.task_scheduler_client_id,
        "due_in_hours": s.task_scheduler_due_in_hours,
        "observer_ids": s.task_scheduler_observer_ids,
        "co_assignee_ids": s.task_scheduler_co_assignee_ids,
        "dedup_window_minutes": s.task_scheduler_dedup_window_minutes,
    }


async def get_scheduler_settings(db: AsyncSession) -> dict[str, Any]:
    """Get effective scheduler settings: env defaults overridden by DB values."""
    base = _scheduler_defaults()
    row = (
        await db.execute(
            select(SystemSetting).where(SystemSetting.key == SCHEDULER_KEY),
        )
    ).scalar_one_or_none()
    if not row or not isinstance(row.value, dict):
        return base
    return {**base, **row.value}


def _scheduler_rule_shape(defaults: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(raw.get("id") or uuid.uuid4()),
        "name": str(raw.get("name") or "Rule"),
        "order": int(raw.get("order", 0)),
        "enabled": bool(raw.get("enabled", defaults["enabled"])),
        "cron_minute": str(raw.get("cron_minute", defaults["cron_minute"])),
        "cron_hour": str(raw.get("cron_hour", defaults["cron_hour"])),
        "cron_day_of_month": str(raw.get("cron_day_of_month", defaults["cron_day_of_month"])),
        "cron_month_of_year": str(raw.get("cron_month_of_year", defaults["cron_month_of_year"])),
        "cron_day_of_week": str(raw.get("cron_day_of_week", defaults["cron_day_of_week"])),
        "title": str(raw.get("title", defaults["title"])),
        "description": raw.get("description", defaults["description"]),
        "priority": str(raw.get("priority", defaults["priority"])),
        "template_id": raw.get("template_id", defaults["template_id"]),
        "assigned_to": raw.get("assigned_to", defaults["assigned_to"]),
        "requested_by": raw.get("requested_by", defaults["requested_by"]),
        "board_id": raw.get("board_id", defaults["board_id"]),
        "client_id": raw.get("client_id", defaults["client_id"]),
        "due_in_hours": int(raw.get("due_in_hours", defaults["due_in_hours"])),
        "observer_ids": list(raw.get("observer_ids", defaults["observer_ids"]) or []),
        "co_assignee_ids": list(raw.get("co_assignee_ids", defaults["co_assignee_ids"]) or []),
        "dedup_window_minutes": int(raw.get("dedup_window_minutes", defaults["dedup_window_minutes"])),
    }


async def get_scheduler_rules(db: AsyncSession) -> list[dict[str, Any]]:
    """Get all scheduler rules from DB or synthesize default single rule."""
    defaults = _scheduler_defaults()
    row = (
        await db.execute(
            select(SystemSetting).where(SystemSetting.key == SCHEDULER_KEY),
        )
    ).scalar_one_or_none()
    if not row or not isinstance(row.value, dict):
        return [_scheduler_rule_shape(defaults, {"id": "default", "name": "Default", "order": 0, **defaults})]
    raw_rules = row.value.get("rules")
    if isinstance(raw_rules, list) and raw_rules:
        shaped = [_scheduler_rule_shape(defaults, r if isinstance(r, dict) else {}) for r in raw_rules]
        return sorted(shaped, key=lambda r: (int(r.get("order", 0)), str(r.get("name", ""))))
    merged = {**defaults, **row.value}
    return [_scheduler_rule_shape(defaults, {"id": "default", "name": "Default", "order": 0, **merged})]


async def _save_scheduler_rules(db: AsyncSession, rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    row = (
        await db.execute(
            select(SystemSetting).where(SystemSetting.key == SCHEDULER_KEY),
        )
    ).scalar_one_or_none()
    payload = {"rules": rules}
    if row is None:
        row = SystemSetting(key=SCHEDULER_KEY, value=payload)
        db.add(row)
    else:
        row.value = payload
    await db.flush()
    return rules


async def create_scheduler_rule(db: AsyncSession, data: dict[str, Any]) -> dict[str, Any]:
    """Create scheduler rule."""
    rules = await get_scheduler_rules(db)
    defaults = _scheduler_defaults()
    next_order = max((int(r.get("order", 0)) for r in rules), default=-1) + 1
    seed = {"id": str(uuid.uuid4()), "order": next_order, **data}
    rule = _scheduler_rule_shape(defaults, seed)
    rules.append(rule)
    await _save_scheduler_rules(db, sorted(rules, key=lambda r: int(r.get("order", 0))))
    return rule


async def update_scheduler_rule(db: AsyncSession, rule_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    """Patch scheduler rule by id."""
    rules = await get_scheduler_rules(db)
    defaults = _scheduler_defaults()
    out: dict[str, Any] | None = None
    next_rules: list[dict[str, Any]] = []
    for rule in rules:
        if str(rule.get("id")) == rule_id:
            merged = {**rule, **patch, "id": rule_id}
            out = _scheduler_rule_shape(defaults, merged)
            next_rules.append(out)
        else:
            next_rules.append(rule)
    if out is None:
        return None
    await _save_scheduler_rules(db, sorted(next_rules, key=lambda r: int(r.get("order", 0))))
    return out


async def delete_scheduler_rule(db: AsyncSession, rule_id: str) -> bool:
    """Delete scheduler rule by id."""
    rules = await get_scheduler_rules(db)
    next_rules = [r for r in rules if str(r.get("id")) != rule_id]
    if len(next_rules) == len(rules):
        return False
    normalized = [{**r, "order": idx} for idx, r in enumerate(next_rules)]
    await _save_scheduler_rules(db, normalized)
    return True


async def patch_scheduler_settings(db: AsyncSession, patch: dict[str, Any]) -> dict[str, Any]:
    """Patch the first (default) scheduler rule for backward compatibility."""
    rules = await get_scheduler_rules(db)
    if not rules:
        defaults = _scheduler_defaults()
        rules = [_scheduler_rule_shape(defaults, {"id": "default", "name": "Default", **defaults})]
    head = rules[0]
    merged = {**head, **patch}
    defaults = _scheduler_defaults()
    rules[0] = _scheduler_rule_shape(defaults, merged)
    await _save_scheduler_rules(db, rules)
    return rules[0]


def env_preview() -> dict[str, str]:
    """Return non-secret env settings for admin diagnostics."""
    s = get_settings()
    raw = s.model_dump()
    out: dict[str, str] = {}
    for key, value in raw.items():
        k = str(key).upper()
        if any(secret in k for secret in ("SECRET", "PASSWORD", "TOKEN", "API_KEY")):
            continue
        if key == "openai_api_key":
            continue
        if key == "github_ssh_key":
            continue
        if isinstance(value, list):
            out[k] = ", ".join(str(x) for x in value)
        else:
            out[k] = str(value)
    return dict(sorted(out.items(), key=lambda kv: kv[0]))

