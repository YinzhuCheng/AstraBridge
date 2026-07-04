# AstraBridge App Hardening Execution Plan

## 总目标

用 20 轮顺序执行的方式，对 AstraBridge app、sidecar、runtime、UI 监督面板、provider 路由、自动化、插件/MCP、多模态、artifact 和审计链路做系统性加固。

本计划不是第二轮 dogfood benchmark，不追求让 agent 长线完成复杂任务，也不做大规模真实 token 消耗。目标是把第一轮 dogfood 暴露出的脆弱点转化为产品级硬化：状态机更稳定、错误更可恢复、UI 更可解释、证据更完整、真实 provider smoke 更可控、用户更容易判断系统正在做什么。

核心产出：

- 一套 app hardening 执行记录，覆盖状态流、runtime/provider contract、UI/UX、自动化恢复、多模态、插件/MCP、artifact/media、安全脱敏和 token/cost 记账。
- 每轮至少一个可验证的产品加固结果：代码修复、测试、诊断报告、截图复核或明确的未修复风险。
- 一条轻量真实 smoke 链路：仅在必要时使用少量真实 provider token 验证修复效果，禁止长线 agent 任务。
- 可继续扩展的第二轮/第三轮加固入口，而不是一次性备忘录。

## 注意事项

- 本计划不是 dogfood benchmark。不要让 AstraBridge agent 运行长线任务，不要用大量 token 让 agent 自行探索。
- 允许少量真实 API 调用验证修复效果，例如 1 到 2 个短 prompt、router health、vision smoke 或 image/media endpoint smoke；每次都必须记录 provider、model、用途、粗略 token/费用信号和脱敏结果。
- 禁止保存 API keys、bearer tokens、cookies、authorization headers、vault passwords、admin tokens 或 provider raw secrets。所有报告和日志必须脱敏。
- 默认保留实验产物，不清理 `PRIVATE/**`、截图、raw summary、validation report、cache、demo run 或中间文件，除非用户明确点名要求清理目标。
- 每轮都要考虑是否需要 in-app browser 或 Playwright 截图。只要涉及 UI/UX、状态面板、错误提示、artifact 预览、自动化 history、provider 状态或用户可见证据，必须截图复核。
- 如果截图发现 UI 不美观、文字溢出、布局拥挤、状态误导、空态不清、按钮语义不准或错误信息不可行动，应在同一步内修复并复测截图。
- 每轮对话只完成一个完整编号步骤。完成后必须更新“当前进度”和“完成记录”，写清下一步入口。
- 后续 agent 必须从“当前进度”里已完成步骤的下一步开始，除非用户明确要求跳转。
- 允许根据实施情况动态调整本计划的细节、顺序和验证标准，但不能降低目标：加固 AstraBridge 的稳定性、可恢复性、可解释性和 UI/UX 监督质量。
- 任何 commit/push 路径前都必须重新做 secret scan，并确保 `PRIVATE/**` 中原始 artifact 不被误 staging，除非用户明确要求。

## 细节

### 加固范围

- 状态机与投影：project、task、thread、provider thread、runtime session、automation run、inbox、artifact 的状态一致性。
- Runtime/provider contract：model catalog、capability metadata、reasoning effort、tool schema、apply patch metadata、token/cost usage、health signal。
- UI/UX 监督：left nav、settings/provider/API key/model views、runtime inspector、browser inspector、capability panels、automation panels、artifact previews、error/empty/loading states。
- 自动化恢复：run finalization、watchdog、cancel/recover、artifact/inbox、interrupted run、success path、失败诊断。
- 多模态与 artifact：chat attachment、vision route、image generation、media endpoint、path allowlist、preview layout。
- 插件/MCP：registry refresh、install/approval state、skill enablement、tool discovery、argument/result/error surfacing。
- 安全与审计：redaction、secret scan、raw summary schema、screenshot risk review、durable report shape。

### 产物路径

- 私有加固产物：`PRIVATE/app-hardening/`
- 截图：`PRIVATE/app-hardening/screenshots/`
- 脱敏 raw summary：`PRIVATE/app-hardening/raw/`
- 每轮报告：`PRIVATE/app-hardening/reports/`
- 可提交总结：按需要新增或更新 `docs/APP_HARDENING_EVIDENCE.md`

### 每轮完成标准

每个编号步骤完成前至少满足：

- 已完成该步骤定义的加固、修复或审计。
- 已运行与风险相称的测试、类型检查、py_compile、API smoke 或 UI 截图验证。
- 如使用真实 provider/API，已记录脱敏 provider/model、用途、结果和 token/费用信号；不得保存 raw secret。
- 如涉及 UI，已保存截图并检查布局、文本、状态、空态、错误态和响应式风险。
- 已保存或更新必要报告。
- 已更新本计划“当前进度”和“完成记录”，明确下一步入口。

## 实现步骤

1. 建立 app hardening 运行目录和报告模板。
   - 创建 `PRIVATE/app-hardening/screenshots/`、`raw/`、`reports/`、`validations/`。
   - 定义单轮 hardening report 字段：step_id、surface、risk_class、changes、tests、screenshots、real_api_used、token_signal、redaction_status、remaining_risk、next_entry。
   - 生成空白模板 JSON/Markdown，并验证没有 secret 字段。

2. 做当前 app 基线 UI/状态截图。
   - 用 in-app browser 打开当前 AstraBridge app，覆盖设置、provider/API key、模型、runtime inspector、capability、automation、artifact 相关入口。
   - 记录 sidecar URL、app-managed/current-source 状态、managed session 脱敏状态、可见 provider/model/automation 状态。
   - 验证：生成基线报告，列出明显 UI/UX 风险和本轮加固优先级。

3. 梳理并固化核心状态机不变量。
   - 建立 project/task/thread/provider thread/runtime/automation/inbox/artifact 的状态关系清单。
   - 找出第一轮 dogfood 中出现过的错配：旧 task 恢复、空 conversation、handoff 上下文、automation stuck running。
   - 验证：新增或更新一份状态不变量文档/测试清单，并明确后续步骤引用它。

4. 加固 task/thread/provider thread 恢复路径。
   - 增加或强化 sidecar 回归测试，覆盖切换 runtime thread、恢复 owning task、provider handoff 后 active thread、missing fallback。
   - 检查桌面端 query invalidation 是否覆盖 project、tasks、conversation、thread、goal、inspector。
   - 验证：相关 tests 通过；如涉及 UI，截图确认不会显示错误空态。

5. 加固 conversation 终态、空态和错误态。
   - 统一 completed/error/cancelled/interrupted/empty/renderable 的判定。
   - 确保 API 有内容但 UI 不可渲染时显示可行动诊断，而不是误导性空态。
   - 验证：单测覆盖空 conversation fallback、error state、stale systemError；截图复核聊天区和 inspector。

6. 加固 runtime/provider capability contract。
   - 审计 model catalog 生成字段：reasoning effort、tool schema、apply_patch_tool_type、web_search、vision、parallel tools、MCP、token usage。
   - 为 provider-specific metadata 和 Codex runtime metadata 建立明确映射/验证。
   - 验证：新增 contract tests；必要时用 1 个短 provider health prompt 做真实 smoke。

7. 统一 provider health、router preview 和 token/cost 记录。
   - 梳理文本、vision、image、web、automation runtime 的 usage 暴露方式。
   - 加固报告字段，让不可用 usage 明确写 `not_available` 和原因，而不是空白。
   - 验证：运行本地测试；可选 1 到 2 个短真实 provider smoke，记录脱敏 token signal。

8. 加固 sidecar 启动、端口归属和 current-source 验证。
   - 解决 app-managed sidecar 和当前源码 sidecar 在报告中混淆的问题。
   - 增加诊断：sidecar origin、pid、command line、source root、port owner、launcher mode。
   - 验证：API/status 和 UI 能显示或报告 sidecar provenance；截图或 raw summary 证明 current-source 与 app-managed 可区分。

9. 建立标准 UI screenshot QA checklist 并接入报告。
   - 定义截图检查项：溢出、截断、空态、loading、错误态、路径可读性、provider/runtime label、按钮语义、窄屏布局。
   - 更新 hardening report 模板，要求 UI 步骤填 checklist。
   - 验证：对现有一个 UI surface 运行 checklist 并保存截图。

10. 加固 runtime/browser inspector evidence UI。
    - 检查 runtime inspector、browser inspector、task report、console/request counters、screenshot path、provider label 的可读性。
    - 修复窄面板、长路径、状态徽标、错误提示和 loading 语义问题。
    - 验证：in-app browser 截图复测 desktop/narrow viewport，确认无明显溢出。

11. 加固多模态 chat attachment 路径。
    - 针对普通聊天附件路径，补齐上传/引用/路由/timeout/final-answer/error 诊断。
    - 避免图片 prompt 卡住时用户不知道是模型、路由、文件还是 agent 问题。
    - 验证：优先用本地 fixture 和 mock；必要时用 1 个短 vision smoke 验证，不执行长线 agent 任务。

12. 加固 artifact/media preview 与路径安全。
    - 覆盖 generated image、vision summary、PDF/markdown、workspace absolute path、`.astrabridge/assets` allowlist、media endpoint。
    - 修复 preview frame、长文本、文件名、MIME、绝对路径和安全错误提示。
    - 验证：API tests + UI 截图；不得暴露本地敏感路径外的内容。

13. 加固 Web lane 证据与失败恢复。
    - 强化 pinned-source、broad-search、fetch failure、cache hit、source_origin、citation/date 展示。
    - 确保用户能区分“已抓取来源包”和“模型综合研究结论”。
    - 验证：使用低成本固定公共 URL fetch，不做长线联网 agent 任务；截图结果页。

14. 加固插件/技能 registry、审批和启用状态。
    - 覆盖 discovery、install pending approval、enabled/disabled/effective disabled、registry refresh、fixture status。
    - 修复 UI/API 状态不一致、长期 loading、禁用原因不清楚的问题。
    - 验证：fixture tests + in-app browser 截图；不自动安装外部插件，除非用户明确批准。

15. 加固 MCP 工具发现、参数错误和结果展示。
    - 覆盖 missing tool、schema error、successful deterministic call、large result truncation、UI/report surfacing。
    - 确保错误可行动，结果可复盘，参数脱敏。
    - 验证：本地 MCP fixture 或低风险工具调用；截图 MCP 状态和结果。

16. 加固 automation 成功路径 finalization。
    - 针对成功 run 设计短 fixture，确保 final agent message、artifact、run history、inbox/无 inbox、status 都一致。
    - 避免长线 agent；优先 mock/fixture，必要时 1 个短真实 prompt。
    - 验证：automation tests + UI 截图 run history/detail。

17. 加固 automation stuck/interrupted watchdog。
    - 强化 running run 超时、进程重启、cancel、recover、artifact/inbox、diagnostic reason。
    - 确保用户能从 UI 看懂为什么 run 被恢复为 failed/cancelled/interrupted。
    - 验证：注入 fixture state，API 和 UI 均显示可复盘结果。

18. 加固安全脱敏和 artifact retention 审计。
    - 审计 report/raw/screenshot 产物中可能出现 secret、header、cookie、password、token、desktop key path 泄漏的场景。
    - 强化 redaction helper、secret scan 命令和 commit 前 checklist。
    - 验证：对 `PRIVATE/app-hardening/` 和本轮公开文档运行 secret scan；记录结果。

19. 做跨 surface UI/UX polish sweep。
    - 用 checklist 扫设置、provider/API key、模型、runtime、capabilities、plugins/MCP、automation、artifact、browser inspector。
    - 每个 surface 至少记录 pass/issue/fix/remaining risk。
    - 验证：保存截图索引和 UI polish report；修复本轮发现的高影响视觉或状态问题。

20. 汇总 app hardening 第一轮结论并制定下一轮入口。
    - 汇总完成步骤、修复主题、测试覆盖、截图索引、真实 token 消耗、剩余风险和下一轮建议。
    - 更新或新增 `docs/APP_HARDENING_EVIDENCE.md`。
    - 验证：本计划当前进度标为 20/20，所有报告可解析，公开文档脱敏，下一轮入口清晰。

## 当前进度

- 当前已完成步骤：20/20
- 下一步入口：第一轮已完成；如继续做第二轮，默认从“设置凭据与 managed-user 登录 hardening”开始，除非用户明确重定向。
- 当前状态说明：已完成步骤 20，汇总 app hardening 第一轮结论并制定下一轮入口。已新增 `docs/APP_HARDENING_EVIDENCE.md` 作为公开摘要入口，汇总 20/20 步完成状态、19 份私有 round report、20 份 validation artifact、42 张被 round report 引用的截图、剩余风险和下一轮建议；同时新增 `PRIVATE/app-hardening/reports/step20-hardening-round-summary.json` 与 `.md` 以及 `PRIVATE/app-hardening/validations/step20-hardening-round-summary-validation.json`，对 `PRIVATE/app-hardening/reports/*.json` 和 `PRIVATE/app-hardening/validations/*.json` 做全量 JSON 可解析校验，并重新通过 `python .\scripts\app_hardening_secret_scan.py --repo .`、`python .\scripts\run_local_gate.py --quick` 和 `git diff --check`。第一轮未调用真实 provider，provider token 总消耗为 0；下一轮默认入口为：1) 设置凭据与 managed-user 登录加固；2) browser workbench session 生命周期与移动端入口策略收敛；3) runtime warning 密度与状态优先级清理；4) 将本地 quick gate 推进为 release-oriented engineering gate。
- 动态调整状态：允许后续 agent 根据实际加固情况调整步骤细节，但必须保留“不做长线 dogfood、少量真实 token smoke、频繁截图检查 UI/UX、逐步加固 app 健壮性”的目标。

## 完成记录

- 2026-06-27：创建本计划。下一步从步骤 1 开始。
- 2026-06-27：完成步骤 1，创建 `PRIVATE/app-hardening/screenshots/`、`raw/`、`reports/`、`validations/`，新增 `reports/round-template.json` 与 `reports/round-template.md`，并生成 `validations/step1-template-validation.json`。验证确认模板 JSON 可解析、必需字段齐全、敏感值扫描无命中；本步未截图、未调用真实 provider。下一步从步骤 2 开始做当前 app 基线 UI/状态截图。
- 2026-06-27：完成步骤 2，做当前 app 基线 UI/状态截图。已记录 current-source sidecar `8839`、managed session、provider/model health、project/runtime/capability/automation 脱敏状态；保存 11 张截图覆盖 runtime、设置、provider/API key、模型、健康检查、capability、plugin/skill、automation 和 artifact 相关 surface；生成 `raw/step2-baseline/`、`reports/step2-baseline-ui-state.json`、`.md` 与 `validations/step2-baseline-validation.json`。验证通过 JSON parse、截图存在、console error 为 0、脱敏扫描；本步未调用真实 provider，token 消耗为 0。下一步从步骤 3 开始梳理并固化核心状态机不变量。
- 2026-06-27：完成步骤 3，梳理并固化核心状态机不变量。已新增 `docs/APP_HARDENING_STATE_INVARIANTS.md`，覆盖 project/task/thread/provider thread/runtime/automation/inbox/artifact 状态关系、`STATE-001` 到 `STATE-012` 不变量、第一轮 dogfood 错配和后续步骤引用；生成 `raw/step3-state-invariants/state-invariant-checklist.json`、`reports/step3-state-invariants.json` 与 `.md`。验证通过 JSON parse、覆盖检索、后续步骤引用检索和脱敏扫描；本步未截图、未调用真实 provider，token 消耗为 0。下一步从步骤 4 开始加固 task/thread/provider thread 恢复路径。
- 2026-06-27：完成步骤 4，加固 task/thread/provider thread 恢复路径。已补强 sidecar restore 测试，覆盖 owning task 恢复、provider handoff 目标 thread 激活和源 route 保留、missing active provider thread diagnostic/fallback；新增 desktop restore invalidation helper/test，覆盖 project、tasks、conversation、thread、goal、inspector 查询刷新，并接入 switch thread、switch task、create/fork thread、start turn 和 checkpoint restore 成功路径。验证通过 sidecar unittest 3 项、desktop vitest 1 项、desktop TypeScript `tsc --noEmit`、`task_service.py` py_compile、diff check 和脱敏复核；本步未截图、未调用真实 provider，token 消耗为 0。下一步从步骤 5 开始加固 conversation 终态、空态和错误态。
- 2026-06-27：完成步骤 5，加固 conversation 终态、空态和错误态。已新增 `describeConversationRenderState`，覆盖 loading、空线程、terminal empty、runtime error、thread not loaded、failed/interrupted/cancelled turn、API 内容不可渲染和 stale runtime error；聊天区用本地化诊断卡替换笼统 `no_messages`，并补充紧凑样式。验证通过 `threadRendering.test.ts` 18 项、desktop TypeScript `tsc --noEmit`、sidecar stale runtime 定向 unittest 3 项、diff check、脱敏扫描和 in-app browser 截图复核；截图与 DOM 摘要位于 `PRIVATE/app-hardening/screenshots/step5-conversation-states/` 与 `raw/step5-conversation-states/`。本步未调用真实 provider，token 消耗为 0。下一步从步骤 6 开始加固 runtime/provider capability contract。
- 2026-06-27：完成步骤 6，加固 runtime/provider capability contract。已新增 `astrabridge-runtime-provider-contract-v1` 合约摘要，覆盖 reasoning effort、tool schema、apply_patch_tool_type、web_search、vision、parallel tools、MCP、token usage，并将 provider-specific metadata 映射为 Codex runtime metadata；capability registry candidate 现在同时暴露 `capability_contract` 与 `runtime_provider_contract`，便于路由页和后续 provider health/token/cost 步骤复用。验证通过新增 contract tests、capability registry tests、capability smoke tests、runtime config/effective catalog 定向回归、py_compile、报告 JSON parse 和脱敏扫描；本步未调用真实 provider，token 消耗为 0，未改可见 UI 因此未截图。下一步从步骤 7 开始统一 provider health、router preview 和 token/cost 记录。
- 2026-06-27：完成步骤 7，统一 provider health、router preview 和 token/cost 记录。已新增 `astrabridge-usage-signal-v1`，让 router preview、router provider health、LLM API Manager health、capability smoke、web lane、automation runtime artifact 都输出统一 `usage_signal`；provider 返回 usage 时记录 normalized tokens 和可选 cost estimate，未调用 provider 或 provider 未返回 usage 时写明 `not_available` 与具体原因。验证通过 usage/router/capability/web/automation 定向 unittest 20 项、py_compile、Automation API 与 router/runtime config 定向回归 6 项、报告 JSON parse 和脱敏扫描；本步未调用真实 provider，token 消耗为 0，未改可见 UI 因此未截图。下一步从步骤 8 开始加固 sidecar 启动、端口归属和 current-source 验证。
- 2026-06-27：完成步骤 8，加固 sidecar 启动、端口归属和 current-source 验证。已新增 `astrabridge-sidecar-provenance-v1`，区分 current-source 与 app-managed sidecar，并在 API/status、isolation audit 和 runtime UI 中展示 sidecar 来源、端口归属、启动模式、源码根和 current-source match；修复 isolation audit `ok=false` 响应被前端吞成 generic request failure 的问题；新增 page-level headless 截图脚本 `scripts/capture_astrabridge_page.mjs`，用于在用户桌面前台窗口无关的情况下截图星桥页面。验证通过 sidecar provenance unittest 8 项、isolation audit/health 定向 unittest 6 项、desktop build、截图脚本语法检查、后台页面截图、报告 JSON parse 和脱敏扫描；截图位于 `PRIVATE/app-hardening/screenshots/step8-runtime-sidecar-provenance-headless.png`。本步未调用真实 provider，token 消耗为 0。下一步从步骤 9 开始建立标准 UI screenshot QA checklist 并接入报告。
- 2026-06-27：完成步骤 9，建立标准 UI screenshot QA checklist 并接入报告。已新增 `docs/APP_HARDENING_UI_SCREENSHOT_QA.md`，定义 `astrabridge-ui-screenshot-qa-v1` 报告形状、9 个检查项、截图要求和同轮修复规则；更新 `PRIVATE/app-hardening/reports/round-template.*` 的 `ui_review` 字段；扩展 `scripts/capture_astrabridge_page.mjs` 支持 viewport 和滚动动作。用 runtime 设置/隔离审计 surface 跑桌面与 390px 窄屏截图 QA，发现并修复窄屏 chips/按钮/路径溢出以及 WSL 依赖错误态文案问题，最终 checklist 9 项通过；截图位于 `PRIVATE/app-hardening/screenshots/step9-ui-screenshot-qa-runtime-desktop-final-settled.png` 和 `PRIVATE/app-hardening/screenshots/step9-ui-screenshot-qa-runtime-narrow-final2.png`。验证通过 `node --check scripts/capture_astrabridge_page.mjs`、`npm.cmd test -- src/features/i18n/catalog.test.ts`、`npm.cmd run build`、报告 JSON parse 和脱敏扫描；本步未调用真实 provider，token 消耗为 0。下一步从步骤 10 开始加固 runtime/browser inspector evidence UI。
- 2026-06-28：完成步骤 10，加固 runtime/browser inspector evidence UI。已删除右侧栏终端页签，重排右侧状态/审查/浏览器/文件 inspector；透明化左右 resize hit zone 并放宽右侧栏宽度上限；将浏览器诊断和 smoke 操作折叠到“详情与操作”；审查/文件列表默认一行并可展开，canvas 优先占据空间；修复 390px 窄屏 stacked inspector 下 browser canvas 塌缩，并让文件栏自动选中第一项预览。截图位于 `PRIVATE/app-hardening/screenshots/inspector-canvas-density-interrupt-20260628/`，报告位于 `PRIVATE/app-hardening/reports/step10-runtime-browser-inspector-evidence.json` 与 `.md`，验证位于 `PRIVATE/app-hardening/validations/step10-runtime-browser-inspector-evidence-validation.json`。验证通过 `npm test -- src/features/runtime/InspectorPanels.test.tsx`、`npm run build`、截图存在性、报告 JSON parse 和 secret-like 扫描；本步未调用真实 provider，token 消耗为 0。下一步从步骤 11 开始加固多模态 chat attachment 路径。
- 2026-06-28：完成步骤 11，加固多模态 chat attachment 路径。补齐附件 staging、输入准备、turn/start timeout/final response 的结构化诊断；图片附件按 localImage、普通文件/文件夹按 mention 的路由在 sidecar 结果和 runtime event 中有安全计数；缺失附件错误改为可操作且不暴露 workspace 绝对路径；前端 composer 在附件存在时显示一行路由摘要，并使用更长 startTurn timeout 防止前端早于 sidecar background pending 返回而 abort。截图位于 `PRIVATE/app-hardening/screenshots/step11-chat-attachments-20260628/attachment-menu-composer-final.png`，报告位于 `PRIVATE/app-hardening/reports/step11-chat-attachment-diagnostics.json` 与 `.md`，验证位于 `PRIVATE/app-hardening/validations/step11-chat-attachment-diagnostics-validation.json`。验证通过 `python -m unittest tests.test_sidecar_services.AstraBridgeServiceTests.test_start_turn_records_attachment_diagnostics_and_routes_images tests.test_sidecar_services.AstraBridgeServiceTests.test_start_turn_missing_attachment_error_is_actionable_and_sanitized tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_service_permission_mapping_and_attachment_staging`、`cmd /c npm test -- src/features/runtime/QueuedInstructionQueue.test.tsx`、`cmd /c npm run build`、`python -m compileall astrabridge_sidecar`、截图存在性和 secret-like 扫描；本步未调用真实 provider，token 消耗为 0。下一步从步骤 12 开始加固 artifact/media preview 与路径安全。
- 2026-06-28：完成步骤 12，加固 artifact/media preview 与路径安全。补齐 files inspector 的 inline preview/media error 呈现和 filename-first metadata；sidecar preview 测试现在覆盖 workspace 内绝对路径 artifact、generated image、PDF media 和被禁止的 `.astrabridge/runtime_events.jsonl` read/media 拦截。截图位于 `PRIVATE/app-hardening/screenshots/step12-artifact-media-preview-20260628/markdown-preview-full.png`、`pdf-preview-full.png` 和 `generated-image-preview-full.png`，报告位于 `PRIVATE/app-hardening/reports/step12-artifact-media-preview.json` 与 `.md`，验证位于 `PRIVATE/app-hardening/validations/step12-artifact-media-preview-validation.json`。验证通过 `python -m unittest tests.test_sidecar_services.AstraBridgeServiceTests.test_project_tools_file_preview_rejects_escape_and_secret_logs`、`cmd /c npm test -- src/features/runtime/InspectorPanels.test.tsx`、`cmd /c npm run build` 和 in-app browser 截图检查；本步未调用真实 provider，token 消耗为 0。下一步从步骤 13 开始加固 Web lane 证据与失败恢复。
- 2026-06-28：完成步骤 13，加固 Web lane 证据与失败恢复。sidecar research/fetch 结果补齐 `source_host`、`cache_hit`、`fetched_at`、`access_date`、`status_code`、`fetch_summary`、`evidence_kind`、`conclusion_status` 和 `conclusion_note`，并为成功抓取建立 canonical URL 缓存；desktop Web tools 面板改为分层展示“结论状态”“已抓取来源包”“来源明细”和“抓取失败”，同时呈现 pinned-source 策略原因、source origin、缓存命中、抓取失败、访问日期与引用规则。真实验证使用固定公共 URL `https://example.com` 与 `https://example.com/not-found` 连跑两次 brief，记录 `research-brief-20260628T115832296765-2abf80`，得到 `1` 条成功来源、`1` 条失败来源和 `1` 次缓存命中。截图位于 `PRIVATE/app-hardening/screenshots/step13-web-lane-evidence-20260628/step13-web-panel-blank.png`、`step13-web-research-first-pass.png` 和 `step13-web-research-lower.png`，报告位于 `PRIVATE/app-hardening/reports/step13-web-lane-evidence.json` 与 `.md`，验证位于 `PRIVATE/app-hardening/validations/step13-web-lane-evidence-validation.json`。验证通过 `python -m unittest tests.test_web_lane`、`cmd /c npm test -- src/features/web/WebToolsPanel.test.tsx`、`cmd /c npm run build`、JSON parse、secret-like 检索和 in-app browser 截图检查；本步未调用真实 provider，provider token 消耗为 0。下一步从步骤 14 开始加固插件/技能 registry、审批和启用状态。
- 2026-06-28：完成步骤 14，加固插件/技能 registry、审批和启用状态。补齐 desktop 插件/技能面板 zh-CN 的 `registryRefresh`、`registryRefreshPending`、`registryRefreshingHint`、`pluginDiscovery` 和 `skillDiscovery` 标签，修复中文 UI 在刷新/loading 状态下回退英文的问题；新增中文 registry refresh/discovery 回归测试，并复跑已有覆盖 discovery、install plan preview/apply、pending approval、blocked owner-plugin、global/project skill enablement、project preset 和 Plugin Creator fixture evidence 的测试。截图位于 `PRIVATE/app-hardening/screenshots/step14-plugin-skill-registry-20260628/extensions-registry-localized.png`，报告位于 `PRIVATE/app-hardening/reports/step14-plugin-skill-registry.json` 与 `.md`，验证位于 `PRIVATE/app-hardening/validations/step14-plugin-skill-registry-validation.json`。验证通过 `npm.cmd test -- src/features/extensions/PluginSkillInventoryPanel.test.tsx src/features/extensions/PluginSkillInventoryPanel.smoke.test.tsx`、`apps\astrabridge-sidecar\.venv\Scripts\python.exe -m pytest apps\astrabridge-sidecar\tests\test_real_scenario_plugin_fixture_contract.py apps\astrabridge-sidecar\tests\test_real_scenario_plugin_fixture_runtime_install.py`、`npm.cmd run build`、JSON parse、secret-like 检索和 in-app browser 截图检查；本步未自动安装外部插件，未调用真实 provider，provider token 消耗为 0。下一步从步骤 15 开始加固 MCP 工具发现、参数错误和结果展示。
- 2026-07-03：完成步骤 15，加固 MCP 工具发现、参数错误和结果展示。已确认当前 8870 sidecar 的 `astrabridge_capabilities` 服务器可见 5 个运行时工具；desktop `McpToolDiagnosticsPanel` 保持 zh-CN 诊断文案、空态提示、JSON 对象参数校验、missing-thread 可行动错误、敏感键脱敏以及大结果截断提示，并通过后台截图脚本在 MCP 页面完成一次对 `astrabridge_capability_routes` 的确定性复放调用，成功展示复放调用包、结果预览和 “246087” 原始长度的大结果截断提示。截图位于 `PRIVATE/app-hardening/screenshots/step15-mcp-tool-diagnostics-20260703/mcp-page-baseline.png` 与 `mcp-tool-call-success.png`，原始页面采集位于 `PRIVATE/app-hardening/raw/step15-mcp-page-baseline.json`、`step15-mcp-success-actions.json` 与 `step15-mcp-tool-call-success.json`，报告位于 `PRIVATE/app-hardening/reports/step15-mcp-tool-diagnostics.json` 与 `.md`，验证位于 `PRIVATE/app-hardening/validations/step15-mcp-tool-diagnostics-validation.json`。验证通过 `npm.cmd test -- src/features/runtime/McpToolDiagnosticsPanel.test.tsx`、`apps\astrabridge-sidecar\.venv\Scripts\python.exe -m pytest apps\astrabridge-sidecar\tests\test_capability_mcp_server.py`、`apps\astrabridge-sidecar\.venv\Scripts\python.exe -m pytest apps\astrabridge-sidecar\tests\test_sidecar_services.py -k "runtime_direct_mcp_tool_call"`、`npm.cmd run build`、JSON parse、secret-like 检索和截图存在性检查；本步未调用真实 provider，provider token 消耗为 0。下一步从步骤 16 开始加固 automation 成功路径 finalization。
- 2026-07-03：完成步骤 16，加固 automation 成功路径 finalization。desktop `AutomationsPanel` 已在运行详情中增加成功收尾提示、Inbox item 摘要和 Manifest 摘要，明确区分 finding 保留未读、no-signal 自动归档、no-signal 仅记录以及无 inbox 成功完成四类结果；sidecar/desktop 测试补齐已完成 no-signal 自动归档和无 inbox 成功收尾覆盖；当前 8870 sidecar 对当前项目注入了 3 个确定性 fixture（`step16-success-finding`、`step16-success-archived`、`step16-success-no-inbox`），并通过后台截图脚本验证了三条成功路径的 UI 收尾。截图位于 `PRIVATE/app-hardening/screenshots/step16-automation-finalization-20260703/step16-automation-enter-test.png`、`step16-automation-finding-detail.png`、`step16-automation-archived-detail.png` 与 `step16-automation-no-inbox-detail.png`，原始采集位于 `PRIVATE/app-hardening/raw/step16-automation-success-fixtures.json`、`step16-automation-detail-capture.mjs`、`step16-automation-finding-detail.json`、`step16-automation-archived-detail.json` 与 `step16-automation-no-inbox-detail.json`，报告位于 `PRIVATE/app-hardening/reports/step16-automation-finalization.json` 与 `.md`，验证位于 `PRIVATE/app-hardening/validations/step16-automation-finalization-validation.json`。验证通过 `npm.cmd test -- src/features/automations/AutomationsPanel.test.tsx`、`apps\astrabridge-sidecar\.venv\Scripts\python.exe -m pytest apps\astrabridge-sidecar\tests\test_automation_api.py`、`npm.cmd run build`、JSON parse、secret-like 检索和截图存在性检查；本步未调用真实 provider，provider token 消耗为 0。下一步从步骤 17 开始加固 automation stuck/interrupted watchdog。
- 2026-07-03：完成步骤 17，加固 automation stuck/interrupted watchdog。sidecar 为 stale timeout 恢复和 service-restart interrupted 恢复补齐结构化 watchdog 元数据、恢复来源和恢复时间，并新增 watchdog reconciliation，把此前只改为 failed 的 recovered run 补齐为可审阅的 Manifest 与 Inbox 证据；desktop `AutomationsPanel` 新增本地化 watchdog/interrupted/cancelled 提示、恢复原因和下次重试字段；当前 8870 sidecar 对当前项目注入了 3 个确定性 fixture（`step17-watchdog-stale`、`step17-interrupted-recovery`、`step17-user-cancelled`），并通过后台截图脚本验证 stale watchdog recovery、service-restart interrupted recovery 和 user-cancelled 三条路径的 UI 收尾。截图位于 `PRIVATE/app-hardening/screenshots/step17-automation-watchdog-20260703/step17-watchdog-stale-detail.png`、`step17-interrupted-detail.png` 与 `step17-cancelled-detail.png`，原始采集位于 `PRIVATE/app-hardening/raw/step17-automation-watchdog-fixtures.json`、`step17-watchdog-stale-detail.json`、`step17-interrupted-detail.json` 与 `step17-cancelled-detail.json`，报告位于 `PRIVATE/app-hardening/reports/step17-automation-watchdog-hardening.json` 与 `.md`，验证位于 `PRIVATE/app-hardening/validations/step17-automation-watchdog-hardening-validation.json`。验证通过 `npm.cmd test -- src/features/automations/AutomationsPanel.test.tsx`、`apps\astrabridge-sidecar\.venv\Scripts\python.exe -m pytest apps\astrabridge-sidecar\tests\test_automation_api.py apps\astrabridge-sidecar\tests\test_automation_scheduler.py`、`npm.cmd run build`、JSON parse、secret-like 检索和截图存在性检查；本步未调用真实 provider，provider token 消耗为 0。下一步从步骤 18 开始加固安全脱敏和 artifact retention 审计。
- 2026-07-03：完成步骤 18，加固安全脱敏和 artifact retention 审计。sidecar 共享 `security.py` 新增桌面 `Desktop\\key.txt` 路径拒绝与脱敏；新增 `scripts/app_hardening_secret_scan.py`，扫描 `PRIVATE/app-hardening/**` 和默认公开文档集中的 secret-like 内容、desktop key path 泄漏、异常 retention bucket、异常 screenshot/report/validation 文件类型以及被误跟踪的 PRIVATE artifact；并将顶层遗留的 `PRIVATE/app-hardening/runtime/**` 日志和 `plan-artifact-preview.html` 迁入 `PRIVATE/app-hardening/raw/**`，使 app-hardening 根目录与保留规则对齐。报告位于 `PRIVATE/app-hardening/reports/step18-redaction-retention-audit.json` 与 `.md`，原始采集位于 `PRIVATE/app-hardening/raw/step18-app-hardening-secret-scan.json` 与 `step18-run-local-gate-quick.txt`，验证位于 `PRIVATE/app-hardening/validations/step18-redaction-retention-audit-validation.json`。验证通过 `python -m unittest discover -s apps/astrabridge-sidecar/tests -p "test_app_hardening_secret_scan.py"`、`python -m unittest discover -s apps/astrabridge-sidecar/tests -p "test_automation_security.py"`、`python .\scripts\app_hardening_secret_scan.py --repo .`、`python .\scripts\run_local_gate.py --quick` 和 `git diff --check`；本步未调用真实 provider，provider token 消耗为 0。下一步从步骤 19 开始做跨 surface UI/UX polish sweep。
- 2026-07-03：完成步骤 19，做跨 surface UI/UX polish sweep。审查范围覆盖 conversation/runtime shell、settings/provider/api key/model、browser inspector、files/review inspector、plugins/MCP/capabilities 和 automation panels；本轮确认高影响问题集中在 browser inspector，于是将 managed browser 的 back/forward/reload 统一改为调用 browser workbench session action，并压薄了标签页、地址栏、状态 chip、工具按钮和 tab close chrome，让右侧窄高浏览器面板可以更多地展示真实网页内容。截图位于 `PRIVATE/app-hardening/screenshots/step19-ui-polish-20260703/step19-browser-panel-clean.png`、`step19-browser-panel-mobile-render.png`、`step19-browser-panel-google-youtube.png` 与 `step19-runtime-baseline.png`，原始采集位于 `PRIVATE/app-hardening/raw/step19-browser-clean-capture-actions.json`、`step19-browser-panel-clean.json`、`step19-browser-mobile-render-capture-actions.json`、`step19-browser-panel-mobile-render.json`、`step19-browser-polish-capture-actions.json`、`step19-browser-panel-google-youtube.json` 与 `step19-runtime-baseline.json`，报告位于 `PRIVATE/app-hardening/reports/step19-ui-polish-sweep.json` 与 `.md`，验证位于 `PRIVATE/app-hardening/validations/step19-ui-polish-sweep-validation.json`。验证通过 `cmd /c npm test -- src/features/runtime/InspectorPanels.test.tsx`、`cmd /c npm run build`、`python .\scripts\app_hardening_secret_scan.py --repo .`、`git diff --check` 和 in-app browser visual QA；本步未调用真实 provider，provider token 消耗为 0。下一步从步骤 20 开始汇总第一轮 app hardening 结论并制定下一轮入口。
- 2026-07-03：完成步骤 20，汇总 app hardening 第一轮结论并制定下一轮入口。新增 `docs/APP_HARDENING_EVIDENCE.md` 作为公开摘要入口，汇总 20/20 步完成状态、私有 round report/validation artifact 索引、截图索引、剩余风险和下一轮执行顺序；新增 `PRIVATE/app-hardening/reports/step20-hardening-round-summary.json` 与 `.md` 和 `PRIVATE/app-hardening/validations/step20-hardening-round-summary-validation.json` 作为第一轮收官产物。验证重新通过 `PRIVATE/app-hardening/reports/*.json` 与 `PRIVATE/app-hardening/validations/*.json` 全量 JSON 解析、`python .\scripts\app_hardening_secret_scan.py --repo .`、`python .\scripts\run_local_gate.py --quick` 和 `git diff --check`；本轮未调用真实 provider，provider token 总消耗为 0。第一轮计划到此闭合，如继续第二轮，默认从“设置凭据与 managed-user 登录 hardening”开始。
