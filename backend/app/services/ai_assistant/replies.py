"""User-facing reply text for AI assistant tool failures."""

from __future__ import annotations

from typing import Any

from app.services.ai_assistant.tender_import import is_russian


def format_tool_failure_reply(user_message: str, tool_result: dict[str, Any]) -> str:
    """Build deterministic user-facing reply from tool `{ok:false}` payload."""
    code = str(tool_result.get("code") or "TOOL_ERROR")
    msg = str(tool_result.get("message") or "").strip()
    details = tool_result.get("details") or {}

    if is_russian(user_message):
        if code == "CONFIRMATION_REQUIRED":
            return (
                "Команда может привести к удалению данных. Подтвердите действие, пожалуйста "
                "(напишите «подтверждаю» или «да» — я передам это в подтверждение команды)."
            )
        if code == "CONFIRM_REQUIRED":
            return (
                "Для этой операции нужно явное подтверждение. Напишите «подтверждаю» или «да», "
                "чтобы ассистент повторил вызов с тем же текстом в параметре подтверждения."
            )
        if code == "VALIDATION_ERROR":
            field = details.get("field")
            reason = details.get("reason")
            field_part = f" Поле: {field}." if field else ""
            if reason:
                return (
                    "Не удалось выполнить операцию из-за ошибки в данных (VALIDATION_ERROR)."
                    f"{field_part} Причина: {reason}"
                )
            return f"Не удалось выполнить операцию из-за ошибки в данных (VALIDATION_ERROR).{field_part}"
        if code == "NOT_FOUND":
            entity = details.get("entity") or "сущность"
            entity_id = details.get("entity_id")
            return f"Не удалось выполнить операцию: не найдено {entity} ({entity_id})."
        if code == "AUTHORIZATION_ERROR":
            required_role = details.get("required_role")
            action = details.get("action")
            return (
                "Не удалось выполнить операцию: недостаточно прав."
                f" Требуется роль: {required_role}."
                + (f" {action}." if action else "")
            )
        if msg:
            return f"Не удалось выполнить операцию ({code}): {msg}"
        return f"Не удалось выполнить операцию ({code})."

    if code == "VALIDATION_ERROR":
        return f"Operation failed (VALIDATION_ERROR): {details.get('reason') or msg}"
    return f"Operation failed ({code}): {msg}" if msg else f"Operation failed ({code})"
