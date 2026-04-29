package com.spec.crm.ui.shell

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.activity.ComponentActivity
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.spec.crm.data.CrmRepository
import com.spec.crm.data.CrmSession
import com.spec.crm.data.SessionRepository
import com.spec.crm.data.remote.dto.CompanyMembershipDto
import com.spec.crm.navigation.NavExtras
import com.spec.crm.navigation.Routes
import com.spec.crm.notifications.TaskNotifications
import com.spec.crm.ui.login.LoginScreen
import com.spec.crm.ui.login.LoginViewModel
import com.spec.crm.ui.screens.AdminScreen
import com.spec.crm.ui.screens.AnalyticsScreen
import com.spec.crm.ui.screens.AssistantScreen
import com.spec.crm.ui.screens.ChatScreen
import com.spec.crm.ui.screens.ClientsScreen
import com.spec.crm.ui.screens.DashboardScreen
import com.spec.crm.ui.screens.DealsScreen
import com.spec.crm.ui.screens.EquipmentScreen
import com.spec.crm.ui.screens.NotificationsScreen
import com.spec.crm.ui.screens.ProfileScreen
import com.spec.crm.ui.screens.RolesMatrixScreen
import com.spec.crm.ui.screens.SettingsReferencesScreen
import com.spec.crm.ui.screens.TemplatesScreen
import com.spec.crm.ui.screens.TenderDetailScreen
import com.spec.crm.ui.screens.TendersListScreen
import com.spec.crm.ui.screens.TimeScreen
import com.spec.crm.ui.screens.UsersScreen
import com.spec.crm.ui.screens.WarehouseScreen
import com.spec.crm.ui.tasks.TaskCreateScreen
import com.spec.crm.ui.tasks.TaskDetailScreen
import com.spec.crm.ui.tasks.TasksListScreen
import com.spec.crm.ui.tasks.TasksViewModel
import com.spec.crm.ui.theme.SpecCrmTheme
import kotlinx.coroutines.launch

private data class DrawerItem(val route: String, val label: String)

private val MAIN_DRAWER = listOf(
    DrawerItem(Routes.DASHBOARD, "Главная"),
    DrawerItem(Routes.TASKS, "Задачи"),
    DrawerItem(Routes.TEMPLATES, "Шаблоны"),
    DrawerItem(Routes.CLIENTS, "Клиенты"),
    DrawerItem(Routes.DEALS, "Сделки"),
    DrawerItem(Routes.TENDERS, "Тендеры"),
    DrawerItem(Routes.CHAT, "Чат"),
    DrawerItem(Routes.ASSISTANT, "AI"),
    DrawerItem(Routes.TIME, "Учёт времени"),
    DrawerItem(Routes.WAREHOUSE, "Склад"),
    DrawerItem(Routes.EQUIPMENT, "Оборудование"),
    DrawerItem(Routes.ANALYTICS, "Аналитика"),
    DrawerItem(Routes.NOTIFICATIONS, "Уведомления"),
    DrawerItem(Routes.PROFILE, "Профиль"),
)

private val BOTTOM_DRAWER = listOf(
    DrawerItem(Routes.SETTINGS, "Настройки"),
    DrawerItem(Routes.SETTINGS_USERS, "Пользователи"),
    DrawerItem(Routes.SETTINGS_ROLES, "Роли"),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CrmRootApp(
    sessionRepository: SessionRepository,
    crmRepository: CrmRepository,
    loginViewModel: LoginViewModel,
    tasksViewModel: TasksViewModel,
    defaultApiBase: String,
) {
    SpecCrmTheme {
        val context = LocalContext.current
        var session by remember { mutableStateOf<CrmSession?>(null) }
        var hydrated by remember { mutableStateOf(false) }

        LaunchedEffect(Unit) {
            sessionRepository.session.collect { next ->
                if (next != null) {
                    sessionRepository.applyFromSession(next)
                } else {
                    sessionRepository.clearApiHolders()
                }
                session = next
                hydrated = true
            }
        }

        LaunchedEffect(session?.accessToken) {
            if (session != null) {
                TaskNotifications.schedule(context)
            } else {
                TaskNotifications.cancel(context)
            }
        }

        when {
            !hydrated -> {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            }
            session == null -> LoginScreen(loginViewModel, defaultApiBase)
            else -> LoggedInShell(
                session = session!!,
                sessionRepository = sessionRepository,
                crmRepository = crmRepository,
                tasksViewModel = tasksViewModel,
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun LoggedInShell(
    session: CrmSession,
    sessionRepository: SessionRepository,
    crmRepository: CrmRepository,
    tasksViewModel: TasksViewModel,
) {
    val nav = rememberNavController()
    val drawer = rememberDrawerState(initialValue = DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    val navBackStack by nav.currentBackStackEntryAsState()
    val destRoute = navBackStack?.destination?.route ?: Routes.DASHBOARD
    val currentRoute = destRoute

    var companies by remember { mutableStateOf<List<CompanyMembershipDto>>(emptyList()) }
    LaunchedEffect(Unit) {
        try {
            companies = crmRepository.withApi { it.companiesMine() }
        } catch (_: Exception) {
            companies = emptyList()
        }
    }

    val activeCompany = companies.find { it.company.id == session.companyId }?.company
    val fieldWorkBoardId = activeCompany?.fieldWorkBoardId

    val activity = LocalContext.current as? ComponentActivity
    LaunchedEffect(activity?.intent, session.companyId) {
        val act = activity ?: return@LaunchedEffect
        val tid = act.intent.getStringExtra(NavExtras.EXTRA_OPEN_TASK_ID)?.trim().orEmpty()
        if (tid.isNotEmpty()) {
            nav.navigate(Routes.taskDetail(tid)) { launchSingleTop = true }
            act.intent.removeExtra(NavExtras.EXTRA_OPEN_TASK_ID)
        }
    }

    val title = routeTitle(currentRoute)

    ModalNavigationDrawer(
        drawerState = drawer,
        drawerContent = {
            ModalDrawerSheet {
                Text(
                    "SPEC CRM",
                    modifier = Modifier.padding(16.dp),
                    style = MaterialTheme.typography.titleMedium,
                )
                Text(
                    session.user.fullName,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                    style = MaterialTheme.typography.bodySmall,
                )
                if (companies.size > 1) {
                    Text("Компания", modifier = Modifier.padding(16.dp, 8.dp, 16.dp, 0.dp), style = MaterialTheme.typography.labelMedium)
                    companies.forEach { m ->
                        val sel = m.company.id == session.companyId
                        NavigationDrawerItem(
                            label = { Text(m.company.name + if (sel) " *" else "") },
                            selected = sel,
                            onClick = {
                                scope.launch {
                                    sessionRepository.switchCompany(m.company.id)
                                    drawer.close()
                                }
                            },
                        )
                    }
                }
                MAIN_DRAWER.forEach { item ->
                    NavigationDrawerItem(
                        label = { Text(item.label) },
                        selected = when (item.route) {
                            Routes.TASKS -> destRoute == Routes.TASKS ||
                                destRoute.startsWith("task/") ||
                                destRoute.startsWith("task_create/")
                            Routes.TENDERS -> destRoute == Routes.TENDERS || destRoute == Routes.TENDER_DETAIL
                            else -> destRoute == item.route || (item.route != Routes.DASHBOARD && destRoute.startsWith(item.route))
                        },
                        onClick = {
                            scope.launch {
                                drawer.close()
                                nav.navigate(item.route) {
                                    popUpTo(nav.graph.findStartDestination().id) { saveState = true }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            }
                        },
                    )
                }
                BOTTOM_DRAWER.forEach { item ->
                    NavigationDrawerItem(
                        label = { Text(item.label) },
                        selected = currentRoute == item.route,
                        onClick = {
                            scope.launch {
                                drawer.close()
                                nav.navigate(item.route) {
                                    launchSingleTop = true
                                }
                            }
                        },
                    )
                }
                if (session.user.role == "admin") {
                    NavigationDrawerItem(
                        label = { Text("Админка") },
                        selected = currentRoute == Routes.SETTINGS_ADMIN,
                        onClick = {
                            scope.launch {
                                drawer.close()
                                nav.navigate(Routes.SETTINGS_ADMIN) { launchSingleTop = true }
                            }
                        },
                    )
                }
                NavigationDrawerItem(
                    label = { Text("Выйти") },
                    selected = false,
                    onClick = {
                        scope.launch {
                            drawer.close()
                            sessionRepository.logout()
                        }
                    },
                )
            }
        },
    ) {
        Scaffold(
            modifier = Modifier.fillMaxSize(),
            topBar = {
                TopAppBar(
                    title = { Text(title) },
                    navigationIcon = {
                        IconButton(onClick = { scope.launch { drawer.open() } }) {
                            Icon(Icons.Default.Menu, contentDescription = "Меню")
                        }
                    },
                )
            },
        ) { padding ->
            NavHost(
                navController = nav,
                startDestination = Routes.DASHBOARD,
                modifier = Modifier.padding(padding),
            ) {
                composable(Routes.DASHBOARD) { DashboardScreen(crmRepository) }
                composable(Routes.TASKS) {
                    TasksListScreen(
                        tasksViewModel,
                        companyIdKey = session.companyId,
                        currentUserId = session.user.id,
                        fieldWorkBoardId = fieldWorkBoardId,
                        onTaskClick = { id -> nav.navigate(Routes.taskDetail(id)) },
                        onCreateTask = { isField ->
                            nav.navigate(Routes.taskCreate(if (isField) "field" else "office"))
                        },
                    )
                }
                composable(
                    Routes.TASK_CREATE,
                    arguments = listOf(navArgument("mode") { type = NavType.StringType }),
                ) { entry ->
                    val mode = entry.arguments?.getString("mode") ?: "office"
                    val isField = mode == "field"
                    TaskCreateScreen(
                        repo = crmRepository,
                        isFieldWork = isField,
                        fieldWorkBoardId = fieldWorkBoardId,
                        defaultFieldTemplateId = activeCompany?.defaultFieldTaskTemplateId,
                        fieldTemplateFilter = activeCompany?.fieldWorkTemplateIds,
                        onCreated = { id ->
                            nav.navigate(Routes.taskDetail(id)) {
                                popUpTo(Routes.TASKS) { inclusive = false }
                            }
                        },
                        onBack = { nav.popBackStack() },
                    )
                }
                composable(
                    Routes.TASK_DETAIL,
                    arguments = listOf(navArgument("taskId") { type = NavType.StringType }),
                ) { entry ->
                    val id = entry.arguments?.getString("taskId") ?: return@composable
                    TaskDetailScreen(
                        taskId = id,
                        crmRepository = crmRepository,
                        fieldWorkBoardId = fieldWorkBoardId,
                        onBack = { nav.popBackStack() },
                    )
                }
                composable(Routes.TEMPLATES) { TemplatesScreen(crmRepository) }
                composable(Routes.CLIENTS) { ClientsScreen(crmRepository) }
                composable(Routes.DEALS) { DealsScreen(crmRepository) }
                composable(Routes.TENDERS) {
                    TendersListScreen(crmRepository) { tid -> nav.navigate(Routes.tenderDetail(tid)) }
                }
                composable(
                    Routes.TENDER_DETAIL,
                    arguments = listOf(navArgument("tenderId") { type = NavType.StringType }),
                ) { entry ->
                    val id = entry.arguments?.getString("tenderId") ?: return@composable
                    TenderDetailScreen(crmRepository, id) { nav.popBackStack() }
                }
                composable(Routes.CHAT) { ChatScreen(crmRepository) }
                composable(Routes.ASSISTANT) { AssistantScreen(crmRepository) }
                composable(Routes.TIME) { TimeScreen(crmRepository) }
                composable(Routes.WAREHOUSE) { WarehouseScreen(crmRepository) }
                composable(Routes.EQUIPMENT) { EquipmentScreen(crmRepository) }
                composable(Routes.ANALYTICS) { AnalyticsScreen(crmRepository) }
                composable(Routes.NOTIFICATIONS) {
                    NotificationsScreen(crmRepository) { taskId ->
                        nav.navigate(Routes.taskDetail(taskId)) { launchSingleTop = true }
                    }
                }
                composable(Routes.PROFILE) { ProfileScreen(crmRepository) }
                composable(Routes.SETTINGS) { SettingsReferencesScreen(crmRepository) }
                composable(Routes.SETTINGS_USERS) { UsersScreen(crmRepository) }
                composable(Routes.SETTINGS_ADMIN) { AdminScreen(crmRepository) }
                composable(Routes.SETTINGS_ROLES) { RolesMatrixScreen() }
            }
        }
    }
}

private fun routeTitle(route: String?): String = when (route?.substringBefore("/")) {
    Routes.DASHBOARD, null -> "Главная"
    Routes.TASKS -> "Задачи"
    "task_create" -> "Новая задача"
    "task" -> "Задача"
    Routes.TEMPLATES -> "Шаблоны"
    Routes.CLIENTS -> "Клиенты"
    Routes.DEALS -> "Сделки"
    Routes.TENDERS -> "Тендеры"
    "tender" -> "Тендер"
    Routes.CHAT -> "Чат"
    Routes.ASSISTANT -> "AI"
    Routes.TIME -> "Учёт времени"
    Routes.WAREHOUSE -> "Склад"
    Routes.EQUIPMENT -> "Оборудование"
    Routes.ANALYTICS -> "Аналитика"
    Routes.NOTIFICATIONS -> "Уведомления"
    Routes.PROFILE -> "Профиль"
    Routes.SETTINGS -> "Настройки"
    Routes.SETTINGS_USERS -> "Пользователи"
    Routes.SETTINGS_ADMIN -> "Админка"
    Routes.SETTINGS_ROLES -> "Роли"
    else -> "SPEC CRM"
}
