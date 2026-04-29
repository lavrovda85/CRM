package com.spec.crm.ui.tasks

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.google.gson.JsonObject
import com.spec.crm.data.CrmRepository
import com.spec.crm.data.remote.dto.TemplateDto
import com.spec.crm.data.remote.dto.UserListItemDto
import kotlinx.coroutines.launch

/**
 * Create a task (office or field-work board). Mirrors web ``CreateTaskModal`` essentials.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TaskCreateScreen(
    repo: CrmRepository,
    isFieldWork: Boolean,
    fieldWorkBoardId: String?,
    defaultFieldTemplateId: String?,
    fieldTemplateFilter: List<String>?,
    onCreated: (String) -> Unit,
    onBack: () -> Unit,
) {
    var title by remember { mutableStateOf("") }
    var description by remember { mutableStateOf("") }
    var priority by remember { mutableStateOf("medium") }
    var dueRaw by remember { mutableStateOf("") }
    var templates by remember { mutableStateOf<List<TemplateDto>>(emptyList()) }
    var users by remember { mutableStateOf<List<UserListItemDto>>(emptyList()) }
    var selectedTemplateId by remember { mutableStateOf<String?>(null) }
    var selectedAssigneeId by remember { mutableStateOf<String?>(null) }
    var templateMenu by remember { mutableStateOf(false) }
    var assigneeMenu by remember { mutableStateOf(false) }
    var loading by remember { mutableStateOf(true) }
    var saving by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val scroll = rememberScrollState()

    LaunchedEffect(isFieldWork) {
        loading = true
        error = null
        try {
            templates = repo.withApi { it.templates(mapOf("limit" to "200")).items }
            if (isFieldWork && !fieldTemplateFilter.isNullOrEmpty()) {
                val allow = fieldTemplateFilter.toSet()
                templates = templates.filter { allow.contains(it.id) }
            }
            users = repo.withApi { it.users(mapOf("limit" to "200")).items }
            if (selectedTemplateId == null && isFieldWork) {
                defaultFieldTemplateId?.takeIf { id ->
                    templates.any { it.id == id }
                }?.let { selectedTemplateId = it }
            }
        } catch (e: Exception) {
            error = e.message
        } finally {
            loading = false
        }
    }

    Column(Modifier.fillMaxSize().padding(16.dp)) {
        OutlinedButton(onClick = onBack) { Text("Назад") }
        Text(
            if (isFieldWork) "Новая выездная задача" else "Новая задача",
            style = MaterialTheme.typography.headlineSmall,
            modifier = Modifier.padding(top = 8.dp),
        )
        Column(
            Modifier
                .verticalScroll(scroll)
                .padding(top = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (error != null) Text(error!!, color = MaterialTheme.colorScheme.error)
            OutlinedTextField(
                title,
                { title = it },
                label = { Text("Название *") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = false,
            )
            OutlinedTextField(
                description,
                { description = it },
                label = { Text("Описание") },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2,
            )
            ExposedDropdownMenuBox(
                expanded = templateMenu,
                onExpandedChange = { templateMenu = it },
            ) {
                OutlinedTextField(
                    readOnly = true,
                    value = templates.find { it.id == selectedTemplateId }?.name ?: "Без шаблона",
                    onValueChange = {},
                    label = { Text("Шаблон") },
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = templateMenu) },
                    modifier = Modifier.menuAnchor().fillMaxWidth(),
                )
                ExposedDropdownMenu(expanded = templateMenu, onDismissRequest = { templateMenu = false }) {
                    DropdownMenuItem(
                        text = { Text("Без шаблона") },
                        onClick = {
                            selectedTemplateId = null
                            templateMenu = false
                        },
                    )
                    templates.forEach { t ->
                        DropdownMenuItem(
                            text = { Text(t.name) },
                            onClick = {
                                selectedTemplateId = t.id
                                templateMenu = false
                            },
                        )
                    }
                }
            }
            ExposedDropdownMenuBox(
                expanded = assigneeMenu,
                onExpandedChange = { assigneeMenu = it },
            ) {
                OutlinedTextField(
                    readOnly = true,
                    value = users.find { it.id == selectedAssigneeId }?.fullName ?: "Не назначен",
                    onValueChange = {},
                    label = { Text("Исполнитель") },
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = assigneeMenu) },
                    modifier = Modifier.menuAnchor().fillMaxWidth(),
                )
                ExposedDropdownMenu(expanded = assigneeMenu, onDismissRequest = { assigneeMenu = false }) {
                    DropdownMenuItem(
                        text = { Text("Не назначен") },
                        onClick = {
                            selectedAssigneeId = null
                            assigneeMenu = false
                        },
                    )
                    users.forEach { u ->
                        DropdownMenuItem(
                            text = { Text(u.fullName) },
                            onClick = {
                                selectedAssigneeId = u.id
                                assigneeMenu = false
                            },
                        )
                    }
                }
            }
            val priorities = listOf("low", "medium", "high", "critical")
            var priOpen by remember { mutableStateOf(false) }
            ExposedDropdownMenuBox(expanded = priOpen, onExpandedChange = { priOpen = it }) {
                OutlinedTextField(
                    readOnly = true,
                    value = priority,
                    onValueChange = {},
                    label = { Text("Приоритет") },
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = priOpen) },
                    modifier = Modifier.menuAnchor().fillMaxWidth(),
                )
                ExposedDropdownMenu(expanded = priOpen, onDismissRequest = { priOpen = false }) {
                    priorities.forEach { p ->
                        DropdownMenuItem(
                            text = { Text(p) },
                            onClick = {
                                priority = p
                                priOpen = false
                            },
                        )
                    }
                }
            }
            OutlinedTextField(
                dueRaw,
                { dueRaw = it },
                label = { Text("Срок (ISO, опционально)") },
                placeholder = { Text("2026-04-30T12:00:00Z") },
                modifier = Modifier.fillMaxWidth(),
            )
            Button(
                onClick = {
                    val t = title.trim()
                    if (t.isEmpty()) {
                        error = "Введите название"
                        return@Button
                    }
                    if (isFieldWork && fieldWorkBoardId.isNullOrBlank()) {
                        error = "Не настроена доска выездных работ"
                        return@Button
                    }
                    scope.launch {
                        saving = true
                        error = null
                        try {
                            val body = JsonObject().apply {
                                addProperty("title", t)
                                if (description.isNotBlank()) addProperty("description", description.trim())
                                addProperty("priority", priority)
                                selectedTemplateId?.let { addProperty("template_id", it) }
                                selectedAssigneeId?.let { addProperty("assigned_to", it) }
                                dueRaw.trim().takeIf { it.isNotEmpty() }?.let { addProperty("due_date", it) }
                                if (isFieldWork) {
                                    addProperty("board_id", fieldWorkBoardId!!)
                                    addProperty("visibility", "participants")
                                }
                            }
                            val created = repo.withApi { it.createTask(body) }
                            onCreated(created.id)
                        } catch (e: Exception) {
                            error = e.message ?: "Ошибка создания"
                        } finally {
                            saving = false
                        }
                    }
                },
                enabled = !loading && !saving,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (saving) "Создание…" else "Создать")
            }
        }
    }
}
