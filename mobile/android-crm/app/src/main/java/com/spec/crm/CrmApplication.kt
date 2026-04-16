package com.spec.crm

import android.app.Application
import com.spec.crm.notifications.TaskNotifications

/**
 * Holds the app-level [AppContainer] (network, session).
 */
class CrmApplication : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
        TaskNotifications.ensureChannel(this)
    }
}
