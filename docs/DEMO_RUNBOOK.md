# AstraBridge Demo Runbook

## Goal

Bring up a local AstraBridge web demo without consuming real model quota by default.

## No-Key Demo

1. Start the sidecar with isolated local state:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:ASTRABRIDGE_APPDATA='D:\AstraBridge\PRIVATE\demo-runs\<timestamp>\appdata'
$env:ASTRABRIDGE_CODEX_HOME='D:\AstraBridge\PRIVATE\demo-runs\<timestamp>\codex-home'
C:\Users\cyz19\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m astrabridge_sidecar.server --serve --port 8790 --seed-root D:\AstraBridge
```

2. Start the web app:

```powershell
$env:PATH='C:\Users\cyz19\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin;' + $env:PATH
$env:VITE_ASTRABRIDGE_SIDECAR_URL='http://127.0.0.1:8790'
C:\Users\cyz19\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\pnpm.cmd dev
```

3. Open:

```text
http://127.0.0.1:5173/?sidecar=http://127.0.0.1:8790
```

4. Create the demo project through the sidecar API:

```powershell
$token = (Invoke-RestMethod http://127.0.0.1:8790/api/admin/session).admin_session_token
$headers = @{ 'X-Admin-Token' = $token; 'Content-Type' = 'application/json' }
$body = @{
  name='AstraBridge Demo'
  project_file='D:\AstraBridge\PRIVATE\demo-runs\<timestamp>\workspace\demo.abproj'
  workspace_root='D:\AstraBridge\PRIVATE\demo-runs\<timestamp>\workspace\demo-workspace'
  entry_mode='new'
} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8790/api/projects/create -Method Post -Headers $headers -Body $body
```

## Browser Smoke

Run local browser smoke against the web app:

```powershell
$token = (Invoke-RestMethod http://127.0.0.1:8790/api/admin/session).admin_session_token
$headers = @{ 'X-Admin-Token' = $token; 'Content-Type' = 'application/json' }
$body = @{
  url='http://127.0.0.1:5173/?sidecar=http://127.0.0.1:8790'
  label='astrabridge-web-demo'
  auto_milestone=$true
  actions=@(
    @{ type='expect_text'; text='AstraBridge Demo'; timeout_ms=15000 },
    @{ type='expect_selector'; selector='.inspector-tabbar'; timeout_ms=10000 },
    @{ type='click_selector'; selector='.inspector-tabbar button:nth-child(2)'; timeout_ms=4000 },
    @{ type='wait_ms'; ms=250 },
    @{ type='click_selector'; selector='.inspector-tabbar button:nth-child(3)'; timeout_ms=4000 },
    @{ type='wait_ms'; ms=250 },
    @{ type='click_selector'; selector='.inspector-tabbar button:nth-child(4)'; timeout_ms=4000 },
    @{ type='wait_ms'; ms=250 },
    @{ type='click_selector'; selector='.inspector-tabbar button:nth-child(5)'; timeout_ms=4000 },
    @{ type='expect_selector'; selector='.inspector-file-list'; timeout_ms=8000 }
  )
} | ConvertTo-Json -Depth 8
Invoke-RestMethod http://127.0.0.1:8790/api/dogfood/browser-smoke -Method Post -Headers $headers -Body $body
```

Expected result:

- HTTP 200
- `status: pass`
- screenshot written under `.astrabridge/captures`

## Artifact Paths

- Demo root:
  `D:\AstraBridge\PRIVATE\demo-runs\<timestamp>\`
- Project file:
  `...\workspace\demo.abproj`
- Workspace state:
  `...\workspace\demo-workspace\.astrabridge\`
- Browser captures:
  `...\workspace\demo-workspace\.astrabridge\captures\`
- Dogfood ledger:
  `...\workspace\demo-workspace\.astrabridge\dogfood_run.json`

## Key Safety Rules

- Default demo mode is no-key.
- Only use environment variables or the encrypted user vault for provider secrets.
- Do not read or commit plaintext secrets from `PRIVATE/secrets/**` unless explicitly requested.
- Do not print or persist raw API keys, bearer tokens, cookies, auth headers, or raw provider secret material.
- Validation output may record `secret_loaded`, `secret_source`, and `secret_fingerprint`, but never the secret value itself.

## Optional Key-Backed Smoke

Only run this when a provider secret is already configured through env or vault and the user explicitly wants a real provider check.

- Confirm `runtime.runtime_config.secret_loaded == true`
- Prefer `/api/llm-manager/keys/test` or provider health checks
- Redact raw responses before saving any durable artifact
