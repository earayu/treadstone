{{- define "sandbox-runtime.name" -}}
{{- .Chart.Name }}
{{- end }}

{{- define "sandbox-runtime.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "sandbox-runtime.labels" -}}
app.kubernetes.io/name: {{ include "sandbox-runtime.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

{{- define "sandbox-runtime.routerLabels" -}}
app.kubernetes.io/name: sandbox-router
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
