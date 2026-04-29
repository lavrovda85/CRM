package com.spec.crm.data.remote.dto

import com.google.gson.annotations.SerializedName

data class LoginRequest(
    val email: String,
    val password: String,
    @SerializedName("company_id") val companyId: String? = null,
)

data class LoginResponse(
    val tokens: TokenBundle,
    val user: UserDto,
    @SerializedName("active_company_id") val activeCompanyId: String,
)

data class TokenBundle(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("refresh_token") val refreshToken: String,
    @SerializedName("token_type") val tokenType: String = "Bearer",
    @SerializedName("expires_in") val expiresIn: Int = 0,
)

data class RefreshRequest(
    @SerializedName("refresh_token") val refreshToken: String,
)

data class RefreshResponse(
    val tokens: TokenBundle,
    val user: UserDto,
)

data class UserDto(
    val id: String,
    val email: String,
    @SerializedName("full_name") val fullName: String,
    val role: String,
    @SerializedName("is_active") val isActive: Boolean,
)

data class PaginatedTasksResponse(
    val items: List<TaskDto>,
    val total: Int,
    val offset: Int,
    val limit: Int,
)

/**
 * Subset of backend task fields used in the mobile list.
 */
data class TaskDto(
    val id: String,
    val title: String,
    val description: String?,
    val status: String,
    val priority: String,
    @SerializedName("due_date") val dueDate: String?,
    @SerializedName("board_id") val boardId: String? = null,
    @SerializedName("template_id") val templateId: String? = null,
    val assignee: UserSummaryDto? = null,
    val template: TemplateSummaryDto? = null,
)
