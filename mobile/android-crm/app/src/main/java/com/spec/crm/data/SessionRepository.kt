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
        val base = p[ks.base] ?: return@map null
        val access = p[ks.access] ?: return@map null
        val refresh = p[ks.refresh] ?: return@map null
        val company = p[ks.company] ?: return@map null
        val userJson = p[ks.user] ?: return@map null
        val user = try {
            gson.fromJson(userJson, UserDto::class.java)
        } catch (_: Exception) {
            return@map null
        }
        CrmSession(base, access, refresh, company, user)
    }

    suspend fun applySessionToHolders() {
        val s = session.first() ?: return
        tokenHolder.accessToken = s.accessToken
        companyHolder.companyId = s.companyId
    }

    suspend fun login(apiBaseInput: String, email: String, password: String) {
        val base = normalizeApiBase(apiBaseInput)
        val api = retrofitFactory.create(base)
        val res = api.login(LoginRequest(email = email.trim(), password = password))
        val user = res.user
        context.dataStore.edit { p ->
            p[ks.base] = base
            p[ks.access] = res.tokens.accessToken
            p[ks.refresh] = res.tokens.refreshToken
            p[ks.company] = res.activeCompanyId
            p[ks.user] = gson.toJson(user)
        }
        tokenHolder.accessToken = res.tokens.accessToken
        companyHolder.companyId = res.activeCompanyId
    }

    /**
     * Uses refresh token; on failure caller should send user to login.
     */
    suspend fun refreshTokens(): Boolean {
        val p = context.dataStore.data.first()
        val base = p[ks.base] ?: return false
        val refresh = p[ks.refresh] ?: return false
        return try {
            val api = retrofitFactory.create(base)
            val res = api.refresh(RefreshRequest(refresh))
            val user = res.user
            context.dataStore.edit { st ->
                st[ks.access] = res.tokens.accessToken
                st[ks.refresh] = res.tokens.refreshToken
                st[ks.user] = gson.toJson(user)
            }
            tokenHolder.accessToken = res.tokens.accessToken
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
        context.dataStore.edit { it[ks.company] = newCompanyId }
        companyHolder.companyId = newCompanyId
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
        } else {
            throw e
        }
    }
}
