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

enum class TaskListFilter {
    /** All visible tasks (paged). */
    ALL,

    /** Office board: hide tasks on the configured field-work board. */
    OFFICE,

    /** Field / crew board only. */
    FIELD,

    /** Current user is assignee, co-assignee, or observer. */
    MY,
}

data class TasksUiState(
    val loading: Boolean = false,
    val items: List<TaskDto> = emptyList(),
    val error: String? = null,
    val filter: TaskListFilter = TaskListFilter.ALL,
)

/**
 * Loads tasks for the active company via [CrmRepository].
 */
class TasksViewModel(
    private val crmRepository: CrmRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(TasksUiState(loading = true))
    val state: StateFlow<TasksUiState> = _state.asStateFlow()

    fun setFilter(filter: TaskListFilter) {
        if (_state.value.filter == filter) return
        _state.value = _state.value.copy(filter = filter)
        load(
            userId = _lastUserId,
            fieldWorkBoardId = _lastFieldBoardId,
            filter = filter,
        )
    }

    private var _lastUserId: String? = null
    private var _lastFieldBoardId: String? = null

    /**
     * @param userId CRM user id (for [TaskListFilter.MY] → ``involves_user``).
     * @param fieldWorkBoardId Company field-work Kanban board id (office/field split).
     */
    fun load(
        userId: String? = null,
        fieldWorkBoardId: String? = null,
        filter: TaskListFilter? = null,
    ) {
        _lastUserId = userId ?: _lastUserId
        _lastFieldBoardId = fieldWorkBoardId ?: _lastFieldBoardId
        val f = filter ?: _state.value.filter
        viewModelScope.launch {
            _state.value = TasksUiState(loading = true, items = emptyList(), error = null, filter = f)
            try {
                val q = LinkedHashMap<String, String>()
                q["limit"] = "200"
                q["order"] = "updated_desc"
                when (f) {
                    TaskListFilter.ALL -> { }
                    TaskListFilter.OFFICE -> {
                        _lastFieldBoardId?.takeIf { it.isNotBlank() }?.let { q["exclude_board_id"] = it }
                    }
                    TaskListFilter.FIELD -> {
                        _lastFieldBoardId?.takeIf { it.isNotBlank() }?.let { q["board_id"] = it }
                            ?: run {
                                _state.value = TasksUiState(
                                    loading = false,
                                    items = emptyList(),
                                    error = "Для выездных задач не настроена доска (field_work_board_id).",
                                    filter = f,
                                )
                                return@launch
                            }
                    }
                    TaskListFilter.MY -> {
                        _lastUserId?.takeIf { it.isNotBlank() }?.let { q["involves_user"] = it }
                            ?: run {
                                _state.value = TasksUiState(
                                    loading = false,
                                    items = emptyList(),
                                    error = "Не удалось определить пользователя.",
                                    filter = f,
                                )
                                return@launch
                            }
                    }
                }
                val res = crmRepository.withApi { it.tasks(q) }
                _state.value = TasksUiState(loading = false, items = res.items, error = null, filter = f)
            } catch (e: HttpException) {
                val raw = e.message()
                val msg = if (raw.isNullOrBlank()) "HTTP ${e.code()}" else raw
                _state.value = TasksUiState(loading = false, items = emptyList(), error = msg, filter = f)
            } catch (e: Exception) {
                val msg = e.message?.takeIf { it.isNotBlank() } ?: "Ошибка загрузки"
                _state.value = TasksUiState(loading = false, items = emptyList(), error = msg, filter = f)
            }
        }
    }
}
