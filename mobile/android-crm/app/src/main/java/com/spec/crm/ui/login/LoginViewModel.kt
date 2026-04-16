package com.spec.crm.ui.login

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.spec.crm.data.SessionRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class LoginUiState(
    val loading: Boolean = false,
    val error: String? = null,
)

/**
 * Handles credential login against `/auth/login`.
 */
class LoginViewModel(
    private val sessionRepository: SessionRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(LoginUiState())
    val state: StateFlow<LoginUiState> = _state.asStateFlow()

    fun login(apiBaseUrl: String, email: String, password: String) {
        viewModelScope.launch {
            _state.value = LoginUiState(loading = true, error = null)
            try {
                sessionRepository.login(apiBaseUrl, email, password)
                _state.value = LoginUiState(loading = false, error = null)
            } catch (e: Exception) {
                val msg = e.message?.takeIf { it.isNotBlank() } ?: "Ошибка входа"
                _state.value = LoginUiState(loading = false, error = msg)
            }
        }
    }
}
