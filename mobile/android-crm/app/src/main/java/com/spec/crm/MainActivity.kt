package com.spec.crm

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.remember
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.spec.crm.ui.login.LoginViewModel
import com.spec.crm.ui.shell.CrmRootApp
import com.spec.crm.ui.tasks.TasksViewModel

/**
 * Entry point: login or full CRM shell (same sections as the web app).
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        requestNotificationPermissionIfNeeded()
        val app = application as CrmApplication

        setContent {
            val loginVm = remember {
                LoginViewModel(app.container.sessionRepository)
            }
            val tasksVm = remember {
                TasksViewModel(app.container.crmRepository)
            }
            CrmRootApp(
                sessionRepository = app.container.sessionRepository,
                crmRepository = app.container.crmRepository,
                loginViewModel = loginVm,
                tasksViewModel = tasksVm,
                defaultApiBase = DEFAULT_DEV_API_BASE,
            )
        }
    }

    companion object {
        const val DEFAULT_DEV_API_BASE: String = "http://84.22.153.24:9000"
        private const val REQ_POST_NOTIFICATIONS = 1001
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        val granted = ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.POST_NOTIFICATIONS,
        ) == PackageManager.PERMISSION_GRANTED
        if (!granted) {
            ActivityCompat.requestPermissions(
                this,
                arrayOf(Manifest.permission.POST_NOTIFICATIONS),
                REQ_POST_NOTIFICATIONS,
            )
        }
    }
}
