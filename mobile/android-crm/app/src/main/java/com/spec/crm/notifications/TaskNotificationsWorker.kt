package com.spec.crm.notifications

import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.spec.crm.AppContainer
import com.spec.crm.MainActivity
import com.spec.crm.data.withTokenRefresh
import com.spec.crm.data.remote.dto.InboxNotificationDto
import com.spec.crm.navigation.NavExtras
import kotlinx.coroutines.flow.first

/**
 * Pulls unread inbox notifications and shows local Android notifications with optional task deep link.
 * Does **not** mark server items as read (inbox stays in sync with the web app).
 */
class TaskNotificationsWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        return try {
            TaskNotifications.ensureChannel(applicationContext)
            val container = AppContainer(applicationContext)
            val session = container.sessionRepository.session.first() ?: return Result.success()
            container.sessionRepository.applySessionToHolders()
            val api = container.sessionRepository.apiForSession(session)
            val response = container.sessionRepository.withTokenRefresh {
                api.notifications(
                    mapOf(
                        "limit" to "30",
                        "offset" to "0",
                        "unread_only" to "true",
                    ),
                )
            }
            showNewTaskNotifications(response.items)
            Result.success()
        } catch (e: Exception) {
            Log.e(TAG, "Failed to process task notifications", e)
            Result.retry()
        }
    }

    private fun showNewTaskNotifications(items: List<InboxNotificationDto>) {
        val manager = applicationContext.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val prefs = applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val seenIds = prefs.getStringSet(KEY_SEEN_IDS, emptySet()).orEmpty().toMutableSet()
        val sorted = items.sortedByDescending { it.createdAt }

        var changed = false
        for (item in sorted) {
            if (item.isRead || !isTaskEvent(item)) continue
            val stableId = item.id
            if (seenIds.contains(stableId)) continue

            val taskId = extractTaskId(item)
            val intent = Intent(applicationContext, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
                if (taskId != null) {
                    putExtra(NavExtras.EXTRA_OPEN_TASK_ID, taskId)
                }
            }
            val pendingIntent = PendingIntent.getActivity(
                applicationContext,
                stableId.hashCode(),
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
            val notif = NotificationCompat.Builder(applicationContext, TaskNotifications.channelId())
                .setSmallIcon(android.R.drawable.stat_notify_more)
                .setContentTitle(item.title.ifBlank { "SPEC CRM" })
                .setContentText(item.body.ifBlank { item.eventType })
                .setStyle(NotificationCompat.BigTextStyle().bigText(item.body))
                .setPriority(NotificationCompat.PRIORITY_DEFAULT)
                .setAutoCancel(true)
                .setContentIntent(pendingIntent)
                .setOnlyAlertOnce(false)
                .build()
            try {
                manager.notify(stableId.hashCode(), notif)
            } catch (e: SecurityException) {
                Log.w(TAG, "Notification permission is not granted", e)
                continue
            }
            seenIds.add(stableId)
            changed = true
        }

        if (changed) {
            val trimmed = seenIds.toList().takeLast(MAX_SEEN_IDS).toSet()
            prefs.edit().putStringSet(KEY_SEEN_IDS, trimmed).apply()
        }
    }

    private fun extractTaskId(item: InboxNotificationDto): String? {
        val raw = item.data["task_id"] ?: return null
        return raw.toString().trim().takeIf { it.isNotEmpty() }
    }

    private fun isTaskEvent(item: InboxNotificationDto): Boolean {
        val event = item.eventType.lowercase()
        val title = item.title.lowercase()
        val body = item.body.lowercase()
        return event.contains("task") ||
            title.contains("задач") ||
            title.contains("task") ||
            body.contains("задач") ||
            body.contains("task")
    }

    companion object {
        private const val TAG = "TaskNotificationsWorker"
        private const val PREFS_NAME = "crm_task_notifications"
        private const val KEY_SEEN_IDS = "seen_ids"
        private const val MAX_SEEN_IDS = 500
    }
}
