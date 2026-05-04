package com.spec.crm

import android.app.Application
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.ProcessLifecycleOwner
import com.spec.crm.notifications.TaskNotifications
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/**
 * Holds the app-level [AppContainer] (network, session).
 */
class CrmApplication : Application() {
    lateinit var container: AppContainer
        private set

    private val appIoScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
        TaskNotifications.ensureChannel(this)
        ProcessLifecycleOwner.get().lifecycle.addObserver(
            object : DefaultLifecycleObserver {
                override fun onStart(owner: LifecycleOwner) {
                    appIoScope.launch {
                        try {
                            container.sessionRepository.refreshIfAccessTokenExpiringSoon()
                        } catch (_: Exception) {
                            /* offline or transient */
                        }
                    }
                }
            },
        )
    }
}
