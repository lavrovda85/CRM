package com.spec.crm.ui.tasks

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun TasksListScreen(
    viewModel: TasksViewModel,
    companyIdKey: String,
    currentUserId: String,
    fieldWorkBoardId: String?,
    onTaskClick: (String) -> Unit,
    onCreateTask: (isFieldWork: Boolean) -> Unit,
) {
    val state by viewModel.state.collectAsState()

    LaunchedEffect(companyIdKey, currentUserId, fieldWorkBoardId) {
        viewModel.load(userId = currentUserId, fieldWorkBoardId = fieldWorkBoardId)
    }

    Scaffold(
        floatingActionButton = {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FloatingActionButton(
                    onClick = { onCreateTask(false) },
                    modifier = Modifier,
                ) {
                    Icon(Icons.Default.Add, contentDescription = "Новая задача")
                }
                if (!fieldWorkBoardId.isNullOrBlank()) {
                    FloatingActionButton(
                        onClick = { onCreateTask(true) },
                    ) {
                        Text("В", style = MaterialTheme.typography.labelLarge)
                    }
                }
            }
        },
    ) { innerPadding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(innerPadding),
        ) {
            Row(
                Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                FilterChip(
                    selected = state.filter == TaskListFilter.ALL,
                    onClick = { viewModel.setFilter(TaskListFilter.ALL) },
                    label = { Text("Все") },
                )
                FilterChip(
                    selected = state.filter == TaskListFilter.OFFICE,
                    onClick = { viewModel.setFilter(TaskListFilter.OFFICE) },
                    label = { Text("Офис") },
                )
                if (!fieldWorkBoardId.isNullOrBlank()) {
                    FilterChip(
                        selected = state.filter == TaskListFilter.FIELD,
                        onClick = { viewModel.setFilter(TaskListFilter.FIELD) },
                        label = { Text("Выезд") },
                    )
                }
                FilterChip(
                    selected = state.filter == TaskListFilter.MY,
                    onClick = { viewModel.setFilter(TaskListFilter.MY) },
                    label = { Text("Мои") },
                )
            }

            when {
                state.loading && state.items.isEmpty() -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }
                state.error != null && state.items.isEmpty() -> {
                    Column(
                        Modifier.fillMaxSize().padding(24.dp),
                        verticalArrangement = Arrangement.Center,
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        Text(state.error!!, color = MaterialTheme.colorScheme.error)
                        androidx.compose.material3.Button(onClick = {
                            viewModel.load(
                                userId = currentUserId,
                                fieldWorkBoardId = fieldWorkBoardId,
                            )
                        }) { Text("Повторить") }
                    }
                }
                else -> {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        items(state.items, key = { it.id }) { task ->
                            val fieldBadge =
                                !fieldWorkBoardId.isNullOrBlank() && task.boardId == fieldWorkBoardId
                            Card(
                                Modifier
                                    .fillMaxWidth()
                                    .clickable { onTaskClick(task.id) },
                            ) {
                                Column(Modifier.padding(16.dp)) {
                                    Row(
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        modifier = Modifier.fillMaxWidth(),
                                    ) {
                                        Text(task.title, style = MaterialTheme.typography.titleMedium)
                                        if (fieldBadge) {
                                            Text(
                                                "Выезд",
                                                style = MaterialTheme.typography.labelSmall,
                                                color = MaterialTheme.colorScheme.primary,
                                            )
                                        }
                                    }
                                    Text(
                                        "${task.status} · ${task.priority}",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                    task.assignee?.let {
                                        Text(
                                            it.fullName,
                                            style = MaterialTheme.typography.labelSmall,
                                        )
                                    }
                                    task.dueDate?.let {
                                        Text("Срок: $it", style = MaterialTheme.typography.labelSmall)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
