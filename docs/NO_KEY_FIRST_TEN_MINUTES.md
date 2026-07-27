# AstraBridge No-Key First Ten Minutes

Status: deterministic no-provider onboarding route; an exact-source
clean-clone proof is recorded for local canonical revision
`c8988fef6f1139ac056fadb68e395122ee59254a`. It is not a release-installer or
provider-compatibility claim.

Last verified: 2026-07-27

## What This Path Proves

This document specifies the Windows PowerShell path for reaching an inspectable
project, task, permission boundary, task graph, and fixture artifacts without
a provider account or provider credential. It deliberately does **not** run a
model request, tool call, or paid provider smoke.

The first useful state is a local `Project -> Task` workspace with a
`Supervisor / Worker / Synthesizer` graph and a completed fixture run. The
fixture route is deterministic and remains separate from any future
provider-backed coding-agent proof. A fresh, isolated virtual environment for
the current source checkout imports the sidecar and passes the focused source
registry/catalog tests. A clean clone of local canonical revision
`c8988fef6f1139ac056fadb68e395122ee59254a` includes this documentation,
installed its declared sidecar dependencies, started from that virtual
environment, and completed the browser fixture. That is exact-source
deterministic onboarding evidence, not a claim about a distributed installer
or any live provider route.

## Prerequisites

- A source revision that includes the sidecar's current runtime dependency
  manifest, including `jsonschema`. The recorded source-clone evidence is for
  local canonical revision `c8988fef6f1139ac056fadb68e395122ee59254a`.
- Windows PowerShell, Python 3.11+, Node.js 22+, and npm available as
  `npm.cmd`.
- No configured provider key and no provider credential exported into the
  shell that starts the sidecar. If the shell already contains one, start a
  fresh shell without it.

The 2026-07-27 evidence run used Windows, Python `3.11.15`, Node
`v22.23.0`, npm `10.9.8`, and Git `2.51.1.windows.1`.

## 1. Clone And Install

Replace the placeholder with the repository URL or owner-approved mirror that
contains this document and the current runtime dependency manifest.

```powershell
git clone <AstraBridge-repository-url> AstraBridge
Set-Location AstraBridge\apps\astrabridge-desktop
npm.cmd ci --no-audit --no-fund
```

For the preserved exact-source validation, use the canonical branch or commit
made available by the project owner; the evidence revision is
`c8988fef6f1139ac056fadb68e395122ee59254a`.

`npm.cmd` is intentional: on the validated Windows PowerShell environment,
the `npm.ps1` shim was blocked by execution policy while `npm.cmd` worked.

## 2. Start An Isolated Sidecar

Open a PowerShell window at the repository root. The three redirected roots
keep the demonstration's application, runtime, and Codex-compatible state out
of ordinary user locations.

```powershell
$repo = (Resolve-Path .).Path
$runRoot = Join-Path $repo 'PRIVATE\demo-runs\no-key-first-ten-minutes'
New-Item -ItemType Directory -Force -Path `
  (Join-Path $runRoot 'AppData'), `
  (Join-Path $runRoot 'Runtime'), `
  (Join-Path $runRoot 'CodexHome'), `
  (Join-Path $runRoot 'workspace') | Out-Null

$env:ASTRABRIDGE_APPDATA = Join-Path $runRoot 'AppData'
$env:ASTRABRIDGE_RUNTIME_ROOT = Join-Path $runRoot 'Runtime'
$env:ASTRABRIDGE_CODEX_HOME = Join-Path $runRoot 'CodexHome'
$env:PYTHONDONTWRITEBYTECODE = '1'

Set-Location (Join-Path $repo 'apps\astrabridge-sidecar')
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --disable-pip-version-check --no-input -e .
& .\.venv\Scripts\python.exe -m astrabridge_sidecar.server --serve --port 8826 --seed-root $repo
```

Leave that process running. `http://127.0.0.1:8826/health` should return HTTP
200 before proceeding.

## 3. Start The Desktop Dev Server

In a second PowerShell window, from the same clone:

```powershell
$repo = (Resolve-Path .).Path
Set-Location (Join-Path $repo 'apps\astrabridge-desktop')
npm.cmd run dev
```

For this validated browser path, keep the standard pairing of Desktop
`127.0.0.1:4181` and sidecar `127.0.0.1:8826`. A custom browser origin needs
corresponding sidecar CORS work and is not part of this no-key guide.

## 4. Create The Fixture-Backed Beginner Project

Paste this URL in a browser address bar:

```text
http://127.0.0.1:4181/?astrabridge_launch=dogfood&sidecar=http%3A%2F%2F127.0.0.1%3A8826&smoke=1
```

Then:

1. Create an empty project named `AstraBridge No-Key Starter`.
2. Use `<runRoot>\workspace\astrabridge-no-key.abproj` for the project file
   and `<runRoot>\workspace` for the workspace.
3. Confirm the project uses `.abproj` and workspace-local `.astrabridge/`
   state.
4. Leave the provider banner in its expected no-key/review-only state; do not
   add a credential or use **Direct Run**.
5. Open **Task Graph**, select **Template**, choose
   **Supervisor / Worker / Synthesizer**, and select **Instantiate template**.
6. Select **Fixture Run**, then open the run inspector.

The expected result is three completed workers, two visible graph edges
(`Context` and `Artifact`), and a run inspector that reports 22 artifacts.
The durable output is retained under
`<runRoot>\workspace\PRIVATE\task-graph\fixture-run\`.

## Evidence And Limits

The Desktop dependency portion of the first local-clone evidence run completed
`npm.cmd ci` in 21 seconds. The browser fixture interaction from first ready
launcher to fixture completion was under two minutes, and the browser
request-host audit contained only `127.0.0.1`; no provider host was contacted.

The original browser fixture used a global Python sidecar process, so it is
preserved as UI/fixture evidence rather than as clean-clone package proof. A
subsequent pristine-clone virtual-environment check failed before server launch
because `jsonschema` was absent from the default committed runtime dependency
manifest. The local candidate revision named above repaired that dependency,
then passed `npm.cmd ci`, the 91 focused task-graph tests, a production build,
editable sidecar installation, `pip check`, and the full browser fixture with
3 workers and 22 artifacts. Browser requests and the listener connection audit
were loopback-only.

The route is proven for the exact source revision above, but it is not a
published release installer. Repeat it for any distributed release artifact
before making an installer or broad public fresh-install claim.

The preserved, secret-free evidence is under
`PRIVATE/open-source-productization/reports/step3-no-key-onboarding-20260727.md`
and `output/playwright/open-source-productization-step3-20260727/`.

This evidence does not verify a public release installer, provider metadata
freshness, a live model response, model reasoning, tool calling, or coding
route authority. Follow the provider compatibility runbook and obtain explicit
credential authorization before attempting any provider-backed smoke.
