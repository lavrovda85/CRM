package com.spec.crm.data.remote

import com.spec.crm.TokenHolder
import com.spec.crm.data.SessionRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.Response

/**
 * Holder for [SessionRepository] so [OkHttpClient] can be built before the repository exists.
 *
 * Interceptor uses it to run refresh on HTTP 401 before returning the error to Retrofit.
 */
class SessionRepositoryBridge {
    @Volatile
    var repository: SessionRepository? = null
}

/**
 * On 401 (except auth endpoints), tries [SessionRepository.refreshTokens] once and retries the request.
 *
 * Retries reuse the same request; [AuthInterceptor] re-reads [TokenHolder] so the new access token is applied.
 */
class TokenRefreshInterceptor(
    private val bridge: SessionRepositoryBridge,
    private val tokenHolder: TokenHolder,
) : Interceptor {

    private val lock = Any()

    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        var response = chain.proceed(request)
        if (response.code != HTTP_UNAUTHORIZED) return response
        if (request.header(HEADER_AUTH_RETRY) != null) return response
        if (isAuthExemptPath(request.url.encodedPath)) return response

        val repo = bridge.repository
        if (repo == null) return response

        response.close()
        synchronized(lock) {
            val refreshed = runBlocking(Dispatchers.IO) { repo.refreshTokens() }
            if (!refreshed) {
                runBlocking(Dispatchers.IO) { repo.logout() }
                return chain.proceed(
                    request.newBuilder()
                        .header(HEADER_AUTH_RETRY, "1")
                        .build(),
                )
            }
        }
        if (tokenHolder.accessToken.isNullOrBlank()) {
            return chain.proceed(request.newBuilder().header(HEADER_AUTH_RETRY, "1").build())
        }
        return chain.proceed(
            request.newBuilder()
                .header(HEADER_AUTH_RETRY, "1")
                .build(),
        )
    }

    private fun isAuthExemptPath(encodedPath: String): Boolean =
        encodedPath.endsWith("/auth/login") ||
            encodedPath.endsWith("/auth/refresh") ||
            encodedPath.endsWith("/companies/login-options")

    companion object {
        private const val HTTP_UNAUTHORIZED = 401
        private const val HEADER_AUTH_RETRY = "X-Auth-Retry"
    }
}
