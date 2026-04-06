"""Session context messages and tool-result patches for AI assistant memory."""

from __future__ import annotations

from typing import Any

_MAX_SUMMARY = 4000
_MAX_SNIPPET = 1500
_MAX_DEADLINE = 120


def build_session_context_message(ctx: dict[str, Any] | None) -> str | None:
    """Build an extra system message from persisted session facts."""
    if not ctx:
        return None
    lines = [
        "Session memory (use for pronouns like «она», «эту задачу»; copy UUIDs into tool arguments):",
    ]
    if tid := ctx.get("last_task_id"):
        lines.append(f"- last_task_id: {tid}")
    if tt := ctx.get("last_task_title"):
        lines.append(f"- last_task_title: {tt}")
    if cid := ctx.get("last_client_id"):
        lines.append(f"- last_client_id: {cid}")
    if tend := ctx.get("last_tender_id"):
        lines.append(f"- last_tender_id: {tend}")
    if tend_t := ctx.get("last_tender_title"):
        lines.append(f"- last_tender_title: {tend_t}")
    if first_u := ctx.get("last_tender_search_first_url"):
        lines.append(
            "- last_tender_search_first_url (default for «добавь/импортируй этот тендер» without pasting a link): "
            f"{first_u}"
        )
    rows = ctx.get("last_tender_search_results")
    if isinstance(rows, list) and rows:
        lines.append(
            "- last_tender_search_results (numbered rows — use `url` in import_tender_from_url; "
            "«первый» = index 1):"
        )
        for r in rows[:40]:
            if not isinstance(r, dict):
                continue
            idx = r.get("index", "")
            u = str(r.get("url") or "")[:2000]
            tit = str(r.get("title") or "")[:200]
            lines.append(f"  [{idx}] {tit} → url: {u}")
    if len(lines) <= 1:
        return None
    return "\n".join(lines)


def extract_context_patch_from_tool(tool_name: str, result: object) -> dict[str, Any]:
    """Derive session-memory updates from a successful tool return value."""
    patch: dict[str, Any] = {}
    if tool_name == "search_tenders_on_web" and isinstance(result, list):
        rows: list[dict[str, Any]] = []
        urls: list[str] = []
        for row in result[:50]:
            if not isinstance(row, dict):
                continue
            u = str(row.get("url") or "").strip()
            if not u:
                continue
            tit = str(row.get("title") or "").strip()[:400]
            urls.append(u)
            entry: dict[str, Any] = {"index": len(rows) + 1, "url": u, "title": tit}
            summ = str(row.get("summary") or "").strip()
            if summ:
                entry["summary"] = summ[:_MAX_SUMMARY]
            snip = str(row.get("snippet") or "").strip()
            if snip:
                entry["snippet"] = snip[:_MAX_SNIPPET]
            sdu = row.get("submission_deadline_utc")
            if sdu is not None and str(sdu).strip():
                entry["submission_deadline_utc"] = str(sdu).strip()[:_MAX_DEADLINE]
            rows.append(entry)
        if urls:
            patch["last_tender_search_urls"] = urls
            patch["last_tender_search_results"] = rows
            patch["last_tender_search_first_url"] = urls[0]
        return patch

    if not isinstance(result, dict):
        return patch
    if result.get("ok") is False:
        return patch
    if tool_name == "bulk_create_tasks":
        created = result.get("created")
        if isinstance(created, list) and created:
            last = created[-1]
            if isinstance(last, dict) and last.get("id"):
                patch["last_task_id"] = str(last["id"])
                if last.get("title"):
                    patch["last_task_title"] = str(last["title"])
        return patch
    tid = result.get("id")
    if tid is None:
        return patch
    tid_str = str(tid)
    if tool_name == "create_task":
        patch["last_task_id"] = tid_str
        if result.get("title"):
            patch["last_task_title"] = str(result["title"])
    elif tool_name in ("update_task", "instantiate_template", "assign_task_to_user"):
        patch["last_task_id"] = tid_str
        if result.get("title"):
            patch["last_task_title"] = str(result["title"])
    elif tool_name == "create_client":
        patch["last_client_id"] = tid_str
    elif tool_name == "import_tender_from_url":
        patch["last_tender_id"] = tid_str
        if result.get("title"):
            patch["last_tender_title"] = str(result["title"])
    return patch
