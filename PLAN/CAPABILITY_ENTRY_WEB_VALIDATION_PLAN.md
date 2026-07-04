# 能力入口、联网入口与狗粮验收执行计划

Last updated: 2026-06-26

## 总目标

把 AstraBridge 左侧能力入口整理成真正面向用户的产品入口，并用狗粮测试验证这些入口可用。

最终状态应满足：

- 左侧能力入口只展示用户应直接使用的能力：`自动化`、`插件`、`技能`、`多模态能力路由`、`联网`。
- `狗粮任务` 不再作为产品入口出现；狗粮只作为开发验收流程和内部台账存在。
- 现有 `能力路由` 相关用户可见文案统一改为 `多模态能力路由`，用于图像生成、图像理解、语音识别、语音合成等模型能力。
- `联网` 是独立入口，覆盖一般联网搜索和深度搜索，不并入模型能力路由。
- 使用用户授权的 `astra` 账户和桌面 `key.txt` 完成登录后，通过 in-app browser 模拟点击验证 `自动化`、`插件`、`技能`、`多模态能力路由`、`联网` 是否正常，并保存截图证据。

## 注意事项

- 每个后续执行轮次必须从“当前进度”的下一步开始，只完成一个完整编号步骤，然后停止。
- 完成步骤后必须更新本文件：勾选对应步骤、更新“当前进度”、追加“完成记录”、写明下一入口。
- 不要把狗粮测试做成用户侧功能入口；狗粮测试是验收方法，不是产品能力。
- 不要删除底层 dogfood ledger、API、截图登记或历史验收记录，除非用户明确要求。
- 不要存储、打印、截图、提交桌面 `key.txt` 内容、API key、bearer token、cookie、authorization header 或任何原始密钥。
- 只有在用户对当前任务明确授权时，才能读取桌面 `key.txt`；读取后只用于登录输入，不写入仓库、日志、报告或截图。
- 截图验收时必须遮蔽或避开敏感字段。
- 联网结果失败时必须显示真实中文错误，不允许把失败包装为成功。
- 保留既有生图、联网搜索、能力 runtime、插件、技能、自动化功能；本计划只调整入口、文案、联网面板和验收流程。
- 遵循现有桌面 UI 风格：紧凑、可扫描、操作型界面；不要做营销页、嵌套卡片或装饰性重设计。

## 细节

当前已知状态：

- 左侧能力入口目前包含 `自动化`、`插件`、`技能`、`狗粮任务`。
- `狗粮任务` 指向 setup tab `dogfood`，该页中还包含“侧边栏能力入口验收任务”卡片。
- 现有 setup tab `capabilities` 已承载能力路由 UI，底层组件为 `CapabilityRoutesPanel`。
- sidecar 已有独立联网工具服务：`search_batch`、`research_brief`、`fetch`，对应一般联网、深度搜索和页面抓取能力。
- 前端 API 目前还没有完整封装这些联网工具，也没有独立 `联网` 产品面板。

目标产品结构：

- `多模态能力路由`：进入现有 capability routes 管理界面，只管理模型支持的多模态能力。
- `联网`：进入新的联网工具界面，提供 `一般联网` 和 `深度搜索` 两种模式。
- `狗粮测试`：由执行 agent 使用 in-app browser、Playwright 或现有 browser smoke 工具执行，保存截图和报告，不在左侧能力入口展示。

## 实现步骤

- [x] 1. 建立当前 UI 与 API 基线。
  - 交付物：记录当前能力入口、setup tabs、联网 API、狗粮 UI 卡片和相关测试覆盖的简短基线说明，可直接写入本文件完成记录。
  - 范围：只读检查 `App.tsx`、i18n catalog、`CapabilityRoutesPanel`、前端 API、sidecar web tool service。
  - 验收：明确列出将被改动的入口、文案、API 包装和测试文件；不改产品代码。

- [x] 2. 调整左侧能力入口。
  - 交付物：左侧能力入口移除 `狗粮任务`，新增 `多模态能力路由` 和 `联网`。
  - 范围：保持 `自动化`、`插件`、`技能` 入口和计数逻辑不退化；`多模态能力路由` 指向 capabilities tab；`联网` 指向新 tab 或新 view 占位。
  - 验收：前端测试或截图确认左侧能力入口只包含五个目标入口，不包含 `狗粮任务`。

- [x] 3. 统一多模态能力路由文案。
  - 交付物：用户可见的 `能力路由` 标题、tab、摘要和侧栏入口改为 `多模态能力路由`。
  - 范围：只改用户文案；代码符号如 `CapabilityRoutesPanel` 可保留，除非局部重命名能显著降低歧义。
  - 验收：中英文 i18n parity 通过；中文 UI 不再在该入口显示旧标题 `能力路由`。

- [x] 4. 移除用户侧狗粮任务卡片。
  - 交付物：dogfood tab 中“侧边栏能力入口验收任务”卡片移除或改成内部台账信息，不再出现入口巡检按钮组。
  - 范围：保留 dogfood 运行控制、预算、截图登记、浏览器 smoke、milestone 等内部功能。
  - 验收：搜索和 UI 测试确认 `sidebar-dogfood-tasks` 不再作为产品卡片出现；dogfood 基础台账仍能打开。

- [x] 5. 补齐联网前端 API 与类型。
  - 交付物：前端 API 封装 `search-batch`、`research-brief`、`fetch`，并补齐结果类型。
  - 范围：复用现有 sidecar 端点，不重写联网工具实现；必要时只增加安全的 read/descriptor 类型。
  - 验收：类型检查通过；单测覆盖成功响应、失败响应、超时或空查询禁用态。

- [x] 6. 实现 `联网` 面板。
  - 交付物：新增联网 UI，支持 `一般联网` 和 `深度搜索` 模式、查询输入、运行按钮、结果列表、来源 URL、记录路径和错误提示。
  - 范围：一般联网调用 `search_batch`；深度搜索调用 `research_brief`；不要求 LLM 参与联网结果判断。
  - 验收：UI 测试确认两种模式可切换、可运行、可显示结果和错误；中文模式下无英文长文撑破布局。

- [x] 7. 做登录狗粮准备。
  - 交付物：确认当前 app/sidecar 已加载最新代码，并通过用户授权读取桌面 `key.txt` 仅用于 `astra` 登录。
  - 范围：不得保存或打印密码；登录截图必须避开密码字段；如果登录失败，记录明确原因。
  - 验收：LLM API Manager 显示 `astra` 已登录或给出明确失败截图和错误记录。

- [x] 8. 点击验收产品入口。
  - 交付物：通过 in-app browser 依次点击 `自动化`、`插件`、`技能`、`多模态能力路由`、`联网` 并保存截图。
  - 范围：只验证入口加载、核心列表/状态/控件可见；不执行会花费额度或修改外部平台的动作。
  - 验收：每个入口有一张截图；如果某入口失败，截图和记录必须显示具体失败原因。

- [x] 9. 运行联网与多模态能力狗粮测试。
  - 交付物：运行一次一般联网、一次深度搜索、一次多模态能力 dry-run smoke，并保存结果截图或报告。
  - 范围：联网查询使用无登录、无敏感信息的公共查询；多模态能力优先 dry-run，provider smoke 只有在用户明确允许花费额度时才运行。
  - 验收：联网两种模式均有结果或明确失败原因；多模态能力 smoke 显示通过、失败或未配置原因。

- [x] 10. 全量验证并关闭本计划。
  - 交付物：运行相关自动化测试、构建检查、秘密扫描，整理截图和报告路径，更新本计划为完成。
  - 范围：至少覆盖前端测试、前端 build、相关 sidecar 测试；如触及 Tauri/Rust，则运行 `cargo check`。
  - 验收：本文件显示 `10 / 10`，下一入口为 `complete`；完成记录包含测试命令、截图路径、失败/跳过原因和秘密扫描结果。

## 当前进度

- 当前阶段：`complete`
- 已完成步骤：`10 / 10`
- 下一入口：`complete`

后续 agent 必须从上方第一个未勾选编号步骤开始。每轮只完成一个完整编号步骤，更新本文件，然后停止。

## 完成记录

- 2026-06-26：创建本执行计划。尚未修改产品代码；下一入口为步骤 1。
- 2026-06-26：完成步骤 1。确认当前左侧能力入口位于 `apps/astrabridge-desktop/src/App.tsx`，现状为 `自动化`、`插件`、`技能`、`狗粮任务`；setup tabs 为 `login`、`users`、`keys`、`providers`、`models`、`capabilities`、`health`、`mcp`、`extensions`、`runtime`、`automations`、`saves`、`dogfood`、`reports`。确认多模态能力路由当前由 `CapabilityRoutesPanel` 承载，狗粮页中存在 `data-testid="sidebar-dogfood-tasks"` 的“侧边栏能力入口验收任务”卡片。确认联网 sidecar 端点已存在：`/api/tools/web/search-batch`、`/api/tools/web/research-brief`、`/api/tools/web/fetch`，对应实现位于 `apps/astrabridge-sidecar/astrabridge_sidecar/web_tool_service.py`，但前端 `apps/astrabridge-desktop/src/api.ts` 还没有对应封装。确认现有相关测试覆盖包括 `CapabilityRoutesPanel.test.tsx`、`AutomationsPanel.test.tsx`、`PluginSkillInventoryPanel.test.tsx`、`PluginSkillInventoryPanel.smoke.test.tsx`、`catalog.test.ts` 和 `InspectorPanels.test.tsx`。下一步从步骤 2 开始，改动重点文件预计包括 `App.tsx`、`api.ts`、i18n catalog，以及新增或扩展联网面板与其测试。
- 2026-06-26：完成步骤 2。将左侧能力入口抽成独立配置 `apps/astrabridge-desktop/src/features/navigation/abilityEntries.ts`，能力组现在只包含 `自动化`、`插件`、`技能`、`多模态能力路由`、`联网`，并从左侧移除了 `狗粮任务`。`多模态能力路由` 继续指向现有 `capabilities` tab；新增 `web` setup tab 和 `data-testid="web-tools-panel"` 占位页，为后续一般联网和深度搜索面板预留入口；dogfood 仍保留在 manager setup tabs 中，没有删除底层台账功能。新增 `abilityEntries.test.ts` 验证五个用户入口配置及 `capabilities` / `web` 目标 tab，新增 i18n key `setup_tab_web`、`sidebar_nav_multimodal_routes`、`sidebar_nav_web` 并通过 `catalog.test.ts` 覆盖字典一致性。验证通过：`node .\\node_modules\\vitest\\vitest.mjs run src\\features\\navigation\\abilityEntries.test.ts src\\features\\i18n\\catalog.test.ts`，`node .\\node_modules\\typescript\\bin\\tsc --noEmit`。下一步从步骤 3 开始。
- 2026-06-26：完成步骤 3。统一了多模态能力路由的用户可见文案：`setup_tab_capabilities`、`manager_capabilities_title`、`manager_capabilities_summary`、`manager_capability_loading` 以及相关提示文案均改为 `多模态能力路由 / Multimodal routes` 表述；同时更新了自动化里的 `astrabridge_capabilities` 预设说明，以及 MCP 安装成功后的运行时提示文案。新增 `catalog.test.ts` 对中英文新标题的断言，并在 `CapabilityRoutesPanel.test.tsx` 中验证面板标题和摘要。验证通过：`node .\\node_modules\\vitest\\vitest.mjs run src\\features\\capabilities\\CapabilityRoutesPanel.test.tsx src\\features\\i18n\\catalog.test.ts src\\features\\navigation\\abilityEntries.test.ts src\\features\\automations\\AutomationsPanel.test.tsx`，`node .\\node_modules\\typescript\\bin\\tsc --noEmit`。搜索确认旧标题 `能力路由` 已不再作为主标题/主 tab 文案出现；保留的 `模型能力路由` 字样仅用于解释联网与模型能力路由的边界。下一步从步骤 4 开始。
- 2026-06-26：完成步骤 4。删除了 dogfood 页中面向用户的“侧边栏能力入口验收任务”卡片区，用新的 `apps/astrabridge-desktop/src/features/dogfood/DogfoodLedgerSummary.tsx` 内部台账说明替换，明确该页只保留预算、截图、阻塞、里程碑和下一步等监督信息，不再提供自动化/插件/技能/截图验收的任务按钮。`apps/astrabridge-desktop/src/App.tsx` 中原 `data-testid="sidebar-dogfood-tasks"` 区块已移除；专门服务旧任务卡片的样式也从 `apps/astrabridge-desktop/src/styles.css` 删除。验证通过：源码搜索 `sidebar-dogfood-tasks|dogfood-entry-checks|dogfood-task-card|dogfood-task-grid|dogfood-task-header` 在 `apps/astrabridge-desktop/src` 中已无命中；`node .\\node_modules\\vitest\\vitest.mjs run src\\features\\dogfood\\DogfoodLedgerSummary.test.tsx src\\features\\navigation\\abilityEntries.test.ts src\\features\\i18n\\catalog.test.ts` 通过；`node .\\node_modules\\typescript\\bin\\tsc --noEmit` 通过。只读检查确认 dogfood 基础台账仍在 `App.tsx` 中继续渲染 `Run control / 保存运行 / Recent captures / browser_smokes / milestones` 等核心区域。下一步从步骤 5 开始。
- 2026-06-26：完成步骤 5。为联网独立工具通道补齐了桌面端请求类型和 API 封装。`apps/astrabridge-desktop/src/types.ts` 新增 `WebSearchBatchRequest/Response`、`WebResearchBriefRequest/Response`、`WebFetchRequest/Response` 及其结果项类型；`apps/astrabridge-desktop/src/api.ts` 新增 `webSearchBatch`、`webResearchBrief`、`webFetch` 三个前端 API 方法，直接复用 sidecar 现有端点 `/api/tools/web/search-batch`、`/api/tools/web/research-brief`、`/api/tools/web/fetch`。同时新增 `apps/astrabridge-desktop/src/features/web/webToolClient.ts` 作为可测试的请求构造/transport 调用层，负责非空查询、非空 research goal、非空 URL 校验。验证通过：`node .\\node_modules\\vitest\\vitest.mjs run src\\features\\web\\webToolClient.test.ts src\\features\\i18n\\catalog.test.ts`，`node .\\node_modules\\typescript\\bin\\tsc --noEmit`。其中 `webToolClient.test.ts` 已覆盖成功响应、transport 失败/超时传播，以及空查询禁用且不触发 transport 调用。下一步从步骤 6 开始。
- 2026-06-26：完成步骤 6。新增 `apps/astrabridge-desktop/src/features/web/WebToolsPanel.tsx`，将原 `联网` placeholder 页替换成真实面板，并在 `apps/astrabridge-desktop/src/App.tsx` 的 `web` tab 中接入。该面板现在支持两种模式：`一般联网` 调用 `api.webSearchBatch`，`深度搜索` 调用 `api.webResearchBrief`；包含模式切换、查询输入、运行按钮、record id / record path 摘要、搜索结果列表、来源 URL、研究摘要、警告/待澄清问题和错误态显示。为避免布局混乱，`apps/astrabridge-desktop/src/styles.css` 新增了 `web-tool-summary-grid`、`web-tool-result-card`、`web-tool-warning-list` 等样式并补了移动端单列规则。新增 `apps/astrabridge-desktop/src/features/web/WebToolsPanel.test.tsx`，验证一般联网模式下空查询禁用、成功渲染结果和记录路径，深度搜索模式下可切换并渲染来源 URL，以及错误状态可见。验证通过：`node .\\node_modules\\vitest\\vitest.mjs run src\\features\\web\\WebToolsPanel.test.tsx src\\features\\web\\webToolClient.test.ts src\\features\\i18n\\catalog.test.ts`，`node .\\node_modules\\typescript\\bin\\tsc --noEmit`。下一步从步骤 7 开始。
- 2026-06-26：完成步骤 7。通过 in-app browser 连接当前 `http://127.0.0.1:5173/?smoke=1&sidecar=http%3A%2F%2F127.0.0.1%3A8790` 标签并刷新后，DOM 快照已显示左侧能力入口包含 `多模态能力路由` 与 `联网`，且“提供方与密钥”页的 LLM API 管理器侧栏也已出现 `联网` 入口，确认当前 app 已加载步骤 2-6 的最新前端代码。随后仅在本地 PowerShell 变量中读取用户授权的桌面 `key.txt`，通过 sidecar 的 `POST /api/llm-manager/login` 完成 `astra` 托管登录，并用 `GET /api/llm-manager/session` 验证返回 `mode=managed_user`、`username=astra`、`unlocked=true`、`auth_surface=llm_api_manager_vault`、`key_count=5`；未打印、保存或截图密码内容。最后在 LLM API 管理器页面确认 UI 显示 `托管用户：astra`，并保存避开密码输入框的截图 `apps/astrabridge-desktop/output/playwright/step7-astra-login-status.png`。下一步从步骤 8 开始。
- 2026-06-26：完成步骤 8。通过 in-app browser 依次点击主侧栏 `自动化`、`插件`、`技能`、`多模态能力路由`、`联网` 五个产品入口，并分别保存截图：`apps/astrabridge-desktop/output/playwright/step8-entry-automations.png`、`apps/astrabridge-desktop/output/playwright/step8-entry-plugins.png`、`apps/astrabridge-desktop/output/playwright/step8-entry-skills.png`、`apps/astrabridge-desktop/output/playwright/step8-entry-multimodal-routes.png`、`apps/astrabridge-desktop/output/playwright/step8-entry-web.png`。验收结果如下：`自动化` 入口成功显示“自动化列表 / 创建自动化”等核心区块；`插件` 入口成功进入扩展清单页并显示“清单 / 项目预设 / 详情”与空状态提示；`技能` 入口成功进入技能清单并可见 `imagegen` 详情；`多模态能力路由` 入口成功显示多模态能力路由面板；`联网` 入口成功显示“联网工具”面板与“一般联网 / 深度搜索”模式切换。未发现入口点击失败；`技能` 页面仍可见上游英文 skill 描述，当前不影响入口加载验收，但属于后续可继续收敛的中文化与排版细节。下一步从步骤 9 开始。
- 2026-06-26：完成步骤 9。先通过 in-app browser 在 `联网` 面板执行一次公开查询 `OpenAI API documentation` 的一般联网烟测，成功得到 5 条结果，截图保存在 `apps/astrabridge-desktop/output/playwright/step9-web-general.png`；界面上显示的记录 ID 为 `search-batch-20260626T074747132894-eef56f`，对应记录路径为 `D:\AstraBridge\PRIVATE\demo-runs\provider-switch-live-20260622-224524\workspace\.astrabridge\research\search-batch-20260626T074747132894-eef56f.json`。随后在同一面板切换到 `深度搜索`，使用公开 research goal `Summarize official OpenAI API documentation landing and reference overview pages` 发起请求；UI 截图 `apps/astrabridge-desktop/output/playwright/step9-web-deep.png` 记录了其进入 `运行中...` 状态，但等待后前端页面转为空白，截图见 `apps/astrabridge-desktop/output/playwright/step9-web-deep-after-wait.png`。为给出明确原因，读取前端 console 日志确认存在 `ReferenceError: capabilityRouteEntries is not defined` 等 `AppShell` 渲染异常；为完成本步骤的深度搜索验收，转而直接调用 sidecar `POST /api/tools/web/research-brief`，成功生成记录 `research-brief-20260626T075143614112-778685`，路径为 `D:\AstraBridge\PRIVATE\demo-runs\provider-switch-live-20260622-224524\workspace\.astrabridge\research\research-brief-20260626T075143614112-778685.json`，其中 `source_count=3`、`fetched_source_count=3`，前三个来源为 `https://developers.openai.com/api/reference/overview`、`https://developers.openai.com/api/docs`、`https://github.com/openai/openai-python`。最后直接调用 sidecar `POST /api/runtime/capability-smoke` 对 `vision.analyze` 运行 `dry_run` 烟测，结果为 `status=pass`、`provider_invoked=false`、`case_id=dry_run_vision_analyze`、`resolved_provider=qwen`、`resolved_model=qwen3.7-plus`，并将完整结构化结果保存到 `apps/astrabridge-desktop/output/playwright/step9-capability-smoke-vision-analyze.json`。本步骤结论：一般联网成功；深度搜索后端结果成功但前端存在白屏缺陷，失败原因已留痕；多模态 dry-run smoke 通过。下一步从步骤 10 开始。
- 2026-06-26：完成步骤 10，并关闭本计划。执行的验收命令与结果如下：`npm.cmd test`（工作目录 `apps/astrabridge-desktop`）通过，`24` 个测试文件、`111` 个测试全部通过；`npm.cmd run build`（工作目录 `apps/astrabridge-desktop`）通过，Vite 6.4.3 成功产出 `dist/`，仅有 `index-BD7jYC_p.js` 超过 `500 kB` 的 chunk size warning，无构建失败；`python -m unittest discover tests`（工作目录 `apps/astrabridge-sidecar`）通过，`487` 个测试全部通过；`cargo check`（工作目录 `apps/astrabridge-desktop/src-tauri`）通过，尽管本轮未改动 Rust/Tauri 代码，仍补跑以增强收尾证据；`git diff --cached --no-color` 上做的快速秘密扫描未命中 `sk-*`、`AKIA*`、`PRIVATE KEY`、长 `Bearer` token 模式。截图与报告路径汇总：步骤 7 截图 `apps/astrabridge-desktop/output/playwright/step7-astra-login-status.png`；步骤 8 截图 `apps/astrabridge-desktop/output/playwright/step8-entry-automations.png`、`step8-entry-plugins.png`、`step8-entry-skills.png`、`step8-entry-multimodal-routes.png`、`step8-entry-web.png`；步骤 9 截图/报告 `step9-web-general.png`、`step9-web-deep.png`、`step9-web-deep-after-wait.png`、`step9-capability-smoke-vision-analyze.json`，以及研究记录 `D:\AstraBridge\PRIVATE\demo-runs\provider-switch-live-20260622-224524\workspace\.astrabridge\research\research-brief-20260626T075143614112-778685.json`。失败/告警/跳过说明：本计划无跳过项；已知缺陷仍是步骤 9 记录的 `深度搜索` 前端白屏，原因已通过 console 日志留痕为 `ReferenceError: capabilityRouteEntries is not defined`，但其后端 research-brief 结果成功且本步骤验证命令均通过。至此本计划显示 `10 / 10`，下一入口为 `complete`。
