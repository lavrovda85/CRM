package com.spec.crm.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.google.gson.Gson
import com.spec.crm.CompanyIdHolder
import com.spec.crm.TokenHolder
import com.spec.crm.data.remote.RetrofitFactory
import com.spec.crm.data.remote.dto.LoginRequest
import com.spec.crm.data.remote.dto.RefreshRequest
import com.spec.crm.data.remote.dto.UserDto
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import retrofit2.HttpException

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "crm_session")

data class CrmSession(
    val baseUrl: String,
    val accessToken: String,
    val refreshToken: String,
    val companyId: String,
    val user: UserDto,
)

/**
 * Persists OAuth tokens, active company, and API base URL; wires [TokenHolder] / [CompanyIdHolder].
 */
class SessionRepository(
    private val context: Context,
    private val gson: Gson,
    private val retrofitFactory: RetrofitFactory,
    private val tokenHolder: TokenHolder,
    private val companyHolder: CompanyIdHolder,
) {
    private val ks = object {
        val base = stringPreferencesKey("api_base_url")
        val access = stringPreferencesKey("access_token")
        val refresh = stringPreferencesKey("refresh_token")
        val company = stringPreferencesKey("company_id")
        val user = stringPreferencesKey("user_json")
    }

    val session: Flow<CrmSession?> = context.dataStore.data.map { p ->
        val base = (p[ks.base] ?: return@map null).trim()
        val access = (p[ks.access] ?: return@map null).trim()
        val refresh = (p[ks.refresh] ?: return@map null).trim()
        val company = (p[ks.company] ?: return@map null).trim()
        if (base.isEmpty() || access.isEmpty() || refresh.isEmpty() || company.isEmpty()) {
            return@map null
        }
        val userJson = p[ks.user] ?: return@map null
        val user = try {
            gson.fromJson(userJson, UserDto::class.java)
        } catch (_: Exception) {
            return@map null
        }
        CrmSession(base, access, refresh, company, user)
    }

    /**
     * Pushes the given session into [TokenHolder] / [CompanyIdHolder] without re-reading DataStore.
     * Use this after [session.first()] or from [session] flow to avoid a race where the first
     * API call runs before holders are populated (symptom: HTTP 401 on dashboard).
     */
    fun applyFromSession(s: CrmSession) {
        tokenHolder.accessToken = s.accessToken.trim().takeIf { it.isNotEmpty() }
        companyHolder.companyId = s.companyId.trim().takeIf { it.isNotEmpty() }
    }

    /** Clears in-memory tokens when the persisted session is gone (logout or cleared storage). */
    fun clearApiHolders() {
        tokenHolder.accessToken = null
        companyHolder.companyId = null
    }

    suspend fun applySessionToHolders() {
        val s = session.first() ?: return
        applyFromSession(s)
    }

    suspend fun login(apiBaseInput: String, email: String, password: String) {
        val base = normalizeApiBase(apiBaseInput)
        val api = retrofitFactory.create(base)
        val res = api.login(LoginRequest(email = email.trim(), password = password))
        val user = res.user
        val access = res.tokens.accessToken.trim()
        val refresh = res.tokens.refreshToken.trim()
        val company = res.activeCompanyId.trim()
        context.dataStore.edit { p ->
            p[ks.base] = base
            p[ks.access] = access
            p[ks.refresh] = refresh
            p[ks.company] = company
            p[ks.user] = gson.toJson(user)
        }
        applyFromSession(
            CrmSession(
                baseUrl = base,
                accessToken = access,
                refreshToken = refresh,
                companyId = company,
                user = user,
            ),
        )
    }

    /**
     * Uses refresh token; on failure caller should send user to login.
     */
    suspend fun refreshTokens(): Boolean {
        val p = context.dataStore.data.first()
        val base = p[ks.base] ?: return false
        val refresh = (p[ks.refresh] ?: return false).trim()
        val companyId = (p[ks.company] ?: return false).trim()
        if (refresh.isEmpty() || companyId.isEmpty()) return false
        return try {
            val api = retrofitFactory.create(base)
            val res = api.refresh(RefreshRequest(refresh))
            val user = res.user
            val newAccess = res.tokens.accessToken.trim()
            val newRefresh = res.tokens.refreshToken.trim()
            context.dataStore.edit { st ->
                st[ks.access] = newAccess
                st[ks.refresh] = newRefresh
                st[ks.user] = gson.toJson(user)
            }
            applyFromSession(
                CrmSession(
                    baseUrl = base,
                    accessToken = newAccess,
                    refreshToken = newRefresh,
                    companyId = companyId,
                    user = user,
                ),
            )
            true
        } catch (_: Exception) {
            false
        }
    }

    suspend fun logout() {
        context.dataStore.edit { p ->
            p.remove(ks.base)
            p.remove(ks.access)
            p.remove(ks.refresh)
            p.remove(ks.company)
            p.remove(ks.user)
        }
        tokenHolder.accessToken = null
        companyHolder.companyId = null
    }

    fun apiForSession(session: CrmSession): com.spec.crm.data.remote.CrmApi =
        retrofitFactory.create(session.baseUrl)

    /**
     * Switch active tenant (`X-Company-Id`). Caller should ensure membership (e.g. from `/companies/mine`).
     */
    suspend fun switchCompany(newCompanyId: String) {
        val cid = newCompanyId.trim()
        context.dataStore.edit { it[ks.company] = cid }
        companyHolder.companyId = cid.takeIf { it.isNotEmpty() }
    }
}

fun normalizeApiBase(input: String): String {
    var s = input.trim().removeSuffix("/")
    if (!s.contains("/api/v1")) {
        s = "$s/api/v1"
    }
    return if (s.endsWith("/")) s else "$s/"
}

suspend fun <T> SessionRepository.withTokenRefresh(block: suspend () -> T): T {
    return try {
        block()
    } catch (e: HttpException) {
        if (e.code() == 401 && refreshTokens()) {
            applySessionToHolders()
            block()
        } else if (e.code() == 401) {
            logout()
            throw e
        } else {
            throw e
        }
    }
}
