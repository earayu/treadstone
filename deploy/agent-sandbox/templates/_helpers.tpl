{{/*
Common labels
*/}}
{{- define "agent-sandbox.labels" -}}
app.kubernetes.io/name: agent-sandbox
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

{{/*
Resolve controller namespace
*/}}
{{- define "agent-sandbox.namespace" -}}
{{- .Values.namespace | default "agent-sandbox-system" }}
{{- end }}
