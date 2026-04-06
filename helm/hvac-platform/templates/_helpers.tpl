{{/*
Expand the name of the chart.
*/}}
{{- define "hvac-platform.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this.
If fullnameOverride is provided, use that. Otherwise combine release name + chart name.
*/}}
{{- define "hvac-platform.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart label value.
*/}}
{{- define "hvac-platform.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels applied to every resource.
*/}}
{{- define "hvac-platform.labels" -}}
helm.sh/chart: {{ include "hvac-platform.chart" . }}
{{ include "hvac-platform.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels — a stable subset used in matchLabels.
*/}}
{{- define "hvac-platform.selectorLabels" -}}
app.kubernetes.io/name: {{ include "hvac-platform.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Service account name.
*/}}
{{- define "hvac-platform.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "hvac-platform.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Backend image reference.
*/}}
{{- define "hvac-platform.backendImage" -}}
{{- printf "%s:%s" .Values.backend.image.repository (default .Chart.AppVersion .Values.backend.image.tag) }}
{{- end }}

{{/*
MCP server image reference.
*/}}
{{- define "hvac-platform.mcpImage" -}}
{{- printf "%s:%s" .Values.mcpServer.image.repository (default .Chart.AppVersion .Values.mcpServer.image.tag) }}
{{- end }}

{{/*
Frontend image reference.
*/}}
{{- define "hvac-platform.frontendImage" -}}
{{- printf "%s:%s" .Values.frontend.image.repository (default .Chart.AppVersion .Values.frontend.image.tag) }}
{{- end }}

{{/*
Resolve PostgreSQL host — subchart service or external.
*/}}
{{- define "hvac-platform.postgresHost" -}}
{{- if .Values.postgresql.enabled }}
{{- printf "%s-postgresql" (include "hvac-platform.fullname" .) }}
{{- else }}
{{- .Values.postgresql.external.host }}
{{- end }}
{{- end }}

{{/*
Resolve PostgreSQL port.
*/}}
{{- define "hvac-platform.postgresPort" -}}
{{- if .Values.postgresql.enabled }}
{{- "5432" }}
{{- else }}
{{- .Values.postgresql.external.port | toString }}
{{- end }}
{{- end }}

{{/*
Resolve Redis host — subchart service or external.
*/}}
{{- define "hvac-platform.redisHost" -}}
{{- if .Values.redis.enabled }}
{{- printf "%s-redis-master" (include "hvac-platform.fullname" .) }}
{{- else }}
{{- .Values.redis.external.host }}
{{- end }}
{{- end }}

{{/*
Resolve Redis port.
*/}}
{{- define "hvac-platform.redisPort" -}}
{{- if .Values.redis.enabled }}
{{- "6379" }}
{{- else }}
{{- .Values.redis.external.port | toString }}
{{- end }}
{{- end }}

{{/*
Resolve MinIO host — subchart service or external.
*/}}
{{- define "hvac-platform.minioHost" -}}
{{- if .Values.minio.enabled }}
{{- printf "%s-minio" (include "hvac-platform.fullname" .) }}
{{- else }}
{{- .Values.minio.external.host }}
{{- end }}
{{- end }}

{{/*
Resolve MinIO port.
*/}}
{{- define "hvac-platform.minioPort" -}}
{{- if .Values.minio.enabled }}
{{- "9000" }}
{{- else }}
{{- .Values.minio.external.port | toString }}
{{- end }}
{{- end }}

{{/*
Resolve Keycloak host — subchart or external.
*/}}
{{- define "hvac-platform.keycloakHost" -}}
{{- if .Values.keycloak.enabled }}
{{- printf "%s-keycloak" (include "hvac-platform.fullname" .) }}
{{- else }}
{{- .Values.keycloak.external.host }}
{{- end }}
{{- end }}

{{/*
Resolve Keycloak port.
*/}}
{{- define "hvac-platform.keycloakPort" -}}
{{- if .Values.keycloak.enabled }}
{{- "8080" }}
{{- else }}
{{- .Values.keycloak.external.port | toString }}
{{- end }}
{{- end }}
