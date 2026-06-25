# AstraBridge Automations Implementation Plan

Last updated: 2026-06-24

## 总目标

把当前以 Codex CLI / app-server runtime patterns 为内核的 AstraBridge 自制 app，升级为具备产品级自动化能力的本地桌面工作台。

目标不是复刻或依赖官方 Codex App 的私有实现，而是在 AstraBridge 的现有边界内实现一套可追踪、可恢复、可审计、可手动 review 的 automation layer：

- 支持用户创建、暂停、编辑、手动触发、删除定时自动化。
- 支持两类 automation：
  - `standalone`：每次调度都创建一次独立运行，适合周期性 repo 检查、报告、lint/test、changelog、依赖扫描等任务。
  - `thread`：复用或唤醒同一个 provider thread / task context，适合持续跟进同一事项、轮询反馈、长期 watch loop。
- 支持本地 workspace 运行与专用 git worktree 运行，默认优先隔离自动化改动，不污染用户当前未完成工作。
- 支持运行历史、finding / no-signal 分类、inbox / triage、失败重试、人工 review 和 promotion 到 task/thread。
- 支持最小权限默认值、secret-safe 日志、运行状态事件流、sidecar API、desktop UI 和端到端 smoke 验证。
- 与 AstraBridge 现有原则保持一致：`.abproj` + `.astrabridge/` 是正常项目状态；不把官方 Codex `~/.codex` 或项目 `.codex*` 作为正常产品路径；OpenAI 只是普通 API-key provider。

官方能力边界参考：

- Codex App 提供内建 Automations、后台定时任务、inbox/triage，以及 project-scoped automation 对本地 Codex App 运行状态和磁盘项目可用性的要求：<https://developers.openai.com/codex/app/automations>
- Codex App features 明确 automations、worktree support 和 Git functionality 是 App 侧产品能力：<https://developers.openai.com/codex/app/features>
- Codex CLI 的自动化基础主要是 `codex exec` 非交互模式，可接入脚本、CI 或外部调度器：<https://developers.openai.com/codex/noninteractive>
- `codex exec` 的 CLI flag 细节与 sandbox / approval 相关风险要以官方 reference 为准：<https://developers.openai.com/codex/cli/reference>
- 自动化运行必须尊重 sandbox 边界：<https://developers.openai.com/codex/concepts/sandboxing>

## 注意事项

- 不要假设 Codex CLI 已经提供官方 App 同款 Automations UI / inbox / scheduler。AstraBridge 需要自己实现 scheduler、run store、triage store、desktop surface 与 recovery logic；CLI 只作为可执行内核或 app-server runtime 来源。
- 不要调用未公开的官方 Codex App automation API，也不要把 AstraBridge 的状态写入官方 Codex `~/.codex/config.toml` 或项目 `.codex*`。
- 不得把 API key、Bearer token、Cookie、授权 header、vault 密码、provider raw secret 写入 git、`.abproj`、`.astrabridge/`、日志、报告、截图、run artifact 或 automation prompt snapshot。
- 自动化默认使用最小权限：默认不允许 `--dangerously-bypass-approvals-and-sandbox` / `--yolo` 等全权限模式；任何 full access 或 destructive command policy 都必须有显式 UI 选择、审计记录和醒目风险提示。
- Project-scoped automation 依赖本地 sidecar / desktop 进程可运行，且 workspace 仍在磁盘上。第一版先实现 app 内调度；OS-level launch agent / Windows Task Scheduler 可以作为后续增强，不纳入本 10 步闭环。
- 时间调度必须同时保存用户 timezone 与 UTC `next_run_at`，避免 DST、跨时区和系统时间变更导致重复运行或漏运行。
- 同一个 automation 同一时间最多一个 active run；全局 worker 数量必须有限制；stale lock / crashed run 必须可恢复。
- 专用 worktree 默认必须在 app-owned runtime root 下创建，不能在用户 workspace 内塞大体积 runtime 产物。worktree cleanup 要区分 retained-for-review 与 safe-to-delete。
- 日志和事件只保存 secret-safe 摘要；原始 stdout/stderr、model output、diff 和 artifact 需要经过 redaction / size limit 后才进入持久状态。
- 自动化触发的 git 改动不得自动 merge / push。默认只产出 reviewable diff、finding、建议命令和可手动接管的 task/thread。
- 运行失败要保留可诊断但脱敏的错误：分类如 `workspace_missing`、`scheduler_paused`、`runtime_secret_missing`、`codex_exec_failed`、`thread_not_found`、`approval_required`、`timeout`。
- 不要破坏当前 capability runtime、web lane、native-kernel、router/provider/model catalog 的已完成状态。自动化应复用已有 routing 与 runtime 配置，而不是另起一套 provider 配置系统。
- 每轮落实计划时只完成一个编号步骤。完成后必须更新本文件的“当前进度”和“完成记录”，然后停止。

## 细节

### 1. 建议新增模块与触点

Sidecar 建议新增：

- `apps/astrabridge-sidecar/astrabridge_sidecar/automations/__init__.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/automations/specs.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/automations/store.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/automations/scheduler.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/automations/workspace.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/automations/runner.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/automations/triage.py`
- `apps/astrabridge-sidecar/tests/test_automation_*.py`

Existing sidecar integration points:

- `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_config_service.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_supervisor_service.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/project_service.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/task_conversation_service.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/mcp_config_service.py`

Desktop 建议新增或扩展：

- `apps/astrabridge-desktop/src/api.ts`
- `apps/astrabridge-desktop/src/types.ts`
- `apps/astrabridge-desktop/src/App.tsx`
- `apps/astrabridge-desktop/src/features/automations/*`
- `apps/astrabridge-desktop/src/features/runtime/*` 中的 runtime/supervisor notice 与 event projection

文档与验证建议更新：

- `docs/ARCHITECTURE.md`
- `docs/SECURITY_AND_ISOLATION.md`
- `docs/DEMO_RUNBOOK.md`
- `docs/RELEASE_CHECKLIST.md`
- `docs/HANDOFF.md`
- `PLAN/AUTOMATIONS_SURFACE_MAP.md` 或同等接口映射文档

### 2. 核心数据合同草案

`AutomationSpec` 建议字段：

```text
automation_id: string
project_id: string
name: string
description: string
enabled: boolean
kind: standalone | thread
prompt: string
schedule: {
  mode: manual | interval | daily | weekly | cron
  expression: string
  timezone: string
  next_run_at: iso8601_utc
  catch_up_policy: skip_missed | run_once | run_all_limited
}
runtime: {
  profile_id: string | null
  model: string | null
  effort: string | null
  permission_mode: auto | read-only | workspace-write | full-access
  collaboration_mode: string | null
  execution_host: windows | wsl | auto
  mcp_preset_ids: string[]
}
workspace: {
  mode: current_workspace | dedicated_worktree
  base_branch: string | null
  worktree_root: string | null
  cleanup_policy: keep_on_finding | keep_on_failure | delete_on_no_signal | manual
}
triage: {
  archive_no_signal: boolean
  notify_on: finding | failure | every_run
  finding_keywords: string[]
}
limits: {
  timeout_sec: number
  max_retries: number
  max_artifact_bytes: number
  max_parallel_runs: number
}
created_at: iso8601_utc
updated_at: iso8601_utc
last_run_at: iso8601_utc | null
last_status: string | null
```

`AutomationRun` 建议字段：

```text
run_id: string
automation_id: string
project_id: string
trigger: schedule | manual | retry
status: queued | running | needs_review | completed | failed | skipped | cancelled
due_at: iso8601_utc
started_at: iso8601_utc | null
finished_at: iso8601_utc | null
thread_id: string | null
turn_id: string | null
worktree_path: string | null
runtime_profile_id: string | null
exit_code: number | null
signal: finding | no_signal | unknown
summary: string
artifact_refs: string[]
redacted_error: string | null
next_retry_at: iso8601_utc | null
```

`AutomationInboxItem` 建议字段：

```text
item_id: string
run_id: string
automation_id: string
project_id: string
state: unread | reviewed | archived | promoted
disposition: finding | no_signal | failure | approval_required
severity: info | warning | error
title: string
summary: string
created_at: iso8601_utc
updated_at: iso8601_utc
promotion_ref: string | null
```

### 3. 持久化位置

建议第一版使用 JSON 文件，后续如有并发或查询压力再迁移 SQLite：

- Workspace-visible metadata：`<workspace>/.astrabridge/automations/automations.json`
- Workspace-visible compact index：`<workspace>/.astrabridge/automations/runs/index.json`
- Large run artifacts：`%APPDATA%/AstraBridge/runtime/<project-runtime-id>/automations/<automation-id>/<run-id>/`
- Dedicated worktrees：`%APPDATA%/AstraBridge/runtime/<project-runtime-id>/automation-worktrees/<automation-id>/<run-id>/`

所有路径都必须通过 existing project/runtime root resolver 获取，不能硬编码官方 Codex state 路径。

### 4. API 草案

建议 sidecar HTTP/JSON surface：

- `GET /api/automations`
- `POST /api/automations/create`
- `POST /api/automations/update`
- `POST /api/automations/delete`
- `POST /api/automations/pause`
- `POST /api/automations/resume`
- `POST /api/automations/run-now`
- `GET /api/automations/runs?automation_id=...`
- `GET /api/automations/run?run_id=...`
- `POST /api/automations/runs/cancel`
- `GET /api/automations/inbox`
- `POST /api/automations/inbox/update`
- `POST /api/automations/inbox/promote`
- `GET /api/automations/scheduler/status`

Event stream 建议复用现有 `/api/runtime/events` 或 `/api/events/stream`，新增事件类型：

- `automation_created`
- `automation_updated`
- `automation_due`
- `automation_run_queued`
- `automation_run_started`
- `automation_run_progress`
- `automation_run_completed`
- `automation_run_failed`
- `automation_inbox_item_created`
- `automation_inbox_item_archived`
- `automation_promoted_to_task`

### 5. 运行模式

`standalone` 模式：

- 适合一次性、无长上下文依赖的周期任务。
- 优先通过 `codex exec` 或现有 native-kernel equivalent 触发非交互运行。
- 每次 run 独立记录 prompt snapshot、runtime snapshot、workspace snapshot、summary、diff/artifacts。
- 默认使用 dedicated worktree，避免影响用户当前 worktree。

`thread` 模式：

- 适合“持续关注同一事项”的长期 automation。
- 优先复用现有 `RuntimeService.start_turn(...)` 与 provider thread/task projection。
- 若 thread 缺失，按 `thread_missing_policy` 执行：`fail`、`recreate_from_task_context` 或 `ask_review`。
- 每次唤醒只发送一轮 prompt，不允许 agent 在同一轮计划外链式推进多个用户不可见步骤。

## 实现步骤

- [x] 1. 定义 automation 领域合同、状态机与第一批单元测试
  - 范围：
    - 新增 `automations/specs.py`，定义 `AutomationSpec`、`AutomationRun`、`AutomationInboxItem`、schedule、workspace、runtime、triage、limits 的 normalized dict/dataclass 合同。
    - 定义状态机允许迁移：`queued -> running -> completed/failed/needs_review/cancelled`，以及 `skipped` 的进入条件。
    - 定义 schedule expression 的最小 MVP：`manual`、`interval_minutes`、`daily HH:MM timezone`；先不实现完整 cron parser。
    - 编码 secret-safe normalization：prompt snapshot 可保存，但 header/key/env secret 必须 redacted。
  - 交付物：
    - `apps/astrabridge-sidecar/astrabridge_sidecar/automations/specs.py`
    - `apps/astrabridge-sidecar/astrabridge_sidecar/automations/__init__.py`
    - `apps/astrabridge-sidecar/tests/test_automation_specs.py`
  - 完成标准：
    - 后续步骤不再靠零散 dict 约定 automation 字段。
    - 无效 schedule、无效 status transition、危险 permission default 都有明确错误或 safe fallback。
  - 验证方式：
    - `cd apps/astrabridge-sidecar && python -B -m unittest tests/test_automation_specs.py`

- [x] 2. 实现 automation store、文件持久化与 CRUD 语义
  - 范围：
    - 新增 `automations/store.py`。
    - 在当前 project runtime/workspace resolver 基础上保存 `automations.json`、run index 和 inbox index。
    - 实现 create/list/get/update/delete/pause/resume，所有写入采用 atomic write。
    - 对删除采用 soft delete 或 archived marker，避免直接丢失 run history。
    - 加入 file lock 或 process-local lock，防止 scheduler 与 UI 同时写坏 JSON。
  - 交付物：
    - `AutomationStore`
    - 持久化目录初始化逻辑
    - CRUD 单元测试
  - 完成标准：
    - 重启 sidecar 后 automation spec、last_run、inbox summary 能从磁盘恢复。
    - store 不写入任何 secret-like value。
  - 验证方式：
    - `cd apps/astrabridge-sidecar && python -B -m unittest tests/test_automation_store.py tests/test_automation_specs.py`

- [x] 3. 实现 scheduler due calculation、claim lock 与 missed-run 策略
  - 范围：
    - 新增 `automations/scheduler.py`。
    - 实现 in-process scheduler service：启动、停止、tick、next wake-up、manual trigger、pause handling。
    - 实现 `next_run_at` 计算，保存 UTC，同时保留 timezone。
    - 实现 missed-run 策略：MVP 默认 `skip_missed`，可配置 `run_once`。
    - 同一 automation 同一时间只能 claim 一个 active run；全局 worker concurrency 有上限。
  - 交付物：
    - `AutomationScheduler`
    - due-run claiming / stale-run recovery 测试
  - 完成标准：
    - 测试可用 fake clock 稳定验证 interval/daily 调度。
    - sidecar 重启后不会重复 claim 已 running 的 run；stale running run 会按规则标记 failed 或 retryable。
  - 验证方式：
    - `cd apps/astrabridge-sidecar && python -B -m unittest tests/test_automation_scheduler.py tests/test_automation_store.py`

- [x] 4. 实现 automation workspace / git worktree isolation manager
  - 范围：
    - 新增 `automations/workspace.py`。
    - 支持 `current_workspace` 与 `dedicated_worktree` 两种 workspace mode。
    - 对 git repo 检测、base branch、dirty workspace、worktree 创建、worktree path 记录、cleanup policy 做显式处理。
    - 所有 worktree / artifact root 默认落在 app-owned runtime root，不能污染用户 workspace。
    - 对非 git workspace 提供 graceful fallback：只能 current_workspace 或报 `git_required_for_worktree`。
  - 交付物：
    - `AutomationWorkspaceManager`
    - worktree lifecycle tests
  - 完成标准：
    - 可创建和定位专用 worktree；run 完成后按 no-signal/finding/failure 决定保留或清理。
    - dirty user workspace 不阻塞 dedicated worktree run，但会阻塞 current_workspace destructive run。
  - 验证方式：
    - `cd apps/astrabridge-sidecar && python -B -m unittest tests/test_automation_workspace.py tests/test_automation_scheduler.py`

- [x] 5. 实现 runner 执行层：standalone `codex exec` 与 thread wake-up adapter
  - 范围：
    - 新增 `automations/runner.py`。
    - `standalone`：封装 `codex exec` / non-interactive equivalent，注入 isolated `CODEX_HOME`、provider env、workspace cwd、timeout、permission profile、MCP preset。
    - `thread`：复用 `RuntimeService.start_turn(...)`，把 automation prompt 作为单轮 turn 发送到目标 thread；处理 thread missing / runtime not configured。
    - runner 不直接决定 triage，只返回 normalized run result、redacted stdout/stderr summary、artifact refs、diff refs。
    - 禁止默认传入 yolo/full-access；危险权限必须来自已保存且 UI 明示过的 spec。
  - 交付物：
    - `AutomationRunner`
    - fake subprocess / fake runtime tests
  - 完成标准：
    - 可以在测试中模拟 standalone 成功、失败、timeout、thread wake-up 成功、thread missing。
    - 运行结果不包含 raw secret-like token。
  - 验证方式：
    - `cd apps/astrabridge-sidecar && python -B -m unittest tests/test_automation_runner.py tests/test_automation_workspace.py tests/test_automation_scheduler.py`

- [x] 6. 实现 run lifecycle、finding/no-signal 分类与 inbox/triage store
  - 范围：
    - 新增 `automations/triage.py` 或在 store 中增加 triage 子服务。
    - 将 runner result 转为 `AutomationRun` final state 与 `AutomationInboxItem`。
    - 实现 `archive_no_signal`：无发现自动归档；finding/failure/approval_required 进入 inbox。
    - 实现 promotion metadata：inbox item 可 promoted 到现有 task/thread 或 review entry，但本步骤只打通后端状态，不做 UI。
    - 实现 artifact manifest：summary、diff、stdout/stderr excerpt、exit status、workspace refs；全部 redacted + size limited。
  - 交付物：
    - run finalization service
    - inbox list/update/promote backend primitives
    - triage tests
  - 完成标准：
    - no-signal run 可自动 archived；finding/failure 会出现 unread inbox item。
    - run history 与 inbox 状态能跨重启恢复。
  - 验证方式：
    - `cd apps/astrabridge-sidecar && python -B -m unittest tests/test_automation_triage.py tests/test_automation_runner.py tests/test_automation_store.py`

- [x] 7. 暴露 sidecar Automations API、事件流与 supervisor/status 集成
  - 范围：
    - 在 `server.py` 注册 automation routes。
    - 在 sidecar context 初始化 store/scheduler/runner/triage，并随 sidecar 生命周期启动/停止 scheduler。
    - API 覆盖 create/update/delete/pause/resume/run-now/list runs/read run/inbox update/promote/scheduler status。
    - 将 automation events 写入现有 runtime event log 或 events stream。
    - Supervisor/status 中增加 automation worker、active runs、last failure、next due summary。
  - 交付物：
    - HTTP/JSON routes
    - context wiring
    - API tests
  - 完成标准：
    - 不打开 desktop UI，也能通过 API 完成创建 automation、run-now、查看 run history、查看 inbox。
    - sidecar health/status 能显示 scheduler 是否 active。
  - 验证方式：
    - `cd apps/astrabridge-sidecar && python -B -m unittest tests/test_automation_api.py tests/test_automation_triage.py`

- [x] 8. 实现 desktop Automations UI 与类型/API 客户端
  - 范围：
    - 在 `api.ts` 与 `types.ts` 增加 automation 类型和 API client。
    - 新增 Automations 页面/面板：list、create/edit form、schedule editor、runtime/profile selector、workspace mode selector、pause/resume、run now。
    - 新增 Inbox/Triage 面板：unread finding/failure、no-signal archived、run detail、artifact/diff links、promote/mark reviewed。
    - UI 必须显示安全提示：权限、worktree mode、secret-safe logging、可能产生 token/cost。
    - 复用现有 i18n catalog 风格，不硬编码大段英文 UI 文案。
  - 交付物：
    - `apps/astrabridge-desktop/src/features/automations/*`
    - API/type updates
    - UI unit tests
  - 完成标准：
    - 用户可从 desktop 创建一个 manual/interval automation 并手动触发。
    - Inbox 可查看 run 结果并 archive/promote。
  - 验证方式：
    - `cd apps/astrabridge-desktop && node ./node_modules/vitest/vitest.mjs run src/features/automations`
    - `cd apps/astrabridge-desktop && node ./node_modules/typescript/bin/tsc --noEmit`

- [x] 9. 补齐安全、权限、恢复、并发和成本控制硬化
  - 范围：
    - 增加 permission policy guard：危险权限需显式确认；自动化默认 workspace-write/read-only，不默认 full-access。
    - 增加 redaction tests，覆盖 env、headers、provider keys、URLs 中 token、stdout/stderr 摘要。
    - 增加 timeout/retry/backoff、cancel、stale run recovery、worker crash recovery。
    - 增加 provider quota/cost guard：可配置每日/每 automation 最大 run 次数。
    - 增加 worktree cleanup guard：保留 finding/failure worktree，no-signal 可自动删。
    - 与 release checklist/security doc 对齐。
  - 交付物：
    - policy guard code
    - recovery tests
    - security doc updates
  - 完成标准：
    - 自动化不能在无显式 opt-in 情况下绕过 sandbox/approval。
    - 崩溃/重启/timeout 后 run 状态可解释、可恢复、不会无限重复消耗。
  - 验证方式：
    - `cd apps/astrabridge-sidecar && python -B -m unittest tests/test_automation_security.py tests/test_automation_scheduler.py tests/test_automation_runner.py`
    - `cd apps/astrabridge-desktop && node ./node_modules/typescript/bin/tsc --noEmit`

- [x] 10. 完成端到端 smoke、文档收尾与 release gate
  - 范围：
    - 增加 automation smoke script 或 runbook：创建 manual automation、run-now、产生 no-signal、产生 finding、进入 inbox、archive/promote。
    - 更新 `docs/ARCHITECTURE.md`、`docs/SECURITY_AND_ISOLATION.md`、`docs/DEMO_RUNBOOK.md`、`docs/RELEASE_CHECKLIST.md`、`docs/HANDOFF.md`。
    - 新增 surface map：记录 sidecar routes、desktop panels、event types、storage paths、legacy/non-goal 边界。
    - 执行 secret scan / legacy path scan / doc link sanity check。
    - 保存脱敏验证产物到允许路径；不要把 `PRIVATE/**` 非白名单文件 staged。
  - 交付物：
    - smoke matrix / runbook
    - updated docs
    - final implementation summary
  - 完成标准：
    - 用户可用 desktop 完成 automation 全流程。
    - Sidecar API、desktop UI、scheduler、runner、triage、security docs 全部一致。
    - 当前计划文件标记 `10 / 10` 完成，并写明后续增强不属于本闭环。
  - 验证方式：
    - `cd apps/astrabridge-sidecar && python -B -m unittest discover -s tests`
    - `cd apps/astrabridge-desktop && node ./node_modules/vitest/vitest.mjs run`
    - `cd apps/astrabridge-desktop && node ./node_modules/typescript/bin/tsc --noEmit`
    - 按 `docs/DEMO_RUNBOOK.md` 完成 automation smoke，并记录脱敏结果。

## 当前进度

- 当前阶段：`step_10_completed`
- 已完成步骤：`10 / 10`
- 下一步入口：`complete`
- 下一轮 agent 执行规则：
  1. 打开本文件，读取“当前进度”的“下一步入口”。
  2. 只完成对应的一个编号步骤，不要顺手推进下一步。
  3. 完成后运行该步骤列出的验证命令；如果验证不能运行，记录原因和替代检查。
  4. 更新“实现步骤”中的 checkbox、更新“当前进度”的已完成步骤和下一步入口。
  5. 在“完成记录”追加日期、完成的步骤编号、核心文件、验证结果、遗留 blocker。
  6. 停止并向用户汇报；下一轮从新的下一步入口继续。
- 当前结论：
  - 官方 Codex App 的 Automations 是 app 侧产品能力；AstraBridge 需要实现自己的 scheduler、run history、inbox/triage 和 UI。
  - Codex CLI 的 `codex exec` 是 standalone automation 的合适执行内核，但不是完整 Automations 产品层。
  - 现有 AstraBridge sidecar 已有 runtime、project、task、router、capability、event stream、desktop API 基础，适合在 sidecar 内新增 automation layer。
  - 步骤 1-8 已完成：sidecar 已具备 automations 领域合同、store、scheduler、workspace isolation、runner、triage、API 与 supervisor/status 集成；desktop 已具备 Automations 设置页、创建/编辑表单、run history、inbox/triage 面板以及对应的类型与 API 客户端。

## 完成记录

- 2026-06-24：创建本计划文件，锁定 10 步执行顺序；当前实现进度为 `0 / 10`，下一轮从步骤 `1` 开始。
- 2026-06-24：完成步骤 `1`（automation 领域合同、状态机与第一批单元测试）；核心文件：`apps/astrabridge-sidecar/astrabridge_sidecar/automations/specs.py`、`apps/astrabridge-sidecar/astrabridge_sidecar/automations/__init__.py`、`apps/astrabridge-sidecar/tests/test_automation_specs.py`；验证结果：`cd apps/astrabridge-sidecar && python -B -m unittest tests/test_automation_specs.py` 通过（`Ran 6 tests`, `OK`）；遗留 blocker：无；下一轮从步骤 `2` 开始。
- 2026-06-24：完成步骤 `2`（automation store、文件持久化与 CRUD 语义）；核心文件：`apps/astrabridge-sidecar/astrabridge_sidecar/automations/store.py`、`apps/astrabridge-sidecar/astrabridge_sidecar/automations/__init__.py`、`apps/astrabridge-sidecar/tests/test_automation_store.py`；验证结果：`cd apps/astrabridge-sidecar && python -B -m unittest tests/test_automation_store.py tests/test_automation_specs.py` 通过（`Ran 8 tests`, `OK`）；遗留 blocker：无；下一轮从步骤 `3` 开始。
- 2026-06-24：完成步骤 `3`（scheduler due calculation、claim lock 与 missed-run 策略）；核心文件：`apps/astrabridge-sidecar/astrabridge_sidecar/automations/scheduler.py`、`apps/astrabridge-sidecar/astrabridge_sidecar/automations/__init__.py`、`apps/astrabridge-sidecar/tests/test_automation_scheduler.py`；验证结果：`cd apps/astrabridge-sidecar && python -B -m unittest tests/test_automation_scheduler.py tests/test_automation_store.py` 通过（`Ran 6 tests`, `OK`）；遗留 blocker：无；下一轮从步骤 `4` 开始。
- 2026-06-24：完成步骤 `4`（automation workspace / git worktree isolation manager）；核心文件：`apps/astrabridge-sidecar/astrabridge_sidecar/automations/workspace.py`、`apps/astrabridge-sidecar/astrabridge_sidecar/automations/__init__.py`、`apps/astrabridge-sidecar/tests/test_automation_workspace.py`；验证结果：`cd apps/astrabridge-sidecar && python -B -m unittest tests/test_automation_workspace.py tests/test_automation_scheduler.py` 通过（`Ran 7 tests`, `OK`）；遗留 blocker：无；下一轮从步骤 `5` 开始。
- 2026-06-24：完成步骤 `5`（runner 执行层：standalone codex exec 与 thread wake-up adapter）；核心文件：`apps/astrabridge-sidecar/astrabridge_sidecar/automations/runner.py`、`apps/astrabridge-sidecar/astrabridge_sidecar/automations/__init__.py`、`apps/astrabridge-sidecar/tests/test_automation_runner.py`；验证结果：`cd apps/astrabridge-sidecar && python -B -m unittest tests/test_automation_runner.py tests/test_automation_workspace.py tests/test_automation_scheduler.py` 通过（`Ran 10 tests`, `OK`）；遗留 blocker：无；下一轮从步骤 `6` 开始。
- 2026-06-24：完成步骤 `6`（run lifecycle、finding/no-signal 分类与 inbox/triage store）；核心文件：`apps/astrabridge-sidecar/astrabridge_sidecar/automations/triage.py`、`apps/astrabridge-sidecar/astrabridge_sidecar/automations/store.py`、`apps/astrabridge-sidecar/astrabridge_sidecar/automations/runner.py`、`apps/astrabridge-sidecar/astrabridge_sidecar/automations/__init__.py`、`apps/astrabridge-sidecar/tests/test_automation_triage.py`；验证结果：`cd apps/astrabridge-sidecar && python -B -m unittest tests/test_automation_triage.py tests/test_automation_runner.py tests/test_automation_store.py` 通过（`Ran 8 tests`, `OK`）；遗留 blocker：无；下一轮从步骤 `7` 开始。
- 2026-06-24：完成步骤 `7`（sidecar Automations API、事件流与 supervisor/status 集成）；核心文件：`apps/astrabridge-sidecar/astrabridge_sidecar/automations/service.py`、`apps/astrabridge-sidecar/astrabridge_sidecar/automations/__init__.py`、`apps/astrabridge-sidecar/astrabridge_sidecar/server.py`、`apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`、`apps/astrabridge-sidecar/astrabridge_sidecar/runtime_supervisor_service.py`、`apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/runtime.py`、`apps/astrabridge-sidecar/tests/test_automation_api.py`；验证结果：`cd apps/astrabridge-sidecar && python -B -m unittest tests/test_automation_api.py tests/test_automation_triage.py` 通过（`Ran 5 tests`, `OK`）；遗留 blocker：无；下一轮从步骤 `8` 开始。
- 2026-06-24：完成步骤 `8`（desktop Automations UI 与类型/API 客户端）；核心文件：`apps/astrabridge-desktop/src/features/automations/AutomationsPanel.tsx`、`apps/astrabridge-desktop/src/features/automations/AutomationsPanel.test.tsx`、`apps/astrabridge-desktop/src/api.ts`、`apps/astrabridge-desktop/src/types.ts`、`apps/astrabridge-desktop/src/App.tsx`、`apps/astrabridge-desktop/src/features/i18n/catalog.ts`、`apps/astrabridge-desktop/src/styles.css`；验证结果：`cd apps/astrabridge-desktop && node ./node_modules/vitest/vitest.mjs run src/features/automations` 通过（`1` 个测试文件，`2` 个测试通过），`cd apps/astrabridge-desktop && node ./node_modules/typescript/bin/tsc --noEmit` 通过；遗留 blocker：无；下一轮从步骤 `9` 开始。
- 2026-06-24：完成步骤 `9`（安全、权限、恢复、并发和成本控制硬化）；核心文件：`apps/astrabridge-sidecar/astrabridge_sidecar/automations/runner.py`、`apps/astrabridge-sidecar/astrabridge_sidecar/automations/scheduler.py`、`apps/astrabridge-sidecar/astrabridge_sidecar/automations/specs.py`、`apps/astrabridge-sidecar/astrabridge_sidecar/automations/triage.py`、`apps/astrabridge-sidecar/astrabridge_sidecar/security.py`、`apps/astrabridge-sidecar/tests/test_automation_security.py`、`apps/astrabridge-sidecar/tests/test_automation_scheduler.py`、`docs/SECURITY_AND_ISOLATION.md`、`docs/RELEASE_CHECKLIST.md`；验证结果：`cd apps/astrabridge-sidecar && python -B -m unittest tests/test_automation_security.py tests/test_automation_scheduler.py tests/test_automation_runner.py` 通过（`Ran 10 tests`, `OK`），`cd apps/astrabridge-desktop && node ./node_modules/typescript/bin/tsc --noEmit` 通过；遗留 blocker：无；下一轮从步骤 `10` 开始。
- 2026-06-25: Completed step `10` (end-to-end automation smoke, docs closeout, release gate). Core files: `scripts/run_automation_smoke.py`, `PLAN/AUTOMATIONS_SURFACE_MAP.md`, `docs/ARCHITECTURE.md`, `docs/SECURITY_AND_ISOLATION.md`, `docs/DEMO_RUNBOOK.md`, `docs/RELEASE_CHECKLIST.md`, `docs/HANDOFF.md`. Validation: sidecar `python -B -m unittest discover -s tests` passed (`Ran 392 tests`, `OK`); desktop `node ./node_modules/vitest/vitest.mjs run` passed (`15` files, `68` tests); desktop `node ./node_modules/typescript/bin/tsc --noEmit` passed; `python ./scripts/run_automation_smoke.py` passed; secret scan, legacy scan, and doc link sanity check executed; sanitized evidence saved under `PRIVATE/demo-runs/automation-smoke-*`. Blockers: none. This 10-step loop is complete.
