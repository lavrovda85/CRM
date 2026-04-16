package com.spec.crm.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.google.gson.JsonObject
import com.spec.crm.data.CrmRepository
import com.spec.crm.data.remote.dto.ChatMessageDto
import com.spec.crm.data.remote.dto.PatchProfileRequest
import com.spec.crm.data.remote.dto.SendChatMessageRequest
import kotlinx.coroutines.launch

@Composable
fun ScreenLoading() {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        CircularProgressIndicator()
    }
}

@Composable
fun DashboardScreen(repo: CrmRepository) {
    var loading by remember { mutableStateOf(true) }
    var err by remember { mutableStateOf<String?>(null) }
    var stats by remember { mutableStateOf<com.spec.crm.data.remote.dto.DashboardStatsDto?>(null) }
    LaunchedEffect(Unit) {
        loading = true
        try {
            stats = repo.withApi { it.dashboard() }
        } catch (e: Exception) {
            err = e.message
        } finally {
            loading = false
        }
    }
    when {
        loading -> ScreenLoading()
        err != null -> Text(err!!, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(16.dp))
        stats != null -> {
            val s = stats!!
            LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                item {
                    Text("Главная", style = MaterialTheme.typography.headlineSmall)
                }
                item { StatCard("Всего задач", s.totalTasks.toString()) }
                item { StatCard("Активных", s.activeTasks.toString()) }
                item { StatCard("Просрочено", s.overdueTasks.toString()) }
                item { StatCard("Сделок", s.totalDeals.toString()) }
                item { StatCard("Сумма сделок", s.dealsAmount.toString()) }
                item { StatCard("Тендеров (активных)", s.activeTenders.toString()) }
                item { StatCard("Мало на складе", s.lowStockItems.toString()) }
            }
        }
    }
}

@Composable
private fun StatCard(label: String, value: String) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(value, style = MaterialTheme.typography.headlineSmall)
        }
    }
}

@Composable
fun ClientsScreen(repo: CrmRepository) {
    var loading by remember { mutableStateOf(true) }
    var err by remember { mutableStateOf<String?>(null) }
    var q by remember { mutableStateOf("") }
    var items by remember { mutableStateOf<List<com.spec.crm.data.remote.dto.ClientDto>>(emptyList()) }
    val scope = rememberCoroutineScope()
    LaunchedEffect(Unit) {
        loading = true
        try {
            items = repo.withApi { it.clients(mapOf("limit" to "100")).items }
        } catch (e: Exception) {
            err = e.message
        } finally {
            loading = false
        }
    }
    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Text("Клиенты", style = MaterialTheme.typography.headlineSmall)
        OutlinedTextField(q, { q = it }, label = { Text("Поиск") }, modifier = Modifier.fillMaxWidth())
        Button(
            onClick = {
                scope.launch {
                    loading = true
                    try {
                        val map = mutableMapOf("limit" to "100")
                        if (q.isNotBlank()) map["search"] = q.trim()
                        items = repo.withApi { it.clients(map).items }
                    } catch (e: Exception) {
                        err = e.message
                    } finally {
                        loading = false
                    }
                }
            },
 modifier = Modifier.padding(top = 8.dp),
        ) { Text("Найти") }
        when {
            loading -> ScreenLoading()
            err != null -> Text(err!!, color = MaterialTheme.colorScheme.error)
            else -> LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(items) { c ->
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(12.dp)) {
                            Text(c.name, style = MaterialTheme.typography.titleMedium)
                            Text(listOfNotNull(c.phone, c.email).joinToString(" · "), style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun DealsScreen(repo: CrmRepository) {
    var loading by remember { mutableStateOf(true) }
    var err by remember { mutableStateOf<String?>(null) }
    var deals by remember { mutableStateOf<List<com.spec.crm.data.remote.dto.DealDto>>(emptyList()) }
    var stages by remember { mutableStateOf<List<com.spec.crm.data.remote.dto.DealStageDto>>(emptyList()) }
    LaunchedEffect(Unit) {
        loading = true
        try {
            deals = repo.withApi { it.deals(mapOf("limit" to "100")).items }
            stages = repo.withApi { it.dealStages() }
        } catch (e: Exception) {
            err = e.message
        } finally {
            loading = false
        }
    }
    val stageName = { id: String -> stages.find { it.id == id }?.name ?: id }
    when {
        loading -> ScreenLoading()
        err != null -> Text(err!!, Modifier.padding(16.dp), color = MaterialTheme.colorScheme.error)
        else -> LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            item { Text("Сделки", style = MaterialTheme.typography.headlineSmall) }
            items(deals) { d ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Text(d.title, style = MaterialTheme.typography.titleMedium)
                        Text("${stageName(d.stageId)} · ${d.amount}", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

@Composable
fun TendersListScreen(repo: CrmRepository, onOpen: (String) -> Unit) {
    var loading by remember { mutableStateOf(true) }
    var err by remember { mutableStateOf<String?>(null) }
    var items by remember { mutableStateOf<List<com.spec.crm.data.remote.dto.TenderListDto>>(emptyList()) }
    LaunchedEffect(Unit) {
        loading = true
        try {
            items = repo.withApi { it.tenders(mapOf("limit" to "100")).items }
        } catch (e: Exception) {
            err = e.message
        } finally {
            loading = false
        }
    }
    when {
        loading -> ScreenLoading()
        err != null -> Text(err!!, Modifier.padding(16.dp), color = MaterialTheme.colorScheme.error)
        else -> LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            item { Text("Тендеры", style = MaterialTheme.typography.headlineSmall) }
            items(items) { t ->
                Card(
                    Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp),
                ) {
                    Column(Modifier.padding(12.dp)) {
                        Text(t.title, style = MaterialTheme.typography.titleMedium)
                        Text("${t.status} · ${t.customerName ?: ""}", style = MaterialTheme.typography.bodySmall)
                        Button(onClick = { onOpen(t.id) }) { Text("Открыть") }
                    }
                }
            }
        }
    }
}

@Composable
fun TenderDetailScreen(repo: CrmRepository, tenderId: String, onBack: () -> Unit) {
    var loading by remember { mutableStateOf(true) }
    var err by remember { mutableStateOf<String?>(null) }
    var t by remember { mutableStateOf<com.spec.crm.data.remote.dto.TenderDetailDto?>(null) }
    LaunchedEffect(tenderId) {
        loading = true
        try {
            t = repo.withApi { it.tenderDetail(tenderId) }
        } catch (e: Exception) {
            err = e.message
        } finally {
            loading = false
        }
    }
    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Button(onClick = onBack) { Text("Назад") }
        when {
            loading -> ScreenLoading()
            err != null -> Text(err!!, color = MaterialTheme.colorScheme.error)
            t != null -> {
                val d = t!!
                Text(d.title, style = MaterialTheme.typography.headlineSmall)
                Text(d.status, style = MaterialTheme.typography.bodyMedium)
                d.description?.takeIf { it.isNotBlank() }?.let { Text(it, Modifier.padding(top = 8.dp)) }
                d.checklists?.forEach { cl ->
                    Text(cl.title, style = MaterialTheme.typography.titleSmall, modifier = Modifier.padding(top = 12.dp))
                    cl.items?.forEach { i ->
                        Text("• ${i.title} ${if (i.isCompleted) "[+]" else ""}", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

@Composable
fun TemplatesScreen(repo: CrmRepository) {
    var loading by remember { mutableStateOf(true) }
    var err by remember { mutableStateOf<String?>(null) }
    var items by remember { mutableStateOf<List<com.spec.crm.data.remote.dto.TemplateDto>>(emptyList()) }
    LaunchedEffect(Unit) {
        loading = true
        try {
            items = repo.withApi { it.templates(mapOf("limit" to "100")).items }
        } catch (e: Exception) {
            err = e.message
        } finally {
            loading = false
        }
    }
    when {
        loading -> ScreenLoading()
        err != null -> Text(err!!, Modifier.padding(16.dp), color = MaterialTheme.colorScheme.error)
        else -> LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            item { Text("Шаблоны", style = MaterialTheme.typography.headlineSmall) }
            items(items) { x ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Text(x.name, style = MaterialTheme.typography.titleMedium)
                        Text(x.category ?: "", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

@Composable
fun ChatScreen(repo: CrmRepository) {
    var loading by remember { mutableStateOf(true) }
    var err by remember { mutableStateOf<String?>(null) }
    var messages by remember { mutableStateOf<List<ChatMessageDto>>(emptyList()) }
    var draft by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    fun reload() {
        scope.launch {
            loading = true
            try {
                messages = repo.withApi { it.chatMessages(mapOf("limit" to "80")).items }.reversed()
            } catch (e: Exception) {
                err = e.message
            } finally {
                loading = false
            }
        }
    }
    LaunchedEffect(Unit) { reload() }
    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Text("Чат", style = MaterialTheme.typography.headlineSmall)
        RowFields(draft, { draft = it }, onSend = {
            if (draft.isBlank()) return@RowFields
            scope.launch {
                try {
                    repo.withApi { it.sendChatMessage(SendChatMessageRequest(body = draft.trim())) }
                    draft = ""
                    reload()
                } catch (e: Exception) {
                    err = e.message
                }
            }
        })
        when {
            loading && messages.isEmpty() -> ScreenLoading()
            err != null -> Text(err!!, color = MaterialTheme.colorScheme.error)
            else -> LazyColumn(
                modifier = Modifier.weight(1f),
                reverseLayout = true,
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                items(messages.size) { idx ->
                    val m = messages[messages.lastIndex - idx]
                    Text(
                        "${m.senderName ?: "?"}: ${m.body}",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
        }
    }
}

@Composable
private fun RowFields(draft: String, onDraft: (String) -> Unit, onSend: () -> Unit) {
    Column {
        OutlinedTextField(draft, onDraft, modifier = Modifier.fillMaxWidth(), label = { Text("Сообщение") })
        Button(onClick = onSend, modifier = Modifier.padding(top = 8.dp)) { Text("Отправить") }
    }
}

@Composable
fun AssistantScreen(repo: CrmRepository) {
    var status by remember { mutableStateOf<String?>(null) }
    var messages by remember { mutableStateOf<List<com.spec.crm.data.remote.dto.AiMessageDto>>(emptyList()) }
    var draft by remember { mutableStateOf("") }
    var err by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    LaunchedEffect(Unit) {
        try {
            val s = repo.withApi { it.aiStatus() }
            status = if (s.enabled) "Модель: ${s.model}" else "AI отключён на сервере"
            messages = repo.withApi { it.aiMessages() }
        } catch (e: Exception) {
            err = e.message
        }
    }
    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Text("AI ассистент", style = MaterialTheme.typography.headlineSmall)
        status?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
        err?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        LazyColumn(modifier = Modifier.weight(1f), reverseLayout = true) {
            items(messages.size) { i ->
                val m = messages[messages.lastIndex - i]
                Text("${m.role}: ${m.content}", style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(4.dp))
            }
        }
        OutlinedTextField(draft, { draft = it }, label = { Text("Вопрос") }, modifier = Modifier.fillMaxWidth())
        Button(
            onClick = {
                scope.launch {
                    try {
                        val body = JsonObject().apply { addProperty("message", draft.trim()) }
                        val r = repo.withApi { it.aiChat(body) }
                        draft = ""
                        messages = r.messages
                    } catch (e: Exception) {
                        err = e.message
                    }
                }
            },
            modifier = Modifier.padding(top = 8.dp),
        ) { Text("Отправить") }
    }
}

@Composable
fun TimeScreen(repo: CrmRepository) {
    var loading by remember { mutableStateOf(true) }
    var err by remember { mutableStateOf<String?>(null) }
    var entries by remember { mutableStateOf<List<com.spec.crm.data.remote.dto.TimeEntryDto>>(emptyList()) }
    var summary by remember { mutableStateOf<com.spec.crm.data.remote.dto.TimeSummaryDto?>(null) }
    LaunchedEffect(Unit) {
        loading = true
        try {
            entries = repo.withApi { it.timeEntries(mapOf("limit" to "50")).items }
            summary = repo.withApi { it.timeSummary(emptyMap()) }
        } catch (e: Exception) {
            err = e.message
        } finally {
            loading = false
        }
    }
    when {
        loading -> ScreenLoading()
        err != null -> Text(err!!, Modifier.padding(16.dp), color = MaterialTheme.colorScheme.error)
        else -> LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            item { Text("Учёт времени", style = MaterialTheme.typography.headlineSmall) }
            summary?.let { s ->
                item {
                    Text("Всего: ${s.totalHours} ч (${s.entriesCount} записей)")
                }
            }
            items(entries) { e ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Text("${e.durationMinutes} мин", style = MaterialTheme.typography.titleMedium)
                        Text(e.notes ?: "", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

@Composable
fun WarehouseScreen(repo: CrmRepository) {
    var loading by remember { mutableStateOf(true) }
    var err by remember { mutableStateOf<String?>(null) }
    var items by remember { mutableStateOf<List<com.spec.crm.data.remote.dto.WarehouseItemDto>>(emptyList()) }
    LaunchedEffect(Unit) {
        loading = true
        try {
            items = repo.withApi { it.warehouseItems(mapOf("limit" to "100")).items }
        } catch (e: Exception) {
            err = e.message
        } finally {
            loading = false
        }
    }
    when {
        loading -> ScreenLoading()
        err != null -> Text(err!!, Modifier.padding(16.dp), color = MaterialTheme.colorScheme.error)
        else -> LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            item { Text("Склад", style = MaterialTheme.typography.headlineSmall) }
            items(items) { w ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Text(w.name, style = MaterialTheme.typography.titleMedium)
                        Text("${w.sku ?: ""} · ${w.quantity ?:0}", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

@Composable
fun EquipmentScreen(repo: CrmRepository) {
    var loading by remember { mutableStateOf(true) }
    var err by remember { mutableStateOf<String?>(null) }
    var items by remember { mutableStateOf<List<com.spec.crm.data.remote.dto.EquipmentDto>>(emptyList()) }
    LaunchedEffect(Unit) {
        loading = true
        try {
            items = repo.withApi { it.equipment(mapOf("limit" to "100")).items }
        } catch (e: Exception) {
            err = e.message
        } finally {
            loading = false
        }
    }
    when {
        loading -> ScreenLoading()
        err != null -> Text(err!!, Modifier.padding(16.dp), color = MaterialTheme.colorScheme.error)
        else -> LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            item { Text("Оборудование", style = MaterialTheme.typography.headlineSmall) }
            items(items) { e ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Text(e.name, style = MaterialTheme.typography.titleMedium)
                        Text(e.status ?: "", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

@Composable
fun AnalyticsScreen(repo: CrmRepository) {
    var loading by remember { mutableStateOf(true) }
    var err by remember { mutableStateOf<String?>(null) }
    var ta by remember { mutableStateOf<com.spec.crm.data.remote.dto.TenderAnalyticsDto?>(null) }
    var wa by remember { mutableStateOf<com.spec.crm.data.remote.dto.WarehouseAnalyticsDto?>(null) }
    LaunchedEffect(Unit) {
        loading = true
        try {
            ta = repo.withApi { it.analyticsTenders() }
            wa = repo.withApi { it.analyticsWarehouse() }
        } catch (e: Exception) {
            err = e.message
        } finally {
            loading = false
        }
    }
    when {
        loading -> ScreenLoading()
        err != null -> Text(err!!, Modifier.padding(16.dp), color = MaterialTheme.colorScheme.error)
        else -> LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            item { Text("Аналитика", style = MaterialTheme.typography.headlineSmall) }
            ta?.let { t ->
                item { Text("Тендеры: ${t.totalTenders}, win rate ${t.winRate}") }
            }
            wa?.let { w ->
                item { Text("Склад: позиций ${w.totalItems}") }
                w.lowStockItems?.forEach { ls ->
                    item { Text("• ${ls.name} (${ls.quantity})", style = MaterialTheme.typography.bodySmall) }
                }
            }
        }
    }
}

@Composable
fun NotificationsScreen(repo: CrmRepository) {
    var loading by remember { mutableStateOf(true) }
    var err by remember { mutableStateOf<String?>(null) }
    var items by remember { mutableStateOf<List<com.spec.crm.data.remote.dto.InboxNotificationDto>>(emptyList()) }
    LaunchedEffect(Unit) {
        loading = true
        try {
            items = repo.withApi { it.notifications(mapOf("limit" to "50")).items }
        } catch (e: Exception) {
            err = e.message
        } finally {
            loading = false
        }
    }
    when {
        loading -> ScreenLoading()
        err != null -> Text(err!!, Modifier.padding(16.dp), color = MaterialTheme.colorScheme.error)
        else -> LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            item { Text("Уведомления", style = MaterialTheme.typography.headlineSmall) }
            items(items) { n ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Text(n.title, style = MaterialTheme.typography.titleMedium)
                        Text(n.body, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

@Composable
fun ProfileScreen(repo: CrmRepository) {
    var loading by remember { mutableStateOf(true) }
    var err by remember { mutableStateOf<String?>(null) }
    var name by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    LaunchedEffect(Unit) {
        loading = true
        try {
            val u = repo.withApi { it.usersMe() }
            name = u.fullName
            phone = u.phone ?: ""
        } catch (e: Exception) {
            err = e.message
        } finally {
            loading = false
        }
    }
    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Text("Профиль", style = MaterialTheme.typography.headlineSmall)
        when {
            loading -> ScreenLoading()
            err != null -> Text(err!!, color = MaterialTheme.colorScheme.error)
            else -> {
                OutlinedTextField(name, { name = it }, label = { Text("Имя") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(phone, { phone = it }, label = { Text("Телефон") }, modifier = Modifier.fillMaxWidth())
                Button(
                    onClick = {
                        scope.launch {
                            try {
                                repo.withApi {
                                    it.patchMe(PatchProfileRequest(phone = phone.ifBlank { null }, fullName = name.ifBlank { null }))
                                }
                            } catch (e: Exception) {
                                err = e.message
                            }
                        }
                    },
                    modifier = Modifier.padding(top = 12.dp),
                ) { Text("Сохранить") }
            }
        }
    }
}

@Composable
fun SettingsReferencesScreen(repo: CrmRepository) {
    var loading by remember { mutableStateOf(true) }
    var err by remember { mutableStateOf<String?>(null) }
    var items by remember { mutableStateOf<List<com.spec.crm.data.remote.dto.ReferenceDto>>(emptyList()) }
    LaunchedEffect(Unit) {
        loading = true
        try {
            items = repo.withApi { it.references(mapOf("limit" to "50")).items }
        } catch (e: Exception) {
            err = e.message
        } finally {
            loading = false
        }
    }
    when {
        loading -> ScreenLoading()
        err != null -> Text(err!!, Modifier.padding(16.dp), color = MaterialTheme.colorScheme.error)
        else -> LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            item { Text("Настройки · справочники", style = MaterialTheme.typography.headlineSmall) }
            items(items) { r ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Text(r.name, style = MaterialTheme.typography.titleMedium)
                        Text(r.code, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

@Composable
fun UsersScreen(repo: CrmRepository) {
    var loading by remember { mutableStateOf(true) }
    var err by remember { mutableStateOf<String?>(null) }
    var items by remember { mutableStateOf<List<com.spec.crm.data.remote.dto.UserListItemDto>>(emptyList()) }
    LaunchedEffect(Unit) {
        loading = true
        try {
            items = repo.withApi { it.users(mapOf("limit" to "100")).items }
        } catch (e: Exception) {
            err = e.message
        } finally {
            loading = false
        }
    }
    when {
        loading -> ScreenLoading()
        err != null -> Text(err!!, Modifier.padding(16.dp), color = MaterialTheme.colorScheme.error)
        else -> LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            item { Text("Пользователи", style = MaterialTheme.typography.headlineSmall) }
            items(items) { u ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Text(u.fullName, style = MaterialTheme.typography.titleMedium)
                        Text("${u.email} · ${u.role}", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

@Composable
fun AdminScreen(repo: CrmRepository) {
    var loading by remember { mutableStateOf(true) }
    var err by remember { mutableStateOf<String?>(null) }
    var dep by remember { mutableStateOf<com.spec.crm.data.remote.dto.DeployStatusDto?>(null) }
    var adm by remember { mutableStateOf<com.spec.crm.data.remote.dto.AdminSettingsEnvelopeDto?>(null) }
    LaunchedEffect(Unit) {
        loading = true
        try {
            dep = repo.withApi { it.deployStatus() }
            adm = repo.withApi { it.adminSettings() }
        } catch (e: Exception) {
            err = e.message
        } finally {
            loading = false
        }
    }
    when {
        loading -> ScreenLoading()
        err != null -> Text(err!!, Modifier.padding(16.dp), color = MaterialTheme.colorScheme.error)
        else -> LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            item { Text("Админка", style = MaterialTheme.typography.headlineSmall) }
            dep?.let { d ->
                item {
                    Text("Деплой UI: ${d.deployUiEnabled}, агент: ${d.agentReachable}, GitHub: ${d.githubRepoConfigured}")
                }
            }
            adm?.scheduler?.let { s ->
                item { Text("Планировщик: ${if (s.enabled) "вкл" else "выкл"} ${s.title ?: ""}") }
            }
        }
    }
}

@Composable
fun RolesMatrixScreen() {
    val matrix = mapOf(
        "tasks" to mapOf("admin" to "full", "manager" to "full", "engineer" to "own"),
        "users" to mapOf("admin" to "full", "manager" to "read"),
        "settings" to mapOf("admin" to "full"),
    )
    LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item { Text("Роли (как в веб-справочнике)", style = MaterialTheme.typography.headlineSmall) }
        item { Text("Матрица прав — справочно; редактирование в веб-версии.", style = MaterialTheme.typography.bodySmall) }
        matrix.forEach { (res, roles) ->
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Text(res, style = MaterialTheme.typography.titleMedium)
                        roles.forEach { (role, perm) ->
                            Text("$role → $perm", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
        }
    }
}
