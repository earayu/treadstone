{{- define "treadstone.name" -}}
{{- .Chart.Name }}
{{- end }}

{{- define "treadstone.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "treadstone.labels" -}}
app.kubernetes.io/name: {{ include "treadstone.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

{{- define "treadstone.selectorLabels" -}}
app.kubernetes.io/name: {{ include "treadstone.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app: sandbox-router
{{- end }}

{{- define "treadstone.serviceAccountName" -}}
{{- if .Values.serviceAccount.name }}
{{- .Values.serviceAccount.name }}
{{- else }}
{{- include "treadstone.fullname" . }}
{{- end }}
{{- end }}
