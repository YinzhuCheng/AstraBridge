# Agent Bench Dogfood Execution Plan

## 总目标

用经典 agent benchmark 的任务形态，组织一套小样本、真实 API、可复盘的 AstraBridge dogfood 评测。目标不是追求完整 benchmark 分数，而是在真实 agent 任务中检验并提升 AstraBridge 的产品体验、运行监督、工具路由、上下文工程、插件/MCP、联网、多模态、自动化和失败恢复能力。

本计划的核心产出是：

- 一套可重复的小样本 agent 任务池，覆盖基础代码能力、文件/命令能力、浏览器联网能力、多模态能力、插件/MCP 能力、自动化能力和跨 provider 路由能力。
- 一条真实运行监督链路，保存截图、脱敏日志、token/费用估算、失败原因、修复记录和复测结果。
- 在测试中发现并修复 AstraBridge app、sidecar、agent harness、上下文包、UI 监督面板、错误提示和恢复路径中的问题。
- 形成可继续扩展的 benchmark dogfood 方法，而不是一次性演示。

## 注意事项

- 允许真实 API 调用和真实 token 消耗，但每轮必须记录 provider、model、任务、是否调用真实 provider、粗略 token/费用信号、失败原因和下一步。
- 禁止保存 API keys、bearer tokens、cookies、authorization headers、平台 token 或任何明文 secret。所有持久日志和报告必须脱敏。
- 不自动写回外部 benchmark 平台、GitHub、网页表单或第三方系统，除非用户在当轮明确批准。
- 默认保留实验产物。不要清理 `PRIVATE/**`、截图、日志、raw request/response、验证报告、缓存或 demo runs，除非用户明确点名要求清理目标路径。
- 遇到 agent 做不出题，不直接替 agent 解题；优先修复 AstraBridge 的 harness、上下文工程、工具说明、路由、UI、错误恢复或 app bug。只有在记录清楚产品层无法改进的情况下，才把任务标为 agent 能力失败。
- 实施过程中要经常用 in-app browser 或 Playwright 截图检查效果。发现 UI 不美观、文字溢出、布局拥挤、状态不清、按钮语义不准、错误信息不可行动时，应在同一步内修复 app UI 并复测截图。
- 每轮对话只完成一个完整编号步骤。完成后必须更新“当前进度”和“完成记录”，写清下一步入口。
- 后续 agent 必须从“当前进度”中已完成步骤的下一步开始，除非用户明确要求跳转。
- 允许根据实际实施情况动态调整本计划的步骤、顺序、任务样本和验证标准，但调整不能损伤本计划的主目标：通过真实测试验证并提升 AstraBridge 的 app 能力、监督体验和 agent 运行质量。
- 如需修改本计划，保留总目标、注意事项、顺序执行规则和进度记录结构，不要把计划改成无法逐步执行的宽泛备忘录。

## 细节

### Benchmark 任务形态

本计划借鉴以下经典 agent benchmark 的任务形态，而不是复刻完整数据集：

- SWE-bench / HumanEval 风格：代码定位、最小修复、运行测试、解释结果。
- AgentBench / OSWorld 风格：本地文件、命令行、长链路操作和环境状态恢复。
- WebArena / BrowserGym 风格：浏览器导航、联网查找、页面状态验证、表单和多页面流程。
- GAIA 风格：联网、文件、图片、多步推理和证据整合。
- ToolBench / tau-bench 风格：多工具调用、API 状态流、工具失败恢复和最终状态一致性。
- AstraBridge 自有产品流：provider key 解锁、router/model 状态、插件/技能、MCP、自动化、dogfood ledger、截图和审计报告。

### 任务分层

- 基础层：代码修改、测试运行、文件读取、shell 命令、错误恢复。
- 路由层：provider/model 切换、managed key 注入、router payload preview、健康检查。
- 浏览器/联网层：web search/fetch/research brief、浏览器任务、截图验证。
- 多模态层：图片理解、图片生成、文件/截图证据引用。
- 扩展层：插件/技能发现、MCP 工具调用、能力路由。
- 自动化层：一次性/计划任务、隔离工作副本、inbox triage、失败复盘。
- 体验层：UI 监督面板、状态文案、错误提示、布局、响应式和可操作性。

### 产物路径

- 原始和私有产物：`PRIVATE/agent-bench-dogfood/`
- 截图：`PRIVATE/agent-bench-dogfood/screenshots/`
- 原始调用和脱敏响应：`PRIVATE/agent-bench-dogfood/raw/`
- 每轮验证报告：`PRIVATE/agent-bench-dogfood/reports/`
- 可提交的脱敏总结：可按需要新增 `docs/AGENT_BENCH_DOGFOOD_EVIDENCE.md`

### 每轮完成标准

每个编号步骤完成前至少满足：

- 已执行该步骤定义的任务或修复。
- 已保存或确认必要截图、日志、报告或测试输出。
- 若发现 UI 问题，已在同一步内完成合理修复并复测。
- 已更新本计划的“当前进度”和“完成记录”。
- 已明确下一步入口。

## 实现步骤

1. 建立 dogfood 运行目录和报告骨架。
   - 创建 `PRIVATE/agent-bench-dogfood/` 子目录结构。
   - 定义单轮报告 JSON/Markdown 字段：task_id、benchmark_shape、provider、model、real_api_used、token_signal、screenshots、artifacts、failure_mode、product_fix、next_entry。
   - 验证：生成一个空白模板报告，并确认没有 secret 字段。

2. 做基线登录、provider key 和 router 状态截图。
   - 用当前 AstraBridge UI 登录 `astra` managed vault。
   - 截图 API 密钥、提供方、模型、运行时状态页。
   - 记录当前 sidecar URL、router URL、managed key 脱敏状态和已验证模型。
   - 验证：报告中能说明基线是否可运行真实 provider。

3. 选定第一批小样本任务池。
   - 选择 8 到 12 个任务，覆盖代码、shell、浏览器、联网、多模态、插件/MCP、自动化和跨 provider。
   - 每个任务必须有可验证终态和失败判定。
   - 避免需要外部账号写回的平台任务。
   - 验证：任务池文档中每个任务都有 `success_criteria` 和 `allowed_tools`。

4. 实现最小 agent harness 记录器。
   - 为每次任务运行记录输入、上下文包摘要、provider/model、工具调用摘要、截图路径和最终状态。
   - 原始请求/响应只保存脱敏版本。
   - 验证：用 dry-run 任务生成一条完整记录。

5. 运行基础代码修复任务。
   - 选一个 SWE-bench 风格的小型本地 bugfix。
   - 让 AstraBridge agent 定位、修改、测试。
   - 不替 agent 手动解题，只修产品层阻塞。
   - 验证：测试通过或记录明确失败模式。

6. 修复基础代码任务暴露的 harness 或 UI 问题。
   - 针对第 5 步发现的问题，改进上下文、错误提示、diff 展示、测试输出或运行按钮。
   - 截图验证修复后的监督体验。
   - 验证：同一任务或等价任务复测改善。

7. 运行本地 shell/file 长链路任务。
   - 任务应覆盖目录读取、文件编辑、命令执行、失败恢复。
   - 记录命令输出摘要和可复现路径。
   - 验证：目标文件或测试状态符合预期。

8. 修复 shell/file 任务暴露的产品问题。
   - 优先修复权限提示、路径显示、命令日志、错误恢复和 Windows 路径问题。
   - 截图检查 UI 是否清楚、美观、无溢出。
   - 验证：复测一条 shell/file 流程。

9. 运行浏览器/WebArena 风格任务。
   - 使用 in-app browser 完成一个只读网页导航或信息查找任务。
   - 保存关键页面截图和最终证据。
   - 验证：最终答案有可追溯网页证据。

10. 修复浏览器监督和截图体验问题。
    - 改进 browser panel、截图路径、页面状态文案、失败提示或等待状态。
    - 验证：截图和 UI 状态能让用户看懂 agent 正在做什么。

11. 运行联网研究/GAIA 风格任务。
    - 使用 web search/fetch/research brief 组合一个小型多源事实任务。
    - 记录引用、来源质量、日期和不确定性。
    - 验证：输出能区分事实、推断和未验证信息。

12. 修复联网任务暴露的上下文和证据问题。
    - 改进 source attribution、引用显示、网络失败恢复、缓存或结果摘要。
    - 验证：复测联网任务并截图报告页面。

13. 运行多模态输入任务。
    - 使用截图或本地图片，让 agent 做图像理解、OCR 或视觉检查。
    - 保存输入图、输出、失败模式和 UI 截图。
    - 验证：结果可由人工根据截图判断对错。

14. 运行多模态生成或资产任务。
    - 使用允许真实 API 的图片生成/资产流，生成一个小型可验证产物。
    - 检查产物预览、路径、manifest/registry 记录和错误提示。
    - 验证：产物可见、路径正确、报告脱敏。

15. 运行插件/技能发现任务。
    - 选择一个插件或技能相关工作流：发现、安装、读取说明、执行 fixture。
    - 验证插件/技能状态在 UI 和 sidecar API 中一致。
    - 验证：任务报告包含插件/技能 ID、状态和失败恢复。

16. 运行 MCP 工具调用任务。
    - 选择一个低风险 MCP 工具任务，验证工具发现、参数传递、结果显示和错误恢复。
    - 截图 MCP 状态和工具调用结果。
    - 验证：MCP 调用结果与 UI 状态一致。

17. 运行自动化任务。
    - 创建一个手动或短间隔自动化，用隔离或明确的工作区模式运行。
    - 检查 run history、inbox、artifact、失败/成功状态。
    - 验证：自动化结果能被用户复盘和处理。

18. 修复自动化和 dogfood ledger 体验问题。
    - 针对第 17 步的问题修复 UI、状态文案、归档/提升按钮、错误展示或报告链接。
    - 截图验证列表、详情和空状态。
    - 验证：复测自动化 run 或 inbox 流程。

19. 运行跨 provider 路由和 handoff 任务。
    - 选择至少两个 provider/model，验证 managed key 注入、router preview、health signal 和 handoff 记录。
    - 真实调用必须记录 provider/model 和脱敏响应摘要。
    - 验证：UI、router 状态和任务报告中的 provider 信息一致。

20. 汇总第一轮 benchmark dogfood 结论并调整下一轮计划。
    - 汇总任务通过率、失败类型、产品修复、token/费用信号、截图索引和剩余风险。
    - 根据真实结果调整任务池和后续计划，但不降低验证 app 能力和修复产品问题的目标。
    - 验证：提交一份脱敏总结，并把本计划当前进度标为 20/20 或追加第二轮步骤。

## 当前进度

- 当前已完成步骤：20/20
- 下一步入口：第一轮计划已完成；如继续第二轮，从 `PLAN/AGENT_BENCH_DOGFOOD_TASK_POOL.md` 的 “Round 2 Adjustments After First Dogfood Round” 开始制定新一轮执行计划。
- 当前状态说明：已完成步骤 20，汇总第一轮 benchmark dogfood 结论并调整下一轮方向。已生成机器可读聚合 `PRIVATE/agent-bench-dogfood/reports/step20-first-round-summary.json` 与 Markdown 摘要 `PRIVATE/agent-bench-dogfood/reports/step20-first-round-summary.md`，并新增 git 跟踪的脱敏证据文档 `docs/AGENT_BENCH_DOGFOOD_EVIDENCE.md`。第一轮共保留 16 条 harness 记录，其中 13 条 pass、3 条 partial；10 个能力族中 7 个最终 pass、2 个 pass after repair、1 个 partial。真实 API/网络记录 8 条，明确 token usage 的记录 3 条，已知 token 信号为 56185 input / 4185 output / 1019 reasoning / 60370 total；费用未计算，因为部分 provider、图片生成、Web/network 和 automation lane 未暴露统一价格或 token 用量。截图索引覆盖 52 张截图。已在 `PLAN/AGENT_BENCH_DOGFOOD_TASK_POOL.md` 追加第二轮调整建议，重点包括 chat attachment 多模态修复、token/cost 统一记账、current-source sidecar 验证、provider fallback、插件安装审批、自动化成功路径和标准截图 QA checklist。已通过 summary JSON 解析、harness records validate、脱敏扫描和 `git diff --check`。本计划第一轮执行完成。
- 动态调整状态：允许后续 agent 根据实施情况调整步骤细节，但必须保留真实 API dogfood、截图监督、UI 修复、harness 改进和逐步进度更新目标。

## 完成记录

- 2026-06-26：创建本计划。下一步从步骤 1 开始。
- 2026-06-26：完成步骤 1，创建 `PRIVATE/agent-bench-dogfood/`、`screenshots/`、`raw/`、`reports/`、`artifacts/`、`validations/`，并新增 `reports/round-template.json` 与 `reports/round-template.md`。验证 JSON 可解析，凭据类字段计数为 0。下一步从步骤 2 开始。
- 2026-06-26：完成步骤 2，使用 in-app browser 登录并确认 `astra` managed session 已解锁，保存 API 密钥、提供方、模型、运行时状态截图到 `PRIVATE/agent-bench-dogfood/screenshots/baseline-20260626-step2/`，并新增脱敏基线报告 `PRIVATE/agent-bench-dogfood/reports/baseline-20260626-step2.json` 与 `PRIVATE/agent-bench-dogfood/reports/baseline-20260626-step2.md`。报告 JSON 可解析，脱敏检查未发现常见明文密钥模式；截图复查未发现本步需要修复的 UI 问题。下一步从步骤 3 开始。
- 2026-06-26：完成步骤 3，新增 git 跟踪任务池文档 `PLAN/AGENT_BENCH_DOGFOOD_TASK_POOL.md`，并在 `PRIVATE/agent-bench-dogfood/reports/task-pool-20260626-step3.json` 保存机器可读版本。任务池包含 10 个任务，覆盖计划要求的主要能力面；验证确认 JSON 可解析，任务数量符合 8 到 12 个范围，每个任务都有 `success_criteria` 和 `allowed_tools`，且未发现常见明文密钥模式。下一步从步骤 4 开始。
- 2026-06-26：完成步骤 4，新增 `scripts/agent_bench_harness.py` 作为最小 agent harness 记录器。已运行 `python scripts/agent_bench_harness.py dry-run --output PRIVATE/agent-bench-dogfood/reports/dry-run-step4-record.json` 生成完整 dry-run 记录，并运行 `python scripts/agent_bench_harness.py validate --input PRIVATE/agent-bench-dogfood/reports/dry-run-step4-record.json` 与 `python -m py_compile scripts/agent_bench_harness.py` 验证。PowerShell 侧复查确认记录包含输入摘要、上下文摘要、provider/model、工具调用、截图路径、最终状态和 2 条 redacted raw records；敏感假值未落盘。下一步从步骤 5 开始。
- 2026-06-26：完成步骤 5，运行 `AB-CODE-001-step5` 基础代码修复任务。Kimi 尝试暴露出 stale `systemError`/无 agent 输出问题；DeepSeek 初次切换暴露出 model catalog `max` effort 不被 Codex runtime 接受的问题。已修复 catalog effort 归一化并通过 `python -B -m unittest tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_config_uses_configured_model_capability_resolver tests.test_sidecar_services.AstraBridgeServiceTests.test_metadata_seed_import_and_effective_catalog_are_conservative`。修复后 DeepSeek 真实 agent 运行成功，修改 private fixture 的 `string_tools.py` 并通过 `python -m unittest discover -s PRIVATE/agent-bench-step5-codefix -p "test_*.py"`。已生成并验证 `PRIVATE/agent-bench-dogfood/reports/step5-codefix-record.json`，另保存 Markdown 摘要与截图。截图发现完成线程会话区仍显示空状态，下一步从步骤 6 开始修复该监控 UI/harness 问题。
- 2026-06-26：完成步骤 6，修复基础代码任务暴露的 UI/harness 问题。已新增 renderable-thread-content 判定，并让聊天视图在 task conversation 聚合线程暂时没有可渲染内容时回退到 selected runtime thread，从而避免已完成 agent 消息被空态覆盖。已运行 `node ./node_modules/typescript/bin/tsc --noEmit`、`node ./node_modules/vitest/vitest.mjs run src/features/runtime/threadRendering.test.ts` 和 `python scripts/agent_bench_harness.py validate --input PRIVATE/agent-bench-dogfood/reports/step6-ui-harness-record.json`；浏览器复测确认 AB-CODE-001 DeepSeek 消息可见、空态消失、控制台无 error，并保存截图到 `PRIVATE/agent-bench-dogfood/screenshots/step6-ui-harness/thread-rendering-after-fallback.png`。下一步从步骤 7 开始。
- 2026-06-26：完成步骤 7，运行 `AB-SHELL-001-step7` 本地 shell/file 长链路任务。已创建并保留 private fixture，baseline validator 明确失败；DeepSeek 真实 runtime agent 在 fresh provider thread `019f043c-32ed-7e62-9f7b-3aba559707ce` 中完成目录读取、命令执行、失败恢复、manifest 修复和 inventory 报告生成，最终 validator 通过。已生成并验证 `PRIVATE/agent-bench-dogfood/reports/step7-shellfile-record.json`，另保存 Markdown 摘要与 UI 截图。截图/API 对比记录了待修复产品问题：task/thread 绑定恢复可能挂到旧任务，且 Step 7 task conversation API 有完整内容时 UI 仍显示空会话。下一步从步骤 8 开始修复这些 shell/file 任务暴露的问题。
- 2026-06-26：完成步骤 8，修复 shell/file 任务暴露的产品问题。已修改 `TaskService.restore_active_provider_thread()`，先解析 provider/fork thread 的拥有者 task 再恢复焦点；已修复 `/api/runtime/threads/switch` 响应，返回 task restore 后的最新 project 投影；已让桌面端 `switchThread` 成功后失效 project、project-tasks、task-conversation、thread 和 goal 查询。新增 `apps/astrabridge-sidecar/tests/test_task_service_restore.py` 并通过相关 sidecar tests；前端 `threadRendering.test.ts` 16 项通过。已重启 8830 sidecar，通过 API 验证旧 task -> Step 7 execution thread 恢复路径，`matched_expected_task=true`、`matched_expected_thread=true`、`response_project_matches_task=true`。in-app browser 截图复测确认 Step 7 消息流显示 8 个 article，包含 `validate_inventory.py` / validation 文本，空会话状态消失。已生成并验证 `PRIVATE/agent-bench-dogfood/reports/step8-shellfile-fix-record.json`，另保存 Markdown 摘要与截图。下一步从步骤 9 开始运行浏览器/WebArena 风格任务。
- 2026-06-26：完成步骤 9，运行 `AB-BROWSER-001-step9` 浏览器/WebArena 风格只读状态证明任务。已用 in-app browser 依次检查聊天基线、提供方与 API 密钥登录状态、API 密钥、提供方、模型和健康检查页面，保存 6 张截图到 `PRIVATE/agent-bench-dogfood/screenshots/step9-browser-state/`。已保存脱敏 sidecar/UI 摘要到 `PRIVATE/agent-bench-dogfood/raw/step9-browser-state/api-ui-summary.json`，并确认 UI/API 状态一致：当前为 anonymous locked session，managed key count 为 0，router/provider/model 和健康检查历史 pass 状态与 UI 可见状态一致；本步未触发新 provider 调用。已生成并验证 `PRIVATE/agent-bench-dogfood/reports/step9-browser-state-record.json` 与 `.md`，并通过 `python -m py_compile scripts/agent_bench_harness.py`。本步修复了 `scripts/agent_bench_harness.py` 对 Windows PowerShell UTF-8 BOM JSON 输入不兼容的问题。下一步从步骤 10 开始修复浏览器监督和截图体验问题。
- 2026-06-26：完成步骤 10，修复浏览器监督和截图体验问题。已在 `BrowserInspectorPanel` 增加 evidence panel，集中展示最近 browser smoke 的状态、控制台计数、请求失败计数、截图路径和报告提示；已补充中英文文案、响应式样式和 `InspectorPanels` 测试。in-app browser 首次截图发现截图路径在右侧窄面板中被压成竖向碎片，随后将截图路径移动到独占整行并复测截图通过。已保存截图到 `PRIVATE/agent-bench-dogfood/screenshots/step10-browser-supervision/`，生成并验证 `PRIVATE/agent-bench-dogfood/reports/step10-browser-supervision-record.json` 与 `.md`。已运行 `node ./node_modules/vitest/vitest.mjs run src/features/runtime/InspectorPanels.test.tsx src/features/i18n/catalog.test.ts`、`node ./node_modules/typescript/bin/tsc --noEmit` 和 harness validate；本步未触发 provider/model 调用。下一步从步骤 11 开始运行联网研究/GAIA 风格任务。
- 2026-06-26：完成步骤 11，运行 `AB-WEB-001-step11` 联网研究/GAIA 风格任务。首次深度搜索运行暴露来源选择失败：中文研究目标被误命中到“截至/截止”用法页面，未得到 OWASP/NIST 证据；同一步内已在 `WebToolsPanel` 增加深度搜索固定来源 URL 输入并传递 `source_urls`，补充回归测试。修复后用 in-app browser 固定 OWASP LLM Top 10、OWASP LLM06 Excessive Agency、NIST AI RMF Core 和 NIST AI RMF Playbook 四个官方来源复测，4/4 固定来源抓取成功，保存截图到 `PRIVATE/agent-bench-dogfood/screenshots/step11-web-research/`。已生成 `PRIVATE/agent-bench-dogfood/raw/step11-web-research/api-web-summary.json`、`PRIVATE/agent-bench-dogfood/reports/step11-web-research-record.json` 与 `.md`，并通过 `node .\node_modules\vitest\vitest.mjs run src\features\web\WebToolsPanel.test.tsx`、`node .\node_modules\typescript\bin\tsc --noEmit` 和 harness validate。记录状态为 `partial`，因为固定来源复测仍混入两个泛搜索来源；下一步从步骤 12 开始修复联网任务上下文和证据归因问题。
- 2026-06-26：完成步骤 12，修复联网任务暴露的上下文和证据问题。已在 sidecar 中为 `source_urls` 无显式查询场景加入固定来源模式，跳过派生泛搜索并返回 `source_policy`；已给来源增加 `source_origin`，并在桌面端 Web 深度搜索结果中展示来源策略摘要和来源徽标。已通过 `python -m unittest apps.astrabridge-sidecar.tests.test_web_lane`、`node .\node_modules\vitest\vitest.mjs run src\features\web\WebToolsPanel.test.tsx`、`node .\node_modules\typescript\bin\tsc --noEmit`、`python -m py_compile apps/astrabridge-sidecar/astrabridge_sidecar/lcr_web_mcp_server.py scripts/agent_bench_harness.py` 以及两条相关 sidecar 回归测试；随后用 in-app browser 固定四个 OWASP/NIST 官方来源复测，记录 `research-brief-20260626T234503437956-36eb5e` 显示 `pinned_source_urls`、搜索扩展已跳过、4/4 来源抓取成功且无无关来源混入。已生成 `PRIVATE/agent-bench-dogfood/raw/step12-web-evidence-fix/api-web-summary.json`、`PRIVATE/agent-bench-dogfood/reports/step12-web-evidence-fix-record.json` 与 `.md`，并通过 harness validate；截图保存到 `PRIVATE/agent-bench-dogfood/screenshots/step12-web-evidence-fix/`。下一步从步骤 13 开始运行多模态输入任务。
- 2026-06-27：完成步骤 13，运行 `AB-VISION-001-step13` 多模态输入任务。已创建并保存本地图像 fixture，记录 GLM 聊天附件路径无可见回答的失败模式；同一步内修复 `vision.analyze` provider smoke 支持自定义本地图像输入并新增回归测试，随后通过 `qwen/qwen3.7-plus` 真实视觉路由得到与图片匹配的 JSON 输出并持久化 request/response/text/summary artifacts。截图复核发现最近产物 JSON 预览过窄，已修复 `apps/astrabridge-desktop/src/styles.css` 的 capability artifact card 布局并复测截图。已生成 `PRIVATE/agent-bench-dogfood/raw/step13-multimodal-input/api-vision-summary.json`、`PRIVATE/agent-bench-dogfood/reports/step13-multimodal-input-record.json` 与 `.md`，并通过 harness validate、sidecar capability smoke/artifact tests、desktop typecheck、CapabilityRoutesPanel/i18n vitest、`git diff --check` 和本轮 raw/report 脱敏扫描。下一步从步骤 14 开始运行多模态生成或资产任务。
- 2026-06-27：完成步骤 14，运行 `AB-ASSET-001-step14` 多模态生成/资产任务。已通过 `yunwu/gpt-image-2` 真实生成透明 PNG 产物 `yunwu-1782492418-cc7a17b8`，确认本地路径、manifest、artifact API、media API 和 UI 预览均可用；同一步内修复 image.generate 路由优先级、provider smoke 空 artifact 判定、generated asset manifest 汇总、网页端媒体 URL、workspace 内绝对路径媒体预览、`.astrabridge/assets` allowlist 和 image artifact preview 溢出问题。已生成 `PRIVATE/agent-bench-dogfood/raw/step14-multimodal-generation/api-image-generation-summary.json`、`PRIVATE/agent-bench-dogfood/reports/step14-multimodal-generation-record.json` 与 `.md`，保存最终截图 `PRIVATE/agent-bench-dogfood/screenshots/step14-multimodal-generation/image-generate-artifact-preview-ui-final.png`，并通过 harness validate、raw/report 脱敏扫描、相关 sidecar unittest、desktop typecheck、CapabilityRoutesPanel/i18n vitest、media endpoint 检查和 `git diff --check`。下一步从步骤 15 开始运行插件/技能发现任务。
- 2026-06-27：完成步骤 15，运行 `AB-PLUGIN-001-step15` 插件/技能发现任务。已发现项目本地插件 `astrabridge-dogfood-fixture` 与技能 `astrabridge-fixture-skill`，读取技能说明后执行声明的本地 fixture 脚本并得到 `ok=true`；最终 sidecar API 与 UI 状态一致，插件为 `installed/unknown/compatible`，技能为 `installed/effective disabled/compatible`，禁用原因记录为 `plugin_install_pending_approval`。已保存最终 API 摘要、harness 输入、harness JSON/Markdown 报告与两张 UI 截图，并通过 harness validate、fixture 执行、报告脱敏扫描和 `python -m py_compile scripts/agent_bench_harness.py`。下一步从步骤 16 开始运行 MCP 工具调用任务。
- 2026-06-27：完成步骤 16，运行 `AB-MCP-001-step16` 低风险 MCP 工具调用任务。已验证 `astrabridge_capabilities` server 工具发现、缺失工具错误捕获、`astrabridge_capability_routes` 参数传递和确定性结果；`vision.analyze` 路由解析到 `qwen/qwen3.7-plus` 且 UI 状态一致。同一步内修复能力路由页相关插件/技能指导在后台 registry 刷新期间长期显示 loading 的问题，并新增回归测试。已保存 raw 摘要、harness 输入、JSON/Markdown 报告和 UI 截图；验证通过 harness validate、脱敏扫描、desktop vitest、desktop typecheck、capability MCP/route sidecar tests、py_compile 和 `git diff --check`。下一步从步骤 17 开始运行自动化任务。
- 2026-06-27：完成步骤 17，运行 `AB-AUTO-001-step17` 短自动化任务。已创建手动只读自动化并触发真实 runtime run path；run 暴露无 final agent message 时不会自动终结的问题，已通过取消路径验证用户可复盘处理。同一步内修复取消后不生成 review artifact/inbox 的问题，并修复 Windows 长路径下 JSON 原子写入临时文件名过长的问题。已保存 API 摘要、harness 输入、JSON/Markdown 报告和三张 UI 截图；验证通过 automation/common sidecar tests、harness validate、脱敏扫描和 `git diff --check`。下一步从步骤 18 开始修复自动化和 dogfood ledger 体验问题。
- 2026-06-27：完成步骤 18，修复自动化和 dogfood ledger 体验问题。已新增 standalone running run 自动恢复机制，将上次进程遗留的活动 run 转为可审阅失败并生成 artifact/inbox；已新增 UI 恢复说明并修复收件箱提升输入框被挤窄的问题。用 Step 18 recovery fixture 复测 API 和 UI，保存 raw 摘要、harness 输入、JSON/Markdown 报告和三张截图；验证通过 automation sidecar tests、AutomationsPanel/i18n vitest、desktop typecheck、harness validate、脱敏扫描和 `git diff --check`。下一步从步骤 19 开始运行跨 provider 路由和 handoff 任务。
- 2026-06-27：完成步骤 19，运行 `AB-ROUTE-001-step19` 跨 provider 路由和 handoff 任务。已对 `glm/glm-5.2` 与 `qwen/qwen3.7-plus` 执行 router preview 和真实 health prompt，确认 managed key 注入、provider/model 路由、health signal 与脱敏响应摘要可用；GLM 到 Qwen 的 runtime handoff 成功，记录 1 条 provider handoff，Qwen turn completed，UI 截图确认 Qwen 会话、2 lanes、1 handoff、managed user `astra` 与 zero console errors。已修复 Codex runtime catalog `json` apply-patch 值不兼容问题，并在 project context pack 中增加 `Active provider route`。已保存 raw 摘要、harness 输入、JSON/Markdown 报告和两张截图；验证通过相关 sidecar unittest、py_compile、harness validate、脱敏扫描和 `git diff --check`。下一步从步骤 20 开始汇总第一轮 benchmark dogfood 结论并调整下一轮计划。
- 2026-06-27：完成步骤 20，汇总第一轮 benchmark dogfood 结论并调整下一轮计划。已生成 `PRIVATE/agent-bench-dogfood/reports/step20-first-round-summary.json` 与 `.md`，新增脱敏证据文档 `docs/AGENT_BENCH_DOGFOOD_EVIDENCE.md`，并在 `PLAN/AGENT_BENCH_DOGFOOD_TASK_POOL.md` 追加第二轮调整。第一轮汇总为 16 条 harness 记录、13 pass、3 partial；10 个能力族中 7 pass、2 pass after repair、1 partial；真实 API/网络记录 8 条；已知 token 信号 60370 total；截图 52 张。验证通过 summary JSON 解析、全部 harness records validate、脱敏扫描和 `git diff --check`。本计划第一轮已完成，当前进度标为 20/20。
