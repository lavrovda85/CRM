package com.spec.crm.data.remote

import com.google.gson.JsonObject
import com.spec.crm.data.remote.dto.AdminSettingsEnvelopeDto
import com.spec.crm.data.remote.dto.AiAssistantStatusDto
import com.spec.crm.data.remote.dto.AiChatResponseDto
import com.spec.crm.data.remote.dto.AiMessageDto
import com.spec.crm.data.remote.dto.ChatMessageDto
import com.spec.crm.data.remote.dto.ChatRoomDto
import com.spec.crm.data.remote.dto.ClientDto
import com.spec.crm.data.remote.dto.CompanyLoginOptionDto
import com.spec.crm.data.remote.dto.CompanyMembershipDto
import com.spec.crm.data.remote.dto.DashboardStatsDto
import com.spec.crm.data.remote.dto.DealStageDto
import com.spec.crm.data.remote.dto.DeployStatusDto
import com.spec.crm.data.remote.dto.InboxNotificationDto
import com.spec.crm.data.remote.dto.LoginRequest
import com.spec.crm.data.remote.dto.LoginResponse
import com.spec.crm.data.remote.dto.PaginatedChatMessagesResponse
import com.spec.crm.data.remote.dto.PaginatedClientsResponse
import com.spec.crm.data.remote.dto.PaginatedDealsResponse
import com.spec.crm.data.remote.dto.PaginatedEquipmentResponse
import com.spec.crm.data.remote.dto.PaginatedNotificationsResponse
import com.spec.crm.data.remote.dto.PaginatedReferencesResponse
import com.spec.crm.data.remote.dto.PaginatedTasksResponse
import com.spec.crm.data.remote.dto.PaginatedTemplatesResponse
import com.spec.crm.data.remote.dto.PaginatedTendersResponse
import com.spec.crm.data.remote.dto.PaginatedTimeEntriesResponse
import com.spec.crm.data.remote.dto.PaginatedUsersResponse
import com.spec.crm.data.remote.dto.PaginatedWarehouseItemsResponse
import com.spec.crm.data.remote.dto.PatchProfileRequest
import com.spec.crm.data.remote.dto.RefreshRequest
import com.spec.crm.data.remote.dto.RefreshResponse
import com.spec.crm.data.remote.dto.ReferenceDto
import com.spec.crm.data.remote.dto.SendChatMessageRequest
import com.spec.crm.data.remote.dto.TaskDetailDto
import com.spec.crm.data.remote.dto.TaskDto
import com.spec.crm.data.remote.dto.TaskTransitionRequest
import com.spec.crm.data.remote.dto.TenderAnalyticsDto
import com.spec.crm.data.remote.dto.TenderDetailDto
import com.spec.crm.data.remote.dto.TimeSummaryDto
import com.spec.crm.data.remote.dto.UserDetailDto
import com.spec.crm.data.remote.dto.UserDto
import com.spec.crm.data.remote.dto.WarehouseAnalyticsDto
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.QueryMap

/**
 * SPEC CRM REST API under base URL `.../api/v1/`.
 */
@Suppress("TooManyFunctions")
interface CrmApi {

    @POST("auth/login")
    suspend fun login(@Body body: LoginRequest): LoginResponse

    @POST("auth/refresh")
    suspend fun refresh(@Body body: RefreshRequest): RefreshResponse

    @GET("auth/me")
    suspend fun me(): UserDto

    @GET("companies/login-options")
    suspend fun loginOptions(): List<CompanyLoginOptionDto>

    @GET("companies/mine")
    suspend fun companiesMine(): List<CompanyMembershipDto>

    @GET("analytics/dashboard")
    suspend fun dashboard(): DashboardStatsDto

    @GET("analytics/tenders")
    suspend fun analyticsTenders(): TenderAnalyticsDto

    @GET("analytics/warehouse")
    suspend fun analyticsWarehouse(): WarehouseAnalyticsDto

    @GET("notifications")
    suspend fun notifications(@QueryMap queries: Map<String, String>): PaginatedNotificationsResponse

    @PATCH("notifications/{id}/read")
    suspend fun markNotificationRead(@Path("id") id: String): InboxNotificationDto

    @GET("tasks")
    suspend fun tasks(@QueryMap queries: Map<String, String>): PaginatedTasksResponse

    @GET("tasks/{id}")
    suspend fun taskDetail(@Path("id") id: String): TaskDetailDto

    @POST("tasks/{id}/transition")
    suspend fun taskTransition(
        @Path("id") id: String,
        @Body body: TaskTransitionRequest,
    ): TaskDto

    @GET("clients")
    suspend fun clients(@QueryMap queries: Map<String, String>): PaginatedClientsResponse

    @POST("clients")
    suspend fun createClient(@Body body: JsonObject): ClientDto

    @GET("deals")
    suspend fun deals(@QueryMap queries: Map<String, String>): PaginatedDealsResponse

    @GET("deals/stages")
    suspend fun dealStages(): List<DealStageDto>

    @GET("tenders")
    suspend fun tenders(@QueryMap queries: Map<String, String>): PaginatedTendersResponse

    @GET("tenders/{id}")
    suspend fun tenderDetail(@Path("id") id: String): TenderDetailDto

    @GET("templates")
    suspend fun templates(@QueryMap queries: Map<String, String>): PaginatedTemplatesResponse

    @GET("chat/messages")
    suspend fun chatMessages(@QueryMap queries: Map<String, String>): PaginatedChatMessagesResponse

    @POST("chat/messages")
    suspend fun sendChatMessage(@Body body: SendChatMessageRequest): ChatMessageDto

    @GET("chat/rooms")
    suspend fun chatRooms(): List<ChatRoomDto>

    @GET("ai-assistant/status")
    suspend fun aiStatus(): AiAssistantStatusDto

    @GET("ai-assistant/messages")
    suspend fun aiMessages(): List<AiMessageDto>

    @POST("ai-assistant/chat")
    suspend fun aiChat(@Body body: JsonObject): AiChatResponseDto

    @GET("time/entries")
    suspend fun timeEntries(@QueryMap queries: Map<String, String>): PaginatedTimeEntriesResponse

    @GET("time/summary")
    suspend fun timeSummary(@QueryMap queries: Map<String, String>): TimeSummaryDto

    @GET("warehouse/items")
    suspend fun warehouseItems(@QueryMap queries: Map<String, String>): PaginatedWarehouseItemsResponse

    @GET("equipment")
    suspend fun equipment(@QueryMap queries: Map<String, String>): PaginatedEquipmentResponse

    @GET("references")
    suspend fun references(@QueryMap queries: Map<String, String>): PaginatedReferencesResponse

    @GET("references/{code}")
    suspend fun reference(@Path("code") code: String): ReferenceDto

    @GET("users/me")
    suspend fun usersMe(): UserDetailDto

    @PATCH("users/me")
    suspend fun patchMe(@Body body: PatchProfileRequest): UserDetailDto

    @GET("users")
    suspend fun users(@QueryMap queries: Map<String, String>): PaginatedUsersResponse

    @GET("admin/settings")
    suspend fun adminSettings(): AdminSettingsEnvelopeDto

    @GET("admin/deploy/status")
    suspend fun deployStatus(): DeployStatusDto
}
