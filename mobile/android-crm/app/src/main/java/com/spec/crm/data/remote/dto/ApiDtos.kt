package com.spec.crm.data.remote.dto

import com.google.gson.annotations.SerializedName

/* ---------- Companies ---------- */

data class CompanyLoginOptionDto(val id: String, val name: String, val slug: String?)

data class CompanyResponseDto(
    val id: String,
    val name: String,
    val slug: String?,
    @SerializedName("is_active") val isActive: Boolean,
)

data class CompanyMembershipDto(
    val company: CompanyResponseDto,
    @SerializedName("is_default") val isDefault: Boolean,
)

/* ---------- Dashboard / analytics ---------- */

data class DashboardStatsDto(
    @SerializedName("total_tasks") val totalTasks: Int,
    @SerializedName("tasks_by_status") val tasksByStatus: Map<String, Double>?,
    @SerializedName("active_tasks") val activeTasks: Int,
    @SerializedName("completed_today") val completedToday: Int,
    @SerializedName("overdue_tasks") val overdueTasks: Int,
    @SerializedName("total_deals") val totalDeals: Int,
    @SerializedName("deals_amount") val dealsAmount: Double,
    @SerializedName("active_tenders") val activeTenders: Int,
    @SerializedName("low_stock_items") val lowStockItems: Int,
)

data class TenderAnalyticsDto(
    @SerializedName("total_tenders") val totalTenders: Int,
    @SerializedName("tenders_by_status") val tendersByStatus: Map<String, Double>?,
    @SerializedName("win_rate") val winRate: Double,
    @SerializedName("total_budget") val totalBudget: Double,
    @SerializedName("total_our_price") val totalOurPrice: Double,
)

data class WarehouseLowStockDto(
    val id: String,
    val name: String,
    val sku: String,
    val quantity: Double,
)

data class WarehouseAnalyticsDto(
    @SerializedName("total_items") val totalItems: Int,
    @SerializedName("low_stock_items") val lowStockItems: List<WarehouseLowStockDto>?,
)

/* ---------- Notifications ---------- */

data class InboxNotificationDto(
    val id: String? = null,
    @SerializedName("event_type") val eventType: String,
    val title: String,
    val body: String,
    @SerializedName("is_read") val isRead: Boolean,
    @SerializedName("created_at") val createdAt: String,
)

data class PaginatedNotificationsResponse(
    val items: List<InboxNotificationDto>,
    val total: Int,
    val offset: Int,
    val limit: Int,
)

/* ---------- Clients ---------- */

data class ClientDto(
    val id: String,
    val name: String,
    val phone: String?,
    val email: String?,
)

data class PaginatedClientsResponse(
    val items: List<ClientDto>,
    val total: Int,
    val offset: Int,
    val limit: Int,
)

/* ---------- Deals ---------- */

data class DealDto(
    val id: String,
    val title: String,
    @SerializedName("stage_id") val stageId: String,
    val amount: Double,
)

data class PaginatedDealsResponse(
    val items: List<DealDto>,
    val total: Int,
    val offset: Int,
    val limit: Int,
)

data class DealStageDto(
    val id: String,
    val name: String,
    val order: Int,
    val color: String? = null,
)

/* ---------- Tenders ---------- */

data class TenderListDto(
    val id: String,
    val title: String,
    val status: String,
    @SerializedName("customer_name") val customerName: String?,
    val deadline: String?,
    val budget: Double?,
)

data class PaginatedTendersResponse(
    val items: List<TenderListDto>,
    val total: Int,
    val offset: Int,
    val limit: Int,
)

data class TenderChecklistItemDto(
    val id: String,
    val title: String,
    @SerializedName("is_completed") val isCompleted: Boolean,
)

data class TenderChecklistDto(
    val id: String,
    val title: String,
    val items: List<TenderChecklistItemDto>?,
)

data class TenderDetailDto(
    val id: String,
    val title: String,
    val status: String,
    val description: String?,
    @SerializedName("customer_name") val customerName: String?,
    val budget: Double?,
    @SerializedName("our_price") val ourPrice: Double?,
    val deadline: String?,
    @SerializedName("allowed_next_statuses") val allowedNextStatuses: List<String>?,
    val tasks: List<TaskDto>?,
    val checklists: List<TenderChecklistDto>?,
)

/* ---------- Templates ---------- */

data class TemplateDto(val id: String, val name: String, val category: String?)
data class PaginatedTemplatesResponse(
    val items: List<TemplateDto>,
    val total: Int,
    val offset: Int,
    val limit: Int,
)

/* ---------- Time ---------- */

data class TimeEntryDto(
    val id: String,
    @SerializedName("task_id") val taskId: String?,
    @SerializedName("duration_minutes") val durationMinutes: Int,
    val notes: String?,
    @SerializedName("started_at") val startedAt: String?,
)

data class PaginatedTimeEntriesResponse(
    val items: List<TimeEntryDto>,
    val total: Int,
    val offset: Int,
    val limit: Int,
)

data class TimeSummaryDto(
    @SerializedName("total_minutes") val totalMinutes: Int,
    @SerializedName("total_hours") val totalHours: Double,
    @SerializedName("entries_count") val entriesCount: Int,
)

/* ---------- Warehouse / equipment ---------- */

data class WarehouseItemDto(
    val id: String,
    val name: String,
    val sku: String?,
    val quantity: Double?,
)

data class PaginatedWarehouseItemsResponse(
    val items: List<WarehouseItemDto>,
    val total: Int,
    val offset: Int,
    val limit: Int,
)

data class EquipmentDto(val id: String, val name: String, val status: String?)
data class PaginatedEquipmentResponse(
    val items: List<EquipmentDto>,
    val total: Int,
    val offset: Int,
    val limit: Int,
)

/* ---------- Chat ---------- */

data class ChatMessageDto(
    val id: String,
    val room: String?,
    @SerializedName("sender_name") val senderName: String?,
    val body: String,
    @SerializedName("created_at") val createdAt: String,
)

data class PaginatedChatMessagesResponse(
    val items: List<ChatMessageDto>,
    val total: Int,
    val offset: Int,
    val limit: Int,
)

data class ChatRoomDto(val id: String, val name: String, val code: String?)

data class SendChatMessageRequest(val room: String? = null, val body: String)

/* ---------- AI assistant ---------- */

data class AiAssistantStatusDto(val enabled: Boolean, val model: String)

data class AiMessageDto(
    val id: String,
    val role: String,
    val content: String,
    @SerializedName("created_at") val createdAt: String,
)

data class AiChatResponseDto(
    val reply: String,
    val messages: List<AiMessageDto>,
)

/* ---------- Task detail ---------- */

data class ChecklistItemDetailDto(
    val id: String,
    val title: String,
    @SerializedName("is_completed") val isCompleted: Boolean,
)

data class ChecklistDetailDto(
    val id: String,
    val title: String,
    val items: List<ChecklistItemDetailDto>?,
)

data class CommentDetailDto(
    val id: String,
    val body: String,
    @SerializedName("author_name") val authorName: String?,
    @SerializedName("created_at") val createdAt: String,
)

data class TaskDetailDto(
    val id: String,
    val title: String,
    val description: String?,
    val status: String,
    val priority: String,
    @SerializedName("due_date") val dueDate: String?,
    val checklists: List<ChecklistDetailDto>?,
    val comments: List<CommentDetailDto>?,
)

/* ---------- References / users / admin ---------- */

data class ReferenceItemDto(
    val id: String,
    val name: String,
    val code: String?,
)

data class ReferenceDto(
    val id: String?,
    val code: String,
    val name: String,
    val items: List<ReferenceItemDto>?,
)

data class UserListItemDto(
    val id: String,
    @SerializedName("full_name") val fullName: String,
    val email: String,
    val role: String,
    @SerializedName("is_active") val isActive: Boolean,
)

data class PaginatedUsersResponse(
    val items: List<UserListItemDto>,
    val total: Int,
    val offset: Int,
    val limit: Int,
)

data class UserDetailDto(
    val id: String,
    val email: String,
    @SerializedName("full_name") val fullName: String,
    val phone: String?,
    val role: String,
    @SerializedName("is_active") val isActive: Boolean,
)

data class AdminSchedulerDto(
    val enabled: Boolean,
    @SerializedName("cron_minute") val cronMinute: String?,
    val title: String?,
)

data class AdminSettingsEnvelopeDto(
    val scheduler: AdminSchedulerDto?,
    @SerializedName("env_preview") val envPreview: Map<String, String>?,
)

data class DeployStatusDto(
    @SerializedName("deploy_ui_enabled") val deployUiEnabled: Boolean,
    @SerializedName("agent_reachable") val agentReachable: Boolean?,
    @SerializedName("github_repo_configured") val githubRepoConfigured: Boolean,
)

data class PaginatedReferencesResponse(
    val items: List<ReferenceDto>,
    val total: Int,
    val offset: Int,
    val limit: Int,
)

/* ---------- Task transition ---------- */

data class TaskTransitionRequest(
    @SerializedName("to_status") val toStatus: String,
    val reason: String? = null,
)

/* ---------- Profile PATCH ---------- */

data class PatchProfileRequest(
    val phone: String? = null,
    @SerializedName("full_name") val fullName: String? = null,
)
