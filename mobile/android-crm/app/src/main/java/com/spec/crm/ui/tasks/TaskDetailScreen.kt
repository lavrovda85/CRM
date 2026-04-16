package com.spec.crm.ui.tasks

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import com.spec.crm.data.CrmRepository
import com.spec.crm.data.remote.dto.TaskDetailDto
import com.spec.crm.data.remote.dto.TaskTransitionRequest
import kotlinx.coroutines.launch

@Composable
fun TaskDetailScreen(
    taskId: String,
    crmRepository: CrmRepository,
    onBack: () -> Unit,
) {
    var detail by remember { mutableStateOf<TaskDetailDto?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }
    var menuOpen by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val scroll = rememberScrollState()

    LaunchedEffect(taskId) {
        loading = true
        error = null
        try {
            detail = crmRepository.withApi { it.taskDetail(taskId) }
        } catch (e: Exception) {
            error = e.message ?: "Ошибка"
        } finally {
            loading = false
        }
    }

    Column(Modifier.fillMaxSize().padding(16.dp)) {
        OutlinedButton(onClick = onBack) { Text("Назад") }

        when {
            loading -> {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            }
            error != null -> Text(error!!, color = MaterialTheme.colorScheme.error)
            detail != null -> {
                val t = detail!!
                Column(Modifier.verticalScroll(scroll)) {
                    Text(t.title, style = MaterialTheme.typography.headlineSmall)
                    Text("${t.status} · ${t.priority}", style = MaterialTheme.typography.bodyMedium)
                    t.description?.takeIf { it.isNotBlank() }?.let {
                        Text(it, Modifier.padding(top = 8.dp))
                    }
                    val next = listOf(
                        "new", "dispatched", "in_progress", "testing", "done", "closed",
                    ).filter { it != t.status }
                    Column(Modifier.padding(top = 12.dp)) {
                        OutlinedButton(onClick = { menuOpen = true }) { Text("Сменить статус") }
                        DropdownMenu(expanded = menuOpen, onDismissRequest = { menuOpen = false }) {
                            next.forEach { st ->
                                DropdownMenuItem(
                                    text = { Text(st) },
                                    onClick = {
                                        menuOpen = false
                                        scope.launch {
                                            try {
                                                crmRepository.withApi {
                                                    it.taskTransition(
                                                        taskId,
                                                        TaskTransitionRequest(toStatus = st),
                                                    )
                                                }
                                                detail = crmRepository.withApi { it.taskDetail(taskId) }
                                            } catch (e: Exception) {
                                                error = e.message
                                            }
                                        }
                                    },
                                )
                            }
                        }
                    }
                    t.checklists?.takeIf { it.isNotEmpty() }?.let { lists ->
                        Text(
                            "Чек-листы",
                            style = MaterialTheme.typography.titleMedium,
                            modifier = Modifier.padding(top = 16.dp),
                        )
                        lists.forEach { cl ->
                            Text(cl.title, style = MaterialTheme.typography.titleSmall)
                            cl.items?.forEach { item ->
                                val mark = if (item.isCompleted) " [+]" else ""
                                Text("• ${item.title}$mark", style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                    t.comments?.takeIf { it.isNotEmpty() }?.let { comments ->
                        Text(
                            "Комментарии",
                            style = MaterialTheme.typography.titleMedium,
                            modifier = Modifier.padding(top = 16.dp),
                        )
                        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            comments.forEach { c ->
                                Text(
                                    "${c.authorName ?: "?"}: ${c.body}",
                                    style = MaterialTheme.typography.bodySmall,
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
