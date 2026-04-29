package com.spec.crm.navigation

/**
 * Route names aligned with web paths for clarity.
 */
object Routes {
    const val DASHBOARD = "dashboard"
    const val TASKS = "tasks"
    const val TASK_CREATE = "task_create/{mode}"
    const val TASK_DETAIL = "task/{taskId}"
    const val TEMPLATES = "templates"
    const val CLIENTS = "clients"
    const val DEALS = "deals"
    const val TENDERS = "tenders"
    const val TENDER_DETAIL = "tender/{tenderId}"
    const val CHAT = "chat"
    const val ASSISTANT = "assistant"
    const val TIME = "time"
    const val WAREHOUSE = "warehouse"
    const val EQUIPMENT = "equipment"
    const val ANALYTICS = "analytics"
    const val NOTIFICATIONS = "notifications"
    const val PROFILE = "profile"
    const val SETTINGS = "settings"
    const val SETTINGS_USERS = "settings_users"
    const val SETTINGS_ADMIN = "settings_admin"
    const val SETTINGS_ROLES = "settings_roles"

    fun taskDetail(taskId: String) = "task/$taskId"

    /** mode: `office` or `field` */
    fun taskCreate(mode: String) = "task_create/$mode"
    fun tenderDetail(tenderId: String) = "tender/$tenderId"
}
