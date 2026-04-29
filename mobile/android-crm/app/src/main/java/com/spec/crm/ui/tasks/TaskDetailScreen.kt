package com.spec.crm.ui.tasks

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import com.spec.crm.data.remote.dto.CommentCreateDto
import com.spec.crm.data.remote.dto.TaskDetailDto
import com.spec.crm.data.remote.dto.TaskTransitionRequest
import com.spec.crm.tasks.TaskWorkflowHelper
import kotlinx.coroutines.launch

@Composable
fun TaskDetailScreen(
    taskId: String,
    crmRepository: CrmRepository,
    fieldWorkBoardId: String?,
    onBack: () -> Unit,
) {
    var detail by remember { mutableStateOf<TaskDetailDto?>(null) }
    var workflow by remember { mutableStateOf<com.google.gson.JsonObject?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }
    var commentDraft by remember { mutableStateOf("") }
    var editTitle by remember { mutableStateOf("") }
    var editDescription by remember { mutableStateOf("") }
    var editing by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val scroll = rememberScrollState()

    fun reload() {
        scope.launch {
            try {
                detail = crmRepository.withApi { it.taskDetail(taskId) }
                detail?.templateId?.let { tid ->
                    try {
                        val tpl = crmRepository.withApi { it.templateDetail(tid) }
                        workflow = tpl.workflowDefinition
                    } catch (_: Exception) {
                        workflow = null
                    }
                } ?: run { workflow = null }
            } catch (e: Exception) {
                error = e.message ?: "Ошибка"
            }
        }
    }

    LaunchedEffect(taskId) {
        loading = true
        error = null
        workflow = null
        try {
            detail = crmRepository.withApi { it.taskDetail(taskId) }
            editTitle = detail?.title.orEmpty()
            editDescription = detail?.description.orEmpty()
            detail?.templateId?.let { tid ->
                try {
                    val tpl = crmRepository.withApi { it.templateDetail(tid) }
                    workflow = tpl.workflowDefinition
                } catch (_: Exception) {
                    workflow = null
                }
            }
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
            error != null && detail == null -> Text(error!!, color = MaterialTheme.colorScheme.error)
            detail != null -> {
                val t = detail!!
                val isField = fieldWorkBoardId != null && t.boardId == fieldWorkBoardId
                Column(Modifier.verticalScroll(scroll)) {
                    if (isField) {
                        Text(
                            "Выездная задача",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.padding(bottom = 4.dp),
                        )
                    }
                    if (editing) {
                        OutlinedTextField(
                            editTitle,
                            { editTitle = it },
                            label = { Text("Название") },
                            modifier = Modifier.fillMaxWidth(),
                        )
                        OutlinedTextField(
                            editDescription,
                            { editDescription = it },
                            label = { Text("Описание") },
                            modifier = Modifier.fillMaxWidth(),
                            minLines = 3,
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(
                                onClick = {
                                    scope.launch {
                                        try {
                                            val patch = JsonObject().apply {
                                                addProperty("title", editTitle.trim())
                                                if (editDescription.isNotBlank()) {
                                                    addProperty("description", editDescription.trim())
                                                }
                                            }
                                            crmRepository.withApi { it.patchTask(taskId, patch) }
                                            editing = false
                                            reload()
                                        } catch (e: Exception) {
                                            error = e.message
                                        }
                                    }
                                },
                            ) { Text("Сохранить") }
                            OutlinedButton(onClick = { editing = false }) { Text("Отмена") }
                        }
                    } else {
                        Text(t.title, style = MaterialTheme.typography.headlineSmall)
                        Text("${t.status} · ${t.priority}", style = MaterialTheme.typography.bodyMedium)
                        t.assignee?.let { Text("Исполнитель: ${it.fullName}", style = MaterialTheme.typography.bodySmall) }
                        t.description?.takeIf { it.isNotBlank() }?.let {
                            Text(it, Modifier.padding(top = 8.dp))
                        }
                        OutlinedButton(
                            onClick = {
                                editTitle = t.title
                                editDescription = t.description.orEmpty()
                                editing = true
                            },
                            modifier = Modifier.padding(top = 8.dp),
                        ) { Text("Редактировать") }
                    }

                    val targets = TaskWorkflowHelper.allowedTargets(t.status, workflow)
                    if (targets.isNotEmpty()) {
                        Text(
                            "Перевести в статус",
                            style = MaterialTheme.typography.titleSmall,
                            modifier = Modifier.padding(top = 12.dp),
                        )
                        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            targets.forEach { st ->
                                OutlinedButton(
                                    onClick = {
                                        scope.launch {
                                            try {
                                                crmRepository.withApi {
                                                    it.taskTransition(
                                                        taskId,
                                                        TaskTransitionRequest(toStatus = st),
                                                    )
                                                }
                                                reload()
                                            } catch (e: Exception) {
                                                error = e.message
                                            }
                                        }
                                    },
                                    modifier = Modifier.fillMaxWidth(),
                                ) { Text(st) }
                            }
                        }
                    }

                    t.customFields?.let { cf ->
                        val keys = cf.keySet().filter { it !in setOf("latitude", "longitude") }
                        if (keys.isNotEmpty()) {
                            Text(
                                "Поля выезда / доп. данные",
                                style = MaterialTheme.typography.titleMedium,
                                modifier = Modifier.padding(top = 16.dp),
                            )
                            keys.forEach { k ->
                                val el = cf.get(k)
                                val v = when {
                                    el != null && el.isJsonPrimitive -> el.asString
                                    el != null && el.isJsonArray -> el.toString()
                                    el != null && el.isJsonObject -> el.toString()
                                    else -> ""
                                }
                                if (v.isNotBlank()) {
                                    Text("$k: $v", style = MaterialTheme.typography.bodySmall)
                                }
                            }
                        }
                    }
                    t.address?.takeIf { it.isNotBlank() }?.let {
                        Text("Адрес: $it", Modifier.padding(top = 8.dp), style = MaterialTheme.typography.bodySmall)
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
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    modifier = Modifier.fillMaxWidth(),
                                ) {
                                    Checkbox(
                                        checked = item.isCompleted,
                                        onCheckedChange = {
                                            scope.launch {
                                                try {
                                                    detail = crmRepository.withApi {
                                                        it.toggleChecklistItem(taskId, cl.id, item.id)
                                                    }
                                                } catch (e: Exception) {
                                                    error = e.message
                                                }
                                            }
                                        },
                                    )
                                    Text(item.title, style = MaterialTheme.typography.bodySmall)
                                }
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
                    Column(Modifier.padding(top = 16.dp)) {
                        OutlinedTextField(
                            commentDraft,
                            { commentDraft = it },
                            label = { Text("Новый комментарий") },
                            modifier = Modifier.fillMaxWidth(),
                            minLines = 2,
                        )
                        Button(
                            onClick = {
                                val body = commentDraft.trim()
                                if (body.isEmpty()) return@Button
                                scope.launch {
                                    try {
                                        crmRepository.withApi {
                                            it.createTaskComment(taskId, CommentCreateDto(body = body))
                                        }
                                        commentDraft = ""
                                        reload()
                                    } catch (e: Exception) {
                                        error = e.message
                                    }
                                }
                            },
                            modifier = Modifier.padding(top = 8.dp),
                        ) { Text("Отправить") }
                    }
                    error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 8.dp)) }
                }
            }
        }
    }
}
