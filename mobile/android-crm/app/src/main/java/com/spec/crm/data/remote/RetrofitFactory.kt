package com.spec.crm.data.remote

import com.google.gson.Gson
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

/**
 * Builds [CrmApi] for a base URL (must include `/api/v1` path segment, trailing slash).
 */
class RetrofitFactory(
    private val gson: Gson,
    private val client: OkHttpClient,
) {
    fun create(baseUrl: String): CrmApi {
        val root = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"
        return Retrofit.Builder()
            .baseUrl(root)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create(gson))
            .build()
            .create(CrmApi::class.java)
    }
}
