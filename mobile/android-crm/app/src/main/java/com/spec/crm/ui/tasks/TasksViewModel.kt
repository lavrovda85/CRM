package com.spec.crm.ui.tasks

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.spec.crm.data.CrmRepository
import com.spec.crm.data.remote.dto.TaskDto
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import retrofit2.HttpException

data class TasksUiState(
    val loading: Boolean = false,
    val items: List<TaskDto> = emptyList(),
    val error: String? = null,
)

/**
 * Loads tasks for the active company via [CrmRepository].
 */
class TasksViewModel(
    private val crmRepository: CrmRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(TasksUiState(loading = true))
    val state: StateFlow<TasksUiState> = _state.asStateFlow()

    fun load(query: Map<String, String> = mapOf("limit" to "200")) {
        viewModelScope.launch {
            _state.value = TasksUiState(loading = true, items = emptyList(), error = null)
            try {
                val res = crmRepository.withApi { it.tasks(query) }
                _state.value = TasksUiState(loading = false, items = res.items, error = null)
            } catch (e: HttpException) {
                val msg = e.message()?.takeIf { !it.isNullOrBlank() } ?: "HTTP ${e.code()}"
                _state.value = TasksUiState(loading = false, items = emptyList(), error = msg)
            } catch (e: Exception) {
                val msg = e.message?.takeIf { it.isNotBlank() } ?: "Ошибка загрузки"
                _state.value = TasksUiState(loading = false, items = emptyList(), error = msg)
            }
        }
    }
}
