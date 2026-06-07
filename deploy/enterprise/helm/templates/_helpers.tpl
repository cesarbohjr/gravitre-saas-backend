{{- define "gravitre.name" -}}
gravitre
{{- end -}}

{{- define "gravitre.labels" -}}
app.kubernetes.io/name: {{ include "gravitre.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
