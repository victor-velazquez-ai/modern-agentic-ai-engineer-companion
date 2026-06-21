# API and webhooks

Nimbus has a REST API and webhooks. Create an API key under **Settings → Developer**; keys are
scoped to one workspace and can be read-only or read-write. Webhooks fire on events like
`import.finished` and `query.scheduled.completed` — register a URL and Nimbus POSTs a signed
payload. Rotate keys regularly and never embed a read-write key in client-side code.
