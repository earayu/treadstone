{{- define "treadstone-web.name" -}}
{{- .Chart.Name }}
{{- end }}

{{- define "treadstone-web.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "treadstone-web.labels" -}}
app.kubernetes.io/name: {{ include "treadstone-web.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

{{- define "treadstone-web.selectorLabels" -}}
app.kubernetes.io/name: {{ include "treadstone-web.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
