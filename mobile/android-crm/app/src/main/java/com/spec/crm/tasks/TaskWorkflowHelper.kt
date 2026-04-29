package com.spec.crm.tasks

import com.google.gson.JsonArray
import com.google.gson.JsonObject

/**
 * Computes allowed workflow target statuses from a template ``workflow_definition``
 * (same rules as the backend: forward transitions + backwards along ``states`` order).
 */
object TaskWorkflowHelper {

    private val FALLBACK: Map<String, List<String>> = mapOf(
        "new" to listOf("dispatched"),
        "dispatched" to listOf("new", "in_progress"),
        "in_progress" to listOf("dispatched", "testing", "photo_report"),
        "testing" to listOf("in_progress", "done", "photo_report"),
        "photo_report" to listOf("testing", "done", "in_progress"),
        "act_signing" to listOf("testing", "done"),
        "done" to listOf("testing", "closed", "completed"),
        "completed" to listOf("closed"),
        "closed" to listOf("done"),
    )

    fun allowedTargets(currentStatus: String, workflow: JsonObject?): List<String> {
        if (workflow == null) return FALLBACK[currentStatus] ?: emptyList()
        val states = workflow.getAsJsonArray("states")?.toStringList() ?: emptyList()
        val transitions = workflow.getAsJsonArray("transitions") ?: return FALLBACK[currentStatus] ?: emptyList()
        val curIdx = states.indexOf(currentStatus)
        val forward = mutableListOf<String>()
        for (el in transitions) {
            if (!el.isJsonObject) continue
            val o = el.asJsonObject
            val from = o.get("from")?.takeIf { it.isJsonPrimitive }?.asString ?: continue
            val to = o.get("to")?.takeIf { it.isJsonPrimitive }?.asString ?: continue
            if (from == currentStatus) forward.add(to)
        }
        val backward = if (curIdx > 0) states.subList(0, curIdx) else emptyList()
        return (forward + backward).distinct()
    }

    private fun JsonArray.toStringList(): List<String> = buildList {
        for (e in this@toStringList) {
            if (e.isJsonPrimitive) add(e.asString)
        }
    }
}
