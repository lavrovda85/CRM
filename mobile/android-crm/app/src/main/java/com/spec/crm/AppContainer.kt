package com.spec.crm

import android.content.Context
import com.google.gson.FieldNamingPolicy
import com.google.gson.Gson
import com.google.gson.GsonBuilder
import com.spec.crm.data.CrmRepository
import com.spec.crm.data.SessionRepository
import com.spec.crm.data.remote.AuthInterceptor
import com.spec.crm.data.remote.CrmApi
import com.spec.crm.data.remote.RetrofitFactory
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import java.util.concurrent.TimeUnit

/**
 * Dependency container built once per process.
 */
class AppContainer(context: Context) {
    private val appContext = context.applicationContext

    val gson: Gson = GsonBuilder()
        .setFieldNamingPolicy(FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES)
        .create()

    private val tokenHolder = TokenHolder()
    private val companyHolder = CompanyIdHolder()

    private val logging = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BASIC
    }

    val okHttp: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(45, TimeUnit.SECONDS)
        .readTimeout(45, TimeUnit.SECONDS)
        .writeTimeout(45, TimeUnit.SECONDS)
        .addInterceptor(logging)
        .addInterceptor(AuthInterceptor(tokenHolder, companyHolder))
        .build()

    val retrofitFactory = RetrofitFactory(gson, okHttp)

    val sessionRepository = SessionRepository(
        appContext,
        gson,
        retrofitFactory,
        tokenHolder,
        companyHolder,
    )

    val crmRepository = CrmRepository(sessionRepository)
}

/** Mutable token for OkHttp interceptor (updated by [SessionRepository]). */
class TokenHolder {
    @Volatile
    var accessToken: String? = null
}

/** Active tenant for `X-Company-Id`. */
class CompanyIdHolder {
    @Volatile
    var companyId: String? = null
}
