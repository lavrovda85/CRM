package com.spec.crm.data.remote

import com.spec.crm.CompanyIdHolder
import com.spec.crm.TokenHolder
import okhttp3.Interceptor
import okhttp3.Response

/**
 * Adds Bearer token and `X-Company-Id` to API calls (same as the web client).
 */
class AuthInterceptor(
    private val tokens: TokenHolder,
    private val company: CompanyIdHolder,
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val req = chain.request()
        val path = req.url.encodedPath
        val isAuthFree =
            path.endsWith("/auth/login") ||
                path.endsWith("/auth/refresh") ||
                path.endsWith("/companies/login-options")
        val b = req.newBuilder().removeHeader("X-Auth-Retry")
        if (!isAuthFree) {
            val access = tokens.accessToken?.trim()?.takeIf { it.isNotEmpty() }
            if (access != null) {
                b.header("Authorization", "Bearer $access")
            }
            company.companyId?.trim()?.takeIf { it.isNotEmpty() }
                ?.let { cid -> b.header("X-Company-Id", cid) }
        }
        return chain.proceed(b.build())
    }
}
