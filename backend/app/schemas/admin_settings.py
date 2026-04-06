"""Schemas for admin runtime settings."""

from pydantic import BaseModel, ConfigDict, Field


class SchedulerSettingsResponse(BaseModel):
    """Scheduler settings exposed to admin UI."""

    model_config = ConfigDict(from_attributes=True)

    enabled: bool = False
    cron_minute: str = "0"
    cron_hour: str = "9"
    cron_day_of_month: str = "*"
    cron_month_of_year: str = "*"
    cron_day_of_week: str = "1-5"
    title: str = "Daily control task"
    description: str | None = None
    priority: str = "medium"
    template_id: str | None = None
    assigned_to: str | None = None
    requested_by: str | None = None
    board_id: str | None = None
    client_id: str | None = None
    due_in_hours: int = 24
    observer_ids: list[str] = Field(default_factory=list)
    co_assignee_ids: list[str] = Field(default_factory=list)
    dedup_window_minutes: int = 180


class SchedulerRuleResponse(SchedulerSettingsResponse):
    """Single scheduler rule item."""

    id: str
    name: str = "Rule"
    order: int = 0


class SchedulerRuleCreate(BaseModel):
    """Create payload for scheduler rule."""

    name: str = "Rule"
    order: int | None = None
    enabled: bool = False
    cron_minute: str = "0"
    cron_hour: str = "9"
    cron_day_of_month: str = "*"
    cron_month_of_year: str = "*"
    cron_day_of_week: str = "1-5"
    title: str = "Daily control task"
    description: str | None = None
    priority: str = "medium"
    template_id: str | None = None
    assigned_to: str | None = None
    requested_by: str | None = None
    board_id: str | None = None
    client_id: str | None = None
    due_in_hours: int = Field(default=24, ge=0, le=24 * 31)
    observer_ids: list[str] = Field(default_factory=list)
    co_assignee_ids: list[str] = Field(default_factory=list)
    dedup_window_minutes: int = Field(default=180, ge=1, le=24 * 60)


class SchedulerSettingsUpdate(BaseModel):
    """Patch payload for scheduler settings."""

    name: str | None = None
    order: int | None = None
    enabled: bool | None = None
    cron_minute: str | None = None
    cron_hour: str | None = None
    cron_day_of_month: str | None = None
    cron_month_of_year: str | None = None
    cron_day_of_week: str | None = None
    title: str | None = None
    description: str | None = None
    priority: str | None = None
    template_id: str | None = None
    assigned_to: str | None = None
    requested_by: str | None = None
    board_id: str | None = None
    client_id: str | None = None
    due_in_hours: int | None = Field(default=None, ge=0, le=24 * 31)
    observer_ids: list[str] | None = None
    co_assignee_ids: list[str] | None = None
    dedup_window_minutes: int | None = Field(default=None, ge=1, le=24 * 60)


class AdminSettingsEnvelope(BaseModel):
    """Composite response for admin settings page."""

    scheduler: SchedulerSettingsResponse
    scheduler_rules: list[SchedulerRuleResponse] = Field(default_factory=list)
    env_preview: dict[str, str]

