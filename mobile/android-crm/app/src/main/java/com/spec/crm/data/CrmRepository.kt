package com.spec.crm.data

import com.spec.crm.data.remote.CrmApi
import kotlinx.coroutines.flow.first

/**
 * Runs API calls with the current session and automatic token refresh on 401.
 */
class CrmRepository(
    private val sessionRepository: SessionRepository,
) {
    suspend fun <T> withApi(block: suspend (CrmApi) -> T): T {
        val session = sessionRepository.session.first() ?: error("Not logged in")
        sessionRepository.applySessionToHolders()
        val api = sessionRepository.apiForSession(session)
        return sessionRepository.withTokenRefresh { block(api) }
    }
}
