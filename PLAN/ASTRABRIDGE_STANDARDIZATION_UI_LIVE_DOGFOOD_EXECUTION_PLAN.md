# AstraBridge Standardization, UI Renewal, And Live Dogfood Execution Plan

## Total Objective

在不推翻已经验证的 AstraBridge 产品能力、不破坏现有项目状态和历史证据的前提下，完成一轮可持续的第二阶段整治：

1. 规范当前文档、代码边界和 API/事件/字段契约，明确唯一真源，归档或隔离过时接口；
2. 对整个 App 做一轮以信息层级和操作效率为中心的 UI/UX 整治，消除大字体、卡片堆叠、冗余说明、低价值常驻文字和大杂烩式组件；
3. 用多个彼此独立的 Agent，通过 AstraBridge 可见 UI 的真实点击、输入、附件、任务图和自动化流程完成代表性任务；
4. 消耗受控的真实 provider token，保存脱敏运行证据，把 Agent 在真实操作中遇到的 UI/UX、状态、恢复和能力问题反馈为下一轮产品修复；
5. 建立可重复执行的文档/API 治理、视觉 QA、真实 dogfood、成本记录和回滚机制，使后续模型、provider 和产品升级不需要重新发明验证方法。

本计划是新的第二阶段执行计划，不是对已经完成工作的重跑。以下已验证记录必须保留并作为输入使用：

- `PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md`
- `PLAN/ASTRABRIDGE_APP_HARDENING_EXECUTION_PLAN.md`
- `PLAN/AGENT_BENCH_DOGFOOD_EXECUTION_PLAN.md`
- `PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md`
- `docs/REPO_GOVERNANCE.md`
- `docs/APP_HARDENING_EVIDENCE.md`
- `docs/AGENT_BENCH_DOGFOOD_EVIDENCE.md`
- `docs/TASK_GRAPH_MAINTAINER_RUNBOOK.md`

## Deliverables

- 当前文档入口、状态、所有者、替代关系和归档位置的机器可检查清单。
- 当前 API、SSE 事件、runtime payload、provider adapter 和兼容 shim 的契约清单与弃用记录。
- 已归档过时接口的替代说明、兼容策略、调用方证据和回归测试。
- App 全局 UI 密度、排版、表面层级、图标、悬停说明、弹窗/抽屉和响应式规则。
- 普通对话、编辑器、设置/Provider、能力/插件/自动化、任务图等核心界面的前后截图证据。
- 四个通过真实 UI 操作的 provider-backed dogfood 任务及其 token/费用、截图、工具轨迹、结果和问题单。
- 每个 dogfood 任务之后对应的产品修复、回归测试和点击复测证据。
- 脱敏的公开总结 `docs/APP_STANDARDIZATION_UI_DOGFOOD_EVIDENCE.md`。
- 私有证据根目录 `PRIVATE/app-standardization-ui-dogfood/`，默认永久保留。

## Product And UI Principles

这些原则是验收标准，不是可选审美建议：

1. **先操作、后解释**：主界面只保留当前动作、当前状态和必要上下文；功能说明、字段解释和次要元数据优先放入 tooltip、popover、可展开详情或按需弹窗。
2. **平铺而不是卡片大战**：页面区段使用间距、分隔线、表格、列表和工作区层级组织；禁止在卡片中继续堆卡片。卡片只用于重复实体、模态内容或确实需要边界的工具。
3. **小而清晰的字阶**：普通工作区正文以紧凑可读为准；大标题只允许出现在真正的一级页面。紧凑面板、侧栏、检查信息和任务图控件不得使用展示级字体。
4. **语义层级稳定**：全局导航 -> 当前工作区 -> 上下文工具栏 -> 主内容 -> 按需详情，不能把导航、编辑、诊断、运行记录和说明混成一个面板。
5. **图标承担熟悉动作**：常见命令优先使用 `lucide-react` 图标；图标按钮必须有 `aria-label`、可聚焦 tooltip 和可辨识的 disabled/active 状态。
6. **悬停不是唯一通道**：低价值解释可以悬停显示，但关键错误、审批、破坏性操作、当前运行状态和下一步动作必须在键盘、触屏和窄布局下可访问。
7. **不靠裁切隐藏设计问题**：长标题、provider/model 名、路径、任务状态和图节点文字必须在稳定尺寸内可理解；允许有意省略，但 tooltip/详情必须提供完整内容。
8. **工作区优先**：聊天区给内容与编辑器，任务图区给画布，管理页给扫描与比较；持续占用大面积的解释文字、装饰卡片和空白必须删除或按需展开。

建议由 Step 8 结合现有设计令牌最终校准以下字阶，而不是逐处硬编码：

- 工作区基础正文：`13px-14px`
- 次要元数据、标签、tooltip：`11px-12px`
- 紧凑区段标题：`14px-16px`
- 一级页面标题：通常不超过 `20px`
- 卡片圆角：默认不超过 `8px`，除非现有品牌组件有明确例外

## Visible-UI Dogfood Contract

Step 16、18、20、22 的 dogfood 操作必须遵守以下契约：

1. 操作者必须使用 `browser:control-in-app-browser`，在 in-app browser 中打开 AstraBridge，通过可见的点击、键盘输入、附件选择、下拉菜单和画布交互完成任务。
2. 不得用 sidecar API、直接数据库写入、localStorage 注入、DOM 脚本改状态、隐藏测试端点或预造成功记录来代替用户操作。
3. 可以在 UI 已复现结果后使用只读 API、日志和文件检查辅助诊断，但它们不能代替 UI 成功证据。
4. 任务图必须由可见 UI 完成节点添加、连线、配置、运行、审批、结果打开和必要的重试/取消操作；不得直接提交图 JSON 来跳过交互。
5. 自动化必须由可见 UI 创建、触发、查看 history/inbox/artifact；不得直接调用创建或运行端点。
6. 每个关键状态都要截图并立即视觉检查：进入页面、配置完成、运行中、成功/失败终态、产物/报告打开、发现问题和修复后复测。
7. 任何截图若出现文字溢出、重叠、卡片堆叠、无意义大标题、冗余说明、不可见主操作或状态歧义，必须登记为产品问题；不得仅因任务最终成功而忽略。
8. UI 操作中不得打开或显示明文密钥。Provider 凭据只可通过 AstraBridge 托管 Vault 注入；不得读取 Desktop `key.txt` 或其他明文 secret 源。
9. 截图前必须先通过 `ui-dogfood-browser-readiness` 的 DOM-first readiness gate。截图通道失败但 DOM 可读时，只能记录为 `browser_screenshot_channel_failure` 和“视觉验收待补”；不得误报 AstraBridge 或 sidecar 故障，也不得宣称视觉验收通过。

## Live Token And Safety Boundary

1. 真实调用只在 Step 16、18、20、22 使用；其他步骤默认使用本地测试、fixture 和已保存证据。
2. 每个 live 任务开始前必须显示并记录：provider、model、能力要求、最大请求数、预计 token 上限、最大重试次数和停止条件。
3. 默认预算上限：
   - `DG-CHAT-CODEFIX-01`：总 token 信号不超过 `30k`，最多一次完整重试；
   - `DG-MULTIMODAL-UI-01`：总 token 信号不超过 `20k`，最多一次路由重试；
   - `DG-GRAPH-PARALLEL-01`：所有节点合计不超过 `80k`，每个失败节点最多重试一次；
   - `DG-AUTOMATION-HANDOFF-01`：总 token 信号不超过 `30k`，自动触发最多两次。
4. 若 provider 不返回 usage，记录 `not_available`、请求数、持续时间和原因，不得虚构 token 或费用。
5. 默认只选择已经在 Vault 中配置且 health check 通过的 provider/model。没有官方 OpenAI 直连 key 时不把官方 OpenAI live verification 作为完成条件；不稳定聚合 provider 不作为发布门槛，除非用户明确指定。
6. 任何任务达到预算、重复失败、出现权限边界不清、可能外部写回、secret 暴露或非预期大范围改动时立即停止并保留证据。
7. 不向第三方平台写回，不发布消息，不创建外部 PR，不修改用户账户设置。

## Evidence Layout And Report Schema

私有证据统一保存在：

```text
PRIVATE/app-standardization-ui-dogfood/
  baseline/
  docs-api/
  ui/
  runs/
    DG-CHAT-CODEFIX-01/
    DG-MULTIMODAL-UI-01/
    DG-GRAPH-PARALLEL-01/
    DG-AUTOMATION-HANDOFF-01/
  repairs/
  validations/
  final/
```

每个 UI 或 dogfood 报告至少包含：

- `step_id`
- `task_id`（若适用）
- `surface`
- `app_url` 和 sidecar provenance（脱敏）
- `operator_mode`
- `visible_click_only`
- `provider` / `model`
- `capability_requirements`
- `request_count`
- `usage_signal`
- `cost_signal`
- `screenshots`
- `actions_summary`
- `agent_result`
- `product_findings`
- `severity`
- `fix_status`
- `tests`
- `redaction_status`
- `remaining_risk`
- `next_entry`

保存 raw request/response 时必须删除 API keys、Authorization、cookies、Vault password 和 provider raw secret。截图需要人工复查，因为文本 secret scan 不会 OCR 图片像素。

## Agent Roles And Handoff Model

- **Governance Agent**：负责 Step 1-6，只处理文档、接口和代码边界，不做视觉重构。
- **UI Systems Agent**：负责 Step 7-14；必须使用 `frontend-ui-engineering`，每步通过 in-app browser 点击和截图验收。
- **Dogfood Operator Agent**：负责 Step 16、18、20、22；每个 live 任务使用新的 Agent 上下文，只通过可见 UI 操作，不读取前一任务的隐含聊天上下文。
- **Product Repair Agent**：负责 Step 17、19、21、23；读取上一任务的报告、截图和脱敏轨迹，修复产品问题并用相同 UI 路径复测。
- **Independent Verifier**：在 Step 23 对文档/API、UI、live 证据、secret scan、token ledger 和剩余风险做最终审计，不以实现者的自评代替证据。

不同 Agent 可以调整实现细节，但不能把真实 UI 操作改成 API 快捷路径，也不能把真实 token 任务替换为 mock 后宣称完成。

## Constraints And Attention Notes

1. 保留 `PRIVATE/**`、截图、日志、raw call、parsed output、缓存和验证报告；除非用户明确点名，不清理任何实验产物。
2. 不重写或删除已经完成计划的历史执行记录。若旧计划会误导当前入口，在新索引中标记 `complete`、`superseded` 或 `archived` 并指向替代文件。
3. `.abproj` 和 workspace-local `.astrabridge/` 是唯一正常项目状态路径；不得复活 `.lcr*`、`.codexproj`、`.codex-shell` 或官方 OpenAI 登录路径。
4. API 弃用默认采用“盘点 -> 调用方证明 -> 替代契约 -> 小 shim -> 回归测试 -> 归档”的顺序。没有证据时不得直接删除看似过时的接口。
5. 兼容 shim 中不得增加新业务逻辑；新代码只能使用 canonical AstraBridge 名称和路径。
6. 工作区可能已有用户改动。不得回滚、覆盖或格式化与当前步骤无关的文件。
7. 每个编号步骤只允许在验收标准全部满足后标记完成；部分完成必须保留为 `in progress` 或拆分子步骤。
8. UI 步骤必须保存正常宽度和窄宽度截图，且至少包含 hover/focus/disabled 或弹窗中的一种交互状态。
9. 任何 commit/push 前必须重新运行 secret scan，并确认未 staging 私有证据和 secret-bearing raw 文件。
10. “从 Step 0 重写计划”默认只表示计划文档重置，不表示重跑已经验证的项目工作。

## Adjustment Policy

Agent 可以根据磁盘证据调整子步骤、文件名、命令、实现方式或未来步骤顺序，但不得改变总目标、降低真实 UI 操作强度、取消 live token 任务、删除视觉验收、弱化 API 弃用证据，或用更容易的 mock/报告工作替代真实产品操作。

若某个核心目标不可行，必须记录：阻塞条件、已尝试路径、原始证据、预算消耗、用户需要决定的问题，以及能最大程度保留原目标的替代方案。

## Evidence Review And Plan Revision Policy

每轮开始前先检查以下触发条件：

1. 当前代码、截图或测试与计划假设矛盾；
2. 已完成步骤的验收标准不足以支撑后续步骤；
3. 正在反复制作报告，但真正阻塞是运行时、provider、UI 或权限问题；
4. 下一步不是当前最高杠杆的阻塞项；
5. dogfood 任务无法通过可见 UI 完成，且操作者试图用 API 绕过；
6. live 任务的 token、费用、provider 稳定性或 secret 风险超出边界。

触发时必须先修订计划，并在 Progress Log 记录：检查的证据、诊断、路线变化、不可削弱的验收门槛和精确下一步。

## Execution Rules

1. 每个 Agent 回合先读本计划、`AGENTS.md` 和该步骤关联的当前文档。
2. 每个回合只完成一个完整编号步骤，除非用户明确要求改变执行规则。
3. 每轮结束前更新 Current Progress、步骤 Status 和 Progress Log。
4. UI 实现步骤使用 `frontend-ui-engineering`；可见操作和截图步骤使用 `browser:control-in-app-browser`。
5. Dogfood Operator 不得修改产品代码；它只执行任务、记录交互与反馈。紧随其后的 Product Repair Agent 负责实现修复。
6. Product Repair Agent 必须复现上一任务发现的问题，并通过相同可见 UI 路径完成修复后复测。
7. 真实调用失败不能被删除或覆盖；原始失败、重试、最终结果和 token 信号都要保留。
8. 每轮交接必须写明：完成内容、文件变化、测试、截图、live 调用、token/费用、阻塞、剩余风险和精确下一步。

## Current Progress

- Current status: Complete
- Completed steps: Step 0, Create Durable Plan; Step 1, Establish Second-Phase Baseline And Scope Map; Step 2, Build The Canonical Documentation Registry; Step 3, Normalize Active Documentation And Archive Stale Guidance; Step 4, Inventory Current And Legacy Interfaces; Step 5, Deprecate Or Archive Obsolete Interfaces Safely; Step 6, Normalize Code Ownership And Contract Validation; Step 7, Capture A Full UI Density And Hierarchy Baseline; Step 8, Establish The Compact UI System; Step 9, Renew Global Shell, Navigation, And Workspace Hierarchy; Step 10, Renew Conversation, Composer, And Artifact Surfaces; Step 11, Renew Settings, Provider, Capability, Plugin, And Automation Surfaces; Step 12, Renew The Agent Graph Canvas And Editing Flow; Step 13, Complete Tooltip, Accessibility, Responsive, And Interaction States; Step 14, Close The UI Renewal With A Cross-Surface Visual Gate; Step 15, Prepare The Live Dogfood Harness, Fixtures, And Cost Ledger; Step 16, Run DG-CHAT-CODEFIX-01 Through Standard Chat; Step 17, Repair Standard-Chat Findings; Step 17.1, Enforce Bounded Code-Fix Tool Policy And Recovery; Step 18, Run DG-MULTIMODAL-UI-01 Through Chat Attachments; Step 19, Repair Multimodal Findings; Step 20, Run DG-GRAPH-PARALLEL-01 Through Task Graph; Step 22, Run DG-AUTOMATION-HANDOFF-01 Through Automation UI
- Current step: None; Step 23, Repair Final Findings And Close The Release Gate, is complete.
- Next step: No remaining step in this plan. Start a new independent plan for any later product scope.
- Last updated: 2026-07-15
- Step 23 status: complete; the final release-gate evidence is recorded below.

## Execution Steps

### 0. Create Durable Plan

Goal: 建立独立、可交接、可验收的第二阶段执行计划，同时保留已有验证成果。

Main actions:

- 定义文档/API 规范化、UI 整治、live dogfood 和修复闭环。
- 写明可见 UI 操作契约、token 边界、证据路径和 Agent 角色。
- 把已完成的 normalization、hardening、dogfood 和 Agent Graph 计划作为输入而不是重跑目标。

Acceptance criteria:

- 本文件存在并包含总目标、约束、调整策略、证据复核策略、当前进度、编号步骤、每步验收和 Progress Log。
- Step 1 是无歧义的下一入口。
- 没有把历史完成记录重新标为待执行。

Status: completed

### 1. Establish Second-Phase Baseline And Scope Map

Goal: 建立当前文档、API、代码模块、UI surface、运行端口和已知风险的事实基线。

Main actions:

- 读取当前 active/reference/complete/superseded/archived 文档和计划，识别重复入口、编码损坏、陈旧说明和无人负责的契约。
- 盘点桌面端主要 surface、sidecar 服务、provider transports、runtime lanes、task graph、automation、plugin/MCP 和 artifact 路径。
- 在 in-app browser 中仅做只读点击，保存普通对话、设置/Provider、任务图、自动化和主要管理页的当前截图。
- 记录现有测试、构建、governance gate 和当前运行进程 provenance；不修复问题。

Acceptance criteria:

- 生成 `PRIVATE/app-standardization-ui-dogfood/baseline/step1-baseline.md` 和机器可读摘要。
- 文档、API、代码和 UI 四类范围都有 owner、current source、风险和后续步骤映射。
- 至少保存正常宽度和窄宽度基线截图，人工确认无 secret。
- 运行 quick governance gate，失败项原样记录，不在本步偷做后续修复。

Status: completed

### 2. Build The Canonical Documentation Registry

Goal: 为所有当前指导文档和执行计划建立唯一、可检查的状态与替代关系。

Main actions:

- 新增或更新文档索引，列出 path、status、owner、scope、last_verified、replacement 和 archive_policy。
- 让 `README.md`、`docs/PROJECT_SUMMARY.md`、`docs/HANDOFF.md` 和 `docs/REPO_GOVERNANCE.md` 指向同一组当前入口。
- 完成计划保留为历史记录；重复或已替代计划只在索引中降级，不改写其执行日志。

Acceptance criteria:

- 当前入口不存在互相矛盾的 active 标记。
- 任一 superseded/archived 文件都能找到替代入口或明确的历史用途。
- 文档链接检查和 governance check 通过，或只留下有证据的 warning。

Status: completed

### 3. Normalize Active Documentation And Archive Stale Guidance

Goal: 清除 active/reference 文档中的乱码、重复说明、旧产品路径和陈旧接口指导，并把历史材料归档到清晰位置。

Main actions:

- 修复 UTF-8/中文乱码、断裂列表、过期命令、旧端口和重复说明。
- 把只具有历史价值的说明移动或标记到 `docs/archive/`，保留来源和 replacement 链接。
- 将稳定事实、操作 runbook、执行记录和私有证据的边界分开。
- 增加 active 文档 mojibake、失效链接和禁用旧路径的自动检查。

Acceptance criteria:

- active/reference 文档中没有未解释的 mojibake、旧项目格式或已退役入口。
- 归档操作不删除历史证据，所有移动都有 redirect/replacement 记录。
- 文档检查和相关测试通过。

Status: completed

### 4. Inventory Current And Legacy Interfaces

Goal: 建立 API、SSE 事件、runtime payload、provider metadata、CLI/launcher 和兼容 shim 的接口注册表。

Main actions:

- 从 server、desktop consumers、tests 和 docs 双向扫描接口定义与调用方。
- 为每个接口标记 `current`、`deprecated`、`shim-only`、`test-only`、`historical` 或 `unknown`。
- 记录 owner、schema、消费者、替代接口、兼容依赖和删除前置条件。
- 把“名字旧但仍有消费者”和“完全无消费者”分开，不根据名称猜测删除。

Acceptance criteria:

- 生成公开的接口治理说明和私有机器可读注册表。
- 每个 cleanup candidate 都有至少一条定义证据和一条 consumer-search 证据。
- unknown 项不能直接进入删除步骤，必须带下一步调查入口。

Status: completed

### 5. Deprecate Or Archive Obsolete Interfaces Safely

Goal: 归档已证明过时的接口，把必要兼容逻辑压缩为显式小 shim，并阻止新代码继续使用旧入口。

Main actions:

- 对零当前消费者的接口执行受控移除或归档；对仍被历史证据依赖的接口保留最小委托 shim。
- 给弃用接口记录 replacement、sunset 条件和回归测试。
- 更新 `docs/archive/LEGACY_COMPATIBILITY_SHIMS.md` 和接口注册表。
- 增加静态检查，禁止新的 current code 引用 shim-only 名称。

Acceptance criteria:

- 所有删除都有 consumer audit 和替代契约证据。
- shim 不包含新业务逻辑，canonical tests 直接测试 canonical 实现。
- sidecar/desktop focused tests 和 quick gate 通过。

Status: completed

### 6. Normalize Code Ownership And Contract Validation

Goal: 收紧高风险模块边界，防止 provider、runtime、UI 和兼容层继续行为漂移。

Main actions:

- 根据 Step 4/5 证据处理重复 adapter、inline legacy branch、散落 schema 和不一致命名。
- 让结构化 payload 使用共享类型/验证器，而不是 ad-hoc 字符串拼接。
- 为文档状态、接口注册表、canonical imports 和 schema drift 增加本地 gate。
- 只重构与已确认漂移相关的模块，不做无边界全仓格式化。

Acceptance criteria:

- owner、canonical module 和 compatibility boundary 在代码与文档中一致。
- 新增/更新的 contract tests 能拦截旧入口回流和字段漂移。
- focused gate、desktop typecheck/build 和 quick governance gate 通过。

Status: completed

### 7. Capture A Full UI Density And Hierarchy Baseline

Goal: 用真实点击建立全 App 视觉问题矩阵，而不是从 CSS 猜问题。

Main actions:

- 使用 in-app browser 逐页点击普通对话、项目任务树、设置、Vault/Provider/Model、能力、插件/MCP、自动化、任务图和 artifact 预览。
- 每个 surface 保存正常和窄宽度截图，并检查大字体、卡片套卡片、无意义说明、空白、重复标题、控制密度、溢出、状态歧义和无 tooltip 图标。
- 把问题按 `P0 interaction blocker`、`P1 task friction`、`P2 visual debt` 分类并映射 Step 8-14。

Acceptance criteria:

- UI matrix 覆盖所有主要 surface，且每个问题有截图路径和具体选择器/组件线索。
- 不能只列审美评价；每项都说明它如何影响扫描、操作、理解或空间利用。
- 本步不做 UI 改动，确保 before 证据稳定。

Status: completed

### 8. Establish The Compact UI System

Goal: 把字体、间距、圆角、表面层级、icon action、tooltip 和 detail disclosure 统一为可复用规则。

Main actions:

- 审计并收敛 typography、spacing、radius、surface、divider、focus 和 icon-button tokens。
- 删除 viewport 驱动的非必要字号放大，建立紧凑面板与一级页面的明确字阶。
- 建立 flat section、dense list、toolbar、dialog、popover、tooltip 和 status row primitives。
- 增加 Storybook 等新系统前先证明现有架构需要；优先复用当前 React/CSS 模式。

Acceptance criteria:

- 设计令牌和 primitives 有代码、文档和测试入口。
- 示例 surface 不再依赖多层背景卡片来制造层级。
- 键盘 focus、hover tooltip、disabled 和窄宽度截图通过视觉检查。

Status: completed

### 9. Renew Global Shell, Navigation, And Workspace Hierarchy

Goal: 让全局导航、项目/任务树、顶部命令和当前工作区的层次清晰且紧凑。

Main actions:

- 删除重复标题、装饰性容器、竖向高亮条和低价值常驻说明。
- 保持 `Project -> Task` 用户语义，内部 lane 信息按需显示。
- 统一顶部命令行、返回对话/任务图切换、项目展开收起和 hover 详情。
- 让侧栏宽度、收起状态、任务数量和长标题在正常/窄布局稳定。

Acceptance criteria:

- 普通用户能在不阅读说明段落的情况下找到项目、任务、对话和任务图。
- 不存在重复页面标题、嵌套背景卡或文字/图标溢出。
- 通过桌面、窄宽度、hover/focus 和真实点击截图验收。

Status: completed

### 10. Renew Conversation, Composer, And Artifact Surfaces

Goal: 让对话内容和输入成为主角，降低消息卡片、工具栏和 artifact 元数据的视觉噪声。

Main actions:

- 收敛 message/reasoning/tool/artifact 的层级和边界，避免每个元素都成为圆角卡片。
- 把 composer 的附件、模式、provider/model、effort、语音和发送控制整合到输入框内部的紧凑工具栏。
- 删除不必要的 resize 斜线、重复标题和说明；保留必要错误、审批和运行状态。
- 检查长代码、JSON、路径、图片/PDF 预览和多轮对话滚动。

Acceptance criteria:

- composer 控件在正常和窄宽度不换成杂乱多行，不遮挡输入。
- 消息流没有卡片堆叠感，artifact 可检查且不泄露敏感路径内容。
- 普通文本、reasoning、tool error、attachment 和 artifact 都有截图及测试。

Status: completed

### 11. Renew Settings, Provider, Capability, Plugin, And Automation Surfaces

Goal: 把管理功能重组为可扫描的列表、分组表单和按需详情，消除大杂烩式管理页。

Main actions:

- 将列表选择、状态摘要、编辑表单、诊断和历史记录分层，不在同一面板同时展示所有细节。
- 短选项使用内容宽度或合理 max-width，不让简短值占满整行。
- 低价值字段解释移到 tooltip/help popover；关键错误、缺 key、审批和不可恢复状态保持可见。
- 对 Provider/Model、Capability、Plugin/MCP、Automation 分别截图和点击复测。

Acceptance criteria:

- 每个管理 surface 的主任务在首屏明确，次要诊断按需展开。
- 不存在窄栏竖排文字、巨大空白输入框、重复 tab/title 或卡片套卡片。
- 所有关联组件测试、typecheck/build 和视觉 QA 通过。

Status: completed

### 12. Renew The Agent Graph Canvas And Editing Flow

Goal: 把任务图打磨成画布优先、图标驱动、点击编辑、运行可观察的通用编排器。

Main actions:

- 画布占据主要空间；节点库收敛为窄图标列；模板、节点/边编辑和运行详情通过按钮、弹窗或按需面板打开。
- 节点标题完整可读，常见 Agent 类型使用独立图标；端口和边类型使用可解释图示与 tooltip。
- 支持可见点击添加节点、端口连线、点击/右键编辑或删除、配置提示词/输入输出契约、启动、取消、重试和打开产物。
- 检查画布缩放、平移、节点密度、长标题、并行分支、审批节点和窄视口。

Acceptance criteria:

- Inspector 不以永久右栏占用画布，编辑操作只在用户选择节点/边时出现。
- 节点/边没有文字超框、无意义图标、四点装饰或大面积空卡片。
- 通过完整“添加两个节点 -> 连线 -> 编辑 -> 运行/取消 -> 查看结果”的可见点击截图链路。

Status: completed

### 13. Complete Tooltip, Accessibility, Responsive, And Interaction States

Goal: 确保减少文字后没有牺牲可发现性、键盘操作、触屏路径和状态可读性。

Main actions:

- 为 icon-only 控件补齐 accessible name、tooltip、focus ring 和触屏可替代详情入口。
- 覆盖 hover、focus、active、selected、disabled、loading、empty、error、approval 和 destructive confirmation。
- 检查正常、窄宽度和高缩放场景中的文字、弹窗、菜单和滚动容器。
- 对 tooltip 延迟、遮挡、越界和无法通过键盘触达的问题加回归测试。

Acceptance criteria:

- 关键操作不依赖 hover 才能完成，所有 icon-only 控件可被辅助技术命名。
- 没有 tooltip 被 viewport 裁切或覆盖主操作。
- 自动化 a11y/interaction 测试与人工截图检查均通过。

Status: completed

### 14. Close The UI Renewal With A Cross-Surface Visual Gate

Goal: 用统一截图和交互门槛确认 UI 整治不是若干孤立 CSS 修补。

Main actions:

- 重新执行 Step 7 的完整点击矩阵，按相同 viewport 保存 after 截图。
- 逐项比较 before/after，统计大标题、嵌套卡片、常驻说明、溢出、重复标题和不可解释 icon 的消除情况。
- 修复本步发现的高影响回归；低影响项必须有 owner 和后续入口。
- 运行 desktop tests、build、focused UI tests 和 screenshot QA schema validation。

Acceptance criteria:

- 所有 P0/P1 UI 问题关闭或有具体 blocker，不允许模糊延期。
- 每个主要 surface 有 before/after 证据及人工 review 结论。
- 主界面层级符合 Product And UI Principles，且 build/tests 通过。

Status: completed

### 15. Prepare The Live Dogfood Harness, Fixtures, And Cost Ledger

Goal: 在消耗真实 token 前固定任务、预算、证据、停止条件和可见操作脚本。

Main actions:

- 为四个任务创建隔离 fixture、预期结果、失败判据、截图检查点和 token/cost ledger。
- 通过 AstraBridge UI 确认托管 Vault、provider health、模型能力和 current-source sidecar；不得读取明文 secret 文件。
- 为每个任务选择满足能力的 provider/model，并声明替代模型与停止条件。
- 创建只读的执行 checklist；不得创建 API 快捷执行脚本。

Acceptance criteria:

- 四个任务均有 prompt、fixture、预期 artifact、最大请求数、token 上限、重试和 abort 规则。
- health/capability 预检通过，或明确记录哪些任务 blocked 以及替代路径。
- ledger 与报告模板可解析且不含 secret 字段。

Status: completed

### 16. Run DG-CHAT-CODEFIX-01 Through Standard Chat

Goal: 用普通对话模式完成一个受控本地代码修复任务，并观察真实用户工作流。

Task definition:

- 在 `PRIVATE/app-standardization-ui-dogfood/fixtures/chat-codefix/` 提供一个小型失败测试和范围明确的实现缺陷。
- 通过 UI 新建任务，选择稳定的代码模型，输入要求：定位问题、用 patch 修复、运行目标测试、报告文件/命令/剩余风险。
- 操作者只点击 App；不得从终端直接替 Agent 执行任务。

Acceptance criteria:

- 真实 provider run 在预算内结束，或保留可诊断的失败终态。
- fixture diff 有边界，目标测试结果可复核。
- 截图覆盖配置、运行、tool/patch、终态和输出打开。
- UI/UX 问题按严重度写入 Step 17 输入，不在本步由 Dogfood Operator 修改产品。

Status: completed with P0/P1 product findings; fixture repair passed but the request was routed to the wrong task

### 17. Repair Standard-Chat Findings

Goal: 修复 Step 16 暴露的对话、composer、工具状态、patch、错误恢复或结果呈现问题。

Main actions:

- 逐项复现 Step 16 产品问题，区分 Agent 能力失败、provider 失败和 App 体验失败。
- 对 App 问题做最小但系统性的修复，补测试。
- 通过相同普通对话点击路径使用 fixture/mock 复测；若必须 live 复测，使用 Step 16 剩余预算且只允许一次短调用。

Acceptance criteria:

- 所有 P0/P1 finding 关闭或有具体外部 blocker。
- before/after 截图、测试和修复映射完整。
- 不把 provider/Agent 失败错误归因成 UI 成功。

Status: completed with a concrete runtime blocker for UI-16-03

### 18. Run DG-MULTIMODAL-UI-01 Through Chat Attachments

Goal: 用视觉模型通过普通聊天附件检查 AstraBridge 自身 UI，并验证附件、路由、结果和 artifact 链路。

Task definition:

- 通过 UI 附加 Step 14 的两张脱敏截图：正常宽度与窄宽度。
- 要求视觉 Agent 只依据可见证据输出结构化 UI QA：问题位置、严重度、原因、建议和不确定项；禁止编造不可见状态。
- 让 Agent 生成 Markdown/JSON 报告 artifact，不直接修改产品代码。

Acceptance criteria:

- 使用明确支持 vision 的模型，真实调用与 usage/cost 信号记录完整。
- 聊天附件、预览、运行状态、最终回答和 artifact 均可从 UI 打开。
- 人工核对 Agent 发现与截图一致，记录 missed issue 和 hallucinated issue。
- 产品链路问题进入 Step 19，不在本步修改产品。

Status: completed

### 19. Repair Multimodal Findings

Goal: 修复 Step 18 暴露的附件上传、视觉路由、timeout、回答检测、artifact 预览和 UI QA 呈现问题。

Main actions:

- 对每个失败判断是模型不支持、路由 metadata 错误、transport 错误、runtime finalization 错误或 UI 状态错误。
- 修复产品层问题，补 capability/transport/runtime/UI 回归测试。
- 通过相同附件点击路径复测；只在本地测试不能证明 live transport 时消耗一次短 live 调用。

Acceptance criteria:

- 视觉任务不再出现无解释卡住、错误模型路由或不可打开 artifact。
- timeout/unsupported/error 均提供明确且可行动的 UI 状态。
- before/after 截图和测试覆盖完整。

Status: completed

### 20. Run DG-GRAPH-PARALLEL-01 Through The Task Graph

Goal: 用任务图和并行 subagent 完成一个受控的跨文档/API/UI 契约审计任务，验证上下文隔离与必要通信。

Task definition:

- 通过 UI 创建或实例化图：`Planner -> [Docs Auditor, API Auditor, UI Wording Auditor] -> Synthesizer`。
- 三个并行 Agent 只读取各自明确范围，产出 typed artifacts；Synthesizer 只能消费声明的 artifacts，不继承全部隐藏历史。
- 任务范围限定为一个管理 surface，例如 Provider/Model 设置，输出一致性报告，不直接修改代码。
- 至少在两个可用 provider/model lane 间分配节点；若只有一个健康 provider，则保留多模型或多 lane 证据并记录限制。

Acceptance criteria:

- 节点添加、连线、提示词/契约编辑、模型选择、运行、并行状态、join 和结果打开全部由可见点击完成。
- 运行证据证明默认上下文隔离、声明 artifact handoff、并行分支和 synthesizer 汇总。
- token/费用按节点和总图记录，未超预算。
- UI/运行时问题进入 Step 21，不在本步修改产品。

Status: completed with findings; the bounded visible live graph run now proved downstream unlock, typed handoff, and current-source latest-run projection on a healthy sidecar, but the authoritative run `graph-run-live-20260714T063002850207-241158` failed at terminal collection with `thread/read` timeout and failed branch reconciliation, so the remaining work returns to Step 21 runtime repair rather than staying inside Step 20 acceptance

### 21. Repair Task-Graph Findings

Goal: 修复 Step 20 暴露的画布编辑、节点契约、并行状态、上下文隔离、artifact handoff、审批或运行监控问题。

Main actions:

- 将问题分为图编辑 UX、编译契约、scheduler、context projector、artifact bus 和可观察性。
- 实现修复并补 unit/contract/integration/UI tests。
- 通过相同图的可见 UI 重新实例化或重跑关键路径；不得直接提交 graph JSON 代替操作验收。

Acceptance criteria:

- P0/P1 图编辑和 runtime finding 关闭或有外部 blocker。
- UI、compiled graph、run timeline 和 artifacts 的状态一致。
- before/after 截图、测试和脱敏运行摘要完整。

Status: in progress; Step 20 is now closed with findings, and the next runtime slice must repair the remaining terminal-collection and failed-branch reconciliation defects exposed by `graph-run-live-20260714T063002850207-241158` while preserving the repaired latest-run projection and compact disclosure behavior

### 22. Run DG-AUTOMATION-HANDOFF-01 Through Automation UI

Goal: 用一轮短自动化和 provider/model handoff 验证可调度任务、history、inbox、artifact、失败恢复和成本可见性。

Task definition:

- 通过 UI 创建一次性维护任务：检查一个受控 fixture 中的文档/API manifest 漂移，生成报告，不修改外部系统。
- 首个 lane 负责提取，第二个 provider/model lane 负责验证或总结；不要求官方 OpenAI 直连。
- 从 UI 触发、观察、打开 run history、inbox 和 artifact；若路由不可用，验证用户可见的失败/恢复路径。

Acceptance criteria:

- 自动化创建、执行和检查完全通过可见点击完成。
- final state、provider/model identity、handoff、history、inbox、artifact 和 usage/cost 信号一致。
- 成功与失败路径至少有一个被真实验证，另一条可用 fixture 回归测试证明。
- 产品问题进入 Step 23。

Status: complete

### 23. Repair Final Findings And Close The Release Gate

Goal: 修复最后一轮问题，完成独立审计，并形成下一阶段清晰入口。

Main actions:

- 修复 Step 22 的 P0/P1 finding，并复测相同 UI 路径。
- 由 Independent Verifier 审核文档/API 注册表、归档接口、UI before/after、四个 live run、token ledger、screenshots、tests 和 secret scan。
- 运行 full local gate、focused sidecar/UI tests、desktop build、secret scan 和最终可见点击 smoke。
- 新增 `docs/APP_STANDARDIZATION_UI_DOGFOOD_EVIDENCE.md`，只写脱敏结果、修复主题、token/cost 总结和剩余风险。
- 更新本计划为 complete，写明任何后续第三阶段入口。

Acceptance criteria:

- 文档/API/UI 三个主目标均有可检查产物和回归门槛。
- 四个 live 任务全部为 pass、pass-after-repair 或有用户认可的外部 blocker；不能用删除失败记录换取通过。
- 所有 P0/P1 finding 已关闭或有明确 blocker/owner/next step。
- secret scan 零 finding，full gate 通过，最终证据可解析且无 secret。
- Current Progress 标记 complete，Next step 明确为无或新的独立计划入口。

Status: in progress

### 2026-07-15 - Step 23 (task-graph route and click repair)

- Implemented: current catalog-aware task-graph model recommendations, sanitized terminal worker bindings, explicit `Preflight` wording, and one native `click` path for all task-graph run controls.
- Visible evidence: the managed `astra` page produced a real `POST /api/task-graphs/dry-run` with HTTP 200 and a visible `PASS 11 / 0 / 0` run-inspection result. The preserved graph-view screenshot is `PRIVATE/app-standardization-ui-dogfood/final/20260715-step23-release-gate/task-graph-dry-run-passed.png`.
- Validation: sidecar task-graph tests 12/12; Desktop TaskGraphWorkspace tests 82/82; TypeScript and production build passed; listener/process audit found one expected frontend and one expected sidecar/router instance.
- Browser boundary: after a later browser-control timeout, the webview stopped accepting even read-only DOM commands. The broken tab was closed instead of leaving another stale page; replacement attachment also timed out. This is `browser_webview_unavailable`, not a product or sidecar failure.
- Remaining gate: the full Step 16/18/20/22 provider-backed verification set and a fresh post-patch screenshot remain pending. The release gate is intentionally not marked complete.
- Evidence: `docs/APP_STANDARDIZATION_UI_DOGFOOD_EVIDENCE.md` and the preserved private Step 23 screenshot directory.
- Next entry: triage the full sidecar baseline blocker without weakening the task-graph contract; after that, restore one claimable in-app tab, repeat task-graph Dry-run through visible clicks, then run the independent verifier over the remaining provider-backed evidence.

### 2026-07-15 - Full gate audit follow-up for Step 23

- Completed: fixed the new evidence-document registry entry and corrected the task-graph run-status labels that governance identified as mojibake.
- Validation: quick local gate passed; focused sidecar task-graph tests passed `12/12`; task-graph contract/persistence/worker tests passed `62` tests plus `14` subtests; Desktop `TaskGraphWorkspace` tests passed `82/82`; TypeScript and production build passed.
- Full-gate result: governance, secret scan, contract audit, and task-graph/API exercise passed, but the complete sidecar suite reported `883 tests, 10 failures, 11 errors`. The failures are clustered in the current automation-runner, metadata/catalog, native-kernel permission, attachment capability, task-conversation projection, and asynchronous metadata-refresh fixtures; they are separate from the Step 23 task-graph route repair. No provider call or secret was used.
- Process hygiene: final listener audit found one expected frontend listener on `4181` and one expected sidecar/router pair on `8852/8787`; no duplicate AstraBridge listener remained.
- Browser blocker: the fresh in-app browser binding still timed out while creating a tab, so no additional page or screenshot was retained. The earlier valid graph-view `PASS 11 / 0 / 0` screenshot remains the claimable UI evidence.
- Status: Step 23 remains in progress. The concrete blocker is `full_sidecar_regression_baseline`; next entry is to triage or rebaseline those failures before claiming release-gate completion.

## Progress Log

### 2026-07-10 - Step 0

- Completed: 创建第二阶段 durable handoff plan，覆盖文档/API/代码规范化、全 App UI renewal、四类 live token dogfood 和成对产品修复。
- Evidence reviewed: 已完成 repository normalization、App hardening、第一轮 Agent Bench dogfood、Agent Graph productization、仓库治理、legacy shim、UI screenshot QA 和 verification matrix。
- Preserved state: 既有完成计划、`PRIVATE/**`、截图、raw records 和验证报告均保留；本计划不是 work reset。
- Files changed: `PLAN/ASTRABRIDGE_STANDARDIZATION_UI_LIVE_DOGFOOD_EXECUTION_PLAN.md`。
- Validation: 计划结构按 `durable-handoff-plan` 模板检查，24 个步骤均有独立 `Acceptance criteria` 和 `Status`，`git diff --check` 通过；Step 1 作为唯一下一入口。
- Known baseline finding: `python scripts/repo_governance_check.py --repo .` 发现 `PLAN/AGENT_GRAPH_GUI_RUNTIME_HANDOFF_EXECUTION_PLAN.md` 两处既有 mojibake。它们不是本计划新增问题，必须在 Step 1 登记并由 Step 3 规范化，不在 Step 0 越步修复。
- Blockers: None.
- Next step: Step 1, Establish Second-Phase Baseline And Scope Map.

### 2026-07-10 - Step 1

- Completed: 建立第二阶段事实基线，覆盖文档/计划、API/接口、代码边界、UI surface、运行进程、当前测试和构建状态；未修复任何发现，也未调用真实 provider。
- Files changed: `PRIVATE/app-standardization-ui-dogfood/baseline/step1-baseline.json`、`PRIVATE/app-standardization-ui-dogfood/baseline/step1-baseline.md`、本计划进度；新增 10 张基线截图到 `PRIVATE/app-standardization-ui-dogfood/baseline/screenshots/`。
- Visible UI evidence: 使用 in-app browser 可见点击检查聊天、设置、Provider、模型、能力、插件、自动化和任务图，并在 `1280x720` 与 `900x760` 保存截图。浏览器 DOM snapshot 能力出现兼容错误后，按浏览器技能要求改用受支持的 visible-node click 与 screenshot 路径，没有切换到外部浏览器或 API 快捷路径。
- Key findings: 67 份计划缺少统一状态注册；两处既有 mojibake；官方 Codex 路由和 Desktop `key.txt` 登录/初始化仍为 active surface；`900x760` 时主工作区被导航推到首屏以下；插件和自动化页有可见文字重叠；控制台样本至少 100 条 duplicate-key warning；多个核心文件高度集中。
- Validation: `python scripts/run_local_gate.py --quick` 失败于两处既有 mojibake；`cmd /c npm.cmd test` 为 296 pass / 4 fail；`cmd /c npm.cmd run build` 通过并保留 1092.23 kB chunk warning。所有失败均原样记录，没有在基线步骤越步修复。
- Security: 真实 provider 调用 0，token 0；10 张截图人工检查未发现 credential value、密码、cookie、Authorization header 或 provider raw secret。聚焦 secret scan 初次因报告中的描述性短语产生一条 false positive，原始失败报告保留为 `step1-secret-scan-initial.json`；调整摘要措辞后最终 `step1-secret-scan.json` 为 pass、0 findings。
- Plan review: 当前证据支持继续原路线。文档状态冲突是 Step 2 的最高杠杆入口，不能先跳到 UI 修复；UI P0/P1 已明确映射到 Step 7-14。
- Blockers: None.
- Next step: Step 2, Build The Canonical Documentation Registry.

### 2026-07-10 - Step 2

- Completed: 建立文档与计划的 canonical registry。`docs/DOCUMENT_REGISTRY.json` 覆盖 101 个当前仓库入口，逐项记录 path、status、owner、scope、last_verified、replacement 和 archive_policy；`docs/DOCUMENT_REGISTRY.md` 提供面向人的优先级、状态、执行队列与归档规则。
- Classification: 101 项包含 active 14、complete 22、reference 45、superseded 19、archived 1。默认执行队列只有本计划；`PLAN/CAPABILITY_RUNTIME_IMPLEMENTATION_PLAN.md` 仅在用户明确要求 capability-runtime 实施时条件激活，因此不存在并行 active 冲突。
- Entry alignment: `README.md`、`docs/PROJECT_SUMMARY.md`、`docs/HANDOFF.md` 和 `docs/REPO_GOVERNANCE.md` 统一指向 registry、本计划和条件执行规则；旧计划正文中的历史 `In progress` 文本不再覆盖 registry 状态。
- Preservation: 19 个陈旧或重复队列只在 registry 中标记为 superseded，并提供有效 replacement；没有改写旧计划的完成日志，没有移动或删除历史证据。为满足本步 governance gate，仅修复 `PLAN/AGENT_GRAPH_GUI_RUNTIME_HANDOFF_EXECUTION_PLAN.md` 中两处已登记 mojibake，未展开 Step 3 的广泛规范化。
- Files changed: `docs/DOCUMENT_REGISTRY.json`、`docs/DOCUMENT_REGISTRY.md`、四个当前入口文档、`docs/PROJECT_LOG.md`、两处 mojibake 所在的历史计划文本和本计划；验证报告保存到 `PRIVATE/app-standardization-ui-dogfood/docs-api/step2-document-registry-validation.json` 与 `.md`。
- Validation: registry coverage 为 101 expected / 101 present，missing、extra、duplicate、missing-field、unknown-status、missing-target 和 invalid replacement 均为 0；五个入口文档的 70 个绝对本地链接均有效；`python scripts/run_local_gate.py --quick` 通过，governance 与 app-hardening 均为 0 error / 0 warning，13 个聚焦测试通过。
- Security: 真实 provider 调用 0，token 0；没有读取或持久化 key、cookie、Authorization header 或 provider raw secret；没有删除 `PRIVATE/**`、日志、截图或 raw experiment artifacts。
- Plan review: registry 已消除当前入口冲突，原路线仍然有效。Step 3 现在可以基于明确状态边界处理 active/reference 文档中的乱码、陈旧路径、重复说明和归档位置；不应提前进入接口清单或 UI 重构。
- Blockers: None.
- Next step: Step 3, Normalize Active Documentation And Archive Stale Guidance.

### 2026-07-10 - Step 3

- Completed: 以 canonical registry 为边界审计并规范 active/reference 指导，固化 registry、replacement、active-plan、当前文档链接、mojibake 和退役路径检查；没有改写完成计划的执行历史，也没有删除任何证据。
- Current-guidance result: registry 仍覆盖 101/101 个入口；当前指导为 14 active、42 reference，共 56 项，其中 55 份 Markdown。检查 107 个 Markdown 链接，missing local target 为 0；active/reference mojibake 为 0；32 个旧项目/登录标记全部具有明确禁用、负向检查、兼容边界或历史语境，非 info finding 为 0。
- Stale-guidance disposition: 将 `PLAN/CAPABILITY_UI_SURFACE_GAP_REPORT.md`、`PLAN/MULTIMODAL_CAPABILITY_SURFACE_DRIFT_REPORT.md` 和 `PLAN/PLUGIN_SKILL_SURFACE_GAP_REPORT.md` 从 reference 改为 complete，为每份文件添加 completed-snapshot banner 和维护入口。采用状态标记而非物理移动，保留稳定证据链接；唯一物理 archive 仍是 `docs/archive/LEGACY_COMPATIBILITY_SHIMS.md`。
- Historical preservation: 扩展的 mojibake 规则在 complete/superseded 历史中识别 36 条 informational finding。它们被保留用于审计，但 registry-aware gate 会阻止同类文本进入 active/reference 指导。
- Automation: `scripts/repo_governance_check.py` 新增 JSON registry 解析、101 文件覆盖、必填字段/状态/重复路径、registered target/replacement、superseded replacement、active-plan 激活、active/reference 本地链接和状态感知旧路径/乱码检查；治理测试从 7 项增加到 11 项。
- Documentation: 更新 `docs/DOCUMENT_REGISTRY.md`、`docs/REPO_GOVERNANCE.md`、`docs/VERIFICATION_MATRIX.md` 和 `docs/PROJECT_SUMMARY.md`，把 Step 1 quick-gate 失败明确为历史快照并记录 Step 3 当前结果。固定端口 `4181`/`8826` 仍是相互一致的本地示例，文档中的 server、kernel/plugin/automation smoke 和 desktop package 入口均存在。
- Evidence: `PRIVATE/app-standardization-ui-dogfood/docs-api/step3-document-normalization-validation.json`、`.md`、`step3-governance-initial.json` 和最终 governance 报告；所有中间与历史 artifact 均保留。
- Validation: Python compilation 通过；`test_repo_governance_check.py` 11 项通过；`python scripts/run_local_gate.py --quick` 通过，governance 0 error / 0 warning，app-hardening secret scan 0 error / 0 warning，quick gate 共 17 项聚焦测试通过。
- Security: 真实 provider 调用 0，token 0；没有读取 Desktop key、Vault secret、cookie、Authorization header 或 provider raw secret。
- Plan review: registry-aware 自动检查已经把文档规范化变成持续门禁，Step 3 目标已满足。下一最高杠杆入口是 Step 4 的接口注册表；不得提前进入接口删除或 UI 重构。
- Blockers: None.
- Next step: Step 4, Inventory Current And Legacy Interfaces.

### 2026-07-10 - Step 4

- Completed: 建立 current/legacy 接口注册表，覆盖 sidecar/router HTTP、SSE、runtime payload、provider metadata、MCP、CLI/launcher 和 compatibility shim；本步只取证和分类，没有删除、重命名或改变任何产品接口。
- Inventory: 私有注册表 `PRIVATE/app-standardization-ui-dogfood/docs-api/step4-interface-registry.json` 包含 251 项：219 current、14 shim-only、12 unknown、3 deprecated、2 test-only、1 historical。接口家族包括 217 HTTP、8 CLI/launcher、7 runtime payload、7 provider metadata、6 compatibility shim、4 MCP 和 2 SSE。
- Bidirectional evidence: 从 `server.py` 与 `router_service.py` AST 提取定义，从非测试 Desktop source、runtime/scripts、tests、registry-selected current docs 和 historical docs 建立消费者证据。Desktop 发现 179 个 HTTP literal path，缺少服务端定义的路径为 0。
- Cleanup boundary: 32 个 cleanup candidate 均有 definition evidence、consumer-search evidence、replacement/compatibility dependency（适用时）、removal prerequisites 和 next investigation；全部 `safe_to_remove=false`。12 个 unknown 只代表仓库内搜索证据不足，必须在 Step 5 继续调查，不能直接删除。
- Explicit classifications: singular project、top-level task/turn 和 path-form agentic-update aliases 为 shim-only；`sidecar_server.py`、两个 `lcr` Web 入口、legacy task-graph lifting 和 DashScope base-URL normalization 均有 replacement；`/api/official-codex/*` 三个禁用 guardrail route 为 deprecated；router inline adapter archive 为 historical；fake modal 与 MCP probe fixture 为 test-only。
- Tooling: 新增 `scripts/interface_registry_audit.py`，通过 AST、一次性 HTTP/text consumer index、source fingerprint 和结构验证生成注册表；新增 `test_interface_registry_audit.py` 四项测试，覆盖 Desktop-to-server 映射、alias/deprecated 分类、非 HTTP 家族和 cleanup safety。
- Documentation: 新增 `docs/INTERFACE_GOVERNANCE.md`，并更新 document registry、human registry、project summary、handoff 和 repo governance。文档注册表现为 102/102 项，14 active、43 reference、25 complete、19 superseded、1 archived。
- Development evidence: 首轮生成暴露 `server.py` UTF-8 BOM、依赖目录未剪枝和逐接口重复扫描问题；第二轮临时 PowerShell coverage 命令误解析 FileInfo；首轮 quick gate 拒绝一条缺少明确禁用语境的 legacy shim 描述。审计器现剥离 BOM、剪枝目录、使用一次性索引，并把 Desktop coverage 纳入正式测试；公开说明已明确禁止新 caller。一次 app-hardening artifact-root scan 因要求固定 evidence bucket 且重报 Step 3 描述性安全规则而失败，原报告 `step4-secret-scan.json` 保留；随后支持任意路径的聚焦扫描对 4 个 Step 4 JSON/Markdown 交付物为 0 finding。
- Validation: generator 在约 4.3 秒内通过并自检；Python compilation 通过；接口注册表测试 4/4 通过；`python scripts/run_local_gate.py --quick` 通过，governance 0 error / 0 warning，secret scan 0 error / 0 warning，quick gate 17 项测试通过；Step 4 focused artifact scan 检查 4 个文件且 0 finding。
- Evidence: `PRIVATE/app-standardization-ui-dogfood/docs-api/step4-interface-registry.json`、`step4-interface-registry-validation.json` 和 `.md`。未删除任何 `PRIVATE/**` 或历史 artifact。
- Security: 真实 provider 调用 0，token 0；没有读取或持久化 key、Vault secret、cookie、Authorization header 或 provider raw secret。
- Plan review: 事实证明 Step 5 不能执行“按旧名称批量删除”；应按高置信 shim/deprecated/test-only/historical 与 unknown 调查两条路径推进，并对每项保留 rollback/compatibility 证据。总目标和原步骤顺序仍有效。
- Blockers: None.
- Next step: Step 5, Deprecate Or Archive Obsolete Interfaces Safely.

### 2026-07-10 - Step 5

- Completed: 仅收敛一项达到“零 current import + canonical replacement + focused regression”标准的历史实现：从 `apps/astrabridge-sidecar/astrabridge_sidecar/router_service.py` 删除 5 个未使用的 inline provider adapter classes（`ProviderAdapter`、`QwenResponsesAdapter`、`ChatCompletionsAdapter`、`DeepSeekChatAdapter`、`KimiChatAdapter`）。运行时 transport 继续只通过 `providers.transports.transport_class_for_profile(...)` 选择。
- Preservation: 删除前逐字保存 40,252-character 原始区块到 `PRIVATE/app-standardization-ui-dogfood/docs-api/step5-router-inline-adapters-before.py`；`docs/archive/LEGACY_COMPATIBILITY_SHIMS.md` 记录 removal、canonical replacement 和私有证据。该 source artifact 是当前 dirty worktree 的保留记录，不依赖 Git history。
- Static boundary: `scripts/repo_governance_check.py` 新增 retired runtime symbol gate。上述 5 个 symbol 在 active code 中出现即为 error；tests、archive/history、治理规则和接口 inventory 仍为 informational context。`test_repo_governance_check.py` 增至 13 项，`test_router_transport_registry.py` 增加 module absence 断言。
- Registry and candidate outcome: `interface_registry_audit.py` 将 router inline adapters 标记为 archived historical evidence、`cleanup_candidate=false`；接口总数与对外契约状态不变，cleanup candidates 从 32 降至 31，12 unknown 保持 12，所有剩余候选仍 `safe_to_remove=false`。HTTP alias、official-codex guardrail、LCR shim、test fixture、DashScope normalizer 和 unknown routes 均未删除。
- Validation: Python compilation 通过；router transport registry 4/4；sidecar provider/router/tool suite 21/21；governance tests 13/13；interface registry tests 5/5；desktop reasoning tests 9/9；desktop production build 通过并保留既有 1092.23 kB Vite chunk warning；quick gate 通过且 governance/secret scan 均为 0 error / 0 warning。
- Secret safety: `step5-secret-scan.json` 对 4 个 JSON/Markdown 交付物为 0 finding；归档 Python block 的 focused bearer/key pattern scan 为 0 match。没有读取或保存 key、Vault secret、cookie、Authorization header 或 provider raw secret；真实 provider 调用 0，token 0。
- Evidence: `PRIVATE/app-standardization-ui-dogfood/docs-api/step5-interface-registry-before.json`、`step5-interface-registry-after.json`、`step5-interface-deprecation-validation.json`、`.md`、`step5-secret-scan.json` 和归档原始区块均保留。
- Plan review: Step 4 的风险边界得到验证。Step 5 不应继续根据静态零匹配批量删除；31 项剩余 candidate 和 12 unknown 必须由 Step 6/后续范围以 owner、contract 和真实 UI/runtime evidence 收敛。下一高杠杆步骤仍是 Step 6 的 ownership/schema drift，不降低既有清理门槛。
- Blockers: None.
- Next step: Step 6, Normalize Code Ownership And Contract Validation.

### 2026-07-10 - Step 6

- Completed: established `scripts/contract_boundary_audit.py` as the local contract-drift gate. It verifies the canonical provider transport registry; all 7 persisted task-graph fixtures through validate -> lift -> compile -> lower -> revalidate; and all 6 portable orchestration examples through validate -> compile -> lower -> lift -> revalidate.
- Ownership: added `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`. Provider metadata/policy, transport selection, normalized response IR, persisted task graphs, portable orchestration graphs, and Desktop projections now have explicit owner modules and bridge rules. The task-graph/orchestration conversion remains intentionally lossy only at the documented canonical lowering boundary.
- Regression boundary: `test_contract_boundary_audit.py` covers the green path plus a mutated provider transport registry and a lowering conversion that changes graph identity. Audit failures now remain structured per fixture/example rather than escaping as an unhelpful traceback. `scripts/run_local_gate.py --quick` runs the audit and `docs/VERIFICATION_MATRIX.md` documents it.
- Validation: contract audit passed with 3/3 checks, 4 provider families, 2 wire fallbacks, 7 persisted fixtures, and 6 orchestration examples. Contract audit tests 3/3; router transport registry 4/4; orchestration contract 5/5; compiler 7/7; Desktop `TaskGraphWorkspace` 60/60; Desktop typecheck/production build passed with the existing 1092.23 kB Vite chunk warning; governance was 0 error / 0 warning.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/docs-api/step6-contract-boundary-audit.json` and `step6-contract-boundary-validation.md` are preserved. No provider call was made by the contract audit and no secret source was read or persisted.
- Directed click note: a user-authorized in-app-browser session separately exercised conversation, Task Graph, node editor, template selection, Dry-run, and one minimal Qwen request. Screenshots are retained under `PRIVATE/app-standardization-ui-dogfood/click-qa/20260710-live-account/`. It is early evidence for Step 7 only, not a claim that Step 7's full surface matrix is complete.
- Blockers: None for Step 6. The user-authorized live request eventually cleared the composer but did not display its required exact reply; the UI switched to Plan mode and showed an empty plan. It is recorded as a failed Step 7/15 evidence path, not a successful provider verification.
- Next step: Step 7, Capture A Full UI Density And Hierarchy Baseline.

### 2026-07-10 - Step 7

- Completed: Captured a cross-surface UI density and hierarchy baseline with visible in-app browser clicks. The operator opened a recent project, entered Task Graph, opened the template picker, triggered Dry-run, checked a 900x760 viewport, and opened user settings. Existing Step 1 screenshots supply the companion chat, provider, model, capability, plugin, and automation surfaces.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/ui-baseline/20260710-step7/step7-ui-density-matrix.json` and `step7-ui-density-summary.md`, plus five current screenshots in the same directory and the ten preserved Step 1 baseline screenshots.
- Findings: P0 compact viewport navigation pushes the task graph canvas below the fold. P1 Dry-run stays visibly pending without a recovery action, the template picker wastes a large empty region, and plugin/automation views have text-control density collisions. P2 settings and provider management retain nested surfaces and repeated explanatory copy.
- Security: provider calls 0; no credential values, passwords, cookies, authorization values, or provider raw secrets were retained in Step 7 evidence.
- Plan review: the original sequence remains valid. Step 8 should first establish compact shell and density rules, then Steps 9 and 10 should address task graph layout and run-state recovery against this stable before evidence.
- Blockers: none for baseline completion. Dry-run pending state is a product finding, not a completed validation.
- Next step: Step 8, Establish The Compact UI System.

### 2026-07-10 - Step 8

- Implemented: added the shared `uiSystem.ts` contract and tests, shared compact CSS tokens/primitives, and initial `SetupLandingPanel` adoption of flat section, dense section, and dense list. The system fixes explicit spacing, typography, control geometry, surface radius, focus, dialog, popover, tooltip, and status-row primitives without starting the Step 9 shell/navigation reconstruction.
- Files changed: `apps/astrabridge-desktop/src/features/ui/uiSystem.ts`, `uiSystem.test.ts`, `styles.css`, `SetupLandingPanel.tsx`, `SetupLandingPanel.test.tsx`, `docs/PROJECT_SUMMARY.md`, `docs/VERIFICATION_MATRIX.md`, and private Step 8 screenshots/validation evidence.
- Validation: focused UI and Task Graph tests passed 64/64; production Desktop build passed with the existing Vite chunk-size warning. Desktop, 900x760, disabled-control, keyboard-focus, and focused-tooltip screenshots are retained at `PRIVATE/app-standardization-ui-dogfood/ui-system/20260710-step8/`.
- Visible repair: the initial focused Supervisor tooltip was clipped by a user-resized 72px palette sidebar. The final shared tooltip boundary rule removes horizontal clipping regardless of `data-sidebar-expanded`; the same visible keyboard path now shows the complete tooltip. Layout evidence records opacity `1`, tooltip width `196px`, sidebar overflow `visible`, and a tooltip edge beyond the sidebar boundary.
- Browser recovery: newly created browser-control tabs initially timed out while attaching. Claiming the existing user-owned in-app AstraBridge tab restored the supported visible UI path; no external browser, API, or hidden state path was used.
- Next step: Step 9, Renew Global Shell, Navigation, And Workspace Hierarchy.

### 2026-07-10 - Step 9

- Implemented: added the `shellLayout` responsive policy and converted the compact global shell from a persistent layout column into an explicitly opened navigation drawer. Compact navigation now overlays the workspace, closes on scrim click and task/project selection, and disables desktop pane resizing at the compact breakpoint. The top-level command bar shares one navigation toggle and keeps the Task Graph/Return to Chat switch visible.
- Files changed: `apps/astrabridge-desktop/src/App.tsx`, `apps/astrabridge-desktop/src/features/navigation/shellLayout.ts`, `shellLayout.test.ts`, `styles.css`, this plan, and `PRIVATE/app-standardization-ui-dogfood/ui-shell/20260710-step9/`.
- Visible validation: used the in-app browser, at `900x760`, to enter Task Graph, open the navigation drawer, dismiss it through the visible scrim, reopen it, select a task, and confirm automatic drawer closure. The graph mode command visibly changed to Return to Chat. Screenshots `compact-graph-closed.png`, `compact-graph-drawer.png`, and `desktop-graph-shell.png` record the compact and desktop states.
- Tests: focused Desktop tests passed 69/69 for `shellLayout`, `ProjectTaskTree`, and `TaskGraphWorkspace`; production build and `git diff --check` passed. The existing Vite chunk-size warning remains.
- Security and cost: provider calls 0; token/cost 0; no credential, cookie, authorization value, or provider raw secret was read or persisted.
- Residual finding: the browser console reports duplicate React keys `item-1`, `item-2`, and `item-3` outside the Step 9 shell components. Preserve this runtime finding for later global UI/runtime repair rather than masking it in navigation code.
- Next step: Step 10, Renew Conversation, Composer, And Artifact Surfaces.

### 2026-07-11 - Step 10

- Completed: renewed the conversation/composer presentation without expanding the product surface. Plan mode no longer renders an empty goal/plan dock when no current or proposed plan exists. Goal mode remains available for its real creation flow. Provider reasoning is now a low-emphasis inline summary with a divider instead of a filled rounded card; the existing explicit expand affordance remains the route to the complete text.
- Files changed: `apps/astrabridge-desktop/src/App.tsx`, `apps/astrabridge-desktop/src/styles.css`, `apps/astrabridge-desktop/src/features/runtime/goalDockVisibility.ts`, `apps/astrabridge-desktop/src/features/runtime/goalDockVisibility.test.ts`, this plan, and `PRIVATE/app-standardization-ui-dogfood/conversation/20260711-step10/step10-conversation-validation.md`.
- Visible validation: used the in-app browser to switch the visible workflow control to Plan mode, confirm the absent empty dock, inspect the flattened reasoning presentation, and resize to `900x760` to confirm that the compact shell leaves the composer as the active surface. Persisted screenshots are `chat-baseline-desktop.png`, `chat-plan-empty-desktop.png`, and `chat-plan-empty-flat-reasoning.png` in the Step 10 evidence directory.
- Tests: `goalDockVisibility` and `ComposerStarTrack` focused tests passed 5/5; Desktop production build passed with the existing Vite chunk-size warning; scoped `git diff --check` passed.
- Security and cost: provider calls 0; token/cost 0; no local attachment, credential, cookie, authorization value, provider secret, or raw provider payload was read or persisted.
- Residuals: attachment, tool-error, and artifact details were not re-run for this presentation-only repair; their baseline evidence is preserved and Steps 16, 18, 20, and 22 remain the end-to-end live verification gate. The existing duplicate React-key console warnings remain separately recorded from Step 9.
- Next step: Step 11, Renew Settings, Provider, Capability, Plugin, And Automation Surfaces.

### 2026-07-11 - Step 11

- Completed: rebuilt management surfaces around the immediate decision and an explicit disclosure boundary. The API-manager sidebar no longer duplicates locale, appearance, or cursor settings. Capability route diagnostics, candidates, smoke evidence, and artifacts are collapsed by default, while route selection and save controls remain visible. Automation keeps the schedule basics visible and collapses advanced runtime settings and activity history. The project plugin preset is also collapsed when it exists.
- Files changed: `apps/astrabridge-desktop/src/App.tsx`, `apps/astrabridge-desktop/src/features/i18n/catalog.ts`, `apps/astrabridge-desktop/src/features/automations/AutomationsPanel.tsx`, `apps/astrabridge-desktop/src/features/capabilities/CapabilityRoutesPanel.tsx`, `apps/astrabridge-desktop/src/features/extensions/PluginSkillInventoryPanel.tsx`, `apps/astrabridge-desktop/src/styles.css`, focused automation/capability tests, this plan, and `PRIVATE/app-standardization-ui-dogfood/management/20260711-step11/step11-management-validation.md`.
- In-app browser evidence: navigated through Settings -> Provider, Tools -> Multimodal capability routing, Tools -> Automation, and Tools -> Plugins and extensions with visible clicks. Capability detail and automation activity disclosures were observed collapsed by default and opened through their summaries. The current workspace has no plugin project preset, so that optional detail surface correctly did not render.
- Tests: focused automation/capability/plugin tests passed 47/47; Desktop production build passed with the existing Vite chunk-size warning; scoped `git diff --check` passed.
- Security and cost: provider calls 0; token/cost 0; no credential, cookie, authorization value, provider secret, or raw provider payload was read or persisted.
- Residuals: the existing Vite chunk-size warning and Step 9 duplicate React-key console finding remain recorded. Browser evidence could not re-click the offscreen advanced-automation summary after activity expansion; component coverage verifies the open/closed behavior.
- Next step: Step 12, Renew The Agent Graph Canvas And Editing Flow.

### 2026-07-11 - Step 12

- Completed: tightened the Task Graph canvas interaction model without adding a permanent inspector sidebar. Node ports now use directional icons in place of low-value `in`/`out` text, while their accessible names and hover titles retain the complete declared port contracts. A node or edge selection now takes priority over a pre-existing Dry-run/runtime record, so an explicit canvas selection opens its own editor instead of being redirected to run inspection.
- Files changed: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`, `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`, `apps/astrabridge-desktop/src/styles.css`, this plan, and `PRIVATE/app-standardization-ui-dogfood/task-graph/20260711-step12/step12-task-graph-validation.md`.
- In-app browser evidence: opened the visible Task Graph for `Provider Switch Live 20260622-224524`, clicked `Worker`, and confirmed its modal editor remained in the selection workspace despite the task's existing Dry-run record (`selectionEditorVisible=1`, `runPanelVisible=0`). The checked port groups no longer render `in`/`out` text, and their visible accessibility titles retain the input/output contract. Browser screenshots were captured during the interaction; no saved graph state was changed.
- Tests: focused `TaskGraphWorkspace` suite passed 62/62; Desktop production build passed with the existing Vite chunk-size warning; scoped `git diff --check` passed.
- Security and cost: provider calls 0; token/cost 0; no key file, Vault secret, cookie, authorization value, provider secret, or raw provider payload was read or persisted.
- Residuals: a provider-backed full graph author/run/approval flow remains reserved for Step 20. The current task's historical Dry-run block remains runtime evidence rather than a UI defect, and the existing Vite chunk-size warning remains open.
- Next step: Step 13, Complete Tooltip, Accessibility, Responsive, And Interaction States.

### 2026-07-11 - Step 13

- Completed: strengthened Task Graph discoverability without restoring low-value text. Palette controls now use a concise accessible name and a semantic associated tooltip description; all canvas icon-only controls have explicit accessible-name regression coverage.
- Files changed: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`, `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`, this plan, and `PRIVATE/app-standardization-ui-dogfood/interaction/20260711-step13/step13-interaction-validation.md`.
- Visible validation: in the in-app browser, clicked the Task Graph command until the workspace visibly opened, set a temporary `900x740` viewport, verified the canvas and toolbar stayed within the viewport, and clicked the visible zoom-in action. Canvas scale changed from `1.00` to `1.15`; no run was started and no graph state was saved.
- Tests: focused `TaskGraphWorkspace` suite passed 63/63; Desktop production build passed with the existing Vite chunk-size warning; scoped `git diff --check` passed.
- Security and cost: provider calls 0; token/cost 0; no key file, Vault secret, cookie, authorization value, provider secret, local attachment, or raw provider payload was read or persisted.
- Residuals: full live graph authoring/approval/parallel-run validation remains Step 20. Browser automation did not expose a direct focus method, so keyboard focus-to-tooltip behavior is covered by component regression rather than script injection. The existing Vite chunk-size warning remains open.
- Next step: Step 14, Close The UI Renewal With A Cross-Surface Visual Gate.

### 2026-07-11 - Step 14

- Completed: closed the cross-surface visual gate against the Step 7 P0/P1/P2 matrix. P0 compact-canvas hierarchy, P1 dry-run recovery, P1 template disclosure, and P1 management-surface collision findings are closed with retained before/after evidence and focused regression coverage. The only remaining visual finding is P2 Tools-landing density: duplicate title/intro copy and unnecessary framing remain operable but should be flattened in Step 23.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/ui-gate/20260711-step14/step14-cross-surface-visual-gate.md`, its schema-validatable JSON companion, and current in-app screenshots `task-graph-narrow-after.png` and `tools-narrow-after.png`. The browser revisited signed-in Provider and Tools navigation plus the settled Task Graph at `900x760`; provider and Tools DOM checks reported no horizontal shell overflow, overflowing controls, or overflowing text.
- Validation: `TaskGraphWorkspace` passed 63/63; automation/capability/plugin suites passed 44/44; Desktop production build passed with the pre-existing Vite chunk-size warning; app-hardening secret scan returned 0 errors and 0 warnings across 180 text files; scoped `git diff --check` passed with line-ending notices only.
- Security and cost: provider calls 0; token/cost 0; no credential, desktop key file, cookie, authorization value, provider secret, raw provider payload, or local attachment was read or persisted. Retained screenshots were manually reviewed for credential or vault leakage.
- Residuals: P2 Tools-landing density is owned by Step 23. The existing Vite chunk-size warning remains outside this UI hierarchy gate.
- Next step: Step 15, Prepare The Live Dogfood Harness, Fixtures, And Cost Ledger.

### 2026-07-11 - Step 15

- Completed: prepared four isolated live-dogfood fixtures, a secret-free machine-readable ledger, a read-only visible-operation checklist, and a local harness validator. The code-fix fixture intentionally begins with two bounded failing assertions; the multimodal fixture only references already redacted Task Graph screenshots; graph and automation fixtures are read-only audits with declared typed artifacts and no external writes.
- Visible preflight: used the in-app browser to open Settings and then Provider. The current UI exposes the managed-Vault login form and provider/model directory entries, but no Vault unlock or health confirmation was available without entering a secret. The ledger therefore records `locked_preflight` and blocks all live work until a subsequent operator visibly unlocks the Vault and verifies the selected route's health/capabilities. No plaintext secret file, provider credential, cookie, authorization value, or Vault record was accessed.
- Validation: `node scripts/validate_live_dogfood_harness.mjs` passed for all four task contracts and local paths with 0 provider calls; the code-fix test failed exactly as intended within the fixture (2 expected assertion failures); catalog inspection confirmed `qwen/qwen3-vl-plus` supports text and image input; scoped `git diff --check` passed.
- Security and cost: provider calls 0; token/cost 0; no raw provider request/response or secret material was persisted. The ledger has an explicit prohibited-secret-field policy and does not include any credential value.
- Residuals: live execution cannot begin until visible Vault unlock plus route-health confirmation. `deepseek/deepseek-v4-pro` and `qwen/qwen3-vl-plus` are catalog-backed candidates, not yet live-health claims.
- Next step: Step 16, Run DG-CHAT-CODEFIX-01 Through Standard Chat, after visible Vault and health preflight.

### 2026-07-11 - Step 16 (blocked preflight)

- Blocker: the visible managed-key health workflow does not provide a durable terminal result. On the in-app API Keys surface, the operator selected `deepseek` and clicked `Test selected` once. When the control settled, the page showed neither `testOutput` nor an error, and its accessible alert/status/live regions were empty. The UI therefore does not prove a provider/model is healthy enough for a cost-controlled task.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-CHAT-CODEFIX-01/step16-preflight-blocked.md`. The desktop source places the intended visible result boundary in `apps/astrabridge-desktop/src/App.tsx` near the managed-key `Test selected` action and its `testManagedKey.error` / `testOutput` rendering.
- Safety and cost: the UI action was attempted once; actual health-check usage/cost was not available from the visible UI and is recorded as `not_available`. No code-fix chat task, fixture mutation, model task, tool/patch call, or external write occurred. No secret source was read or persisted.
- Route change: Step 16 remains blocked. Run Step 17 next as a narrowly scoped preflight-repair slice for UI-16-01, then return to Step 16 and repeat the same visible health check before starting the real bounded code-fix task.

### 2026-07-11 - Step 17

- Completed: repaired `UI-16-01`, the missing managed-key health-test terminal feedback that blocked Step 16. The managed-key test now clears stale state, presents an explicit pending state, and always leaves an accessible success or failure result with route, HTTP status, usage/cost availability, diagnostic, and next action. Successful results intentionally suppress verbose response and reasoning excerpts; failure diagnostics are normalized to a bounded single line.
- Visible validation: using the same in-app Settings > API Keys path and a visible `Test selected` click, the managed DeepSeek route displayed a durable HTTP 200 success status. The final status region had `role=status`, `aria-live=polite`, and no detected horizontal overflow. Screenshots were manually reviewed: `PRIVATE/app-standardization-ui-dogfood/repairs/20260711-step17/managed-key-test-feedback.png` and `PRIVATE/app-standardization-ui-dogfood/repairs/20260711-step17/managed-key-test-feedback-compact.png`.
- Evidence and tests: `PRIVATE/app-standardization-ui-dogfood/repairs/20260711-step17/step17-managed-key-health-feedback.md`; `managedKeyTestFeedback` tests passed 5/5; desktop production build passed with the existing Vite chunk-size warning; the app-hardening secret scan passed with 0 errors and 0 warnings across 180 text files.
- Safety and cost: two short managed-key health checks occurred during repair validation. The visible provider result reported usage and cost as `not_available`; no code-fix task, fixture mutation, Agent tool call, patch, or external write was started. No plaintext secret source was read or persisted.
- Remaining risk: the selected route's short health response does not validate the full code-fix workflow. Step 16 must still create and run the bounded ordinary chat task through the UI and retain its independent screenshots, task result, artifact evidence, and token ledger.
- Next step: Step 16, Run DG-CHAT-CODEFIX-01 Through Standard Chat.

### 2026-07-11 - Step 16

- Completed dogfood run: the operator used only visible in-app UI to create `DG Chat Codefix 01`, select `deepseek/deepseek-v4-pro`, set default work mode, and submit one bounded fixture-repair request. The provider completed in about 39 seconds, repaired only `PRIVATE/app-standardization-ui-dogfood/fixtures/chat-codefix/src/normalize-issue.mjs`, and the independent target-test check passed 2/2. The provider exposed no usage or cost signal in the UI, so both remain `not_available`.
- Critical result: the created task was not activated before send. The prompt and provider run were attached to the pre-existing Step 11 conversation; its injected context names that prior task. Re-opening the visibly created `DG Chat Codefix 01` task after completion showed an empty message stream. This is `UI-16-02` (P0) because work can silently execute under the wrong task context.
- Additional findings: `UI-16-03` (P1), the agent used a direct shell edit after an explicit `apply_patch` instruction; `UI-16-04` (P2), task creation/selection lacks a durable active-task confirmation and leaves stale conversation content visible. No retry was made because it would consume a second provider run without fixing the task-binding failure.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-CHAT-CODEFIX-01/step16-standard-chat-report.md`, configuration/running/final/empty-task screenshots under the same directory, and the updated `PRIVATE/app-standardization-ui-dogfood/runs/step15-live-dogfood-ledger.json`.
- Safety: one bounded provider call; no plaintext secret source read, no external write requested, no model network task requested, and no user-account change attempted. The model's fixture edit is retained as historical evidence; it is not proof that the isolated-task workflow is correct.
- Next step: Step 17, Repair Standard-Chat Findings (`UI-16-02` through `UI-16-04`) before any live standard-chat retry.

### 2026-07-11 - Step 17 (standard-chat routing repair)

- Completed: repaired `UI-16-02` by making the persisted project task pointer authoritative over a stale `current_task` query response, and by keeping the server-returned sidebar selection guarded until query cache reconciliation completes. Repaired `UI-16-04` with a compact, accessible composer task-context label and an explicit sidebar-selection error message instead of silently swallowing selection failures.
- Visible validation: in a fresh in-app browser session, the operator clicked the visible `DG Chat Codefix 01` sidebar row. The composer context became `DG Chat Codefix 01` and the selected task rendered an empty message stream (`0` articles), rather than retaining the old Step 11 conversation. Screenshot: `PRIVATE/app-standardization-ui-dogfood/repairs/20260711-step17/task-selection-context.png`.
- Runtime boundary: the isolated sidecar had no configured provider key and did not load the selected task's execution lane, so no second provider request was submitted. `UI-16-03` remains a concrete capability gap: ordinary app-server turns expose only permission mode, not a verified per-tool allow-list that can enforce `apply_patch`-only edits. The prior direct-shell behavior remains preserved as evidence and is not described as compliant.
- Evidence and validation: `PRIVATE/app-standardization-ui-dogfood/repairs/20260711-step17/step17-standard-chat-routing-repair.md`; `taskThreadRestore` tests passed 5/5; the desktop production build passed with the existing Vite chunk-size warning. This repair validation incurred 0 provider calls and 0 token/cost signal.
- Next step: Step 18, Run DG-MULTIMODAL-UI-01 Through Chat Attachments, after a visible managed-Vault and vision-route preflight.

### 2026-07-11 - Step 18 (visible preflight blocked)

- Blocker: the prior managed sidecar on port `8815` did not load or capture a visible browser page within the browser timeout. The responsive instance on port `8816` visibly rendered AstraBridge but showed an anonymous session and `缺少当前设置下的 Key，请设置`; no visibly healthy vision-capable route was available.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-MULTIMODAL-UI-01/step18-visible-preflight-blocked.md` and `step18-anonymous-missing-key.png`. The screenshot was manually reviewed and contains no credential value.
- Safety and cost: no attachment, provider request, model task, artifact generation, or external write occurred; provider calls and token/cost signals are 0. No plaintext secret source was accessed.
- Next entry: remain at Step 18. Resume only after the user visibly unlocks a responsive managed Vault session and the UI displays a healthy vision-capable provider/model route; then run the full attachment workflow through visible clicks.

### 2026-07-11 - Step 17.1 (execution-policy hardening)

- Completed: added a per-turn `standard` / `patch_only` execution-policy contract to the desktop request, sidecar route, and runtime. `patch_only` now fails closed before `turn/start` unless the app-server profile explicitly advertises verified native patch-only enforcement. It never silently falls back to shell access.
- Fallback behavior: a verified strict turn automatically declines command, file-change, and legacy command approvals; the action is recorded without command payload. Thread reads attach `executionPolicy` evidence. A prohibited command/file trace makes a terminal turn `violated`, sets `compliant_success` to false, and prescribes review plus a fresh constrained retry. No automatic file revert is attempted because that could overwrite user work.
- UI: added a compact composer execution-policy picker with accessible labels and hover titles. It defaults to standard behavior and avoids a persistent explanatory panel.
- Validation: five targeted sidecar tests passed; Python compilation passed; desktop production build passed with the existing Vite chunk-size warning; scoped secret scan found no candidate secret. Provider calls: 0. Token/cost signal: 0.
- Visible UI validation: after the authenticated `astra` session returned, the operator clicked the composer policy picker, selected `仅补丁`, verified its visible state, then restored `标准执行`. This is recorded in `PRIVATE/app-standardization-ui-dogfood/repairs/20260711-step17/step17-1-execution-policy-hardening.md`.
- Next step: Step 18, restore a responsive authenticated project session, repeat the visible picker interaction, then complete the attachment dogfood workflow.

### 2026-07-11 - Step 18 (runtime recheck)

- Recheck: the managed process on `8815` still owns its listening port, but `GET /health` timed out after five seconds. The separately started `8816` process returned HTTP 200, confirming that the browser failure is backed by an unresponsive managed sidecar rather than a browser-only render fault.
- Boundary: the responsive `8816` UI remains an anonymous, missing-key session and cannot be used to substitute for the authenticated vision-route acceptance gate. No process was terminated, no account was changed, and no secret source was accessed.
- Next entry: remain at Step 18 until the `8815` session becomes responsive or the user visibly establishes an authenticated managed-Vault session with a healthy vision route.

### 2026-07-11 - Step 18 (third blocked recheck)

- Repeated blocker: a third no-side-effect health recheck produced the same result: `8815 /health` timed out after five seconds while `8816 /health` returned HTTP 200. The responsive route remains an anonymous missing-key UI, so it cannot satisfy the authenticated vision-route gate.
- Decision: no further retries, process changes, Vault inspection, or substitute provider calls are justified without an external session-state change. The durable plan remains at Step 18 with the same exact unblock condition.
- Next entry: resume Step 18 only after a responsive authenticated managed-Vault session visibly exposes a healthy vision-capable provider/model route.

### 2026-07-11 - Step 18 (authenticated route and thread-create blocker)

- Visible preflight: the authenticated managed `astra` session was restored on `8815`. The Runtime Health page visibly recorded `qwen/qwen3.7-plus` as `web pass / pass`, and the composer visibly selected the Qwen route. This closes the prior missing-session / missing-key condition.
- Visible failure: creating the isolated `DG Multimodal UI 01` task displayed `The desktop sidecar did not respond in time for /api/runtime/threads/create.` The sidebar still rendered the task while the conversation pane was empty, leaving an unconfirmed local task without a safe thread target.
- Safety and cost: no attachment chooser, provider request, model response, artifact write, or external write occurred. Provider calls and token/cost signals remain `0`.
- Required repair: make thread creation timeout recovery idempotent and user-visible. A retry must reconcile a server-created thread if it eventually succeeded, or roll back the local task before retrying; it must never silently route an attachment to an older task.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-MULTIMODAL-UI-01/step18-visible-preflight-blocked.md`.
- Next entry: remain at Step 18. Repair and visually validate the thread-create recovery path, then repeat the bounded Qwen attachment task.

### 2026-07-11 - Step 18 (idempotent thread-create recovery implemented)

- Repair: desktop thread creation now carries an operation ID. The sidecar registers it before waiting for the runtime start lock, records terminal completion or failure, and exposes a recovery read endpoint. Recovery never sends a second `thread/start` request: it returns `pending`, the original completed thread, or a terminal error.
- UI: a create error exposes the compact tooltip-backed `检查创建状态` action. It does not retry the provider; a completed recovery selects the confirmed task/thread while pending and failed states stay visible.
- Validation: two focused sidecar recovery tests passed, including the no-duplicate-start invariant; Python compilation passed; desktop production build passed with the existing Vite chunk-size warning. No provider or attachment request was made.
- Visual QA: the authenticated in-app browser health page was screenshot after the compact-list repair. Its results list now renders model, short route summary, and status without text overlap; long diagnostics are no longer rendered in the list body.
- Remaining acceptance gap: port `8815` is an already-running Python sidecar. Reload it, then use visible UI to create a bounded task, reproduce/recover a pending create operation, and only then resume the attachment test.
- Next entry: remain at Step 18. Reload the managed sidecar and complete the visible thread-create recovery plus the bounded Qwen attachment workflow.

### 2026-07-11 - Step 18 (fresh-sidecar session boundary confirmed)

- Environment check: a fresh sidecar from the updated source was started on `8817` without terminating the user-managed `8815` process. `GET /health` returned HTTP `200`.
- Visible result: the `8817` application page was anonymous and displayed `缺少当前设置下的 Key，请设置`; it did not inherit the managed `astra` Vault session. Returning to `8815` rendered the new-project surface instead of the previous authenticated task session.
- Safety: no desktop key file, password, Vault secret, cookie, token, provider request, attachment, or external write was accessed. The fresh process and its stdout/stderr logs are preserved under the Step 18 evidence directory.
- Remaining acceptance gap: the recovery endpoint is source-tested but cannot be exercised against a real managed provider until the user visibly restores the `astra` managed session on the updated sidecar. A fresh anonymous sidecar is not an acceptable substitute.
- Next entry: remain at Step 18. Restore the managed session visibly, then use only UI clicks to verify recovery and complete the bounded multimodal attachment run.

### 2026-07-11 - Browser Readiness Gate

- Implemented: added the project skill `apps/astrabridge-sidecar/skills/ui-dogfood-browser-readiness/SKILL.md`. It requires a claimed user-visible tab, page-specific DOM readiness signal, pre/post interaction screenshots, bounded retry, and final tab handoff.
- Failure boundary: browser tab/webview failure, session or route mismatch, screenshot-channel-only failure, and actual app/sidecar surface failure are now separate classifications. A readable DOM plus failed screenshot is functional evidence only; it leaves visual acceptance pending and cannot be reported as a product defect or a visual pass.
- Plan contract: Step 16/18/20/22 now explicitly require this gate before screenshot-dependent acceptance. The skill validator passed. No provider, attachment, secret read, or external write occurred.
- Next entry: remain at Step 18. Restore the managed session visibly, then use the readiness gate before testing thread recovery and the bounded multimodal attachment workflow.

### 2026-07-11 - Metadata Editor Scroll Repair

- Repair: the narrow-layout media rule removed the only `max-height` from the shared `metadata-detail-pane` while the workspace itself suppressed page scrolling. Long model contracts were therefore clipped after `推理与温度`. The detail pane now owns vertical scrolling at every breakpoint, reserves a visible scrollbar gutter, supports keyboard focus, and prevents horizontal overflow.
- Scope check: this class is shared by model, provider, and other metadata editor detail forms, so the repair prevents the same inaccessible-long-form failure across those surfaces rather than special-casing one model section. The unrelated task-graph `max-height: none` rules use their own run-panel scrolling contract and were not changed.
- Validation: desktop production build passed with the existing Vite chunk-size warning. The required visual recheck is pending: the first claimed in-app tab timed out during webview attachment, and the single permitted local-tab fallback also timed out before DOM readiness. This is classified as `browser_webview_unavailable`, not a product failure or a visual pass.
- Next entry: retry the model-editor screenshot only after the in-app webview is claimable, then continue Step 18 from the managed-session restoration gate.

### 2026-07-11 - Step 18 (managed session restored)

- Visible session result: after explicit one-time user authorization, the local managed-Vault login for `astra` succeeded on the updated `8817` sidecar. The visible post-login page showed five managed keys and five verified models. The password was cleared from the visible form and automation memory immediately after submission; no value was persisted in repository evidence.
- Security repair: a DOM snapshot after a password fill exposed the field value despite `type=password`. Sensitive desktop inputs now carry `data-sensitive-field` plus appropriate `autocomplete` values, and `ui-dogfood-browser-readiness` now forbids DOM, screenshot, console, or value capture after sensitive-field fills until clearing or replacement. Login is verified through non-sensitive session status only.
- Live-task boundary: an isolated task creation was clicked but the visible task context remained the old active Step 11 task while it was sending. No attachment or provider request was sent from that ambiguous context. This is not counted as a Step 18 run.
- Next entry: remain at Step 18. Wait for the old task to become idle, visibly create and switch to the isolated task, then perform Qwen health preflight and the bounded attachment workflow.

### 2026-07-11 - Step 18 (isolated task-create retry still blocked)

- Visible retry: after the old Step 11 inspector showed `空闲`, the operator created `DG Multimodal UI 01 Retry 2` through the normal dialog. The visible composer context did not change to that title, and the old Step 11 inspector switched back to `正在发送`.
- Boundary: the target task identity was not visibly confirmed, so no attachment chooser, Qwen prompt, provider request, artifact, or token-consuming multimodal operation was attempted.
- Product finding: task creation/recovery remains ambiguous when an older task's runtime or goal runner resumes. The UI needs an explicit pending state tied to the create operation and must not leave the old task as the active send target during creation.
- Next entry: remain at Step 18. Diagnose and repair the task-create/runtime-activity synchronization path, then repeat the isolated task creation through visible UI before any Qwen attachment preflight.

### 2026-07-11 - Step 18 (async task-create repair; visual recheck blocked)

- Live evidence: the visible `DG Multimodal UI 01 Retry 4` create action now rendered a first-viewport pending state with its name and an explicit old-task input boundary. The composer was disabled, so no attachment or prompt could be misrouted while creation was unresolved.
- Repair: manual new-task creation now starts an idempotent background runtime operation through `/api/runtime/threads/create/start`; it returns immediate pending/completed/failed state instead of holding the user-facing HTTP request behind the serialized app-server start lock. The existing synchronous create route remains for automatic send creation. Recovery only reads the same operation and uses a bounded five-second request.
- Validation: focused sidecar recovery tests 3/3 passed; desktop waiting-state tests 7/7 passed; desktop production build passed with the existing Vite chunk-size warning. A fresh `8818` sidecar from the repaired source returned health 200.
- Visual boundary: after navigating the in-app browser to `8818`, both DOM and screenshot commands timed out; one permitted fresh-tab fallback also timed out during webview attachment. This is `browser_webview_unavailable`, not an application visual pass or failure. No second managed login, attachment, provider request, model response, or token-consuming action occurred.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-MULTIMODAL-UI-01/step18-thread-create-async-repair.md`.
- Next entry: remain at Step 18. Once the in-app webview is attachable, visibly restore `astra` on `8818`, verify the immediate pending/recovery task handoff, then run the bounded Qwen attachment workflow.

### 2026-07-11 - Step 18 (webview reattachment still unavailable)

- Recheck: the old authenticated `8817` tab was briefly claimable and visibly rendered the existing dogfood project and isolated task list. Navigation to repaired `8818` reached the launcher and began opening the same project, but the in-app browser control kernel timed out during the loading surface. After reconnecting, the browser bridge exposed no claimable user tab.
- Boundary: `8818 /health` remained HTTP 200. This is a repeated `browser_webview_unavailable` condition, not evidence of a sidecar crash or a visual acceptance pass. No visible managed login occurred on `8818`; no attachment, provider request, model response, artifact, or external write was attempted.
- Evidence: appended `2026-07-11 Reattachment Recheck` in `PRIVATE/app-standardization-ui-dogfood/runs/DG-MULTIMODAL-UI-01/step18-thread-create-async-repair.md`.
- Next entry: remain at Step 18. Reattach a visible in-app tab, restore `astra` on `8818`, and use only the normal UI to verify the asynchronous pending/recovery task handoff before the Qwen attachment workflow.

### 2026-07-11 - Step 18 (disconnect diagnostic hardening)

- Repair: normal JSON and file response writers now stop cleanly on a client disconnect instead of falling into the generic request handler and attempting a second HTTP 400 response. This removes misleading `ConnectionAbortedError` stack traces created when the browser bridge times out after a response is prepared.
- Validation: focused disconnect and thread-create tests passed 4/4; `server.py` and `runtime_service.py` compiled successfully. This validation made no provider call or external write.
- Boundary: the in-app browser still exposed no claimable tab after the reattachment failure. The repair improves diagnosis only; the required visible `astra` login on `8818`, task creation/recovery, and Qwen attachment acceptance remain pending.
- Evidence: appended `2026-07-11 Disconnect Diagnostic Repair` in `PRIVATE/app-standardization-ui-dogfood/runs/DG-MULTIMODAL-UI-01/step18-thread-create-async-repair.md`.
- Next entry: remain at Step 18. Reattach a visible in-app tab, restore `astra` on `8818`, and use only the normal UI to verify the asynchronous pending/recovery task handoff before the Qwen attachment workflow.

### 2026-07-11 - Step 18 (explicit managed-login attempt interrupted)

- User authorization: the user explicitly authorized a one-time `Desktop/key.txt` read for the `astra` managed-Vault login on `8818`.
- Visible result: the page exposed the ordinary anonymous login form. Browser control timed out during the non-sensitive username replacement, so the first submission used the default `user` name. That managed session was visibly signed out; sidecar state then confirmed anonymous mode.
- Boundary: subsequent attempts to set the visible username to `astra` through the DOM and native keyboard paths reset or lost the browser-control kernel before submit. The final bridge recheck had no claimable tab. No direct login API, session/cookie injection, attachment, provider request, model response, artifact, or external write substituted for the visible UI.
- Evidence: appended `2026-07-11 Explicit astra Login Attempt` in `PRIVATE/app-standardization-ui-dogfood/runs/DG-MULTIMODAL-UI-01/step18-thread-create-async-repair.md`.
- Next entry: remain at Step 18. Once an in-app tab is claimable, use the normal login panel to set the username to `astra`, enter the user-authorized desktop Vault password without capture, and verify only the non-sensitive `托管用户：astra` status before continuing the asynchronous task-create and Qwen attachment acceptance.

### 2026-07-11 - Step 18 (resumable managed session repaired)

- Root cause: `LlmApiManagerService` always initialized an anonymous in-memory session. A new sidecar did not inherit an unlocked encrypted Vault even though the Windows account and Vault files were unchanged. The desktop Web API client also cached the first `?sidecar=` route in a module-level promise, so visible navigation to a new local sidecar kept session queries on the old instance.
- Repair: after a successful managed login, the service stores only the derived Vault unlock key in Windows Credential Manager and persists a non-secret username/reference record in manager state. A fresh Windows sidecar restores the Vault through that credential; explicit logout removes the reference. The login panel now uses a native existing-user selector rather than a hard-coded `user` text default. Browser-side requests now resolve the current query sidecar URL for every request; only Tauri keeps its stable route cache.
- Visible and runtime proof: through the normal UI the user-authorized `astra` login on `8819` succeeded with five managed keys. A separate fresh `8820` process then reported `managed_user`, `astra`, five keys, and `windows_credential_manager_resume` without another password read. Manager persistence/login plus disconnect tests passed 4/4; desktop production build passed with the existing Vite chunk-size warning.
- Remaining visual boundary: the in-app browser control kernel timed out while reloading the `8820` page, so the final visible `托管用户：astra` screenshot is pending. No attachment or provider request was sent during this repair.
- Evidence: appended `2026-07-11 Resumable Managed Session Repair` in `PRIVATE/app-standardization-ui-dogfood/runs/DG-MULTIMODAL-UI-01/step18-thread-create-async-repair.md`.
- Next entry: remain at Step 18. Once the browser page is claimable after the reload, verify the visible resumed `astra` session, then run the asynchronous task-create handoff and the bounded Qwen attachment workflow through normal UI clicks.

### 2026-07-11 - Step 18 (live create recovered; Qwen turn-start remains blocked)

- Visible route/session: a fresh `8834` sidecar page rendered `托管用户：astra` through the managed-Vault resume path. The explicit `?sidecar=` query is now honored before Tauri routing, preventing the prior anonymous/default-sidecar split.
- Visible create result: using the normal `新任务` dialog created `DG Multimodal UI 01 Recovery 10`. After recovery, it appeared in the task tree with its own active lane and no desktop-sidecar timeout error. The start/recovery receipt timeout is now bounded at 20 seconds, and project-open no longer synchronously waits for old app-server shutdown.
- Live model boundary: a minimum real composer request selected `Qwen / DashScope · qwen3.7-plus`. Redacted runtime events showed the turn reached the local router, exhausted five reconnects on `401 Missing or invalid router token`, and completed with an error while the UI still displayed `正在启动下一轮对话`. No image attachment was attempted after the turn failed to reach a stable ready/completed state.
- Validation: focused thread-create tests passed 5/5; server/runtime compilation and desktop production build passed. Browser DOM remained available; the screenshot channel remains unavailable, so visual screenshot acceptance is still pending.
- Evidence: appended `2026-07-11 Explicit Sidecar Route And Live Task-Create Recovery` in `PRIVATE/app-standardization-ui-dogfood/runs/DG-MULTIMODAL-UI-01/step18-thread-create-async-repair.md`.
- Next entry: remain at Step 18. Repair local router-token propagation/reconciliation on app-server startup and project/runtime switching, then make the composer consume terminal error notifications. Repeat the same visible Qwen request until it reaches a correctly rendered terminal response before attempting the Qwen image attachment workflow.

### 2026-07-11 - Step 18 (router launch contract and terminal-state repair)

- Router repair: `RouterService` now provides an instance-private launch environment, and `RuntimeService` uses it for both config rendering and app-server spawn. This removes the implicit process-global token/port dependency that produced the observed Qwen local-router `401`.
- UI repair: clearing a terminal turn now removes its live turn id instead of only its streamed content. Redacted runtime errors are promoted to a compact composer failure after the matching terminal event, so an error-only response cannot leave the composer stuck in sending state.
- Validation: router suite passed 14/14, focused desktop activity-state tests passed 4/4, Python compilation passed, and the desktop production build passed. A fresh `8835` sidecar resumed `astra` with five managed keys.
- Browser boundary: the fresh `8835` page could not attach to the in-app webview control channel, so no visible Qwen retry or screenshot was available. This is `browser_webview_unavailable`, not a successful live-provider verification.
- Evidence: appended `2026-07-11 Router Launch Contract And Terminal UI Recovery` in `PRIVATE/app-standardization-ui-dogfood/runs/DG-MULTIMODAL-UI-01/step18-thread-create-async-repair.md`.
- Next entry: remain at Step 18. Reattach an in-app page to `8835`, use visible controls to send the same bounded Qwen text request, verify either a final response or a compact terminal error with the composer re-enabled, then continue with the Qwen attachment workflow only after that route is healthy.

### 2026-07-11 - Step 18 (visible terminal-state recovery confirmed)

- Visible result: the retained page routed to `8835` showed the managed `astra` session and switched through the normal selector to `Qwen / Qwen3.7 Plus`. The prior error-only turn was idle with a compact `模型运行失败` message rather than a permanently loading composer. This validates the terminal live-turn cleanup at the user-visible level.
- Browser boundary: after the visible provider switch, the in-app CDP bridge returned an internal interaction failure and then timed out while resolving the send control. No new provider request, attachment, or artifact action was submitted. Screenshot acceptance remains unavailable.
- Evidence: appended `2026-07-11 Visible Terminal-State Recheck` in `PRIVATE/app-standardization-ui-dogfood/runs/DG-MULTIMODAL-UI-01/step18-thread-create-async-repair.md`.
- Next entry: remain at Step 18. Once the browser bridge is stable, submit the bounded Qwen text request through the composer and verify a final response before attachment testing. Treat the repeated browser control timeout as `browser_webview_unavailable`, not a provider pass or fail.

### 2026-07-11 - Step 18 (terminal snapshot and launcher density repair)

- Repair: terminal app-server notifications now schedule a background thread snapshot sync, persist the final decorated thread into task conversation storage, and preserve the completed pinned provider lane as the visible task thread. `TaskConversationService` now resolves full task records instead of compact sidebar list items when mapping a thread snapshot back to a task.
- UI repair: the launcher recent-project list no longer prints full workspace paths in the left column. It shows the project name, relative update time, and a compact workspace folder label; full workspace and project-file paths remain available via hover/title metadata.
- Validation: focused recovery/terminal-projection tests passed 3/3; desktop activity-state tests passed 4/4; disconnect tests passed 4/4; Python compilation passed; desktop production build passed with the existing Vite chunk-size warning. Fresh sidecar `8838` restored managed `astra` and Qwen secret, and the visible page showed no missing-key, blocked, or runtime-failure state.
- Boundary: the current browser page was inside an already-open project, not the launcher surface, so the compact recent-project list still needs a direct visual screenshot when the launcher is visible. The Qwen text-plus-image attachment workflow remains pending.
- Evidence: appended `2026-07-11 Terminal Snapshot Projection And Recent-Project Density Repair` in `PRIVATE/app-standardization-ui-dogfood/runs/DG-MULTIMODAL-UI-01/step18-thread-create-async-repair.md`.
- Next entry: remain at Step 18. Return to the launcher to visually confirm compact recent-project rows, then retry the bounded Qwen attachment flow through visible UI clicks.

### 2026-07-11 - Step 18 (launcher path compression follow-up)

- User feedback isolated one remaining launcher density defect: recent-project rows still rendered full workspace paths as always-on text in the left column.
- Repair: launcher recent-project rows now show only project name, relative time, and a compact workspace-folder tail. Full workspace and `.abproj` paths moved to hover/title metadata and accessibility labels.
- Validation: desktop production build passed. The current in-app session remained inside the already-open workspace rather than the launcher, so a direct launcher screenshot from the repaired code is still pending.
- Evidence: appended `2026-07-11 Launcher Recent-Project Path Compression Follow-up` in `PRIVATE/app-standardization-ui-dogfood/runs/DG-MULTIMODAL-UI-01/step18-thread-create-async-repair.md`.
- Next entry: remain at Step 18. Revisit the launcher surface for a visual check, then continue the bounded Qwen attachment workflow.

### 2026-07-11 - Step 18 (launcher hover-only path tightening)

- Follow-up review concluded that even the compact workspace-tail label was unnecessary list noise for recent projects.
- Repair: launcher recent-project rows now render only project name plus relative update time. Full workspace and `.abproj` paths remain available only through hover/title metadata rather than visible list text.
- Validation: desktop production build passed, and a headless capture against the active `4181` dev surface confirmed the left column no longer prints any path text. Evidence saved at `PRIVATE/app-standardization-ui-dogfood/ui/launcher-recent-projects-tightened-20260711.png` with matching JSON report.
- Evidence: appended `2026-07-11 Launcher Recent-Project Hover-Only Path Tightening` in `PRIVATE/app-standardization-ui-dogfood/runs/DG-MULTIMODAL-UI-01/step18-thread-create-async-repair.md`.
- Next entry: remain at Step 18. Continue the bounded Qwen attachment workflow through visible UI clicks on the recovered `8838` surface.

### 2026-07-11 - Step 18 (send-target hardening and visible task-misroute blocker)

- Completed repair: the desktop send path now refuses to reuse a stale selected thread when the current task has no active provider lane. `resolveTaskSendTargetThreadId(...)` was added to keep ordinary sends from silently inheriting a previous task's thread id. Targeted desktop tests passed 9/9 and the desktop production build passed with the existing Vite chunk-size warning.
- Visible recheck: the recovered in-app `8838` surface was used again. The launcher recent-project list was visibly reconfirmed after reload and saved as `PRIVATE/app-standardization-ui-dogfood/runs/DG-MULTIMODAL-UI-01/step18-launcher-tightened-visible-20260711.png`.
- New blocker: the visible sidebar row that reads `DG Multimodal UI 01 Recovery 10` still does not reliably become the real active conversation. Both semantic and coordinate clicks on that row returned the main pane to the older `Step 11 source for compact_handoff-yunwu-gpt-5.5-same_task.handoff_target-run` thread. A real Qwen image send then cleared the composer but still posted into Step 11, leaving the isolated DG task empty. Evidence screenshot: `PRIVATE/app-standardization-ui-dogfood/runs/DG-MULTIMODAL-UI-01/step18-dg-click-misroutes-to-step11-20260711.png`.
- Runtime evidence: the sidecar accepted `POST /api/runtime/turns/start`, but the active project pointers and task transcript remained aligned with Step 11 rather than the lane-less DG task. This confirms a visible task-targeting mismatch, not merely a browser-control no-op.
- Next entry: remain at Step 18. Repair the sidebar task-selection misbinding for lane-less tasks, then rerun the same bounded Qwen text-plus-image workflow through visible UI clicks and retain the reply/result screenshots plus token ledger.

### 2026-07-11 - Step 18 (ghost-thread fallback repaired; in-app webview blank)

- Completed repair: the desktop chat surface no longer treats a stale previously loaded runtime thread as a valid render fallback after the current task switches to a lane-less task. `shouldUseSelectedRuntimeThread(...)` now limits runtime-thread reuse to threads that still belong to the current task, or to taskless conversation mode. This closes the UI path where `DG Multimodal UI 01 Recovery 10` could still appear to show the old Step 11 conversation even after task selection moved away from that lane.
- Validation: `taskThreadRestore.test.ts` passed 12/12, `threadRendering.test.ts` passed 20/20, and the desktop production build passed with the existing Vite chunk-size warning. Provider calls: 0. Token/cost signal: 0.
- New blocker: after the repair, the prior working in-app `8838` tab was no longer claimable. Recreating a fresh in-app tab at the same URL produced a blank root page: `document.readyState` reached `complete`, but `#root` remained empty after reload and no visible DOM text was available for click-driven acceptance. Screenshot evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-MULTIMODAL-UI-01/step18-inapp-blank-webview-20260711.png`.
- Classification: this is `browser_webview_unavailable`, not a provider pass/fail and not proof that the visible DG task selection path is fixed. The user-visible Step 18 acceptance still requires a nonblank in-app page plus the same ordinary click path.
- Next entry: remain at Step 18. Recover a usable in-app browser page on `8838`, then visibly select `DG Multimodal UI 01 Recovery 10`, verify that the old Step 11 conversation no longer remains visible, and continue the bounded Qwen text-plus-image attachment workflow only after that visual gate passes.

### 2026-07-11 - Step 18 (launcher legacy-path name sanitization)

- Completed repair: the launcher recent-project title formatter now strips legacy inline path fragments out of stored project names before rendering. Recent rows keep only a human-readable title in the visible list; workspace and `.abproj` paths remain available only through hover/title metadata. This closes the case where older recent-project records could still print `D:\...` text in the left column even after the visible row layout had been tightened.
- Validation: `src/features/navigation/recentProjectCards.test.ts` passed 5/5, including new cases for newline-appended paths, inline `D:\...` suffixes, and path-only legacy names. The managed `8838` surface also rendered nonblank again under headless capture, with evidence saved at `PRIVATE/app-standardization-ui-dogfood/runs/DG-MULTIMODAL-UI-01/step18-launcher-path-tightening-verify.png`.
- Scope note: this round did not complete a fresh visible launcher screenshot because the recovered `8838` session reopened directly into the active project surface instead of the launcher. The repair is therefore code-validated and ready for the next visible launcher pass, but it does not replace the remaining Step 18 task-selection and bounded Qwen attachment acceptance.
- Next entry: remain at Step 18. Revisit the launcher through ordinary UI navigation to confirm that recent-project rows no longer show path text, then continue the bounded Qwen attachment workflow through visible UI clicks on the recovered `8838` surface.

### 2026-07-11 - Step 18 (optimistic sidebar task switch guard)

- Root cause refinement: the `DG Multimodal UI 01 Recovery 10` row was not failing at the click layer. A headless replay showed the row click enters `selectSidebarTask(...)`, completes `ensureSidebarProjectOpen(...)`, and sends `POST /api/project/tasks/switch`, but Chromium on the managed `8838` surface can take about 12 seconds to receive the HTTP response even though the same endpoint returns in under a second through an external tokenized shell call. During that browser-local wait window, the UI previously continued to render the old Step 11 task and left the user vulnerable to sending the next turn into the stale context.
- Completed repair: sidebar task selection is now optimistic on the desktop side. When the user chooses a task row, AstraBridge immediately projects that task into the visible task context, suppresses the stale active-row highlight from the previously current task inside the same project, and keeps the composer send path disabled while the real switch is still pending. Once the delayed `/api/project/tasks/switch` response reconciles, the optimistic state collapses back into the persisted task state.
- Validation: `src/features/navigation/ProjectTaskTree.test.tsx` passed 8/8, `src/features/runtime/taskThreadRestore.test.ts` passed 12/12, and the desktop production build passed with the existing Vite chunk-size warning. A headless replay on `8838` confirmed both the early and settled states now keep the composer task label on `DG Multimodal UI 01 Recovery 10`, show only the DG row as active, and preserve that state after the delayed response returns. Evidence screenshot: `PRIVATE/app-standardization-ui-dogfood/runs/DG-MULTIMODAL-UI-01/step18-optimistic-task-selection.png`.
- Safety: provider calls 0, attachment sends 0, token/cost signal 0. This round only repaired the local task-targeting guardrail around the existing delayed switch response.
- Next entry: remain at Step 18. Use the recovered `8838` surface to run the bounded Qwen text-plus-image workflow through ordinary UI clicks on the DG task, now that stale Step 11 task rendering no longer survives the sidebar switch window.

### 2026-07-11 - Step 18 (recent-project visible label hardening)

- Root cause refinement: the launcher still had one density leak around historical recent-project rows. Some stored project names could carry embedded `D:\...` fragments, while the old path detector also treated any slash-containing title as path-like. That left raw path text eligible for the visible row and made normal slash-delimited titles overly fragile.
- Completed repair: recent-project title sanitization now scans every stored name line, skips path-only lines, strips only real Windows/UNC path suffixes, preserves ordinary slash-delimited titles, and renders the row through a dedicated `recent-project-title` text container. Full workspace and project-file paths remain hover-only metadata.
- Validation: `src/features/navigation/recentProjectCards.test.ts` passed 7/7 and the desktop production build passed with the existing Vite chunk-size warning. Headless evidence was refreshed at `PRIVATE/app-standardization-ui-dogfood/ui/20260711-launcher-recent-projects-tightened.png` and `PRIVATE/app-standardization-ui-dogfood/ui/20260711-launcher-recent-projects-tightened.json`; that recovered `8838` capture reopened the active project shell rather than the launcher, so one ordinary launcher revisit is still required for row-by-row visual confirmation.
- Safety: provider calls 0, attachment sends 0, token/cost signal 0. This round only tightened the desktop-side visible-label contract for recent projects.
- Next entry: remain at Step 18. Revisit the launcher through ordinary UI navigation to confirm recent-project rows no longer print raw paths, then continue the bounded Qwen text-plus-image attachment workflow on the recovered `8838` surface.

### 2026-07-11 - Step 18 (launcher intro copy tightened; hover-only path recheck)

- User feedback identified a second launcher density issue beyond the recent-project rows: the hero still printed the `.abproj` / `.astrabridge` storage-path sentence as always-on body copy even though that detail is only needed on demand.
- Completed repair: the launcher hero now keeps only the product summary and setup action sentence. The storage-path note moved behind a compact hover/focus help icon, and the recent-project row typography/padding were tightened slightly so the left column stays title-first.
- Validation: `src/features/navigation/recentProjectCards.test.ts` still passed 7/7, the desktop production build passed with the existing Vite chunk-size warning, and a fresh headless launcher capture on the managed `8838` route was saved at `PRIVATE/app-standardization-ui-dogfood/ui/20260711-launcher-path-copy-tightened.png` with matching JSON report `PRIVATE/app-standardization-ui-dogfood/ui/20260711-launcher-path-copy-tightened.json`. The screenshot confirms the left column no longer prints raw workspace/project paths and the top hero no longer renders the storage-path sentence as persistent text.
- Safety: provider calls 0, attachment sends 0, token/cost signal 0. This round stayed inside launcher-density/UI polish only.
- Next entry: remain at Step 18. Return to the bounded multimodal recovery flow on the recovered `8838` surface; the next blocker remains visible DG task selection plus the Qwen text-plus-image workflow, not further launcher copy churn.

### 2026-07-11 - Step 18 (recent-project compact location label)

- User feedback: the launcher recent-project list still spent too much left-column space on raw location text; full absolute paths were only useful as hover detail, not as always-on copy.
- Completed repair: the launcher recent-project helper now computes a short visible location tail from the workspace root, while leaving the full workspace and `.abproj` paths in `title`/hover metadata only. The row renderer now shows `recent-project-title` plus a muted `recent-project-meta` line instead of dumping long path blocks into the list.
- Files changed: `apps/astrabridge-desktop/src/features/navigation/recentProjectCards.ts`, `apps/astrabridge-desktop/src/features/navigation/recentProjectCards.test.ts`, `apps/astrabridge-desktop/src/App.tsx`, `apps/astrabridge-desktop/src/styles.css`.
- Validation: `node ./node_modules/vitest/vitest.mjs run src/features/navigation/recentProjectCards.test.ts` passed 9/9; `node ./node_modules/typescript/bin/tsc --noEmit` passed.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/ui/step18-launcher-recent-project-compact.png` and `PRIVATE/app-standardization-ui-dogfood/ui/step18-launcher-recent-project-compact.json` confirm the recovered `8838` shell surface is no longer printing raw path blocks in the left project/task area. A launcher-specific visual recheck is still pending because the managed session reopened directly into the active project shell instead of the new-project launcher.
- Safety: provider calls 0, attachment sends 0, token/cost signal 0. This round only tightened visible recent-project density.
- Next entry: remain at Step 18. Revisit the launcher through ordinary UI navigation when it is reachable again, confirm the compact recent-project rows there, then continue the bounded Qwen text-plus-image attachment workflow on the recovered `8838` surface.

### 2026-07-11 - Step 18 (ordinary launcher reopen repaired)

- Completed repair: the sidecar `POST /api/projects/open` path no longer blocks the launcher while it waits for runtime restart and automation scheduler startup. The route now returns the reopened project payload first and defers `runtime.restart_in_background()` plus `automations.start()` into a background thread. This removes the visible timeout banner that previously stranded the user on the launcher even after a healthy managed `astra` session was restored.
- Validation: `test_sidecar_services.py` gained a handler-level order check for the deferred open-project background path; the new test and the adjacent close-project timing test passed 2/2. Project-service regressions around `open_project(...)` passed 3/3, and `python -m py_compile apps/astrabridge-sidecar/astrabridge_sidecar/server.py` passed.
- Visible evidence: after restarting the managed `8838` sidecar, a fresh click-driven capture of the launcher recent-project row reopened the real project shell instead of ending on `The desktop sidecar did not respond in time for /api/projects/open`. Evidence: `PRIVATE/app-standardization-ui-dogfood/ui/launcher-open-project-after-project-open-background-fix-longwait-20260711.png` and its JSON report.
- Route inventory recheck: the recovered `8838` runtime resumed `astra` automatically and now reports configured image-input-capable router models (`kimi-k2.6`, `kimi-k2.7-code`, `qwen3.6-flash`, `qwen3.7-max-2026-06-08`, `qwen3.7-plus`). The remaining blocker is no longer launcher responsiveness; it is still the bounded DG attachment workflow through visible UI.
- Safety: provider calls 0, attachment sends 0, token/cost signal 0. This round stayed inside local sidecar/desktop repair plus click-driven verification.
- Evidence: appended `2026-07-11 Project-Open Background Restart Repair` in `PRIVATE/app-standardization-ui-dogfood/runs/DG-MULTIMODAL-UI-01/step18-thread-create-async-repair.md`.
- Next entry: remain at Step 18. Use the recovered ordinary launcher path on `8838`, switch into the dedicated DG task through normal UI controls, and run the bounded image-attachment workflow against a visibly image-capable model.

### 2026-07-11 - Step 18 (sidebar smoke-title prefix suppression)

- User feedback isolated one remaining low-value label leak in the project/task sidebar: smoke-generated task names such as `Step 11 source for compact_handoff-...` were still rendered verbatim, so the visible row spent its first characters on internal orchestration metadata instead of the meaningful route suffix.
- Completed repair: the desktop sidebar task tree now strips the leading `Step <n> source for` and `Step <n> target for` prefix from visible task labels and the task hover-card title. This is display-only normalization; no task record, evidence artifact, or persisted title was rewritten.
- Validation: `npm.cmd test -- ProjectTaskTree.test.tsx` passed 10/10, including a new regression case covering `Step 11 source for compact_handoff-yunwu-gpt-5.5-same_task.handoff_target-run`.
- Scope note: this round only tightened the visible task-title contract. It does not replace the remaining Step 18 visible DG task selection and bounded multimodal attachment acceptance.
- Next entry: remain at Step 18. Continue from the recovered `8838` surface, verify the DG task through visible UI clicks, and resume the bounded image-attachment workflow.

### 2026-07-11 - Step 18 (shared smoke-title display cleanup)

- Follow-up repair: the same smoke-step prefix suppression now lives in a shared desktop helper instead of only inside the task-tree row renderer. Both the sidebar task rows and any desktop thread label path that renders `displayName`/`preview` now normalize `Step <n> source for ...` and `Step <n> target for ...` down to the meaningful suffix.
- Files changed: `apps/astrabridge-desktop/src/features/navigation/displayTitle.ts`, `apps/astrabridge-desktop/src/features/navigation/displayTitle.test.ts`, `apps/astrabridge-desktop/src/features/navigation/ProjectTaskTree.tsx`, `apps/astrabridge-desktop/src/App.tsx`.
- Validation: `npm.cmd test -- ProjectTaskTree.test.tsx displayTitle.test.ts` passed 13/13; desktop `tsc --noEmit` passed. A fresh headless capture on `8839` reopened the launcher surface cleanly and did not expose the old `Step 11 source for comp...` prefix in visible text.
- Scope note: this remains a display-only cleanup. It does not change stored task/thread names and it does not replace the remaining Step 18 multimodal visible-flow acceptance.
- Next entry: remain at Step 18. Re-enter the active project from the ordinary launcher path, then continue the bounded visible multimodal workflow.

### 2026-07-11 - Step 18 (remaining smoke-title leak sealed)

- User feedback: one visible `Step 11 source for comp...` leak was still being reported after the shared title helper landed, so the remaining goal for this round was to remove any last raw smoke-step prefix from ordinary desktop title inputs rather than only from list rows.
- Completed repair: generic-task-title checks now run against `visibleTaskTitle(...)`, and the thread rename dialog now seeds both `defaultValue` and `placeholder` from `visibleThreadTitle(...)` instead of the raw stored `displayName`. This keeps the smoke-step prefix out of the remaining user-visible title entry path without rewriting persisted task or thread records.
- Files changed: `apps/astrabridge-desktop/src/App.tsx`.
- Validation: `npm.cmd test -- ProjectTaskTree.test.tsx displayTitle.test.ts` passed 13/13; desktop `tsc --noEmit` passed. A fresh headless capture of the active managed page on `8839` was saved at `PRIVATE/tmp/step18-title-cleanup-8839.png` with JSON report `PRIVATE/tmp/step18-title-cleanup-8839.json`; its visible text excerpt no longer contains `Step 11 source for`.
- Scope note: this is still display-contract hardening only. It does not replace the remaining Step 18 DG task-switch and bounded multimodal attachment acceptance.
- Next entry: remain at Step 18. Return to the visible DG multimodal flow, verify the dedicated DG task stays selected in the main pane, then continue the bounded attachment workflow.

### 2026-07-11 - Step 18 (task-conversation title source tightened; `8839` host mismatch remains)

- Follow-up repair: the sidecar task-conversation projection now strips `Step <n> source/target for ...` at the data-source layer, not only in desktop render helpers. `TaskConversationService.conversation(...)` and persisted thread snapshots now emit normalized `thread.name` and `thread.displayName`.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/task_conversation_service.py`, `apps/astrabridge-sidecar/tests/test_sidecar_services.py`.
- Validation: focused sidecar tests passed 2/2, including a new regression asserting that `Step 11 source for compact_handoff-...` becomes `compact_handoff-...`; `py_compile` passed. A direct one-shot Python read against the same persisted current project state returned sanitized `thread.name` and `thread.displayName` for task `task-20260706T203416736564-9380ce`.
- Remaining blocker: the managed HTTP listener currently attached to `http://127.0.0.1:8839` still returns the old raw title on `/api/project/task-conversation`, even after source update. This isolates the remaining issue to the `8839` host/launcher process path rather than the repaired projection logic itself.
- Next entry: remain at Step 18. Reconcile the `8839` managed host so the visible page consumes the updated sidecar projection, then recheck the visible smoke-title leak before resuming the bounded DG multimodal flow.

### 2026-07-11 - Step 18 (desktop API normalization sealed the remaining visible smoke-title leak)

- User feedback confirmed one visible `Step 11 source for comp...` fragment still survived in the ordinary desktop shell after the shared display helper and sidecar-source cleanup. That meant at least one render path was still consuming raw task/thread payloads instead of the normalized display helper.
- Completed repair: the desktop API layer now normalizes smoke-step prefixes as responses enter the app, not only when individual components remember to call a helper. `projectSidebar`, `projectTasks`, `taskConversation`, `threads`, `readThread`, `createTask`, `switchTask`, `switchThread`, `create/fork thread`, and thread-create recovery responses now sanitize visible task titles, thread `name`/`displayName`, preview text, and provider-thread names. The local optimistic sidebar-task stub also now uses `visibleTaskTitle(...)` so the prefix cannot flash during prefetch or task-switch transitions.
- Files changed: `apps/astrabridge-desktop/src/api.ts`, `apps/astrabridge-desktop/src/api.test.ts`, `apps/astrabridge-desktop/src/App.tsx`.
- Validation: `node ./node_modules/vitest/vitest.mjs run src/api.test.ts src/features/navigation/displayTitle.test.ts src/features/navigation/ProjectTaskTree.test.tsx` passed 18/18; `node ./node_modules/typescript/bin/tsc --noEmit` passed.
- Scope note: this is still display-contract hardening. Stored task/thread records remain unchanged. The deeper `8839` managed-sidecar loader mismatch still exists, but it no longer controls the user-visible desktop title contract on the normal response path.
- Next entry: remain at Step 18. Re-open the active project shell on the managed route, visually confirm the raw `Step 11 source for ...` fragment is gone, then resume the bounded DG multimodal acceptance flow.

### 2026-07-11 - Step 18 (live multimodal attempt exposed route and task-binding defects)

- Visible operation: in the managed `astra` session on `8839`, the operator selected `DG Multimodal UI 01 Recovery 10`, pasted two existing redacted UI screenshots through the visible composer, and sent one bounded UI QA request on `qwen / qwen3.7-plus / high`. The attachment preview and running state were captured through the in-app browser.
- Outcome: the turn did not remain bound to the selected DG task. The provider response explicitly reported that image input had been omitted because `qwen3.7-plus` did not support it, then entered a vision-tool recovery loop without producing a final QA report or artifact. The main UI notice remained a generic unclassified runtime failure.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-MULTIMODAL-UI-01/step18-live-route-mismatch-report.md`, matching JSON, and `step18-dg-task-preflight-8839.png`, `step18-two-attachments-ready-8839.png`, `step18-multimodal-running-8839.png`, `step18-vision-route-mismatch-8839.png`, and `step18-multimodal-stalled-vision-tool-8839.png`.
- Safety: one explicit provider-backed turn was submitted; usage and cost signals were `not_available`. No plaintext secret was read or persisted, no retry was attempted, and no external write occurred.
- Next entry: Step 19 repairs the first-turn task binding, verified image-capability gate, classified terminal-state/recovery UI, and bounded tool-loop behavior. Step 18 remains incomplete until a visible retry returns a real image-grounded QA result and artifact.

### 2026-07-11 - Step 19 (task bootstrap and image-route fail-closed repair)

- Completed code repair: first-turn bootstrap carries the selected `task_id` into runtime thread creation, and `TaskService.bind_thread_to_task_id(...)` binds the new lane to that task rather than creating a `New task`. This directly closes the Step 18 task-identity drift path.
- Completed capability repair: App Server chat routes now reject image attachments before `turn/start` unless the route reports explicit `app_server_image_input_status=verified`. Provider documentation alone no longer authorizes image dispatch through the Codex App Server bridge. The composer consumes the same status and disables send with a compact route-specific explanation.
- Completed test evidence: `test_task_service_restore.py` passed 6/6; targeted `test_sidecar_services.py` passed 2/2; desktop `attachmentRoute` plus `taskThreadRestore` tests passed 17/17; sidecar `py_compile` and desktop `tsc --noEmit` passed.
- Visual recheck blocker: after the managed `8839` sidecar restart, the in-app browser returned an empty DOM, screenshot capture was unavailable, and a fresh localhost page timed out while attaching. Recorded as `browser_screenshot_channel_failure`, not as product acceptance.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260711-step19/step19-multimodal-routing-repair.md`.
- Next entry: remain in Step 19 only for the visible UI recheck. Once browser attachment is restored, confirm the unverified-image send block and first-turn task binding through normal clicks; then Step 18 can retry only on a transport explicitly verified for image input.

### 2026-07-11 - Step 19 (in-app browser readiness recheck)

- Browser result: the user-visible managed `8839` tab was claimed again after the repair, but its in-app browser DOM stayed empty after a wait and screenshot capture was unavailable. A fresh browser page had previously timed out at webview attachment.
- Availability evidence: `http://127.0.0.1:4181/` returned HTTP 200 with the application root; `http://127.0.0.1:8839/health` returned HTTP 200 from the current-source sidecar process; no page console errors were exposed through the failed attachment. This is a `browser_screenshot_channel_failure`, not evidence that AstraBridge is unavailable or visually accepted.
- Next entry: remain in Step 19. Retry the same visible UI recheck only after the in-app webview is able to attach; do not spend another provider request until the unverified-route send block is visibly confirmed.

### 2026-07-11 - Step 19 (webview verification blocked after three consecutive checks)

- Third repeated check: the managed `8839` page was claimed in the in-app browser again, but `domSnapshot()` returned an empty document after a wait and `Page.captureScreenshot` timed out. This repeats the same browser attachment/capture failure from the preceding two execution rounds.
- Boundary: local frontend `4181` and sidecar `8839/health` had already returned HTTP 200, so this is recorded as an external `browser_screenshot_channel_failure`, not a product runtime failure. No provider request, data write, or retry was performed in this round.
- Blocker: Step 19 cannot satisfy its visible UI acceptance gate until the in-app webview attaches. Repair code and focused regression tests remain preserved in `PRIVATE/app-standardization-ui-dogfood/repairs/20260711-step19/step19-multimodal-routing-repair.md`.
- Next entry: when browser attachment is restored, resume the exact UI recheck: select the lane-less DG task, attach an image, confirm send is disabled with the verified-route message, then create a first thread and confirm it remains bound to the selected task.

### 2026-07-12 - Step 19 (composer runtime-failure status consolidation)

- User feedback: a terminal model failure was visible twice: as a large red composer-footer panel and as a compact top conversation status item. The footer panel consumed workspace height and repeated information already available in the status strip.
- Completed repair: removed the composer-footer `sendFailure` panel. `ConversationNoticeBar` now receives one compact fallback notice only when the supervisor has not persisted a more actionable runtime diagnostic; it strips the redundant localized failure prefix. Key-setup failures retain their existing setup action.
- Files changed: `apps/astrabridge-desktop/src/App.tsx`, `apps/astrabridge-desktop/src/features/runtime/runtimeErrorNotice.ts`, `apps/astrabridge-desktop/src/features/runtime/runtimeErrorNotice.test.ts`.
- Validation: `node ./node_modules/vitest/vitest.mjs run src/features/runtime/runtimeErrorNotice.test.ts` passed 5/5; `node ./node_modules/typescript/bin/tsc --noEmit` passed.
- Browser result: the in-app browser discovered and claimed the user-visible `8839` AstraBridge tab, but `reload()` plus `domSnapshot()` timed out and reset the connection. This is recorded as `browser_screenshot_channel_failure`; no provider call, token usage, secret read, or visual-acceptance claim was made.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260712-step19/step19-composer-failure-notice-repair.md`.
- Next entry: remain in Step 19. When webview attachment recovers, reproduce a terminal runtime failure via visible UI and verify that exactly one compact top-strip notice remains, alongside the existing attachment-route and first-turn task-binding rechecks.

### 2026-07-12 - Step 19 (in-app browser recovered; normal-state visual recheck)

- Browser recovery: a fresh in-app browser binding attached to the user-visible managed `8839` AstraBridge tab. The DOM is readable and screenshot capture works again.
- Visible operation: through normal UI, selected the lane-less `DG Multimodal UI 01 Recovery 10` task. The selected task rendered its empty conversation state, the compact top status strip remained visible, and the composer footer did not contain the removed large `sendFailure` panel.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260712-step19/step19-webview-recovered-dg-task.png` and the accompanying repair report.
- Boundary: this does not yet reproduce a terminal model failure, attach an image, or create a first thread; it is normal-state confirmation only. No provider request, token usage, secret read, or external write occurred.
- Next entry: remain in Step 19. Use visible UI to complete the unverified-image-route and first-turn task-binding checks, then trigger one bounded terminal-failure case to verify that its status is represented only in the compact top strip.

### 2026-07-12 - Step 19 (completed live recheck and current-source restart repair)

- Visible unverified-image acceptance: pasted a non-sensitive screenshot into the lane-less `DG Multimodal UI 01 Recovery 10` task through the composer UI. The draft rendered, the UI stated that the App Server image route was unverified, and Send stayed disabled. No provider request was made for that attachment.
- Visible terminal-status acceptance: a bounded Qwen text turn completed. Its initial stale supervisor error was reduced to the compact top strip and then correctly suppressed once the newest persisted turn was `completed` without an error; the removed composer-footer error card did not return.
- Binding finding: two attempts against the old `8839` process exposed that it had started before the latest source changes. The desktop now anchors the last user-selected task and validates the server task response before starting a turn, so a mismatched response fails closed with an actionable compact notice.
- Restart repair: restarting `8839` exposed a current-source `RuntimeConfigService` NameError caused by modality normalization in `status()`. The logic was moved to `_normalize_profile()`, inactive status now exposes a stable `input_modalities` field, and known plus configured modalities are merged so a legacy text-only profile cannot erase a known Kimi image capability. The replacement `8839` process started at `2026-07-12T07:35:36` and returned health with `input_modalities: [text, image]`.
- Final visible binding acceptance: after the current-source restart, selected the DG task through the visible sidebar and sent `Reply exactly: task-binding-current-source`. Qwen returned the exact reply. Read-only task projection confirmed the current task ID matched the DG task, its active provider thread was `019f5356-208f-7110-b141-f170b9f86273`, and lane count was `1`.
- Validation: sidecar `test_task_service_restore.py` 6/6; focused `test_sidecar_services.py` 4/4; Python compilation passed. Desktop `attachmentRoute`, `runtimeErrorNotice`, and `taskThreadRestore` 25/25; `tsc --noEmit` passed.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260712-step19/step19-unverified-image-route-visible.png`, `step19-terminal-failure-top-strip.png`, `step19-stale-runtime-error-cleared.png`, and `step19-task-binding-current-source.png`, plus the updated repair report. Two confirmed provider-backed Qwen text turns completed; provider usage/cost remained `not_available` and was not inferred.
- Step 19 status: completed. The remaining Step 18 blocker is not browser availability: no App Server image-input transport has yet been explicitly verified, so the live image task must not bypass the disabled-route gate.
- Next entry: return to Step 18 only after verifying a documented App Server image-input transport, then repeat the visible image attachment flow and require an image-grounded final artifact.

### 2026-07-12 - Step 18 (image transport contract repair; live probe still required)

- Contract evidence: the locally generated Codex App Server v2 schema explicitly accepts `localImage` user input. Alibaba Model Studio documents Qwen visual input as Responses `input_image` with a URL or data URI, including `qwen3.7-plus` visual-understanding examples.
- Repair: the Qwen Responses transport now converts App Server `localImage` and `image` items into provider-compatible `input_image` data URIs, preserving image detail and preview redaction. The local-image data encoder is shared by Responses and chat transports.
- Fail-closed repair: attachment preflight was moved from `fork_thread()` into `start_turn()` before any client, provider-thread, or provider request. This removes the undefined-variable fork defect and ensures unverified image input cannot dispatch through the normal turn path.
- Validation: focused sidecar tests passed 3/3, covering normal-turn preflight rejection, Qwen Responses conversion, and existing Kimi conversion. Python compilation passed.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260712-step18/step18-image-transport-contract-repair.md` and the generated redacted App Server schema bundle beside it.
- Remaining gate: the route stays unverified until a sidecar restarted from this source completes a bounded, visible-composer image probe whose response proves image grounding. No production image-send gate has been relaxed.
- Next entry: restart the current-source sidecar, then perform exactly one visible Qwen image probe and record the terminal result before considering the route verified.

### 2026-07-12 - Step 18 (visible Qwen vision probe exhausted its bounded retry)

- Visible UI operation: in the managed `astra` session, opened `LLM API 管理器 -> 模型`, selected `Qwen3.7 Plus`, and triggered the compact `测试视觉输入` action. It sent only the internal red-square PNG fixture and a one-word color request.
- Attempt 1 evidence: Qwen received the redacted Responses `input_image` request and its reasoning described the solid image, but it returned no visible final assistant message. The health action reported failure rather than incorrectly treating reasoning text as a compliant result. Provider usage was zero-valued and cost remained `not_available`; no value was inferred.
- Repair: the Qwen adapter now recognizes the internal `astrabridge_probe_force_final` flag, sends `enable_thinking=false`, and removes the flag from the upstream request. Focused conversion and probe tests passed 3/3; Python compilation passed. Desktop typecheck passed.
- Attempt 2: the same visible action was repeated after restarting the sidecar. Its redacted preview still showed `enable_thinking=true`, showing that the listener serving that request had not yet loaded the final force-final repair. It remains a failed record. Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260712-step18/step18-qwen-vision-probe-failed.png` and the redacted router `latest_test` snapshot retained by the managed sidecar.
- Boundary: the planned one retry has been consumed. The App Server/composer route remains unverified and disabled; no third provider request was made.
- Next entry: require explicit approval for one additional bounded live Qwen retry after a current-source restart. Acceptance requires redacted preview `enable_thinking=false` and exact final `red`, then a separate visible composer attachment turn with image-grounded output.

### 2026-07-12 - Browser recovery verification

- After the Codex desktop restart, the in-app browser successfully reattached to the existing AstraBridge tab at `127.0.0.1:4181` with sidecar `8839`.
- A fresh DOM snapshot and viewport screenshot both rendered the signed-in `astra` managed-user model page. This clears the prior empty-DOM / capture-timeout condition as a transient Codex webview attachment failure, not an AstraBridge frontend or sidecar outage.
- This recovery does not change the Step 18 live-provider boundary: the Qwen image route remains unverified and a further real provider retry still requires explicit approval.

### 2026-07-12 - Step 18 authorization received; browser-control environment regression

- The user explicitly authorized one additional bounded Qwen vision probe and future equivalent low-risk, Vault-managed capability probes. The allowed fixture remains the built-in non-sensitive red-square PNG; no user file or secret may be uploaded or displayed.
- Before any provider request, the in-app Browser binding became unavailable after its previous tab session was finalized. The required bundled `scripts/browser-client.mjs` is absent from the current Codex browser-plugin cache, so a fresh in-app Browser session cannot be initialized.

### 2026-07-12 - Step 21 (task-graph live-run and inspector repair slice)

- Completed code repair: added a real `/api/task-graphs/run` live-run path, compact run-ref persistence, and Desktop wiring for a visible `Live run` action. The runtime now validates the graph, performs a dry-run gate first, schedules runnable fan-out nodes before waiting, persists worker/handoff/artifact summaries, and restores the visible provider thread after completion.
- Completed UX repair: Task Graph toolbar actions now close the modal inspector before `Live run`, fixture run, cancelable fixture run, or Dry-run. Saving a node or edge also closes the inspector, removing the old blocked author/edit/run loop.
- Validation: sidecar focused suites `test_task_graph_api` and `test_task_graph_worker_runtime` passed 23/23; Desktop `TaskGraphWorkspace.test.tsx` passed 63/63 after updating assertions to match the new close-on-save interaction; Desktop production build passed with the existing Vite chunk-size warning; focused sidecar `py_compile` passed for `runtime_service.py`, `task_service.py`, and `server.py`.
- Remaining blocker: the browser bridge reattached to the signed-in `8839` tab and can read normal-page DOM again, but the Task Graph transition is still not visually reliable enough to close Step 21. A claimed task tab exposed normal DOM, yet entering graph mode returned an empty DOM and earlier `Page.captureScreenshot` on the same surface still timed out. Record this as `browser_screenshot_channel_failure` / task-graph webview instability, not as a passed visible Task Graph acceptance.
- Evidence: current-source code in `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`, `task_service.py`, and `server.py`; Desktop wiring in `apps/astrabridge-desktop/src/App.tsx`, `api.ts`, and `features/runtime/TaskGraphWorkspace.tsx`; regression coverage in `apps/astrabridge-sidecar/tests/test_task_graph_api.py`, `test_task_graph_worker_runtime.py`, and `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`.
- Next entry: remain at Step 21. Reclaim a visible Task Graph page, verify the `Live run` control and close-on-save behavior through the browser-readiness gate, then return to Step 20 for the first bounded provider-backed parallel graph run.
- Per the visible-UI dogfood contract, no sidecar API, direct request, or alternative automation surface was used to replace the required UI click. This is an environment regression, not a pass/fail signal for AstraBridge or Qwen.
- Next entry: restore the Codex in-app Browser plugin/control bridge, reattach the visible AstraBridge tab, then perform exactly one additional bounded Qwen vision probe via the compact model-editor image action. Record the visible terminal result and screenshot before enabling any composer image route.

### 2026-07-12 - Step 18 direct Qwen LLM transport probe passed

- User authorization clarification: direct LLM/provider API calls are allowed and encouraged for AstraBridge stability testing; only AstraBridge sidecar HTTP APIs remain disallowed as a substitute for visible UI operations.
- One bounded direct request was sent through the current AstraBridge Qwen Responses transport, with the managed `astra` Vault key injected in memory and immediately restored after the request. It did not use a sidecar HTTP endpoint.
- Result: `qwen/qwen3.7-plus` returned HTTP `200` and exact final `red` for the internal red-square image. The captured redacted invariants prove `input_image` was present, `enable_thinking=false`, and `astrabridge_probe_force_final` was absent from the upstream payload.
- Usage: provider reported 132 input, 2 output, 0 reasoning, 134 total tokens. Cost remained `not_available` because pricing is not configured; no cost was inferred.
- Regression: the focused attachment preflight, Qwen conversion, and bounded-probe tests passed 3/3.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260712-step18/step18-qwen-direct-llm-vision-probe.md`.
- Step 18 status: still in progress. This proves the Qwen provider transport, but does not replace the App Server `localImage` attachment and visible composer acceptance. Do not enable the composer image route yet.
- Next entry: repair or restore the Codex in-app Browser control bridge, then use visible UI to attach the same non-sensitive fixture and verify an image-grounded composer result. A further bounded provider request is allowed under the user's standing authorization only when that UI operation is ready.

### 2026-07-12 - Step 18 App Server-shaped Qwen local-image transport repair

- Direct LLM verification was extended to the exact top-level sequence emitted by `RuntimeService`: one `text` item followed by one `localImage` item. The first request reached Qwen with the image but received a verbose color description rather than the required exact `red`; it was retained as a non-compliant result.
- Diagnosis: `QwenResponsesTransport` had converted those adjacent items into separate user messages. The second image-only message therefore lost the preceding output constraint.
- Repair: Qwen Responses conversion now combines adjacent App Server text/image entries into one user message, flushing before transitions, tool items, and other non-user items. This preserves the original turn boundary instead of relying on prompt repetition or parsing a non-compliant response.
- Validation: focused sidecar tests passed 3/3. The bounded direct retest passed with HTTP `200`, exact final `red`, one upstream user message containing both `input_text` and `input_image`, `enable_thinking=false`, and no internal `localImage` / force-final field leaked to the provider. Usage was 132 input, 2 output, 0 reasoning, 134 total; cost was `not_available`.
- Evidence: the preserved red-square fixture and updated `PRIVATE/app-standardization-ui-dogfood/repairs/20260712-step18/step18-qwen-direct-llm-vision-probe.md`.
- Step 18 status: still in progress. Qwen transport is now directly live-verified for the concrete App Server-shaped input, while the real App Server process turn and visible composer attachment acceptance remain mandatory before changing `app_server_image_input_status` or enabling image send.
- Next entry: restore the Codex in-app Browser control bridge; execute the visible composer attachment workflow against the preserved fixture and retain screenshots of attachment, running, and terminal image-grounded result. Direct LLM calls remain allowed within the user's standing authorization but cannot substitute for that UI evidence.

### 2026-07-12 - Codex App Server readiness check

- A no-provider-token `initialize` request to the installed Codex App Server succeeded. The remaining visual acceptance blocker is therefore not the App Server executable itself.
- The initialization emitted a separate user-environment warning: the user-level `protect-codex.rules` contains an unsupported `decision="deny"` value, so the entire custom rules file was not applied by the current Codex runtime.
- This rules-file defect is outside the AstraBridge repository. Do not treat the App Server as having the intended custom safety policy until the current Codex rule syntax is confirmed and the user-level configuration is repaired under a separate, explicit change scope.
- Next entry remains the visible composer attachment acceptance after restoring the in-app Browser control bridge; do not use this initialization check as a replacement for UI evidence.

### 2026-07-12 - Codex user-rule parser repair

- User approved repairing the local Codex configuration so the plan can continue. The original `C:\Users\cyz19\.codex\rules\protect-codex.rules` was preserved as `protect-codex.rules.backup-20260712-0849` before modification.
- Local Codex binary diagnostics establish that `prefix_rule` accepts restrictive decisions `prompt` and `forbidden`; `deny` is invalid in the installed runtime.
- Replaced only the invalid `decision="deny"` values with `decision="forbidden"`. The protected command patterns are unchanged.
- Validation: a fresh `codex app-server` initialize invocation exited successfully without `Error parsing rules` or a `protect-codex.rules` parser diagnostic. `codex doctor` exceeded the bounded local timeout and is retained as non-evidence rather than a pass.
- The previous custom-rules warning is resolved. The separate in-app Browser control-bridge issue remains the only blocker for visible composer acceptance.

### 2026-07-12 - Codex in-app Browser bundle recovery

- The browser bundle cache was materially incomplete: its required `scripts/browser-client.mjs`, transitive `scripts/node_modules`, and packaged `docs` tree were missing. The documented in-app browser bootstrap could not import.
- Official OpenAI Codex issue evidence identifies the same Windows cache defect and establishes that the same-version bundled Chrome plugin ships the shared Browser Use client capable of serving the `iab` backend. The normal bundled marketplace does not expose a separately installable `browser` plugin; attempting that install was a clean no-op failure. The installed `chrome@openai-bundled` plugin was re-added through the official CLI first.
- Recovery: restored the missing browser runtime assets from `chrome@openai-bundled` version `26.707.31428` into the corresponding browser cache version. The restored `browser-client.mjs` SHA-256 is `C8B7E809D7CF9E20A57123B2530D476CCEC9A01A6230A7B2B924FEA7D94D7F4A`, exactly matching the source. The expected browser path now imports successfully.
- Remaining session-bound condition: the current Node REPL request metadata has no browser-backend list and no native pipe, so `agent.browsers.list()` remains empty even though the repaired client imports. This is a Codex Desktop task/session injection state, not an AstraBridge fault or a missing plugin file.
- Next entry: restart Codex Desktop or open a fresh Codex task after the repaired bundle is in place, then reopen/claim the existing AstraBridge in-app tab. Verify `agent.browsers.list()` exposes `iab` before continuing the required visible composer attachment flow.

### 2026-07-12 - Codex restart and moved-cache reattachment verified

- After the user restarted Codex Desktop and moved the AstraBridge cache directory, the restored browser bundle again exposed the `iab` backend in the fresh desktop session.
- The existing AstraBridge tab at `127.0.0.1:4181` with sidecar `8839` was claimed through the in-app Browser. A fresh DOM snapshot rendered the local project landing page, and a viewport screenshot rendered normally; the former empty-DOM and screenshot-timeout failure is resolved for this session.
- Current visible product state is the unaffiliated new-project landing page (`尚未打开项目`), not a managed project conversation. This verifies the browser-control bridge only; it is not evidence for the Step 18 composer attachment route or managed-Vault readiness.
- Next entry: use only visible UI to open or create the designated dogfood project, restore the managed session if required, and then resume the Step 18 composer attachment acceptance from its existing bounded preflight gate.

### 2026-07-12 - Step 18 visible attachment-gate recheck after cache move

- Recovery: the moved application runtime remains correctly junctioned to `D:\AstraBridgeRuntime`, but no sidecar process was listening on `8839` after the Codex restart. The standard current-source sidecar entrypoint was restored on `8839`; visible UI then restored the managed `astra` session, `Provider Switch Live 20260622-224524`, and `DG Multimodal UI 01 Recovery 10`.
- Visible operation: two redacted Step 14 task-graph screenshots were pasted through the Composer. Both previews rendered and the visible summary reported `2` attachments / `2` images.
- Visible result: `qwen / Qwen3.7 Plus / high` rendered the route-specific App Server image-transport warning and kept Send disabled. No prompt, provider request, or model response occurred; token/cost for this recheck is `0` / `not applicable`.
- Source diagnosis: the runtime and desktop gates correctly fail closed on `app_server_image_input_status != verified`, while current source only defaults that field to `unverified`; it has no bounded real App Server probe that can issue and record an authenticated promotion to `verified`. Direct provider transport evidence remains insufficient for this status.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-MULTIMODAL-UI-01/step18-attachment-gate-recheck-20260712.md` and `step18-two-attachments-gated-20260712.png`.
- Next entry: implement the bounded, UI-invocable App Server local-image verification path with redacted evidence and exact-result promotion criteria; then repeat this same Composer path before attempting the full UI-QA task.

### 2026-07-12 - Step 18 completed live multimodal acceptance

- Browser recovery recheck: after the Codex restart and cache move, the restored browser bundle again exposed the `iab` backend. The in-app browser successfully claimed the visible AstraBridge tab on `8839`, returned a fresh DOM snapshot, and captured a viewport screenshot. Evidence: `step18-browser-bridge-recovered-20260712.png`.
- Runtime repair proof: the stale-runtime image gate was fixed in current source by refreshing `runtime_status` from live router model metadata before `turn/start`. Files changed for the repair were `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py` and `apps/astrabridge-sidecar/tests/test_sidecar_services.py`.
- Validation: the focused sidecar regression command passed `4/4`, covering verified-image-route refresh, pre-dispatch image rejection for unverified routes, and the App Server image verification path.
- Visible live success: using the visible DG task UI, one live multimodal Qwen turn completed on current-source sidecar `8841`. The final answer rendered a Chinese UI/UX findings table grounded in the two attached screenshots. Evidence: `step18-final-answer-visible-8841-20260712.png`.
- Visible artifact acceptance: through the right-side file inspector, filtered for `ui-qa-report`, opened `ui-qa-report.json`, and confirmed that its JSON body was rendered in the visible UI. Evidence: `step18-ui-qa-report-open-8841-20260712.png`.
- Artifact and usage: `PRIVATE/demo-runs/provider-switch-live-20260622-224524/workspace/reports/ui-qa-report.json` exists and contains the expected `summary`, `findings`, and `based_on: "two_attached_screenshots_only"` fields. Provider usage/cost stayed `not_available` and was not inferred.
- Residual finding: the main conversation pane can require a reload or revisit before a completed provider-lane answer appears after handoff. This is recorded as a remaining P2 refresh issue, not a Step 18 blocker.
- Evidence record: `PRIVATE/app-standardization-ui-dogfood/runs/DG-MULTIMODAL-UI-01/step18-live-success-report.md` and `.json`.
- Step 18 status: completed.
- Next entry: Step 20, instantiate the bounded Planner -> parallel auditors -> Synthesizer graph through visible UI and retain lane-isolation plus artifact-handoff evidence.

### 2026-07-12 - Step 20 visible task-graph execution gap confirmed

- Browser state: after the Codex restart and cache-move recovery, the in-app browser remained healthy for this session. The live AstraBridge tab on `8839` was claimable, DOM snapshots worked, and viewport screenshots rendered normally. This removes the older `browser_webview_unavailable` condition for the current Step 20 attempt.
- Visible progress: through the real task-graph UI, the operator re-entered the graph workspace, opened the template browser, instantiated `Fan-out / Fan-in Research`, opened the compact node palette, and entered the edge inspector modal. Evidence was preserved under `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/`.
- Concrete blocker 1: the visible toolbar still exposes only `夹具运行`, `可取消夹具`, and `Dry-run`. Current source matches that surface: the desktop task-graph workspace renders only those actions, and the sidecar task-graph service exposes dry-run and fixture execution paths but no current-source live provider-backed task-graph run entrypoint for this UI path.
- Concrete blocker 2: once the edge inspector modal was open, repeated visible close/run attempts did not reliably dismiss the modal or reach the intended canvas/run controls. The preserved screenshots show the modal covering the graph while the run toolbar remains behind it, which blocks a clean visible author/edit/run loop.
- Safety and cost: no provider-backed graph request, no external write, and no secret read occurred. Token/cost for this Step 20 attempt remain `0` / `not_available`.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/step20-blocked-report.md` and `.json`.
- Step 20 status: still in progress, currently blocked by a product capability gap rather than operator error.
- Next entry: remain at Step 20. Add a visible live graph-run action, repair inspector-modal dismissal/re-entry, then rerun the bounded `Planner -> parallel auditors -> Synthesizer` graph through visible UI and retain per-node artifact plus lane-isolation evidence.

### 2026-07-12 - Step 20 graph-source selection repair and live-run preflight recheck

- Reproduced visible blocker: on the fresh current-source sidecar `8842`, the launcher opened the `Provider Switch Live 20260622-224524` project quickly and the visible `任务图` button remained present, but entering the graph workspace still crashed in the browser with `Cannot read properties of undefined (reading 'find')`.
- Root cause: `App.tsx` built `currentTaskGraphBase` from `currentTask.graph_definitions` before preferring `/api/task-graphs/current`. The `project/tasks` payload only carried summary graph definitions (`graph_id`, `title`, counts, timestamps) and omitted `nodes` / `edges`, so the workspace received a summary object instead of the full route graph.
- Repair: added `hasRenderableTaskGraphStructure` and changed `currentTaskGraphBase` selection to treat summary-only graph definitions as non-renderable. The workspace now prefers the route graph or another full graph definition before rendering. Files changed: `apps/astrabridge-desktop/src/App.tsx`, `apps/astrabridge-desktop/src/features/runtime/taskGraphSelection.ts`, `apps/astrabridge-desktop/src/features/runtime/taskGraphSelection.test.ts`.
- Validation: focused desktop tests passed `66/66` (`taskGraphSelection` + `TaskGraphWorkspace`), and the desktop production build passed with the existing Vite chunk-size warning.
- Independent browser proof: a local headless browser repeated the real path `Provider Switch Live 20260622-224524 -> 任务图` against `8842` and no longer reported any page errors. The resulting surface shows the graph workspace, run controls, snapshots, and the instantiated `Fan-out / Fan-in Research` graph. Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260712-step20/step20-task-graph-open-after-app-fix.json` and `.png`.
- Remaining blocker 1: the in-app browser transport regressed again during this slice. After one successful attached session, fresh tabs began failing with `Timed out waiting for the Browser webview to attach`, and the reused attached tab later failed with `Page.getFrameTree` / `Runtime.evaluate` timeouts. This is `browser_webview_unavailable`, not renewed product proof of a task-graph crash.
- Remaining blocker 2: the repaired graph workspace now renders a visible readiness warning, `Model has no verified structured tool-calling surface.` This means the next Step 20 live-run attempt must start from a task/provider lane whose active thread satisfies the structured tool-calling gate, or the run will remain blocked at preflight even though the workspace itself opens.
- Step 20 status: still in progress. The task-graph crash path is repaired, but the bounded live graph run has not yet been completed through the required visible in-app browser path.
- Next entry: remain at Step 20. Reattach a stable in-app browser tab on the responsive `8842` current-source sidecar, switch into a task/lane with verified structured tool-calling support, then complete the visible `Planner -> parallel auditors -> Synthesizer` graph run and retain node-level artifact and lane-isolation evidence.

### 2026-07-12 - Step 21 task-graph crash repaired after browser/cache recovery

- Browser and cache state: after the cache-directory move and Codex restart, the in-app browser control bridge recovered. A fresh in-app AstraBridge tab on `8839` loaded successfully, returned visible DOM, and showed the managed `astra` session. `.astrabridge/` project-local runtime state remained present.
- Reproduced blocker: entering `任务图` still crashed current source with `TypeError: Cannot read properties of undefined (reading 'find')` inside `TaskGraphWorkspace`, proving the remaining Step 20 blocker was product-side and not just browser transport noise.
- Repair: normalized runtime array props at the `TaskGraphWorkspace` boundary so `templates`, `providerOptions`, `modelSuggestions`, and `snapshotRefs` fail closed to empty arrays before any `find`/`some`/`map` access. Added a regression test that renders the workspace with those props missing.
- Files changed: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx` and `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`.
- Validation: focused `TaskGraphWorkspace` suite passed `64/64`; desktop production build passed with the existing Vite chunk-size warning.
- Visible acceptance: an independent headless local-browser capture repeated the real UI path `Provider Switch Live 20260622-224524 -> 任务图` and no longer produced any page errors. The captured surface now shows `返回对话`, `模板`, and `还没有任务图`, proving the graph workspace opens instead of crashing. Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260712-step21/task-graph-headless-check-after-fix.json` and `.png`.
- Residuals: the in-app browser's `reload()` path still produced an empty DOM once during this slice, so browser transport remains less stable than the fresh-tab and independent-headless paths. That is not the Step 21 product blocker anymore.
- Step 21 status: completed.
- Next entry: return to Step 20 and continue the visible provider-backed graph-run path from the now-stable Task Graph workspace.

### 2026-07-12 - Step 20 runtime-lane mismatch isolated

- Browser/service state: the current-source desktop app on `4181` and sidecar on `8839` were healthy again, and the earlier Step 20 UI-path repair still held in source. The task-graph run actions and run-inspection surface are no longer the primary blocker.
- Current blocker 1: the active authenticated project runtime catalog at `D:\AstraBridgeRuntime\project_runtime\Provider-Switch-Live-20260622-224524-2581ddc60f57\codex_home\models\astrabridge-models.json` now exposes only one model, `qwen/qwen3.7-plus`, and that catalog marks it `authority_tier: C` with `authority_reason: Model has no verified structured tool-calling surface.` This lane therefore cannot satisfy Step 20's provider-backed graph-run gate.
- Current blocker 2: task-graph template defaults are stale. `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py` still seeds `fanout_fanin_research` and other graph templates with `qwen / qwen3-coder-plus`, while the current project runtime catalog no longer exposes that model. This matches the visible dry-run reason `No configured profile matches qwen / qwen3-coder-plus.`
- Browser boundary: after the restart recovery, the browser plugin could again lose the already-open in-app tab handle and only create controllable `about:blank` tabs. This is `browser_webview_unavailable`, not evidence that AstraBridge itself failed.
- Safety and cost: no provider-backed graph run, no external write, and no secret read occurred in this slice. Provider calls remain `0`; token/cost signals remain `not_available`.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/step20-runtime-lane-blocker-20260712.md` and `.json`.
- Step 20 status: still in progress. The remaining gap is now a concrete runtime/model-lane mismatch plus stale template defaults, not an unexplained task-graph UI failure.
- Next entry: remain at Step 20. Enter a visible authenticated task/lane whose runtime catalog exposes an acceptable structured-tool model, repair stale task-graph template defaults so seeded node models exist in the active catalog, then rerun the bounded `Planner -> [Docs Auditor, API Auditor, UI Wording Auditor] -> Synthesizer` graph through visible UI and retain node-level artifact plus lane-isolation evidence.

### 2026-07-12 - Step 20 browser attachment recovered after cache move and Codex restart

- Browser recovery: after the user moved the AstraBridge cache directory and restarted Codex, the in-app browser control bridge was reattached successfully in this session. The live AstraBridge tab remained controllable as tab `29`, DOM snapshots worked again, and a fresh viewport screenshot rendered normally.
- Service state: `http://127.0.0.1:4181` returned HTTP `200`, `http://127.0.0.1:8839/health` returned `ok: true`, and the sampled browser console log had no warning/error entries. This means the current blocker is no longer webview attachment or a dead frontend/sidecar process.
- Visible auth state: the left rail again showed hosted user `astra`, so the current visible session is authenticated rather than anonymous in this slice.
- Remaining blocker: Step 20 still cannot complete because the active runtime lane continues to expose only `qwen/qwen3.7-plus`, and the graph UI still warns `Model has no verified structured tool-calling surface.` The provider-backed task-graph run therefore remains blocked by runtime/model authority, not by the cache move or browser transport.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/step20-browser-recovery-status-20260712.md` and `step20-browser-recovered-after-restart.png`.
- Step 20 status: still in progress.
- Next entry: remain at Step 20. Keep the recovered visible browser path, then switch or repair the active authenticated runtime/model lane so the bounded provider-backed graph run can clear structured-tool preflight and proceed.

### 2026-07-12 - Step 20 fallback graph persistence repaired after cache move

- Reproduced the current visible failure path on the recovered `8839` session: entering `DG Graph Parallel 01 Fresh` and clicking visible `Dry-run` opened the run-check modal with `Graph not found.` even though a graph was drawn on the canvas.
- Root cause: after the cache-directory move and restart, the desktop app could still render a locally cached fallback graph for the current task, but the sidecar task state for `DG Graph Parallel 01 Fresh` had `graph_definitions: []`. Server-backed actions therefore attempted to run against a graph id that existed only in desktop-local fallback storage.
- Repair: added explicit fallback/server reconciliation in the desktop task-graph workspace. Before server-backed actions (`dry-run`, live run, fixture run, snapshot, export), the app now checks whether the current visible graph exists only as a fallback/local graph and automatically persists it back through `saveTaskGraph` before continuing.
- Files changed: `apps/astrabridge-desktop/src/App.tsx`, `apps/astrabridge-desktop/src/features/runtime/taskGraphFallbackState.ts`, `apps/astrabridge-desktop/src/features/runtime/taskGraphFallbackState.test.ts`.
- Validation: focused Vitest suite passed for the new persistence helper, and the desktop production build passed.
- Visible recheck: after reload, the same real UI path (`任务图 -> 模板 -> Supervisor / Worker / Synthesizer -> 实例化模板 -> Dry-run`) no longer produced `Graph not found.`. The run-check modal now reaches a real blocked dry-run result with concrete business diagnostics: `No configured profile matches qwen / qwen3-coder-plus.`
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/step20-fallback-graph-persist-repair-20260712.md` and `step20-dry-run-after-fallback-persist-fix.jpg`.
- Step 20 status: still in progress. The missing-graph/cache-detachment failure is repaired; the remaining blocker is now stale template/provider defaults against the active qwen catalog.
- Next entry: remain at Step 20. Repair the seeded task-graph template/model defaults or add a compatible profile mapping so the visible `DG Graph Parallel 01` dry-run can clear the `qwen / qwen3-coder-plus` mismatch on the current authenticated lane.

### 2026-07-12 - Step 20 bounded graph-worker collaboration-mode repair

- Re-read current evidence after the Codex restart and cache move. The visible `8839` app session was healthy again, the managed `astra` lane was still present, and `8839 /health` returned `ok: true`; however the existing live graph run `graph-run-live-20260712T181657539242-cdd2dd` was still stranded after `node_supervisor-started`.
- Runtime diagnosis from persisted rollout evidence showed the active graph-worker thread entered Codex `collaboration_mode = "plan"` even though the task-graph node expected one bounded structured reply. The rollout file `D:\AstraBridgeRuntime\project_runtime\Provider-Switch-Live-20260622-224524-2581ddc60f57\codex_home\sessions\2026\07\12\rollout-2026-07-12T18-17-12-019f559d-c1f1-72d2-bf31-1a9e3aba8e61.jsonl` contained Plan Mode developer instructions and shell exploration instead of immediate node output.
- Repair: bounded task-graph workers now normalize `collaboration_mode = plan` to `default` at runtime, and newly instantiated graph templates now default every node to `default` instead of seeding supervisors/synthesizers/reviewers with `plan`. The live-run prompt now explicitly states that a graph worker is one bounded node, must finish in a single structured reply, and must not enter an extended planning loop or inspect the repository unless the prompt explicitly requires it.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`, and `apps/astrabridge-sidecar/tests/test_task_graph_worker_runtime.py`.
- Validation: targeted Python compilation passed for the two sidecar modules plus the focused task-graph runtime test file. Focused task-graph runtime tests passed 3/3 under a temporary `ASTRABRIDGE_RUNTIME_ROOT`, covering new template defaults, collaboration-mode normalization, and live-run dispatch preserving `default` mode for repaired supervisor/synthesizer nodes.
- Remaining blocker: the repaired source has not yet been proven through the required visible authenticated in-app task-graph run because the currently visible `8839` session is still the pre-restart process, while alternate fresh sidecar launches on `8840` were only provable in foreground health probes and were not converted into a durable visible authenticated session in this turn.
- Step 20 status: still in progress. The bounded-worker runtime defect is repaired in source and regression-tested, but the required visible provider-backed graph rerun on the repaired sidecar/session is still pending.
- Next entry: remain at Step 20. Reload or restart the visible authenticated sidecar/session on repaired source, use the recovered in-app browser path to rerun `DG Graph Parallel 01`, and verify that the supervisor no longer enters a plan-mode loop before continuing the bounded parallel graph acceptance.

### 2026-07-12 - Step 20 live-run pending-state repair

- Visible defect: in the recovered authenticated in-app session on `8839`, clicking visible `直接运行` in `DG Graph Parallel 01 Fresh` briefly produced a synthetic `pending-graph-*` latest-run dock and toolbar wording `正在运行夹具...`, even though the operator had not clicked any fixture action. After the pending window, the workspace fell back to the older `graph-run-live-20260712T202335525698-e372e0` run record. This showed that the direct-live launch UI was incorrectly reusing fixture-pending presentation.
- Root cause: `App.tsx` passed `runTaskGraph.isPending` into the `isFixtureRunPending` prop for `TaskGraphWorkspace`. The workspace then used that prop to synthesize the `pending-${graph.graph_id}` run dock and fixture copy. The result was a user-visible state lie: direct live launch looked like fixture launch.
- Repair: added a dedicated `isLiveRunPending` prop, removed `runTaskGraph.isPending` from `isFixtureRunPending`, added live-launch-specific pending copy, and taught the run dock to synthesize a live-launch pending state separately from fixture launch. Files changed: `apps/astrabridge-desktop/src/App.tsx`, `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`, and `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`.
- Validation: focused desktop tests passed (`TaskGraphWorkspace`, `taskGraphSelection`, `taskGraphFallbackState`; `75` tests total) and desktop TypeScript compile passed with `tsc -p .\\tsconfig.json --noEmit`. Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260712-step20-live-run-pending-state.md`.
- Remaining blocker: after hot reload, the visible in-app browser session fell back to the launcher, the recent-project list was empty, and manual reopen of `D:/AstraBridge/PRIVATE/demo-runs/provider-switch-live-20260622-224524/Provider-Switch-Live-20260622-224524.abproj` remained stuck on `加载中…`. That prevented same-turn visible confirmation of the corrected live-run wording on the repaired session.
- Step 20 status: still in progress. The live-run pending-state defect is repaired in source and regression-tested, but the bounded visible graph acceptance is still waiting on a responsive authenticated project-open path.
- Next entry: remain at Step 20. Reopen the authenticated `Provider Switch Live 20260622-224524` project through visible UI on the repaired source, re-enter Task Graph, verify the corrected live-run pending presentation, then continue the bounded parallel graph acceptance.

### 2026-07-12 - Step 20 live-run visible recheck after browser recovery

- Visible preflight: on the recovered authenticated `8839` session, the operator re-entered `DG Graph Parallel 01 Fresh`, opened `任务图`, and confirmed the same active runtime lane warning, `Model has no verified structured tool-calling surface.` The visible session remained hosted as `astra`; this was not an anonymous or launcher fallback slice.
- Verified fix: clicking visible `直接运行` now shows truthful live-run pending copy, `正在启动直接运行...`, and a synthetic pending run row instead of fixture wording. This closes the specific pending-state lie repaired earlier in source.
- New visible blocker: roughly ten seconds later, the workspace no longer shows a live-run pending row. It falls back to the older stale row `graph-dry-run-... / dry_run_blocked`, surfaces `Failed to fetch`, and exposes `重试 Dry-run`. The toolbar resets to `直接运行` without any persisted live-run result.
- Read-only diagnostics: `D:\AstraBridge\PRIVATE\demo-runs\provider-switch-live-20260622-224524\workspace\PRIVATE\task-graph\workers\` and `D:\AstraBridgeRuntime\project_runtime\Provider-Switch-Live-20260622-224524-2581ddc60f57\` showed no fresh `graph-run-live-*` directory after the visible click. `GET /api/runtime/events?limit=200` also showed no fresh graph-run or worker-start event proving the live run advanced into a real provider-backed execution path.
- Safety and cost: no external write occurred, no secret source was accessed, and no trustworthy usage/cost signal was produced. Record this slice as `usage_signal: not_available` and `cost_signal: not_available`.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260712-live-run-recheck/step20-live-run-visible-recheck-20260712.md`, `.json`, and screenshots under the same directory.
- Step 20 status: still in progress. The pending-state repair is visibly verified, but the remaining blocker is now the `/api/task-graphs/run` failure/stale-last-run fallback on the authenticated `qwen/qwen3.7-plus` lane, not browser transport or project-open state.
- Next entry: remain at Step 20. Inspect and repair the `/api/task-graphs/run` failure/stale-last-run fallback on the authenticated `qwen/qwen3.7-plus` lane, then rerun the bounded `Planner -> [Docs Auditor, API Auditor, UI Wording Auditor] -> Synthesizer` graph through visible UI and retain node-level artifact plus lane-isolation evidence.

### 2026-07-12 - Step 20 post-restart browser recheck after cache move

- Browser state: after the user reported a moved AstraBridge cache directory and restarted Codex, the in-app browser bridge reattached successfully again. The visible AstraBridge tab on `4181/?astrabridge_launch=dogfood&sidecar=...8839` was claimable, DOM snapshots worked, screenshots worked, and the hosted user remained `astra`.
- Service state: `http://127.0.0.1:4181/` still returned HTTP `200`, and `http://127.0.0.1:8839/health` still returned `ok: true`. This slice therefore does not support a launcher, frontend, sidecar, or browser-bridge outage explanation.
- Visible rerun: from the visible task-graph toolbar, the operator clicked `直接运行` again inside `DG Graph Parallel 01 Fresh`.
- Settled failure: the UI again failed to materialize a fresh live provider-backed graph run. The settled view opened the run-check dialog and showed stale dry-run provenance (`graph-dry-run-... / dry_run_blocked`) with the diagnostic `Not found`, while the toolbar fell back to idle `直接运行`.
- Read-only diagnostics: `GET /api/runtime/events?limit=80` showed no fresh graph-run or worker-start event for this click, and `D:\AstraBridge\PRIVATE\demo-runs\provider-switch-live-20260622-224524\workspace\PRIVATE\task-graph\live-run\` did not gain a fresh `graph-run-live-*` directory. The failure remains upstream of real run creation.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260712-post-restart-recheck/step20-post-restart-live-run-recheck.md`, `.json`, and `01-post-restart-live-run-settled.png`.
- Step 20 status: still in progress. The restart/cache move did not re-break the browser or shell; the remaining blocker is still the task-graph live-run request path itself.
- Next entry: remain at Step 20. Inspect and repair the server-backed `/api/task-graphs/run` request path or desktop fallback logic that leaves the visible UI on stale dry-run state with `Not found`, then rerun the bounded graph through visible UI.

### 2026-07-12 - Step 20 stale template route auto-repair landed

- Visible narrowing on the recovered `8839` session: clicking visible `鐩存帴杩愯` no longer settled on stale `Not found`. The same real UI path now reaches a concrete dry-run-preflight blocker: `Task graph live run is blocked until dry-run passes. No configured profile matches qwen / qwen3-coder-plus.`
- Root cause: older persisted task graphs still carried template-seeded node routes for `qwen3-coder-plus`. The current authenticated runtime lane exposes `qwen3.7-plus`, so dry-run blocked before a real live graph run could start.
- Repair: `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py` now auto-repairs stale template-seeded provider/model pairs against the current configured model catalog during `dry_run_graph`, but only when a node still exactly matches the raw template default for that node. This keeps the fix narrow and avoids rewriting arbitrary user-custom routing.
- Validation: focused regression `tests.test_task_graph_api.TaskGraphApiTests.test_dry_run_repairs_stale_template_defaults_against_current_configured_models` passed under a temporary `ASTRABRIDGE_RUNTIME_ROOT`.
- Patched-sidecar check: a fresh current-source sidecar on `8845` was launched successfully and `GET /health` returned `ok: true`. The visible `4181?...sidecar=8845` session reopened with managed user `astra`, but follow-on browser-driven project-open interactions hit repeated browser-control timeouts before the patched Step 20 rerun could be completed.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/step20-stale-template-route-autorepair-20260712.md` and `.json`.
- Step 20 status: still in progress. The stale template-route blocker is repaired in source and unit-tested, but the required visible rerun on the patched sidecar has not yet been completed.
- Next entry: remain at Step 20. Reopen `Provider Switch Live 20260622-224524` through visible UI on `8845`, re-enter `DG Graph Parallel 01 Fresh`, verify the `qwen / qwen3-coder-plus` blocker is gone, then continue the bounded live graph acceptance.

### 2026-07-12 - Step 20 visible 8846 dry-run pass and graph editing recovery

- Visible recovery: on a fresh controlled in-app tab pointed at patched sidecar `8846`, the operator re-entered `Provider Switch Live 20260622-224524`, opened `DG Graph Parallel 01 Fresh`, and returned to `任务图` under the hosted `astra` session.
- Cleared blocker through visible UI: clicking visible `Dry-run` no longer produced `No configured profile matches qwen / qwen3-coder-plus.` The run-check modal settled to `pass 5 / 0 / 0`, so the stale template-route blocker is now visibly cleared on the patched session rather than only unit-tested in source.
- Visible editing recovery: the node palette opened from the left rail, the node inspector modal opened by clicking a graph node, and two `Custom Agent` nodes were added through visible clicks. This proves Step 20 graph editing is again usable on the patched session.
- Visible rewire start: one of the newly added branches was renamed and saved as `API Auditor` on `qwen/qwen3.7-plus`, so the bounded parallel graph rebuild has moved from generic palette recovery into concrete graph rewiring on the live canvas.
- Remaining blocker: the currently attached graph is still not the required bounded parallel audit topology. The visible inspector still exposes `graph_title = API debug instantiate probe 8843b` and `graph_template_id = supervisor_worker_synthesizer`, so Step 20 cannot yet be marked complete even though dry-run is now healthy.
- Safety and cost: no trustworthy provider-backed live graph completion occurred in this slice; record `request_count = 0`, `usage_signal = not_available`, and `cost_signal = not_available`.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260712-8846-visible-recheck/step20-8846-visible-dry-run-pass-and-graph-editing.md`, `.json`, `01-graph-after-dry-run-pass.png`, and `02-node-palette-and-inspector-editing.png`.
- Step 20 status: still in progress. The old qwen3-coder-plus blocker is visibly cleared and graph editing is recovered, but the required `Planner -> [Docs Auditor, API Auditor, UI Wording Auditor] -> Synthesizer` graph still needs to be instantiated and run.
- Next entry: remain at Step 20 on patched `8846`; finish rewiring the graph into the required bounded parallel topology, save node/edge contracts through the visible inspector, then rerun dry-run and bounded live execution with node-level artifact and lane-isolation evidence.

### 2026-07-12 - Step 20 patched 8846 session degraded after partial rewire

- Continued the same Step 20 visible rewire on `8846` and successfully returned to `DG Graph Parallel 01 Fresh`, reopened the graph canvas, and confirmed the partial graph state was still present: the base `Supervisor -> Worker -> Synthesizer` chain plus the new `API Auditor` branch and one remaining unnamed custom branch.
- New blocker: while renaming the remaining branch, browser control degraded from graph interaction into transport failures: `Runtime.evaluate` timeout on tab `16`, then `Page.getFrameTree` timeout, then a fresh browser-use page failed to attach its webview. In the same slice, `GET http://127.0.0.1:8846/health` also started timing out.
- Cross-check: `http://127.0.0.1:4181` still returned `200`, and `http://127.0.0.1:8839/health` still returned `ok: true`. So the current blocker is not a full AstraBridge outage; it is a degraded patched `8846` session plus browser bridge instability while `8839` remains healthy.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260712-8846-visible-recheck/step20-8846-session-degraded-after-partial-rewire.md`.
- Step 20 status: still in progress. The graph rewrite has started but cannot be completed on the hung `8846` session.
- Next entry: remain at Step 20 and resume from the healthy visible `8839` session, finish renaming the remaining branch and planner node, complete the required fan-out/fan-in wiring, then rerun visible dry-run and bounded live execution.

### 2026-07-12 - Step 20 recovered `8839` graph rewire advanced to the native-select blocker

- Browser/session recovery was confirmed again on the healthy visible `8839` session after the Codex restart and cache move: `http://127.0.0.1:4181/` returned `200`, `http://127.0.0.1:8839/health` returned `ok: true`, the hosted user remained `astra`, the in-app DOM was readable, and viewport screenshots worked again.
- Visible graph progress: through the recovered task-graph UI, the remaining branch rename work continued and two additional edges were created through the visible canvas/editor path:
  - `Planner -> API Auditor` as `control_dependency`
  - `API Auditor -> Synthesizer` as `artifact_handoff`
- The remaining required branch did not complete. Opening the visible `Planner -> UI Wording Auditor` draft edge left the modal on default `artifact_handoff` with `No compatible typed ports between source outputs and target inputs.` and a disabled `创建边` action.
- Concrete interaction blocker: repeated visible attempts to change the edge-type select from `artifact_handoff` to `control_dependency` did not move the control at all in this session. Preserved attempts included DOM-node click plus `ArrowDown/Enter`, `Alt+ArrowDown`, coordinate click on the native dropdown glyph, and the same keyboard probe on another select as a control check. After every attempt the modal still showed source `node_supervisor`, target `node_artifact_source_2`, edge type `artifact_handoff`, the same compatibility warning, and a disabled `创建边`.
- Stronger diagnosis from the follow-up repro on the same healthy `8839` session: the edge-type `<select>` is not disabled and does take focus, but focused visible keyboard paths still do not change its value. Read-only checks showed `document.activeElement` became the `SELECT` after both coordinate click and DOM-node click, yet `dom_cua.keypress`, `cua.keypress`, and Playwright `press('ArrowDown')` all left the value on `artifact_handoff`. A fresh output-to-node-body edge gesture also reopened the same default draft edge instead of discovering an alternate visible route, and the rendered `task-graph-inspector-close` button returned without runtime error while leaving the modal open in the next screenshot.
- Interpretation: Step 20 is no longer blocked by browser attach, service health, stale template defaults, or the earlier live-run request path in this slice. It is now blocked by the visible task-graph edge modal's native select control, which did not respond to the mandated click-driven path well enough to finish the last required branch on `8839`.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260712-step20-select-blocker/step20-ui-wording-edge-select-blocker.md`, `step20-ui-wording-edge-select-blocker.json`, `step20-ui-wording-edge-select-blocker.dom.txt`, `step20-ui-wording-edge-select-blocker.png`, and `step20-ui-wording-edge-select-blocker-refreshed.png`.
- Step 20 status: still in progress. The graph is closer to the required topology, but the final `UI Wording Auditor` branch and its join edge are still missing, so dry-run and bounded live acceptance were not rerun in this slice.
- Next entry: remain at Step 20 on `8839`. Resume from the preserved `Planner -> UI Wording Auditor` draft-edge blocker, make the edge-type control visibly operable or replace it with another still-visible product path, create the remaining branch and join edge, then rerun visible `Dry-run` and bounded live execution with node-level artifact and lane-isolation evidence.

### 2026-07-13 - Step 20 browser recovery confirmed after cache move and Codex restart

- Browser recovery: after the cache move and Codex restart, `browser-client.mjs` was present again, the in-app browser bridge reattached successfully, and a fresh visible tab was created and navigated back to `http://127.0.0.1:4181/?astrabridge_launch=dogfood&sidecar=http%3A%2F%2F127.0.0.1%3A8839`.
- Visible recovery evidence: the restored tab rendered normal AstraBridge UI, reopened `DG Graph Parallel 01 Fresh`, and re-entered `任务图` through the visible chat surface. Screenshots were preserved as `step20-browser-recovery-visible.jpg` and `step20-task-graph-visible.jpg` under `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260713-browser-recovery/`.
- Graph state on recovery: the required five-node topology remained visible on screen (`Planner`, `Docs Auditor`, `API Auditor`, `UI Wording Auditor`, `Synthesizer`), so the current Step 20 blocker is no longer the earlier edge-modal select defect or a missing graph after restart.
- New blocker: a visible `Dry-run` click now starts a recent-run path instead of returning the earlier `blocked` validation state, but it still does not settle into a terminal result. After more than 40 seconds of observation, the page continued to expose `RUNNING` without clear `COMPLETED`, `PARTIAL`, or `FAILED` state. Evidence was preserved as `step20-dry-run-recheck.jpg`, `step20-dry-run-settled.jpg`, `step20-browser-recovery-status-20260713.md`, and `.json`.
- Scope boundary: this slice did not prove that mixed-provider node edits were saved successfully through the restored node inspector. The visible node modal remained automation-fragile, so no new provider-backed live acceptance claim is made from this slice.
- Step 20 status: still in progress. The browser/webview recovery is verified, but the remaining blocker has moved to the task-graph run path itself.
- Next entry: remain at Step 20. Diagnose whether the persistent `RUNNING` state is stale latest-run UI or a real scheduler/runtime hang on the restored visible `8839` session, then either complete bounded live acceptance or route the concrete runtime defect through Step 21 before retrying.

### 2026-07-13 - Step 20 stale run and orchestration-sync root cause isolated

- Visible reproduction: reclaimed the restarted in-app browser tab, re-entered `DG Graph Parallel 01 Fresh`, clicked `Dry-run`, and observed the current validation error `agent_orchestration_edge edge-20260712T234505018965-71dac2 references unknown node ids.` alongside the unrelated historical live run `graph-run-live-20260712T215824389806-b0ae98` still presented as `RUNNING`.
- Visible cancellation check: clicked `取消运行` for that stale live run. The control remained on `正在取消...` during the first 2.5-second check, then settled to `CANCELLED` before the evidence screenshot. Cancellation works, but stale refs require manual cleanup and pending feedback lacks a clear time boundary.
- Persisted-state diagnosis: the canonical graph contains five nodes and three persisted edges, while its embedded orchestration graph contains only the original three template nodes but still preserves an edge targeting the canonical-only `node_artifact_source`. The current synchronizer updates matching orchestration nodes and edges but neither adds missing canonical nodes nor prunes obsolete orchestration records.
- UI diagnosis: `currentTaskGraphRunRef` selects the newest persisted run ref without a staleness boundary, and the inspector renders that historical run beside the current Dry-run failure. This makes a failed current validation action look like a newly running job.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260713-stale-run-root-cause/step20-stale-running-and-sync-blocker.md`, `.json`, and `step20-stale-running-and-sync-blocker.png`.
- Safety and cost: visible UI actions plus read-only diagnostics only; no provider request, secret read, or external write occurred. Token/cost remain `0` / `not_available`.
- Step 20 status: still in progress. The browser and project-open paths are healthy, but provider-backed graph acceptance cannot proceed until the canonical synchronization and stale-run finalization defects are repaired.
- Next entry: Step 21. Repair task-graph/orchestration synchronization, stale run terminalization, and current-action-versus-history presentation; add focused regression coverage; then rerun the same visible Dry-run before returning to Step 20 live acceptance.

### 2026-07-13 - Step 21 canonical synchronization and visible Dry-run repair completed

- Browser/cache recovery: after the cache move and Codex restart, the current browser plugin again exposed `scripts/browser-client.mjs`; the in-app browser binding claimed the existing AstraBridge tab, returned a complete DOM, and captured screenshots normally.
- Runtime repair: task graph authoring state now projects only entry-reachable nodes and edges into the executable orchestration graph. Newly connected draft nodes are promoted, disconnected or removed records are pruned, and existing rich orchestration metadata is preserved by stable ID.
- Compatibility repair: new graph nodes declare `structured_json` instead of the invalid legacy `required_output` artifact marker. Existing graphs normalize `required_output` and `smoke_matrix` through explicit migration aliases before strict orchestration validation; unknown artifact kinds remain rejected.
- UI repair: current Dry-run readiness takes priority over historical run history, and active persisted run refs older than the bounded staleness window render as `stale` instead of presenting an unrelated current `RUNNING` state.
- Validation: sidecar `tests/test_task_graph_api.py` passed `7/7`; Desktop `taskGraphRunRefs.test.ts` plus `TaskGraphWorkspace.test.tsx` passed `74/74`; Desktop production build passed with the existing Vite chunk-size warning. The integration helper timeout was raised from 5 to 15 seconds because the Windows service completed correctly but occasionally returned after the old test-only boundary.
- Visible acceptance: started current-source sidecar `8847` with normal desktop permissions, retained the managed `astra` session, opened `Provider Switch Live 20260622-224524 -> DG Graph Parallel 01 Fresh -> 任务图`, and clicked `Dry-run`. The inspector returned `11 pass / 0 warning / 0 blocked`; the former unknown-node error and unrelated historical `RUNNING` presentation were absent.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260713-step21-repair/`, including `step21-visible-dry-run-pass.png`, `step21-visible-dry-run-pass.dom.txt`, focused test logs, and the production build log.
- Safety and cost: no provider request, secret read, external write, or live run occurred. Token use is `0`; cost is `not_available`.
- Step 21 status: completed. Next entry: return to Step 20 and perform one bounded provider-backed parallel graph run through the same visible UI path.

### 2026-07-13 - Step 20 provider-backed run reached terminal collector defect

- Browser recovery: after the cache move and Codex restart, the bundled `browser-client.mjs` loaded successfully. A fresh visible in-app tab opened the current-source `8847` application, exposed a complete interactive DOM, captured screenshots, and retained the managed `astra` session.
- Visible execution: reopened `DG Graph Parallel 01 Fresh -> 任务图`, verified the required five-node/six-edge topology, and started one bounded provider-backed run through the visible `直接运行` control. Run ID: `graph-run-live-20260713T145612107318-b8152c`.
- Provider result: the Planner thread completed with valid structured JSON. Its redacted rollout token event reports 6,857 input, 527 output, 249 reasoning output, and 7,384 total tokens. Cost and graph-projected provider call count remain unavailable; at least one provider-backed worker call occurred.
- Concrete blocker: the task-graph runtime did not consume the terminal app-server result. The run remained at one worker, two artifacts, maximum parallelism 1, and no fan-out/join/Synthesizer output. The collector eventually raised the image-probe-specific terminal wait timeout while the provider rollout already contained `task_complete`.
- Visible cleanup: after browser recovery, the run still appeared `running`. The operator opened `运行检查`, clicked `取消运行`, waited for the persisted update, closed/reopened the panel, and visibly confirmed final `cancelled` status.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260713-step20-live-runtime-collector-timeout/`, including recovery/cancellation screenshots, visible DOM snapshots, and redacted Markdown/JSON diagnosis.
- Safety: no plaintext secret source, cookie, authorization header, provider key, or raw provider request was read or persisted. Product code was not changed in Step 20.
- Step 20 status: still in progress; parallel graph acceptance is not met.
- Next entry: Step 21. Repair app-server terminal result recognition, caller-specific timeout diagnostics, and failed-run terminalization; add focused regression coverage; then rerun the same visible bounded graph from Step 20.

### 2026-07-13 - Step 21 terminal collector and failed-run finalization repair completed

- Runtime repair: app-server terminal notifications now retain the nested `params.turn.id` and terminal status. When `thread/read` remains stale, the collector reconciles the terminal notification after a bounded grace period while preserving any available final agent message.
- Failure repair: task-graph timeout messages now name the graph node rather than the image probe. Any unhandled live-run failure terminalizes the persisted run as `failed`, marks the active node failed and downstream nodes blocked, emits terminal events, and writes redacted failure, summary, report, and manifest artifacts without overriding an already terminal cancellation.
- Regression coverage: `tests.test_task_graph_worker_runtime` passed `22/22`, including the real nested-turn/stale-projection case and timeout finalization; `tests.test_task_graph_api` passed `7/7`; Desktop `TaskGraphWorkspace.test.tsx` plus `taskGraphRunRefs.test.ts` passed `74/74`; Python compilation and the Desktop production build passed. The existing Vite large-chunk warning remains.
- Cache boundary: the first restricted test attempt could not write the newly migrated default `D:\AstraBridgeRuntime` root. The authoritative test rerun used an isolated repository-local runtime root and passed; the managed cache was not altered by tests.
- Visible acceptance: launched current-source sidecar `8848`, retained the managed `astra` session, opened `DG Graph Parallel 01 Fresh -> 任务图` through the visible in-app browser, and clicked `Dry-run`. The canvas and inspector agreed on `11 pass / 0 warning / 0 blocked`.
- Screenshot channel: the first full-viewport capture timed out while DOM remained healthy; a bounded clip capture then succeeded. This remained a browser screenshot-channel recovery detail, not an AstraBridge product failure.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260713-step21-terminal-collector-repair/`.
- Safety and cost: provider calls `0`, token use `0`, cost `not_available`; no plaintext secret source, cookie, authorization header, raw provider request, or external write was read or persisted.
- Step 21 status: completed. Next entry: return to Step 20 and rerun one bounded provider-backed graph through the same visible UI path, proving terminal collection, fan-out, join, Synthesizer output, artifacts, isolation, and the existing `80k` token boundary.

### 2026-07-13 - Step 20 provider-backed rerun exposed cross-lane terminal mismatch

- Visible execution: retained the managed `astra` session on current-source sidecar `8848`, confirmed the required five-node/six-edge graph and `11 pass / 0 warning / 0 blocked` Dry-run, then started exactly one provider-backed run through the visible `direct_run` control. Run ID: `graph-run-live-20260713T160712055059-a4fc3d`.
- Terminal presentation: the current UI visibly reported `Timed out waiting for task graph node Planner to reach a terminal state.` The persisted run is now correctly terminalized as `failed`, with Planner failed, four downstream nodes blocked, six diagnostic artifacts, and no misleading stale `RUNNING` state.
- Concrete root cause: Planner's worker lane was `019f5a4d-3ec7-76c1-adc7-0dd747cfe195`, while provider handoff executed the shared turn `019f5a4d-ff61-7d13-a3f7-b5bad6e63f97` on provider lane `019f5a4d-9d4d-7952-8468-1bf89edeef43`. That provider lane emitted `turn/completed` at `16:08:28` and synchronized its terminal snapshot at `16:08:36`; the collector, indexed by the original `(worker_thread_id, turn_id)`, timed out at `16:10:44`.
- Acceptance: terminal collection failed; fan-out, join, Synthesizer output, typed node artifacts, and full branch-isolation evidence were not reached. No whole-graph retry was made in this slice.
- Usage and safety: the authoritative token notification reports 6,857 input, 437 output, 313 reasoning-output, and 7,294 total tokens, within the `80k` case limit. At least one provider call occurred; exact call count and cost remain unavailable. No plaintext key, cookie, authorization header, raw provider request, or external write was persisted.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260713-step20-provider-backed-rerun/`, including visible preflight/start/failure screenshots and DOM snapshots plus the redacted JSON/Markdown diagnosis.
- Step 20 status: still in progress. Next entry: Step 21. Reconcile terminal results across worker-to-provider lane handoffs by turn ID, preserve the authoritative terminal thread ID, add a regression with distinct worker/provider thread IDs, then rerun Step 20 through the same visible path.

### 2026-07-13 - Step 21 cross-lane terminal and run-snapshot repair completed

- Root cause repaired: graph workers were created on one lane, while `start_turn` could hand the same turn to a provider lane. The live collector still waited on the original worker thread and therefore missed a valid provider-lane terminal event.
- Runtime repair: live graph execution now records `worker_thread_id`, authoritative `execution_thread_id`, and `turn_id`, waits on the effective execution thread, and emits a redacted `graph_worker_turn_thread_resolved` event. Live snapshots merge the latest persisted run ref before writing so a stale local snapshot cannot erase a newly recorded worker binding.
- Regression evidence: the first focused test intentionally exposed the stale-snapshot overwrite and is preserved. The corrected focused rerun passed; sidecar task-graph suites passed `29/29`; Desktop task-graph suites passed `74/74`; Python compilation and the production build passed. The existing Vite large-chunk warning remains unchanged.
- Visible acceptance: current-source sidecar `8849` retained the managed `astra` session and `qwen/qwen3.7-plus` route. Through the in-app browser, the five-node/six-edge graph returned `11 pass / 0 warning / 0 blocked` on Dry-run. The cache-directory move and Codex restart did not re-break the browser bridge or project session.
- Safety and cost: provider calls `0`, token use `0`, cost `not_available`; no plaintext secret, cookie, authorization header, raw provider request, or external write was persisted.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260713-step21-cross-lane-terminal/step21-cross-lane-terminal-repair.md` and `.json`, with focused/regression/build logs plus visible screenshot and DOM capture in the same directory.
- Step 21 status: completed. Next entry: return to Step 20 and run exactly one bounded provider-backed graph through the visible `8849` UI, proving terminal collection, fan-out, join, Synthesizer output, typed artifacts, isolation, and the `80k` token boundary.

### 2026-07-13 - Step 20 visible rerun exposed atomic-dispatch, orphan-turn, and budget defects

- Visible execution: through the current-source `8849` in-app page, with managed user `astra`, exactly one `Direct run` click started `graph-run-live-20260713T171530148207-89ad99`. No whole-graph retry was made.
- Cross-lane result: Planner completed successfully on its authoritative provider execution thread and committed typed artifacts. This proves the immediately preceding Step 21 cross-lane repair works for the entry node.
- Terminal result: the run failed with two workers and ten visible artifacts. Persisted failure was `Graph node node_artifact_source_2 is missing a provider.` Planner passed; Docs Auditor and Synthesizer were blocked; API Auditor and UI Wording Auditor were marked failed.
- P0 preflight/dispatch defect: Dry-run had returned `11 pass / 0 warning / 0 blocked`, yet UI Wording Auditor had no provider. Group dispatch started API Auditor before validating every runnable node, then failed when resolving UI Wording Auditor. Fan-out preparation is not atomic.
- P0 orphan-turn defect: the graph terminalized at `17:18:36`, but API Auditor's provider turn continued after failure and completed at `17:20:07`. Its final output was not committed to the failed graph and no cancellation/reconciliation was recorded.
- P0 budget defect: Planner reported `7290` total tokens and API Auditor `99580`, for `106870` total against the `80000` case boundary, an overrun of `26870`. The run manifest recorded budget `not_configured`; the visible inspector showed budget within bounds and token usage unavailable.
- P1 semantic/observability defects: the graph still carried stale `API debug instantiate probe 8843b` title and prompt semantics instead of the read-only Provider/Model consistency fixture. API Auditor attempted capability invocations. The final inspector also claimed no worker output despite committed Planner artifacts.
- Environment note: the Codex restart/cache migration changed the browser plugin directory from `26.707.61608` to `26.707.62119`; browser control was reattached without restarting the run. The terminal screenshot and DOM were retained after recovery.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260713-step20-cross-lane-rerun/step20-run-verdict.md` and `.json`, `03-failed-terminal.png`, `03-failed-terminal.dom.txt`, plus the preserved live-run/worker artifacts referenced by the verdict.
- Safety: no plaintext key, cookie, authorization header, or raw provider response was copied into the report. Exact cost and billed provider-call count remain unavailable. No external write was performed and no retry was attempted.
- Step 20 status: still in progress. Next entry: Step 21. Repair fail-closed all-node route preflight, atomic fan-out preparation, orphan-turn cancellation/reconciliation, mandatory run-budget enforcement and UI projection, fixture-semantic validation, and truthful worker-output presentation before returning to Step 20.

### 17.1. Enforce Bounded Code-Fix Tool Policy And Recovery

Goal: Turn the existing model instruction into an enforceable runtime contract. A strict code-edit policy must never silently downgrade into unrestricted shell behavior. When the runtime cannot prove native `apply_patch`-only support, it must fail closed before a provider request. Any observed policy violation must remain visible on the turn and prevent a misleading compliant-success state.

Main actions:

- Add a normalized per-turn execution policy contract with `standard` and `patch_only` modes.
- Reject `patch_only` before provider dispatch unless the runtime advertises verified native patch-only enforcement; preserve a concise recovery instruction instead of silently falling back.
- Attach a compact policy instruction to strict requests when the runtime can enforce it, automatically decline shell/file-change approvals that violate the contract, and record the decision as redacted runtime evidence.
- Decorate completed turns with policy status, observed prohibited tools, and a recovery action. Do not auto-revert files because an automatic revert can overwrite user work; instead make the violation non-compliant and require review/retry from a fresh constrained turn.
- Expose a compact, keyboard-accessible composer policy picker with tooltips. It must default to standard behavior and not add a persistent explanatory card.
- Add isolated service tests for normalization, fail-closed preflight, approval fallback, and audit decoration; build the desktop app. No provider call or secret source is permitted for this step.

Acceptance criteria:

- A request asking for `patch_only` cannot reach `turn/start` on an unverified app-server runtime.
- A strict active turn automatically returns a decline response for command/file-change approval requests and writes a redacted policy event.
- Thread reads expose an explicit `executionPolicy` result for strict turns, including `violated` status and recovery guidance if prohibited execution appears in the tool trace.
- The composer exposes the policy via a compact labeled control with an accessible tooltip and sends it to the sidecar for both new and existing threads.
- Targeted tests, desktop production build, and secret scan pass; no provider request is made.

### 2026-07-13 - Step 21 atomic preflight, reconciliation, and budget repair completed

- Live preflight now fails closed across every reachable node before provider dispatch unless provider, model, explicit prompt, provider-call permission, and a positive total-token budget are present.
- Fan-out groups are prepared atomically. If any sibling cannot start, no sibling is dispatched. Every already-started unsettled turn is inspected, interrupted when necessary, boundedly polled to terminal state, and retained in a redacted reconciliation record.
- The visible `Token 上限` control defaults to `80000` and is sent consistently to live Dry-run and Direct run. The runtime deterministically allocates per-node budgets, applies them before `turn/start`, and projects matching real token-usage notifications into node and graph budget results.
- Run-reference merging now preserves terminal worker bindings, artifacts, timeline, diagnostics, metrics, and budget evidence instead of allowing stale snapshots to overwrite richer state. The inspector no longer calls synchronizing worker data absent output.
- Verification passed: Python compilation; sidecar task-graph suites `32/32`; Desktop task-graph suites `76/76`; Desktop production build. The existing Vite large-chunk warning remains.
- Visible acceptance used only the in-app browser virtual pointer on current-source sidecar `8850`, retained managed user `astra`, and clicked `Dry-run` once with the visible `80000` limit. The stale fixture correctly returned `6 pass / 0 warning / 5 blocked`: five missing explicit prompts, with one node also missing provider/model. All six edges passed. No provider call occurred.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260713-step21-atomic-budget/step21-atomic-budget-repair.md` and `.json`, plus the saved screenshots, semantic DOM excerpt, and focused test/build logs in the same directory.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_available_no_billable_call`; no secret source, raw provider payload, authorization header, or external write was used.
- Step 21 status: completed. Next entry: Step 20. Through visible UI, repair the stale read-only Provider/Model consistency fixture, require a passing live Dry-run, then perform exactly one provider-backed run with the visible `80000` token limit and retain fan-out, join, Synthesizer, typed-artifact, isolation, reconciliation, and observed-usage evidence.

### 2026-07-13 - Step 21 disclosure-density follow-up completed

- User-directed finding: the Dry-run summary and reason list carried too much secondary text, while the recent-snapshot strip exposed too many snapshot chips at once.
- UI repair: both reason and snapshot collections now show three entries by default and expose the remainder through compact Chevron disclosure controls. The Dry-run node-count summary uses a smaller scoped meta style.
- Accessibility: disclosure controls expose dynamic visible text, hover titles, `aria-label`, and `aria-expanded`; focused component tests verify collapsed, expanded, and re-collapsed states.
- Verification: `TaskGraphWorkspace.test.tsx` passed `69/69`; Desktop production build passed; focused `git diff --check` passed. The existing Vite large-chunk warning remains.
- Visible acceptance: only the in-app browser virtual pointer was used on sidecar `8850`. The collapsed UI showed three reasons plus `展开 4`, and three snapshots plus `展开 21`; expanded reason evidence was captured. A later reload reproduced the independent CDP screenshot-channel timeout without an AstraBridge service failure.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260713-step21-disclosure-density/step21-disclosure-density-repair.md` and `.json`, plus the screenshot and semantic DOM capture in the same directory.
- Safety and cost: provider calls `0`, provider tokens `0`; no secret source, cookie, authorization header, raw provider payload, external write, or system-wide mouse control was used.
- Step 21 follow-up status: completed. Next entry remains Step 20: finish the visible read-only Provider/Model graph configuration, require a passing Dry-run, and execute exactly one bounded provider-backed run.

### 2026-07-13 - Step 20 bounded live rerun exposed no-tools enforcement and aborted-turn reconciliation defects

- Visible execution: using only the in-app browser virtual pointer on current-source sidecar `8851`, retained managed user `astra`, repaired all five node configurations through visible controls, and obtained a passing Dry-run: `11 pass / 0 warning / 0 blocked`. Dry-run ID: `graph-dry-run-20260713T212830859403-1db2f8`.
- Exactly one provider-backed run was started with the visible `80000` token limit. Run ID: `graph-run-live-20260713T213048917125-2aa00a`. No whole-graph retry was made.
- Terminal result: the run failed as `terminal_collection_timeout`. Planner was marked failed; Docs Auditor, API Auditor, UI Wording Auditor, and Synthesizer were blocked. Maximum observed parallelism remained `1`, so fan-out, join, Synthesizer output, typed branch artifacts, and lane-isolation acceptance were not reached.
- Enforcement defect: Planner's explicit prompt prohibited tools and external state, but the provider rollout emitted four `shell_command` function calls. This proves prompt-only restraint is insufficient and the graph node's no-tools contract is not enforced at the provider tool surface.
- Reconciliation defect: the authoritative provider rollout recorded `turn_aborted` with reason `interrupted`, while graph reconciliation ended as `interrupt_failed` and the collector timed out. An aborted provider turn is not being converted into a deterministic graph-node terminal policy/runtime outcome.
- Usage and safety: at least one provider call occurred. Run-export token usage and cost remain unavailable, so the `80000` boundary cannot be proven from observed usage for this failed run. No plaintext key, cookie, authorization header, raw provider payload, or shell arguments were copied into durable evidence. No product code or external state was changed by this Step 20 attempt.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260713-step20-bounded-success/`, including passing Dry-run evidence, visible pre-run/start screenshots, the terminal-failure DOM capture, preserved sidecar logs, and the redacted `step20-run-verdict.md` / `.json`.
- Step 20 status: still in progress. Next entry: Step 21. Enforce graph-node tool policy before provider dispatch, auto-decline or terminalize undeclared tool calls, reconcile `turn_aborted` by authoritative execution-thread and turn identity, add focused regression coverage, then rerun Step 20 exactly once through the same visible UI path.

### 2026-07-13 - Step 21 no-tools enforcement and aborted-turn reconciliation completed

- Root cause repaired: an empty graph tool policy previously relied on prompt compliance while the provider thread still exposed dynamic tools. Terminal policy tracking also retained the graph turn identity while provider/runtime notifications could report a nested turn id, so authoritative `turn_aborted` events could miss the collector's canonical key.
- Runtime enforcement: graph nodes with no allowed tool classes and no MCP access now use a normalized `no_tools` execution policy. Their thread/turn surfaces omit dynamic tools, use read-only/untrusted permissions, and automatically decline dynamic-tool, command, file-change, approval, MCP elicitation, user-input, patch, and exec requests.
- Fail-closed result: prohibited tool requests and tool-like item notifications create redacted policy events without arguments. A graph node with any such evidence ends as `policy_violated`, even if the provider subsequently emits a completed answer.
- Terminal reconciliation: `turn_aborted`, interrupted, and cancelled status variants normalize to a cancelled terminal state. Nested provider/runtime turn ids are mapped to the canonical strict graph turn before terminal storage, snapshot scheduling, and policy cleanup.
- Compatibility: the existing `patch_only` execution contract remains intact. Its focused fail-closed, approval-decline, and non-compliance regressions passed `3/3`.
- Verification: `tests.test_task_graph_worker_runtime` passed `28/28`; task-graph API/contract/persistence suites passed `17/17`; Python compilation and focused `git diff --check` passed.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260713-step21-no-tools-aborted-turn/step21-no-tools-aborted-turn-repair.md` and `.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no secret source, raw provider payload, authorization material, or external write was used.
- Step 21 status: completed. Next entry: return to Step 20. Through only the in-app browser virtual pointer, require a passing Dry-run, then start exactly one bounded provider-backed run and verify Planner produces no tool calls before evaluating fan-out, join, Synthesizer output, typed artifacts, lane isolation, reconciliation, and the visible `80000` token boundary.

### 2026-07-13 - Step 20 visible rerun exposed direct-run dispatch regression

- Visible execution: using only the in-app browser virtual pointer on current-source sidecar `8851`, retained managed user `astra`, and stayed on `DG Graph Parallel 01 Fresh`.
- Dry-run acceptance: a visible `Dry-run` click created `graph-dry-run-20260713T222847075685-80dc03`, which passed with `11 pass / 0 warning / 0 blocked`. The graph remained the expected five-node, six-edge, three-parallel-group read-only Provider/Model consistency fixture.
- Corrected blocker: subsequent persisted-run inspection proved that the visible `直接运行` path did create a new live run, `graph-run-live-20260713T223558321498-759e2c`, but the task's latest visible run ref was still replaced by a newer dry-run record, `graph-dry-run-20260713T223516368120-8252b0`. The UI therefore surfaced the wrong latest run state even though a live run existed on disk.
- Corrected diagnosis: the immediate defect is no longer “live dispatch created no live run.” It is “the new live run was not preserved/projected as the latest visible run ref, and its terminal result remained mismatched with the task-facing run summary.” Step 20 therefore still cannot produce provider-backed fan-out, join, Synthesizer, typed-artifact, isolation, or observed-usage evidence through visible UI.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260713-step20-no-tools-rerun/`, including preflight/dry-run/direct-run screenshots, DOM captures, and redacted Markdown/JSON verdict files.
- Safety and cost: no new provider-backed graph run started; provider calls `0`, provider tokens `0`, cost `not_applicable_no_live_dispatch`; no plaintext key, cookie, authorization header, or raw provider payload was read or persisted.
- Step 20 status: still in progress.
- Next entry: Step 21. Repair the visible `直接运行` latest-run projection/finalization path so a new bounded `graph-run-live-*` run is surfaced as the latest visible record instead of being replaced by a newer dry-run ref, then return to Step 20.

### 2026-07-13 - Step 21 disclosure reset and compact snapshot strip completed

- User-directed finding: the Dry-run readiness summary still gave too much visual weight to the gray `Nodes: ... pass / ... warning / ... blocked` line, and the top snapshot/state strip could re-open into a noisy multi-chip row after the underlying list changed.
- UI repair: the Dry-run node-count summary now uses a smaller compact meta style. Dry-run reasons and recent snapshot chips both keep the first three items visible by default, ellipsize long chip labels, and reset back to the collapsed state whenever a new result or snapshot list arrives.
- Regression coverage: Desktop `TaskGraphWorkspace.test.tsx` passed `71/71`, including new focused cases that verify the Dry-run reasons disclosure re-collapses on a new result and the snapshot strip re-collapses when the snapshot list changes.
- Visible acceptance: only the in-app browser virtual pointer was used. The managed `astra` session remained active on current-source sidecar `8851`; the task-graph page showed three compact snapshot chips plus an expand control, and the evidence was saved to `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260713-step21-disclosure-density-followup-02/`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no secret source, raw provider payload, authorization material, or external write was used.
- Step 21 status: completed. Next entry: return to the still-open Step 21 latest-run projection/finalization repair for the visible `直接运行` path, then resume Step 20 bounded provider-backed graph evidence.

### 2026-07-13 - Step 21 live-run error payload and latest-run projection repair completed

- Root cause tightened: a visible `直接运行` could create and finalize a failed `graph-run-live-*` record, but the HTTP request still returned only a plain 400 error string. The desktop mutation therefore kept only the error banner and never cached the newest failed `live_run.run_ref` or refreshed `task` state, so the task graph could continue to present the earlier dry-run record as the newest visible run.
- Sidecar repair: live-run failure finalization now attaches a redacted `public_payload` to the raised exception after the failed run has already been persisted. The public error response preserves compact `task`, `graph`, `live_run.run_ref`, `run_status`, and `artifact_paths` without exposing secrets.
- Desktop repair: `api.ts` now throws `ApiRequestError` with parsed structured response data. On task-graph live-run failure, `App.tsx` consumes the structured payload inside `onError`, caches the failed `live_run.run_ref`, updates the project-task cache, refreshes the active graph query, and still surfaces the human-readable failure message.
- Validation: sidecar `test_live_graph_timeout_persists_failed_terminal_state_and_diagnostics` passed with isolated `ASTRABRIDGE_RUNTIME_ROOT=D:\AstraBridge\PRIVATE\tmp-runtime-tests`; desktop `src/api.test.ts` passed `1/1`; desktop `TaskGraphWorkspace.test.tsx` passed `71/71`; desktop `vite build` passed with the existing large-chunk warning.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260713-step21-live-run-error-projection/step21-live-run-error-projection.md`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext key, cookie, authorization header, raw provider payload, or external write was used.
- Step 21 status: completed. Next entry: return to Step 20 and run one bounded visible provider-backed `直接运行` to verify that the newest live-run record now remains the latest visible task-graph run after a real failure or completion.
### 2026-07-13 - Step 21 readiness density tighten completed

- User-directed follow-up: the dry-run readiness summary still gave the gray `Nodes: ...` line too much weight, and there was fresh doubt about whether the recent-snapshot strip was still capped to three visible items.
- UI repair: the readiness summary meta line was tightened again in `styles.css` so the gray node-count summary reads smaller and lighter.
- Current-source verification: the 4181 dev surface is already serving the compact snapshot-strip logic. In-app browser evidence on the active task-graph page recorded exactly three visible snapshot chips with the disclosure control still collapsed (`展开 21`).
- Validation: desktop `TaskGraphWorkspace.test.tsx` passed `71/71`; desktop `vite build` passed with the existing large-chunk warning.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260713-step21-readiness-density-tighten/step21-readiness-density-tighten.md` and `.json`, plus `01-task-graph-current.png` and `snapshot-strip-state.json` in the same directory.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no secret source, cookie, authorization header, raw provider payload, or external write was used.
- Step 21 status: completed. Next entry remains Step 20 visible task-graph live rerun work.

### 2026-07-14 - Step 21 compact preview hardening completed

- User-directed finding: the gray `Nodes: ... pass / ... warning / ... blocked` line still read too large, and the dry-run reasons plus top snapshot strip needed a hard three-item preview cap with explicit disclosure for the remainder.
- UI repair: `TaskGraphWorkspace.tsx` now uses one shared compact-preview constant for dry-run reasons and recent snapshots. The snapshot strip stays collapsed into a single compact row by default, while expanded state can still wrap. `styles.css` further reduces the readiness-summary and readiness-list typography so the gray node-count line reads as secondary metadata.
- Regression coverage: Desktop `TaskGraphWorkspace.test.tsx` passed `71/71`, including focused assertions that the collapsed dry-run reason list renders exactly three entries and the collapsed snapshot strip renders exactly three chips before expansion. Desktop `vite build` passed with the existing large-chunk warning unchanged.
- In-app browser acceptance: the in-app browser was reattached and opened the active AstraBridge dogfood page on sidecar `8850`; the visible `任务图` button was clicked successfully to reopen the task-graph surface. Post-open screenshot and deeper CDP DOM reads then timed out, so this round records `browser_screenshot_channel_failure` rather than a completed visual screenshot. The failure is in the Codex browser-control channel, not in AstraBridge startup or routing.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260714-step21-compact-preview-hardening/step21-compact-preview-hardening.md` and `.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no secret source, raw provider payload, authorization material, or external write was used.
- Step 21 status: completed. Next entry remains Step 20 visible task-graph live rerun work.

### 2026-07-14 - Step 21 three-item preview follow-up completed

- User-directed follow-up: the dry-run `Nodes: ...` gray meta line still felt visually heavy, and both the blocked-reason bullets and recent snapshot chips needed a harder guarantee that only three preview items appear before disclosure.
- UI repair: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx` now routes both dry-run reasons and recent snapshots through a shared `buildDisclosurePreview()` helper. Hidden-count tracking remains stable while expanded, so the disclosure control stays visible and can collapse back cleanly. `apps/astrabridge-desktop/src/styles.css` further tightens the readiness-summary and readiness-list typography.
- Verification: Desktop `TaskGraphWorkspace.test.tsx` passed `71/71`; Desktop `pnpm build` passed with the existing Vite large-chunk warning unchanged.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260714-step21-three-item-preview-followup/step21-three-item-preview-followup.md` and `.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no secret source, raw provider payload, authorization material, or external write was used.
- Step 21 status: completed. Next entry remains Step 20 visible task-graph live rerun work.

### 2026-07-14 - Step 20 visible live rerun 02 narrowed the blocker to direct-run misrouting

- Visible execution: using only the in-app browser virtual controls on the already-open AstraBridge tab, stayed on `DG Graph Parallel 01 Fresh` and clicked the visible `直接运行` button exactly once. The visible token budget remained `80000`, and the snapshot strip stayed at three preview chips plus `展开 21`.
- Visible result: for roughly 18 seconds after the click, the task-graph surface did not render a new latest live-run dock. The visible status remained `dry_run_passed`, with no new live-run id and no visible error banner.
- Disk-backed diagnosis: workspace-local `.astrabridge` state files updated in the click window. The current task record now shows a new newest run, `graph-dry-run-20260714T015441471615-c116e5`, with status `dry_run_passed`; the previous newest live run remains `graph-run-live-20260713T223558321498-759e2c`. No `graph-run-live-20260714*` record was found in the inspected task transcript state.
- Corrected blocker: on the current visible task-graph path, the `直接运行` control is misrouted to dry-run creation rather than live-run dispatch. This is stronger and narrower than the earlier projection-only hypothesis.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260714-step20-visible-live-rerun-02/step20-run-verdict.md` and `.json`, plus `01-pre-state.*`, `02-immediate-post-click-state.*`, and `03-ui-poll-state.json` in the same directory.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable_no_live_dispatch`; no secret source, raw provider payload, authorization material, or external write was used.
- Step 20 status: still in progress.
- Next entry: Step 21. Repair the visible task-graph `直接运行` dispatch path so it creates a bounded `graph-run-live-*` run instead of a new `graph-dry-run-*` run, then return to Step 20 for one more visible rerun.

### 2026-07-14 - Step 20 direct-run misrouting diagnosis superseded by later disk evidence

- The earlier `20260714-step20-visible-live-rerun-02` note was too narrow. Later persisted task-state inspection showed that the same visible click window did create `graph-run-live-20260714T015810993474-10238a`, while the UI still failed to surface that live run promptly.
- The remaining Step 20 blocker should therefore be treated as a live-run visibility/projection or delayed-refresh defect, not a pure dry-run-only misrouting path.
- Next entry remains Step 20: reproduce one bounded visible live run and verify that the newest `graph-run-live-*` record remains the latest visible task-graph run even when a dry-run preflight occurs first.

### 2026-07-14 - Step 21 preview density tighten 02 completed

- User-directed finding: the gray `Nodes: ... pass / ... warning / ... blocked` meta line still read too large, and the dry-run readiness bullets plus recent-snapshot chips needed an explicit `3 visible + disclosure` contract at the screenshot scale.
- UI repair: `apps/astrabridge-desktop/src/styles.css` further reduced the dry-run summary weight and tightened readiness-list typography. `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx` now validates six-item dry-run and snapshot collections, requiring `Show more 3` for both.
- Verification: `node ./node_modules/vitest/vitest.mjs run src/features/runtime/TaskGraphWorkspace.test.tsx` passed `71/71`; `npm.cmd run build` passed with the existing Vite large-chunk warning unchanged.
- In-app browser acceptance: using only the in-app browser virtual controls on the active AstraBridge tab, the current task-graph surface showed exactly three visible snapshot chips and a disclosure control of `展开 21`. The current task state did not expose a dry-run readiness block, so that branch remains test-backed in this round.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260714-step21-preview-density-tighten-02/step21-preview-density-tighten-02.md` and `.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no secret source, raw provider payload, authorization material, or external write was used.
- Step 21 follow-up status: completed. Next entry remains Step 20 visible task-graph live rerun work with the corrected live-run visibility/projection diagnosis.

### 2026-07-14 - Step 20 visible live rerun 03 proved live-run creation but exposed post-Planner state loss

- Visible execution: using only the in-app browser virtual controls on current-source sidecar `8850`, stayed on `DG Graph Parallel 01 Fresh`, opened the visible task graph, confirmed the visible `80000` budget and `3 + 展开 21` snapshot preview, then clicked `直接运行` exactly once.
- Persisted creation: the visible action created dry-run `graph-dry-run-20260714T023235389130-dffa11` and then live run `graph-run-live-20260714T023240586014-a3ffee`. Immediately after the click, the UI showed a latest-run dock for the new live run and disabled `直接运行`.
- Corrected success boundary: the earlier live-dispatch blocker is now closed on sidecar `8850`. The visible `直接运行` path does create a fresh `graph-run-live-*` record after its dry-run preflight.
- New blocker: roughly 90 seconds later, workspace-local state still showed `graph-run-live-20260714T023240586014-a3ffee` as `running`, but the visible latest-run dock had disappeared and `直接运行` was enabled again. Persisted state became internally inconsistent: `tasks.json` reported `latest_event_type = node_completed`, yet the same run still reported `running = 1 / waiting_on_dependencies = 4`, and `run-manifest.json` still left `node_supervisor` at `queued/pending`.
- Runtime evidence: the Planner worker rollout `rollout-2026-07-14T02-33-09-019f5c8a-1d84-7963-84eb-34426c12b696.jsonl` ended with `task_complete` after about `34.7s`, proving that Planner completion was reached in the provider lane but not reconciled back into the graph run coherently.
- Acceptance impact: Step 20 is still not complete. This round does not prove downstream parallel branch execution, artifact handoff, or Synthesizer merge; it narrows the remaining blocker to post-Planner run-state reconciliation, downstream unlock, and stable latest-run dock projection.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260714-step20-visible-live-rerun-03/step20-run-verdict.md` and `.json`, plus `01-pre-state.*`, `02-immediate-post-click-state.*`, and `03-post-poll-state.*`.
- Safety and cost: at least one real provider-backed live run occurred; provider tokens and cost remained `not_available`. No plaintext key, cookie, authorization header, or raw provider payload was read or persisted.
- Step 20 status: still in progress.
- Next entry: Step 21. Repair the Planner-completion reconciliation path so the graph run records completion coherently, unlocks downstream nodes, and keeps the newest live run visible in the task-graph dock while active.

### 2026-07-14 - Step 21 preview density tighten 03 completed

- User-directed finding: the muted dry-run `Nodes: ...` summary still carried too much visual weight, repeated dry-run blockers spammed identical bullet text, and recent snapshots needed to remain hard-capped at three visible chips before disclosure.
- UI repair: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx` now deduplicates repeated dry-run reasons before collapse, keeps the three-item disclosure contract explicit, and removes the visible `Nodes:` prefix while preserving the full text in the tooltip. `apps/astrabridge-desktop/src/styles.css` tightens the muted summary row and adds a compact duplicate counter. `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx` adds a regression test for repeated-reason collapse.
- Verification: `node .\\node_modules\\vitest\\vitest.mjs run src\\features\\runtime\\TaskGraphWorkspace.test.tsx` passed `72/72`. Headless visible capture on sidecar `8850` confirmed the snapshot strip at three visible chips plus `展开 21`; screenshots are saved at `PRIVATE/app-standardization-ui-dogfood/ui/20260714-step21-dryrun-collapse-check.png` and `PRIVATE/app-standardization-ui-dogfood/ui/20260714-step21-dryrun-collapse-taskgraph.png`.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260714-step21-preview-density-tighten-03/step21-preview-density-tighten-03.md` and `.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, cookie, authorization header, or raw provider payload was read or persisted.
- Remaining risk: the current visible session did not expose a live dry-run reasons block, so the repeated-reason branch is test-backed in this round; the runtime-side post-Planner reconciliation defect remains the next execution blocker.
- Step 21 follow-up status: completed. Next entry remains Step 21 runtime reconciliation repair, then return to Step 20 visible live rerun.

### 2026-07-14 - Step 21 preview density tighten 04 completed

- User-directed follow-up: the muted dry-run summary line and collapsed recent-snapshot row still felt visually too large even after the earlier three-item disclosure work.
- UI repair: `apps/astrabridge-desktop/src/styles.css` further reduced the dry-run summary font size, the readiness-list font size, the duplicate-count badge size, the dock meta font size, and the collapsed snapshot chip sizing. The behavior contract stays unchanged: both the dry-run reasons and recent snapshots still default to `3 visible + disclosure`.
- Verification: desktop `pnpm build` passed. The repository `pnpm test -- src/features/runtime/TaskGraphWorkspace.test.tsx` entry still ran the wider suite, but the targeted `src/features/runtime/TaskGraphWorkspace.test.tsx` file itself passed `72/72`. Unrelated pre-existing failures remained in `taskWorkflowFacts.test.ts`, `abilityEntries.test.ts`, and `catalog.test.ts`.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260714-step21-preview-density-tighten-04/step21-preview-density-tighten-04.md` and `.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, authorization material, or external write was used.
- Step 21 follow-up status: completed. Next entry remains Step 21 runtime reconciliation repair, then return to Step 20 visible live rerun.

### 2026-07-14 - Step 21 runtime reconciliation repair completed

- Root cause tightened: the remaining Step 20 blocker came from two persistence drifts. First, `run-manifest.json` only refreshed at live-run start and terminal completion, so Planner completion was not written back mid-run. Second, same-`run_id` compact `graph_run_refs` were merged as additive deltas, allowing stale saves to duplicate worker/artifact arrays or reintroduce stale compact state.
- Sidecar repair: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py` now writes live manifest snapshots immediately after run start, after each node completion snapshot, and again at terminal finalization through one shared helper. `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py` now reconciles same-run compact snapshots by preferring newer sort keys first, using terminal status only as a tie-breaker, selecting timeline/object arrays as authoritative snapshots instead of blind unions, and preserving aggregate `worker_count` when detail arrays are absent.
- Regression coverage: `apps/astrabridge-sidecar/tests/test_task_graph_worker_runtime.py` now proves the live manifest already records Planner completion before downstream branch workers start. `apps/astrabridge-sidecar/tests/test_task_graph_task_persistence.py` now proves a stale same-timestamp save preserves the richer compact live-run snapshot rather than degrading it.
- Verification: with `ASTRABRIDGE_RUNTIME_ROOT=D:\AstraBridge\.tmp\runtime-test-step21`, `python -m unittest -v apps.astrabridge-sidecar.tests.test_task_graph_worker_runtime apps.astrabridge-sidecar.tests.test_task_graph_task_persistence` passed `33/33`.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260714-step21-runtime-reconciliation-repair/step21-runtime-reconciliation-repair.md` and `.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, authorization material, or external write was used.
- Step 21 status: completed. Next entry: return to Step 20 and run one bounded visible task-graph live rerun through the in-app browser to verify the repaired persistence path survives the real UI workflow.

### 2026-07-14 - Step 21 preview density tighten 05 completed

- User-directed follow-up: the muted dry-run summary line still felt too prominent at screenshot scale, and the current visible graph needed another direct in-app check that recent snapshots stay capped at three visible chips before disclosure.
- UI repair: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx` now keeps the full dry-run reason text in a hover title while rendering the duplicate marker as compact ASCII `xN`. `apps/astrabridge-desktop/src/styles.css` further reduces the muted summary, readiness-list, duplicate-count, and collapsed snapshot-chip sizing while keeping the same disclosure behavior contract.
- Verification: `node .\\node_modules\\vitest\\vitest.mjs run src\\features\\runtime\\TaskGraphWorkspace.test.tsx` passed `72/72`; `node .\\node_modules\\typescript\\bin\\tsc --noEmit` passed.
- In-app browser acceptance: using only the in-app browser bridge and virtual page controls, the current AstraBridge task-graph tab showed exactly three recent-snapshot chips plus `展开 21`. The current dry-run state was `pass 11 / 0 / 0`, so the blocked-reason collapsed branch remained test-backed rather than visibly reproduced in this round.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260714-step21-preview-density-tighten-05/step21-preview-density-tighten-05.md` and `.json`, plus `taskgraph-snapshot-preview.png`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, authorization material, or external write was used.
- Step 21 follow-up status: completed. Next entry remains Step 20 visible task-graph live rerun work with the runtime reconciliation repair already in place.

### 2026-07-14 - Step 20 visible live rerun 05 narrowed the current blocker back to direct-run dry-run-only dispatch

- Visible execution: through only the claimed in-app browser tab on current-source sidecar `8851`, stayed on `DG Graph Parallel 01 Fresh`, confirmed the correct task-graph surface (`返回对话`, `直接运行`, `Dry-run`, `展开 21`, managed `astra` session), captured pre-action evidence, and clicked the visible `直接运行` button exactly once.
- Visible result: neither the immediate nor 12-second delayed post-click UI showed a new live-run dock, running state, disabled direct-run control, or fresh graph-run identifier. The canvas continued to display the prior all-pass graph state.
- Disk-backed result: the same click window created only `graph-dry-run-20260714T040927835810-1eae86`. `tasks.json` updated the task's `latest_run_id` to that new dry-run and `latest_run_status` to `dry_run_passed`. No new `graph-run-live-20260714T04*` directory or task-state record was created; the newest live-run directory remains the older `graph-run-live-20260714T023240586014-a3ffee`.
- Corrected blocker: on the current visible `8851` surface, the user-visible `直接运行` control has regressed to a dry-run-only path again. This is stronger than a mere visibility/projection fault: the live run itself was not dispatched.
- Acceptance impact: Step 20 remains incomplete. This round does not prove a fresh provider-backed rerun, Planner persistence on that rerun, downstream fan-out unlock, or Synthesizer merge.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260714-step20-visible-live-rerun-05/step20-run-verdict.md` and `.json`, plus `01-pre-state.*`, `02-immediate-post-click.*`, and `03-delayed-post-click.*`.
- Safety and cost: provider-backed live dispatches `0`, dry-runs `1`, provider tokens `0`, cost `not_applicable_no_live_dispatch`; no plaintext secret source, cookie, authorization header, or raw provider payload was read or persisted.
- Step 20 status: still in progress and concretely blocked on current-source direct-run dispatch.
- Next entry: Step 21. Repair the current-source task-graph direct-run control so a visible `直接运行` click on `8851` dispatches a fresh `graph-run-live-*` run after its dry-run preflight, then return to Step 20 for one more bounded visible rerun.
### 2026-07-14 - Step 21 task-graph disclosure density 01 completed

- User-directed follow-up: the muted dry-run summary still read too large in screenshots, and the task-graph disclosure surfaces needed to remain obviously bounded at `3 visible + disclosure`.
- UI repair: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx` now centralizes the dry-run summary tooltip text without the heavier visible `Nodes:` phrasing. `apps/astrabridge-desktop/src/styles.css` further reduces the dry-run summary font size, readiness-list typography, duplicate-count size, disclosure-button footprint, and collapsed snapshot-chip density.
- Verification: `node .\\node_modules\\vitest\\vitest.mjs run src\\features\\runtime\\TaskGraphWorkspace.test.tsx` passed `72/72`; `node .\\node_modules\\typescript\\bin\\tsc --noEmit` passed.
- In-app browser acceptance: using only the in-app browser bridge on the claimed AstraBridge tab, the current task-graph surface on sidecar `8851` remained visibly collapsed at `还有 3 条` for recent snapshots. The current graph did not expose a blocked dry-run reasons panel, so that branch is test-backed rather than visibly reproduced in this round.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260714-step21-taskgraph-disclosure-density-01/step21-taskgraph-disclosure-density-01.md` and `.json`, plus `taskgraph-disclosure-density.png` and `taskgraph-disclosure-density-dom.txt`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, cookie, authorization header, or raw provider payload was read or persisted.
- Step 21 follow-up status: completed.
- Next entry: Step 21. Repair the current-source task-graph direct-run control so a visible `直接运行` click on `8851` dispatches a fresh `graph-run-live-*` run after its dry-run preflight, then return to Step 20 for one more bounded visible rerun.

### 2026-07-14 - Step 21 task-graph disclosure density 02 completed

- User-directed follow-up: the muted dry-run summary line still felt too large, and both the dry-run reasons list plus recent-snapshot strip needed to stay on a strict `3 visible + collapse the rest` rule.
- UI repair: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx` now uses compact remaining-count disclosure labels (`还有 N 条` / `N more`) for both surfaces while keeping the three-item preview cap intact. `apps/astrabridge-desktop/src/styles.css` further reduces the dry-run summary, readiness list, duplicate counter, disclosure button, snapshot label, and snapshot chip footprint.
- Verification: `node .\\node_modules\\vitest\\vitest.mjs run src\\features\\runtime\\TaskGraphWorkspace.test.tsx` passed `72/72`; `node .\\node_modules\\typescript\\bin\\tsc --noEmit` passed.
- In-app browser acceptance: using only the in-app browser bridge on the claimed AstraBridge tab for sidecar `8851`, reloaded the page, opened `任务图`, and verified by DOM plus screenshot that the recent-snapshot strip renders exactly `3` chips with the remainder collapsed behind `还有 3 条`. The current visible graph state did not expose a blocked dry-run reasons panel, so that branch remained test-backed in this round.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260714-step21-taskgraph-disclosure-density-02/step21-taskgraph-disclosure-density-02.md` and `.json`, plus `taskgraph-disclosure-density-02.png` and `taskgraph-disclosure-density-02-dom.txt`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, authorization material, or external write was used.
- Step 21 follow-up status: completed.
- Next entry remains Step 21: repair the current-source task-graph direct-run control so a visible `直接运行` click on `8851` dispatches a fresh `graph-run-live-*` run after its dry-run preflight, then return to Step 20 for one more bounded visible rerun.
### 2026-07-14 - Step 21 task-graph disclosure density 03 completed

- User-directed follow-up: the muted dry-run summary line still looked visually too large, and both the dry-run reasons list plus recent-snapshot strip needed to remain obviously bounded at `3 visible + disclosure`.
- UI repair: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx` now marks the dry-run reasons list as expanded or collapsed so typography can differ by state. `apps/astrabridge-desktop/src/styles.css` further reduces the muted summary weight, tightens dry-run reason spacing, clamps collapsed dry-run rows to one visible line, and reduces recent-snapshot label, chip, and disclosure sizing.
- Verification: `node .\\node_modules\\vitest\\vitest.mjs run src\\features\\runtime\\TaskGraphWorkspace.test.tsx` passed `72/72`; `node .\\node_modules\\typescript\\bin\\tsc --noEmit` passed.
- In-app browser acceptance: using only the in-app browser bridge on the claimed AstraBridge tab for sidecar `8851`, verified by fresh screenshot that the current recent-snapshot strip renders exactly `3` visible chips and collapses the remainder behind `3 more`. The current visible graph state still did not expose a blocked dry-run reasons panel, so that branch remained test-backed in this round rather than visibly reproduced.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260714-step21-taskgraph-disclosure-density-03/step21-taskgraph-disclosure-density-03.md` and `.json`, plus `taskgraph-disclosure-density-03.png`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, authorization material, or external write was used.
- Step 21 follow-up status: completed.
- Next entry remains Step 21: repair the current-source task-graph direct-run control so a visible `direct run` click on `8851` dispatches a fresh `graph-run-live-*` run after its dry-run preflight, then return to Step 20 for one more bounded visible rerun.

### 2026-07-14 - Step 21 direct-run dispatch fallback repair completed

- Root cause boundary for this round: the static desktop toolbar wiring already points `task-graph-run-live` at `onRunLive`, but the current-source `8851` evidence still showed an occasional dry-run-only outcome. The remaining desktop-side gap was that the client had no bounded recovery path when a successful dry-run result appeared while the active user intent was still `live`.
- Desktop repair: `apps/astrabridge-desktop/src/features/runtime/taskGraphRunDispatch.ts` now centralizes the fallback-promotion rule. `apps/astrabridge-desktop/src/App.tsx` now records explicit `dry_run` vs `live` intent for task-graph toolbar actions and, when a `pass` dry-run arrives while the active intent is still `live`, immediately dispatches one bounded live run for the same graph and token budget before clearing the intent. The fallback is one-shot and cannot loop.
- Regression coverage: `apps/astrabridge-desktop/src/features/runtime/taskGraphRunDispatch.test.ts` proves when promotion is allowed or denied, and `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx` now proves the visible live toolbar button does not call the dry-run callback.
- Verification: `node .\\node_modules\\vitest\\vitest.mjs run src\\features\\runtime\\TaskGraphWorkspace.test.tsx src\\features\\runtime\\taskGraphRunDispatch.test.ts` passed `77/77`; `node .\\node_modules\\typescript\\bin\\tsc --noEmit` passed.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260714-step21-direct-run-dispatch-fallback-repair/step21-direct-run-dispatch-fallback-repair.md` and `.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, authorization material, or external write was used.
- Step 21 status: completed.
- Next entry: return to Step 20 and rerun the visible `direct run` path on current-source sidecar `8851` through the in-app browser to confirm a fresh `graph-run-live-*` record is created and kept visible.

### 2026-07-14 - Step 20 visible live rerun 06 closed the dry-run-only regression and exposed stale latest-run projection

- Visible execution: through the in-app browser page bridge on current-source sidecar `8851`, recovered the `DG Graph Parallel 01 Fresh` task workspace, reopened `任务图`, captured pre-action evidence, and clicked the visible `direct run` button exactly once.
- Runtime result: the same click window created dry-run `graph-dry-run-20260714T053635798502-73e0a8` and fresh live run `graph-run-live-20260714T053643563390-853cb0`. Runtime events then recorded `graph_worker_started` for `node_supervisor`, proving that provider-backed live execution really began on `8851`.
- Corrected boundary: the earlier `direct run only creates dry-run` blocker is now closed on current-source `8851`.
- New blocker: the visible latest-run panel remained pinned to the older dry-run projection (`graph-dry-run-...1eae86 / DRY_RUN_PASSED`) even though the current task's `graph_activity_summary.latest_run_id` already moved to the new running `graph-run-live-20260714T053643563390-853cb0`. The top-level task fields still stayed `latest_run_id = null` and `latest_run_status = null`, which points to a stale latest-run projection or selection-state merge rather than a dispatch failure.
- Acceptance impact: Step 20 is still in progress. This round does not yet prove that the visible task-graph dock selects and keeps showing the fresh live run, nor does it prove downstream branch unlock or Synthesizer completion on that fresh rerun.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260714-step20-visible-live-rerun-06/step20-run-verdict.md` and `.json`, plus `01-pre-state.*`, `02-immediate-post-click.*`, and `03-delayed-post-click.*`.
- Safety and cost: provider-backed live dispatches `1`, dry-runs `1`, provider tokens `not_available`, cost `not_available`; no plaintext secret source, cookie, authorization header, or raw provider payload was read or persisted.
- Step 20 status: still in progress, but the blocker has narrowed from dispatch failure to stale latest-run projection on the visible task-graph surface.
- Next entry: Step 21. Repair the current-source task-graph latest-run projection so the visible dock prefers the fresh `graph-run-live-*` record over the older dry-run entry, then return to Step 20 for one more bounded visible rerun.

### 2026-07-14 - Step 21 task-graph disclosure density 04 completed

- User-directed follow-up: the muted dry-run summary row still looked visually too large in screenshots, and the user asked both the dry-run reasons block plus the recent snapshot strip to stay on a strict `3 visible + disclosure` contract.
- UI repair: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx` now keeps the full dry-run wording in the tooltip while reducing the visible muted summary to compact counts only. `apps/astrabridge-desktop/src/styles.css` further reduces the dry-run summary emphasis and tightens the recent snapshot strip width.
- Regression coverage: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx` now asserts the compact visible summary while preserving the three-item disclosure contract for dry-run reasons and recent snapshots.
- Verification: `node .\\node_modules\\vitest\\vitest.mjs run src\\features\\runtime\\TaskGraphWorkspace.test.tsx` passed `73/73`; `node .\\node_modules\\typescript\\bin\\tsc --noEmit` passed.
- In-app browser acceptance: using only the in-app browser bridge on the claimed AstraBridge tab for sidecar `8851`, reloaded the current task, reopened `任务图`, and verified by DOM plus screenshot that the recent snapshot strip renders exactly `3` visible chips with the remainder collapsed behind `还有 21 条`. The current visible graph state did not expose a blocked dry-run reasons panel, so that branch remained test-backed in this round.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260714-step21-taskgraph-disclosure-density-04/step21-taskgraph-disclosure-density-04.md` and `.json`, plus `taskgraph-disclosure-density-04.png` and `taskgraph-disclosure-density-04-dom.txt`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, cookie, or authorization material was read or persisted.
- Step 21 follow-up status: completed.
- Next entry remains the runtime line: repair the stale task-graph latest-run projection, then return to Step 20 for one bounded visible live rerun.

### 2026-07-14 - Step 21 latest-run projection repair completed

- Runtime boundary for this round: after visible rerun 06, direct-run dispatch was already fixed, but the task-graph dock could still remain pinned to stale dry-run entries while the fresh live run was between user click and the first authoritative live `run_ref`.
- Desktop repair: `apps/astrabridge-desktop/src/features/runtime/taskGraphRunRefs.ts` now exposes `selectCurrentTaskGraphRunRef(...)` for the real latest-run selection chain plus `createOptimisticTaskGraphLiveRunRef(...)` for one bounded optimistic running ref. `apps/astrabridge-desktop/src/App.tsx` now primes that optimistic live ref on visible live-run request and on the dry-run-to-live fallback promotion path, clears it when a real live `run_ref` arrives or the live request fails, and routes `currentTaskGraphRunRef` through the new shared helper.
- Regression coverage: `apps/astrabridge-desktop/src/features/runtime/taskGraphRunRefs.test.ts` now proves an optimistic live ref outranks stale dry-run query refs for the same graph while keeping dry-run fallback behavior covered when no live refs exist.
- Verification: `node .\\node_modules\\vitest\\vitest.mjs run src\\features\\runtime\\taskGraphRunRefs.test.ts src\\features\\runtime\\taskGraphRunDispatch.test.ts src\\features\\runtime\\TaskGraphWorkspace.test.tsx` passed `86/86`; `node .\\node_modules\\typescript\\bin\\tsc --noEmit` passed.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260714-step21-latest-run-projection-repair/step21-latest-run-projection-repair.md` and `.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, cookie, or authorization material was read or persisted.
- Step 21 status: completed.
- Next entry: return to Step 20 and run one bounded visible live task-graph rerun through the in-app browser to verify the dock now stays on the fresh live run instead of the stale dry-run projection.

### 2026-07-14 - Step 21 task-graph disclosure density 06 completed

- User-directed follow-up: the muted dry-run summary still read too large in the screenshot, and both the dry-run detail bullets plus the recent-snapshot strip needed to stay at `3 visible + disclosure`.
- UI repair: `apps/astrabridge-desktop/src/styles.css` further reduces the muted dry-run summary typography and the dry-run reason/count typography. `apps/astrabridge-desktop/src/App.tsx` now applies the same disclosure pattern to manager `Latest results`, showing three rows by default with explicit expand/collapse for the remainder. The task-graph disclosure logic remains capped at three visible items.
- Verification: `node .\\node_modules\\vitest\\vitest.mjs run src\\features\\runtime\\TaskGraphWorkspace.test.tsx` passed `73/73`; `node .\\node_modules\\typescript\\bin\\tsc --noEmit` passed.
- In-app browser acceptance: using only the in-app browser page bridge, reopened `Provider Switch Live 20260622-224524`, re-entered `DG Graph Parallel 01 Fresh -> 任务图`, and verified from the live DOM that `最近快照` still renders exactly `3` listitems followed by `还有 21 条`. The current live graph dry-run produced `11 / 0 / 0` with `没有阻塞或警告`, so the blocked-reason list from the earlier screenshot did not reappear in this session and remains regression-backed.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260714-step21-taskgraph-disclosure-density-06/step21-taskgraph-disclosure-density-06.md` and `.json`, plus `taskgraph-disclosure-density-06.png` and `taskgraph-disclosure-density-06-dom.txt`.
- Safety and cost: provider live runs `0`, dry-runs `1`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, cookie, authorization header, or raw provider payload was read or persisted.
- Step 21 follow-up status: completed.
- Next entry: return to Step 20 and run one bounded visible live task-graph rerun through the in-app browser to verify the dock now stays on the fresh live run instead of the stale dry-run projection.

### 2026-07-14 - Step 20 visible live rerun 09 verified latest-run projection on `8851`

- Visible execution path: using only the in-app browser page bridge, returned to `Provider Switch Live 20260622-224524 -> DG Graph Parallel 01 Fresh -> 任务图`, captured pre-run evidence, and triggered exactly one visible `直接运行` click from the clean canvas state.
- Immediate UI result: the task-graph dock switched to a fresh optimistic live slot (`running`, `0 个 worker / 0 个产物`, truncated `optimistic-liv...`) instead of reverting to the stale dry-run record. This closes the older stale-dry-run projection symptom for the direct-run preflight window.
- Authoritative runtime confirmation: workspace task state under `PRIVATE/demo-runs/provider-switch-live-20260622-224524/workspace/.astrabridge/tasks.json` now records `latest_run_id = graph-run-live-20260714T063002850207-241158` and `latest_run_status = running`, and the corresponding live-run artifact directory was created under `PRIVATE/task-graph/live-run/graph-run-live-20260714T063002850207-241158/`.
- Post-sync visible result: a later capture from the same visible tab shows the dock no longer on the optimistic placeholder. It now displays the real live slot as `最近一次运行 running 1 个 worker / 2 个产物` with the truncated authoritative run id `graph-run-live...241158`. This proves the UI eventually resolves from optimistic live state to the authoritative live run instead of snapping back to the stale dry-run.
- Acceptance impact: the specific projection objective for this slice is met, but Step 20 remains in progress because this round does not yet prove downstream unlock, terminal collection, Synthesizer completion, or final artifact hydration for the new run.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260714-step20-visible-live-rerun-09/step20-run-verdict.md` and `.json`, plus `01-pre-state.*`, `02-immediate-post-click.*`, `03-delayed-post-click.*`, and `04-post-authoritative-run.*`.
- Safety and cost: provider-backed direct-run clicks `1`; no plaintext secret source, cookie, authorization header, or raw provider payload was read or persisted. Provider token usage and cost remain unavailable from the visible surface for this slice.
- Step 20 status: still in progress.
- Next entry: continue the same visible `graph-run-live-20260714T063002850207-241158` execution and determine whether downstream unlock, worker-output hydration, and terminal collection complete cleanly.

### 2026-07-14 - Step 21 task-graph disclosure density 07 completed

- User-directed follow-up: the grey task-graph summary copy still read too large, and the snapshot strip needed a visible acceptance record proving it stayed at `3 visible + disclosure`.
- UI repair: `apps/astrabridge-desktop/src/styles.css` further compresses the dry-run muted summary, dry-run bullet list, disclosure control, snapshot label, snapshot chip, and snapshot toggle typography so those secondary surfaces stop competing with the canvas.
- Verification: `node .\\node_modules\\vitest\\vitest.mjs run src\\features\\runtime\\TaskGraphWorkspace.test.tsx` passed `73/73`; `node .\\node_modules\\typescript\\bin\\tsc --noEmit` passed.
- In-app browser acceptance: using only the in-app browser page bridge on the selected AstraBridge tab for sidecar `8851`, captured the live task-graph canvas and verified by DOM that the recent snapshot strip renders exactly `3` visible chips with `aria-expanded=\"false\"` and the disclosure copy `还有 21 条`.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260714-step21-taskgraph-disclosure-density-07/step21-taskgraph-disclosure-density-07.md`, `taskgraph-disclosure-density-07.json`, and `taskgraph-disclosure-density-07.png`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, cookie, or authorization material was read or persisted.
- Step 21 follow-up status: completed.
- Next entry remains the runtime line: continue the same visible `graph-run-live-20260714T063002850207-241158` execution and determine whether downstream unlock, worker-output hydration, and terminal collection complete cleanly.

### 2026-07-14 - Step 21 task-graph disclosure density 08 completed

- User-directed follow-up: the gray task-graph meta line still read too large, and both the dry-run blocker list plus the recent-snapshot strip needed to re-collapse to `3 visible + disclosure` whenever a fresh run arrives, even if the visible text stays the same.
- UI repair: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx` now resets the dry-run disclosure when a new dry-run `run_id` arrives and resets the snapshot disclosure when the latest visible run changes, so stale expanded state cannot spill into the next screenshot. `apps/astrabridge-desktop/src/styles.css` further reduces the muted summary weight and tightens the secondary snapshot-strip typography.
- Regression coverage: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx` now proves both re-collapse cases: same-reason new dry-run runs and same-snapshot-list new latest runs.
- Verification: `node .\\node_modules\\vitest\\vitest.mjs run src\\features\\runtime\\TaskGraphWorkspace.test.tsx` passed `75/75`.
- In-app browser acceptance: the in-app browser bridge reattached to the selected AstraBridge tab on sidecar `8851` and reloaded successfully, but the session landed on the launcher `新建项目` page. A virtual-pointer click on the recent-project entry did not transition back into the visible task-graph workspace during this round, so the repaired disclosure surfaces remain test-verified here and still need one fresh task-graph screenshot on re-entry.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260714-step21-taskgraph-disclosure-density-08/step21-taskgraph-disclosure-density-08.md` and `.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, cookie, or authorization material was read or persisted.
- Step 21 follow-up status: completed.
- Next entry: return to Step 20 by re-entering the visible task-graph session from the launcher-attached `8851` tab, verify the repaired three-item preview behavior there, then continue the same `graph-run-live-20260714T063002850207-241158` run-state validation.

### 2026-07-14 - Step 20 visible live rerun 10 completed with authoritative failed-run alignment

- Browser/session recovery: the launcher-attached `8851` sidecar was no longer healthy (`/health` timed out) even though the `4181` frontend still rendered. A healthy current-source sidecar was available on `8839`, so the same visible in-app browser tab was switched to `?sidecar=http://127.0.0.1:8839` and reused without falling back to hidden API task execution.
- Visible re-entry: using only the in-app browser virtual-pointer and DOM-CUA path, the operator returned to `Provider Switch Live 20260622-224524`, reopened `DG Graph Parallel 01 Fresh`, and re-entered the task-graph canvas.
- Visible acceptance on the repaired canvas: the compact disclosure contract now holds on the real task-graph surface, not just in tests. Recent snapshots expose exactly three visible chips and collapse the remainder behind `还有 21 条`. The screenshot and DOM capture are preserved under `06-task-graph-visible-8839.*`.
- Visible run inspection: the recovered `8839` session now shows the authoritative latest run instead of the stale `/api/task-graphs/run` timeout banner. `运行检查` reports `最近一次运行 failed`, `4 个 worker / 14 个产物`, run-id fragment `graph-run-live...207-241158`, `时间线 21`, and `更新 2026/7/14 06:43:02`. This aligns with the run artifacts already on disk.
- Authoritative runtime result: `PRIVATE/demo-runs/provider-switch-live-20260622-224524/workspace/PRIVATE/task-graph/live-run/graph-run-live-20260714T063002850207-241158/report.md`, `summary.json`, and `run-export.json` confirm that Planner and API Auditor completed, downstream branches unlocked, Docs Auditor and UI Wording Auditor later failed, Synthesizer remained blocked, and the terminal defect is `terminal_collection_timeout` / `Timed out waiting for app-server response: thread/read` with `safe_to_resume = false`.
- Acceptance impact: Step 20 is now complete as a numbered execution step with concrete findings. The required visible bounded graph run, lane isolation/handoff evidence, compact disclosure repair, and latest-run projection repair have all been exercised through the real UI. Remaining work belongs to Step 21 runtime repair: terminal collection, failed-branch reconciliation, and any residual failed-run projection drift.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260714-step20-visible-live-rerun-10/step20-run-verdict.md`, `.json`, `06-task-graph-visible-8839.png`, `06-task-graph-visible-8839-dom.txt`, `07-run-inspection-visible-8839.png`, and `07-run-inspection-visible-8839-dom.txt`.
- Safety and cost: no plaintext secret source, raw provider payload, cookie, or authorization material was read or persisted. No external writeback occurred. Provider token usage and cost remain unavailable from the authoritative app-server artifacts for this run.
- Next entry: return to Step 21 and repair the remaining terminal-collection and failed-branch reconciliation defects exposed by `graph-run-live-20260714T063002850207-241158`, then rerun the bounded visible task graph once on a healthy current-source sidecar.

### 2026-07-14 - Step 21 task-graph disclosure density 09 completed

- User-directed follow-up: the grey `run check` copy still read too large in screenshots, and the task-graph dry-run findings plus recent-snapshot strip still had to stay on the explicit `3 visible + disclosure` contract.
- UI repair: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx` now normalizes whitespace and punctuation spacing before dry-run finding deduplication, so repeated runtime/provider findings cannot spill into extra preview rows just because their spacing differs. `apps/astrabridge-desktop/src/styles.css` further reduces the visual weight of task-graph secondary grey copy, including the dock summary meta, dry-run summary, dry-run count pills, disclosure control, snapshot label, and snapshot chip meta.
- Regression coverage: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx` now proves whitespace-variant repeated dry-run findings still collapse to a single visible row with `x3`, while the collapsed preview remains capped at three visible rows.
- Verification: `node.exe node_modules/vitest/vitest.mjs run src/features/runtime/TaskGraphWorkspace.test.tsx` passed `76/76`; `node.exe node_modules/typescript/bin/tsc --noEmit` passed.
- In-app browser acceptance: using only the in-app browser virtual pointer and DOM-CUA on sidecar `8839`, re-entered `Provider Switch Live 20260622-224524 -> DG Graph Parallel 01 Fresh -> 任务图` and captured fresh visible evidence. The current task-graph surface again shows the recent-snapshot strip collapsed behind a disclosure after three visible items; the earlier crowded dry-run blocker branch does not currently re-render on this recovered run, so that branch is test-backed in this slice after the whitespace-dedup hardening.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260714-step21-taskgraph-disclosure-density-09/step21-taskgraph-disclosure-density-09.md`, `.json`, `taskgraph-disclosure-density-09.png`, and `taskgraph-disclosure-density-09-dom.txt`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, cookie, or authorization material was read or persisted.
- Step 21 follow-up status: completed.
- Next entry remains the runtime line: repair the remaining terminal-collection and failed-branch reconciliation defects exposed by `graph-run-live-20260714T063002850207-241158`, keep failed-run projection aligned with authoritative runtime status, then rerun the bounded visible task graph once on a healthy current-source sidecar.

### 2026-07-14 - Step 21 runtime terminal read fallback 01 completed

- Runtime defect focus: the remaining failed live graph run had already observed downstream unlock and later terminal notifications, but `_wait_for_probe_turn_terminal(...)` still surfaced `thread/read` timeouts immediately when the final collection pass failed, so the run could not reuse the already-observed terminal signal plus the latest thread snapshot.
- Runtime repair: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py` now catches `thread/read` failures inside `_wait_for_probe_turn_terminal(...)`, checks for a terminal notification, and attempts reconciliation against either the latest successful thread snapshot or a cached native thread snapshot. When that reconciled snapshot proves terminal failure/cancel or preserves completed final text, the helper returns the reconciled terminal thread instead of propagating the read error. Timeout diagnostics now also persist the last `thread_read_error_type` and `thread_read_error_message`.
- Regression coverage: `apps/astrabridge-sidecar/tests/test_task_graph_worker_runtime.py` now adds `test_wait_for_probe_turn_terminal_recovers_after_thread_read_timeout_when_terminal_notification_exists`, proving the helper can recover a completed worker result after `turn/completed` has already arrived and every subsequent `thread/read` attempt times out. Existing terminal-notification reconciliation, aborted-turn cancellation, and failed-timeout persistence tests still pass in the same focused run.
- Verification: with `ASTRABRIDGE_RUNTIME_ROOT=D:\\AstraBridge\\PRIVATE\\test-runtime-root` to avoid the host `D:\\AstraBridgeRuntime` permission blocker, `python.exe -m unittest -v tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_wait_for_probe_turn_terminal_recovers_after_thread_read_timeout_when_terminal_notification_exists tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_terminal_notification_reconciles_nested_turn_id_with_stale_thread_projection tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_live_graph_timeout_persists_failed_terminal_state_and_diagnostics tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_turn_aborted_notification_reconciles_as_cancelled_terminal` passed `4/4`.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260714-step21-runtime-terminal-read-fallback-01/step21-runtime-terminal-read-fallback-01.md` and `.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was used.
- Step 21 follow-up status: completed.
- Next entry: rerun one bounded visible task-graph live session on the healthy current-source sidecar and verify whether the repaired terminal-notification fallback eliminates or narrows the earlier `thread/read` terminal-collection failure for the real graph path.

### 2026-07-14 - Step 21 task-graph disclosure density 10 completed

- User-directed follow-up: the grey `Nodes` / snapshot-strip meta still looked oversized, and the visible recent-snapshot strip still needed a fresh acceptance record proving it stayed at `3 visible + disclosure`.
- UI repair: `apps/astrabridge-desktop/src/styles.css` further reduces the visual weight of task-graph secondary disclosure surfaces, including the dry-run readiness summary, dry-run reason rows, disclosure control, inline grey meta pills, and recent-snapshot label/chip sizing.
- Verification: `node .\\node_modules\\vitest\\vitest.mjs run .\\src\\features\\runtime\\TaskGraphWorkspace.test.tsx` passed `76/76`; `node .\\node_modules\\typescript\\bin\\tsc --noEmit` passed.
- In-app browser acceptance: using only the in-app browser bridge and virtual pointer / DOM-CUA on sidecar `8850`, the visible recent-snapshot strip renders exactly three chips followed by the disclosure copy `还有 21 条`. The current recovered page state did not re-render the earlier blocked dry-run findings branch, so that branch remains regression-backed in this slice rather than freshly screenshot-reproduced.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260714-step21-taskgraph-disclosure-density-10/step21-taskgraph-disclosure-density-10.md` and `.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was used.
- Step 21 follow-up status: completed.
- Next entry remains the runtime line: rerun one bounded visible task-graph live session on the healthy current-source sidecar and verify whether the repaired terminal-notification fallback narrows or removes the earlier `thread/read` terminal-collection failure.

### 2026-07-14 - Step 21 task-graph disclosure density 11 completed

- User-directed follow-up: the task-graph disclosure controls still needed to read smaller and more compactly, and both the dry-run findings plus the recent-snapshot strip had to keep the `3 visible + disclosure` contract without long secondary button copy.
- UI repair: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx` now renders collapsed disclosure copy as compact `+N` text while preserving the fuller accessibility label, and normalizes the snapshot tooltip separator to plain ASCII. `apps/astrabridge-desktop/src/styles.css` further tightens the dry-run summary, dry-run findings list, repeated-count badge, disclosure button, snapshot label, and snapshot chip typography.
- Verification: `node .\\node_modules\\vitest\\vitest.mjs run .\\src\\features\\runtime\\TaskGraphWorkspace.test.tsx` passed `76/76`; `node .\\node_modules\\typescript\\bin\\tsc --noEmit -p .\\apps\\astrabridge-desktop\\tsconfig.json` passed.
- In-app browser acceptance attempt: the requested in-app browser bridge was reconnected and the browser documentation path completed, but the next tab/open step failed with `Timed out waiting for the Browser webview to attach for this browser-use page`. This slice is therefore code-and-test verified, with visible acceptance still pending on the browser bridge rather than on AstraBridge rendering.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260714-step21-taskgraph-disclosure-density-11/step21-taskgraph-disclosure-density-11.md` and `.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was used.
- Step 21 follow-up status: completed.
- Next entry remains the runtime line: once the browser reattaches cleanly, confirm this three-item compact disclosure pass on the visible task-graph surface, then continue the bounded live rerun for the terminal-notification fallback.

### 2026-07-14 - Step 21 status-notice preview 12 completed

- User-directed follow-up: secondary gray warning copy and notice stacks still consumed too much visual weight, and the app-level warning/attention surfaces needed the same `3 visible + disclosure` contract already enforced inside the task graph.
- UI repair: `apps/astrabridge-desktop/src/App.tsx` now applies a shared three-item preview rule to `ConversationNoticeBar` and `RuntimeAttentionPanel`. The collapsed conversation notice stack keeps the highest-severity item first, then shows at most two more before disclosure; the runtime attention panel now previews up to three items before its expand control. `apps/astrabridge-desktop/src/styles.css` further tightens conversation-notice typography, spacing, and toggle chrome so those secondary warnings stop overpowering the main workspace.
- Verification: `node .\\node_modules\\typescript\\bin\\tsc --noEmit` passed from `apps\\astrabridge-desktop`.
- In-app browser acceptance attempt: the browser reattached and refreshed successfully, but the refreshed surface fell back to the launcher `新建项目` page instead of reopening the active task-graph workspace. A visible click attempt on the recent-project entry did not recover the task-graph screen within this round, so this slice is code-verified and still needs one fresh visible task-graph screenshot after re-entry.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: completed.
- Next entry remains the runtime line: re-enter the visible task-graph workspace on a healthy current-source sidecar, capture one fresh screenshot for the three-item notice/disclosure pass, then continue the bounded live rerun and terminal-collection validation.

### 2026-07-14 - Step 21 launcher sidecar gate 13 completed

- Blocking observation: after refresh, the browser fell back to the launcher while the chosen sidecar was unhealthy. The launcher still exposed recent-project and create/open entry points, and the failure copy could degrade to raw `Failed to fetch`.
- UI repair: `apps/astrabridge-desktop/src/App.tsx` now runs a launcher health query and gates recent-project open plus create/open actions while the sidecar is pending or unavailable. `apps/astrabridge-desktop/src/features/navigation/launcherSidecarGate.ts` normalizes raw fetch and `/health` timeout failures into user-facing copy. `apps/astrabridge-desktop/src/features/navigation/RecentProjectButton.tsx` now supports a disabled state, with regression coverage in `RecentProjectButton.test.tsx`; `launcherSidecarGate.test.ts` covers the copy normalization path. `apps/astrabridge-desktop/src/styles.css` adds disabled recent-project styling and compact launcher-gate spacing.
- Verification: `node .\\node_modules\\vitest\\vitest.mjs run src\\features\\navigation\\RecentProjectButton.test.tsx src\\features\\navigation\\launcherSidecarGate.test.ts` passed `6/6`; `node .\\node_modules\\typescript\\bin\\tsc --noEmit` passed from `apps\\astrabridge-desktop`.
- In-app browser acceptance: on the live launcher tab for sidecar `8839`, Playwright locator readback confirmed the settled gate copy `当前本地 sidecar 不可用，已暂时禁用最近项目和打开/创建动作。请先在运行时面板恢复 sidecar。`, and DOM-CUA confirmed the launcher action buttons remained disabled while the gate was active. Screenshot capture failed with `Timed out running CDP command "Page.captureScreenshot" for tab 32`, so this slice is DOM-accepted with `browser_screenshot_channel_failure` still recorded.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260714-step21-launcher-sidecar-gate-13/step21-launcher-sidecar-gate-13.md` and `.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: completed.
- Next entry remains the runtime line: restore or relaunch a healthy current-source sidecar, re-enter the visible task-graph workspace from the launcher, then continue the bounded live rerun and terminal-collection validation.

### 2026-07-14 - Step 21 task-graph disclosure density 14 completed

- User-directed follow-up: the grey `Nodes ... pass / warning / blocked` style copy still read too loudly, and both the dry-run findings plus the recent-snapshot strip needed a clearer `3 visible + disclosure` preview contract.
- UI repair: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx` now renders compact preview-meta copy for both disclosure surfaces so the current collapsed state is explicit. `apps/astrabridge-desktop/src/styles.css` further reduces the size and opacity of the secondary grey task-graph copy, including dry-run preview text, disclosure controls, snapshot labels, and snapshot chip meta.
- Regression coverage: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx` now asserts the new preview-meta copy on both dry-run findings and recent snapshots while retaining the existing three-item preview contract.
- Verification: `D:\AstraBridge\apps\astrabridge-desktop\node_modules\.bin\vitest.cmd run src\features\runtime\TaskGraphWorkspace.test.tsx` passed `76/76`; `D:\AstraBridge\apps\astrabridge-desktop\node_modules\.bin\tsc.cmd --noEmit` passed.
- In-app browser acceptance attempt: reconnected to the requested in-app browser runtime and found the live AstraBridge tab on sidecar `8839`, but claiming the tab for virtual-pointer / DOM-CUA validation still failed with `Timed out waiting for the Browser webview to attach for this browser-use page`. This slice is therefore code-and-test verified, with visible screenshot acceptance still blocked by the Codex webview attach channel rather than AstraBridge rendering.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260714-step21-taskgraph-disclosure-density-14/step21-taskgraph-disclosure-density-14.md` and `.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: completed.
- Next entry remains the runtime line: reattach the in-app browser successfully, verify the denser three-item preview state on the live task-graph surface, then continue the Step 21 runtime rerun and terminal-collection validation line.

### 2026-07-14 - Step 21 process hygiene 15 completed

- User-directed repository rule: [AGENTS.md](D:/AstraBridge/AGENTS.md) now explicitly requires regular inspection and prompt cleanup of stale AstraBridge-owned frontend, sidecar, and helper processes from failed runs, while preserving unrelated user processes unless ownership is clear.
- Runtime/process repair: added [scripts/run_sidecar_8852_detached.cmd](D:/AstraBridge/scripts/run_sidecar_8852_detached.cmd) as the stable detached relaunch path for the current-source sidecar in this environment, because the sandbox `Start-Process` path remained unreliable and parent/child cleanup inference proved unsafe.
- Process hygiene result: removed the extra non-listening sidecar probe Python processes created during this round, preserved the actively used frontend on `4181`, and recovered the current-source sidecar on `8852` with router `8787`.
- In-app browser recovery: the in-app browser runtime reattached, a fresh AstraBridge tab opened successfully on `http://127.0.0.1:4181/?astrabridge_launch=dogfood&sidecar=http://127.0.0.1:8852`, and screenshot evidence was captured. One DOM capture attempt still returned an empty string despite successful screenshot capture, so browser-channel text capture remains slightly weaker than screenshot capture on this slice.
- Verification: `rg -n "background processes regularly" D:\AstraBridge\AGENTS.md` confirmed the new rule; `curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:4181/` returned `200`; `curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:8852/health` returned `200` during the recovered-sidecar pass; `netstat -ano -p TCP | Select-String '127.0.0.1:4181|127.0.0.1:8852|0.0.0.0:8787'` confirmed the recovered local stack.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260714-step21-process-hygiene-15/step21-process-hygiene-15.md`, `.json`, `.png`, and `step21-process-hygiene-15-browser.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: completed.
- Next entry remains the runtime line: repair the remaining terminal-collection and failed-branch reconciliation defects exposed by `graph-run-live-20260714T063002850207-241158`, then rerun one bounded visible task-graph session through the restored in-app browser stack on `4181 + 8852`.

### 2026-07-14 - Step 21 runtime reconciliation artifacts 16 completed

- Runtime defect focus: the authoritative failed run `graph-run-live-20260714T063002850207-241158` had already narrowed to terminal collection plus failed-branch reconciliation. The helper `_commit_graph_live_reconciled_execution_result(...)` existed, but the `execute_task_graph_run(...)` exception path still had an older reconciliation callsite that did not pass run artifact refs into `_reconcile_graph_live_started_turns(...)`. That left the new persistence path undercovered and allowed the failed-run branch-output loss symptom to survive the catch/finalize path.
- Runtime repair: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py` now passes `artifact_refs=run_artifact_refs` through the exception-path `_reconcile_graph_live_started_turns(...)` call inside `execute_task_graph_run(...)`, so a started sibling branch that already reached a terminal result can merge its recovered worker artifacts into the failed live run before finalization.
- Regression coverage: `apps/astrabridge-sidecar/tests/test_task_graph_worker_runtime.py` upgrades `test_live_graph_failure_reconciles_started_sibling_turn` from a status-only cancel-path assertion into a persisted-output reconciliation test. It now creates a real dry-run-backed run ref plus worker binding, feeds a completed sibling branch through reconciliation, and asserts no interrupt occurs, reconciliation becomes `terminal_result_committed`, the node state becomes `completed`, both `turn_reconciled` and `node_completed` events exist, recovered worker output lands on disk, and the live run artifact refs include the recovered `output.json`.
- Verification: with `ASTRABRIDGE_RUNTIME_ROOT=D:\\AstraBridge\\PRIVATE\\test-runtime-root`, `python.exe -m unittest -v tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_live_graph_failure_reconciles_started_sibling_turn tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_wait_for_probe_turn_terminal_recovers_after_thread_read_timeout_when_terminal_notification_exists tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_live_graph_timeout_persists_failed_terminal_state_and_diagnostics tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_terminal_notification_reconciles_nested_turn_id_with_stale_thread_projection` passed `4/4`.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260714-step21-runtime-reconciliation-artifacts-16/step21-runtime-reconciliation-artifacts-16.md` and `.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: completed.
- Next entry: rerun one bounded visible task-graph session through the restored `4181 + 8852` stack and verify whether the repaired reconciliation path removes the missing-worker-output / `interrupt_failed` symptom on the real graph run; if not, capture the remaining terminal-collection defect with fresh authoritative evidence.

### 2026-07-14 - Step 21 visible rerun 17 completed

- Visible execution: using only the in-app browser virtual pointer on the restored `4181 + 8852` stack, reopened `Provider Switch Live 20260622-224524 -> DG Graph Parallel 01 Fresh -> 任务图`, captured pre-run evidence, and clicked the visible `直接运行` control exactly once. Evidence was preserved under `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260714-step21-visible-rerun-01/`.
- Authoritative runtime progression: the click created fresh run `graph-run-live-20260714T223926888480-028c65`, updated `graph_activity_summary.latest_run_id`, and produced new live-run artifacts `compiled-plan.json`, `run-export.json`, and `run-manifest.json`. `node_supervisor` now persisted `output.json`, `output-envelope.json`, `summary.md`, and `handoff.json`, and downstream nodes `node_artifact_source`, `node_artifact_source_2`, and `node_worker` each emitted `graph_worker_started`. This is materially past the older `interrupt_failed` symptom on `graph-run-live-20260714T063002850207-241158`, where the run died before a stable downstream fan-out with persisted supervisor output.
- Remaining blocker: even after waiting past the downstream node timeout windows, the live-run directory still had no `summary.json` or `report.md`, and `graph_activity_summary.latest_run_status` remained `running`. Runtime events show `API Auditor` received the bounded `no_tools` JSON-only prompt, completed a structured JSON answer, and then the same execution thread immediately entered a follow-on default-mode turn that began planning to inspect artifact files. That means bounded task-graph node execution is not terminating after the first structured response, so the live run never reaches terminal finalization even though worker output exists.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260714-step21-visible-rerun-01/step21-visible-rerun-17.md`, `.json`, `01-pre-conversation.png`, `02-task-graph-pre-run.png`, `02-task-graph-pre-run.dom.txt`, `03-immediate-post-click.png`, `03-immediate-post-click.dom.txt`, and `04-stuck-running-ui.*`. Authoritative runtime artifacts and logs are the fresh live-run directory plus `PRIVATE/task-graph/workers/graph-run-live-20260714T223926888480-028c65/node_supervisor/*` and the matching `runtime_events.jsonl` records for `graph-run-live-20260714T223926888480-028c65`.
- Safety and cost: visible-click-only interaction was preserved; no sidecar API wrote state outside the same user-equivalent task-graph click path. This rerun used the managed `astra` lane on `qwen / qwen3.7-plus`, so it consumed real provider-backed execution. Usage/cost remain `not_available` because the run never finalized and no authoritative usage projection was emitted.
- Step 21 follow-up status: in progress.
- Next entry: repair the bounded task-graph worker termination/finalize path so `no_tools` graph nodes stop after the first structured JSON answer, commit worker output plus run summary, and do not fall through into a second default-mode turn. Then rerun one bounded visible task-graph session on `4181 + 8852` to confirm that the live run reaches a terminal summary instead of remaining stuck in `running`.

### 2026-07-14 - Step 21 bounded-turn termination repair 18 completed

- Runtime repair: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py` now treats terminal collection as target-turn-specific even when the execution thread has already started a newer follow-on turn. `_wait_for_probe_turn_terminal(...)` now recovers the requested turn from cached thread snapshots plus terminal notifications instead of silently falling through to the latest turn when the original turn is no longer present in the active `thread/read` projection. This directly covers the `graph-run-live-20260714T223926888480-028c65` symptom where the bounded JSON-only worker completed once and then the same execution thread entered a second default-mode turn.
- Runtime repair, bounded cleanup: after a bounded task-graph worker turn reaches terminal state, the live-run path now clears the thread goal and immediately checks for a newer non-terminal turn on the same execution thread. If one exists, AstraBridge interrupts it and records a `bounded_turn_follow_on_cleanup` event. This is the explicit guardrail that prevents the worker lane from continuing past its first bounded reply.
- Regression coverage: `apps/astrabridge-sidecar/tests/test_task_graph_worker_runtime.py` now adds one test that proves terminal recovery still succeeds when `thread/read` only exposes a follow-on turn while the target turn survives in cached thread state, plus one live-run test that proves AstraBridge clears the bounded goal and interrupts the newer follow-on turn before finalizing the node result.
- Verification: `python -m pytest D:\AstraBridge\apps\astrabridge-sidecar\tests\test_task_graph_worker_runtime.py -k "wait_for_probe_turn_terminal_recovers_when_follow_on_turn_hides_target_turn or live_graph_clears_bounded_goal_and_interrupts_follow_on_turn or wait_for_probe_turn_terminal_recovers_after_thread_read_timeout_when_terminal_notification_exists or live_graph_failure_reconciles_started_sibling_turn or live_graph_marks_completed_turn_failed_when_no_tools_policy_is_violated or live_graph_salvages_structured_response_after_no_tools_policy_violation" -q` passed `6/6`; `python -m py_compile D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\runtime_service.py D:\AstraBridge\apps\astrabridge-sidecar\tests\test_task_graph_worker_runtime.py` passed.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; this slice was runtime-only and test-only, with no plaintext secret source, raw provider payload, cookie, authorization material, or external writeback.
- Step 21 follow-up status: in progress.
- Next entry: rerun one bounded visible task-graph session on `4181 + 8852` and confirm that the live run now writes terminal `summary.json` and `report.md`, updates the latest-run dock coherently, and no longer falls through into a second default-mode turn after the first bounded worker response.

### 2026-07-14 - Step 21 visible rerun 19 blocked by browser/session instability

- Runtime reload precondition: before the visible rerun, the active `8852` sidecar was restarted through `scripts/run_sidecar_8852_detached.cmd` so the bounded-turn termination repair would be exercised on the live stack rather than only in tests.
- Visible progress before block: a fresh in-app tab reached the authenticated `astra` session on `4181 + 8852`, displayed the `DG Graph Parallel 01 Fresh` task list, and exposed a blocking approval modal on the conversation surface. That modal was visibly dismissed, leaving the task ready for a `任务图` transition attempt.
- Blocking failures:
  - entering `任务图` then hit `Timed out waiting for the Browser webview to attach for this browser-use page`
  - a fresh-tab retry hit the same attach-timeout failure
  - the previously working tab then became stale with `Tab not found: 4. Existing tabs: none`
  - after the patched sidecar reload, `4181` remained responsive but `8852/health` repeatedly timed out after 8 seconds with zero bytes returned, so the browser failure is now accompanied by a real sidecar-health regression rather than a browser-only screenshot-channel issue
- Safety and execution boundary: no fresh provider-backed graph run was dispatched during this blocked attempt. The newest live-run directory remained `graph-run-live-20260714T223926888480-028c65`, so no new live token budget was consumed and the Step 21 acceptance claim remains unproven.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260714-step21-visible-rerun-02/step21-visible-rerun-19-blocked.md` and `.json`, plus the preserved screenshots and DOM captures in the same directory.
- Step 21 follow-up status: in progress with a concrete blocker.
- Next entry: repair the patched `8852` sidecar health-timeout condition after reload, restore a claimable/attachable in-app browser tab on `4181 + 8852`, and only then rerun one bounded visible task-graph live session to validate terminal summary generation and bounded-turn cleanup on the real UI path.

### 2026-07-14 - Step 21 sidecar health-timeout repair 20 completed

- Runtime readiness repair: `apps/astrabridge-sidecar/astrabridge_sidecar/server.py` now serves `GET /health` from lightweight `runtime.health_environment()` plus `router.health_status()` instead of the heavier detailed runtime/router endpoints. `apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py` and `router_service.py` add the supporting lightweight router snapshot path.
- Runtime regression fix: the first lightweight implementation exposed a real bug because `RuntimeService.__init__` does not initialize `_active_runtime`. `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py` now guards the unconfigured-runtime path with `getattr(...)`, so `/health` works before any provider/runtime pin exists.
- Process hygiene hardening: `scripts/cleanup_stale_astrabridge_processes.ps1` now provides a safe stale-wrapper reap pass, and `scripts/run_sidecar_8852_detached.cmd` invokes it before detached relaunch. This folds the new AGENTS hygiene rule into an executable local recovery path instead of leaving it as policy text only.
- Verification: `python -m pytest D:\AstraBridge\apps\astrabridge-sidecar\tests\test_sidecar_services.py -k "handler_health_includes_sidecar_provenance or runtime_health_environment_handles_unconfigured_runtime" -q` passed `2/2`; `python -m py_compile` over the touched sidecar files passed; after clearing the stale `8852` sidecar tree and starting a fresh current-source sidecar, `Invoke-WebRequest http://127.0.0.1:8852/health` returned HTTP `200` and `Get-NetTCPConnection` confirmed a clean `8852 + 8787` listener pair.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260714-step21-sidecar-health-timeout-repair-20/step21-sidecar-health-timeout-repair-20.md` and `.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: in progress.
- Next entry: reclaim an attachable in-app browser tab on the restored `4181 + 8852` stack, then rerun one bounded visible task-graph session and verify that the repaired bounded-turn termination path now reaches terminal `summary.json` / `report.md` instead of leaving the run stuck in `running`.

### 2026-07-15 - Step 21 terminal transcript fallback 21 completed

- Runtime defect focus: the fresh failing evidence had shifted again. In `graph-run-live-20260714T235350875211-6c6b33`, `run-manifest.json` persisted `node_supervisor` as `policy_violated` with empty `response_text`, yet the authoritative execution-thread transcript for the same execution thread already contained a valid bounded JSON answer. That meant the live graph path was still willing to trust an empty terminal `thread/read` projection over a richer snapshot of the same target turn.
- Runtime repair: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py` now scores same-turn snapshots by terminal completeness and prefers the richer target-turn view during terminal reconciliation. `_wait_for_probe_turn_terminal(...)` no longer blindly accepts a terminal `thread/read` result when its target turn has empty `items`; it can now enrich that turn from the richer cached/task-transcript snapshot before the node outcome is derived. `_terminal_turn_recovery_thread(...)` uses the same quality preference instead of returning the first exact-turn match. `_read_native_thread(...)` now also falls back to `task_transcripts.json` via `TaskConversationService.thread_snapshot(...)` when thread cache lacks a full native thread snapshot.
- Regression coverage: `apps/astrabridge-sidecar/tests/test_task_graph_worker_runtime.py` now adds one focused test that proves `_wait_for_probe_turn_terminal(...)` prefers a richer cached snapshot over an empty terminal `thread/read` result, plus one focused test that proves `_read_native_thread(...)` can recover a full thread from task-transcript snapshots without relying on thread cache.
- Verification: the focused worker-runtime suite covering `test_wait_for_probe_turn_terminal_prefers_richer_cached_snapshot_over_empty_terminal_read`, `test_read_native_thread_falls_back_to_task_transcript_snapshot`, `test_wait_for_probe_turn_terminal_recovers_after_thread_read_timeout_when_terminal_notification_exists`, `test_wait_for_probe_turn_terminal_recovers_when_follow_on_turn_hides_target_turn`, and `test_live_graph_salvages_structured_response_after_no_tools_policy_violation` passed `5/5`; `python -m py_compile` over `runtime_service.py`, `task_conversation_service.py`, and `test_task_graph_worker_runtime.py` passed.
- Evidence: current-source code in `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py` and `task_conversation_service.py`, plus the focused regression updates in `apps/astrabridge-sidecar/tests/test_task_graph_worker_runtime.py`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; this slice was runtime-only and test-only, with no plaintext secret source, raw provider payload, cookie, authorization material, or external writeback.
- Step 21 follow-up status: completed.
- Next entry: reclaim an attachable in-app browser tab on the restored `4181 + 8852` stack, then rerun one bounded visible task-graph session and verify that the repaired terminal transcript fallback eliminates the false `policy_violated` / empty-response outcome on a valid structured node reply, while still writing terminal `summary.json` / `report.md`.

### 2026-07-15 - Step 21 visible rerun 22 completed

- Visible execution: reopened AstraBridge on `4181 + 8852` through the in-app browser with the managed `astra` session, selected `DG Graph Parallel 01 Fresh`, entered `任务图`, and clicked `直接运行` exactly once. The toolbar switched to `正在启动直接运行...`, and the run-check dialog showed a fresh optimistic live run in `running` with a visible `取消运行` action.
- Fresh authoritative run: this created `graph-run-live-20260715T002032432722-a21f69`. The live-run directory exists and currently contains only `compiled-plan.json`, `run-export.json`, and `run-manifest.json`.
- New blocker evidence: `run-manifest.json` still reports `status: running` with `node_supervisor.status: queued`, no worker artifact directory exists for the run yet, and the run-check UI still shows `0 个 worker / 0 个产物`. But runtime events prove the run progressed further: `graph_worker_started` fired for `node_supervisor` on worker thread `019f6137-584d-71c3-9614-02f107330cbe`, and later a `provider_handoff` moved that work to provider thread `019f6137-aa77-78d0-b174-62436e53abe4`.
- Interpretation: the latest visible rerun did not yet re-hit the prior false `policy_violated` / empty `response_text` terminalization defect. Instead it exposed an earlier persistence drift: once the worker lane starts and then hands off to a provider execution thread, the live-run manifest, worker artifact tree, and run-check UI do not advance to that authoritative execution-thread lifecycle.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260715-step21-visible-rerun-22/step21-visible-rerun-22.md` and `.json`.
- Safety and cost: exactly one visible `直接运行` click was issued through the in-app browser. This slice used the managed `astra` lane on `qwen / qwen3.7-plus`, so it consumed a real provider-backed run attempt. No plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: completed.
- Next entry: repair the `graph_worker_started -> provider_handoff -> turn-start/result persistence` path so live-run state, worker artifacts, and the run-check UI advance coherently after handoff; then rerun one bounded visible task-graph live session on `4181 + 8852`.

### 2026-07-15 - Step 21 observed-turn terminal recovery 23 completed

- Runtime defect focus: once `graph-run-live-20260715T002032432722-a21f69` finished persisting, the earlier "still queued" diagnosis was no longer authoritative. The stronger evidence showed turn-identity drift instead: `turn/start` returned target turn id `019f6138-f568-7993-b6d1-410f9e5e1a27`, while the real bounded completion and transcript content landed on observed turn id `0c57afd3-4eb5-4db2-bc6e-0652af0c1042`. Terminal reconciliation therefore rebuilt an empty synthetic completed turn (`final_text_present=false`) and the live graph degraded into `policy_violated` even though the observed completed turn already contained the correct bounded planner JSON.
- Runtime repair: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py` now maps a richer observed completed turn back onto the target turn id during terminal recovery. `_terminal_turn_recovery_thread(...)` reads `observedTurnId` / notification turn ids, and `_thread_with_observed_turn_mapped_to_target(...)` clones the richer observed turn content under the target turn id so bounded-turn parsing, no-tools salvage, and follow-on cleanup see the real completed payload instead of an empty shell.
- Regression coverage: `apps/astrabridge-sidecar/tests/test_task_graph_worker_runtime.py` now adds `test_wait_for_probe_turn_terminal_maps_observed_completed_turn_onto_target_turn_id` and keeps it green alongside the existing follow-on recovery, no-tools salvage, and bounded follow-on cleanup tests.
- Verification: `python -m pytest apps/astrabridge-sidecar/tests/test_task_graph_worker_runtime.py -k "maps_observed_completed_turn_onto_target_turn_id or recovers_when_follow_on_turn_hides_target_turn or salvages_structured_response_after_no_tools_policy_violation or live_graph_clears_bounded_goal_and_interrupts_follow_on_turn" -q` passed `4/4`; `python -m py_compile apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py apps/astrabridge-sidecar/tests/test_task_graph_worker_runtime.py` passed.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260715-step21-observed-turn-terminal-recovery-23/step21-observed-turn-terminal-recovery-23.md` and `.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: completed.
- Next entry: rerun one bounded visible task-graph live session on `4181 + 8852` and verify that the first bounded planner reply is now preserved through terminal reconciliation instead of degrading into an empty `policy_violated` failure.

### 2026-07-15 - Step 21 visible rerun 25 completed

- Runtime reload precondition: the current-source `8852` sidecar was restarted before the rerun, and `GET /health` returned HTTP `200` afterwards.
- Visible execution: through only the in-app browser virtual pointer, reopened AstraBridge on `4181 + 8852`, opened `DG Graph Parallel 01 Fresh`, entered `任务图`, and clicked visible `直接运行` exactly once. The control switched to `正在启动直接运行...`, and the run-check panel exposed a fresh optimistic live run in `running`.
- Fresh authoritative run: the click created `graph-run-live-20260715T020614500136-270355`. The live-run directory persisted only `compiled-plan.json`, `run-export.json`, and `run-manifest.json`, and no worker artifact directory appeared even after repeated waits. `run-manifest.json` remained stuck at `status: running` with `node_supervisor.status: queued`.
- Strongest blocker evidence: runtime events prove the live lane advanced past queueing and into provider execution, but a new earlier drift now dominates. `graph_worker_turn_thread_resolved` recorded target turn id `019f619a-0b0c-74b1-9127-98e1eb139ac4`, while live notifications and tool attempts immediately continued on observed turn id `034b8460-3d53-452b-aa3c-5d2e3a11cae8`. The provider then emitted agent reasoning, agent text, and three command-execution items on that observed turn despite the active `no_tools` contract. AstraBridge recorded `turn_execution_policy_tool_blocked` and auto-declined approvals, but the provider thread still entered `waitingOnApproval`, and the run never advanced its manifest/worker-artifact state coherently.
- Acceptance impact: this rerun does not re-open the older empty-terminal-reconciliation defect directly. Instead it proves a stronger pre-terminal coherence bug remains: bounded task-graph workers can drift from the target turn returned by `turn/start` onto a different observed notification turn before fail-closed termination and persistence complete.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260715-step21-visible-rerun-25/step21-visible-rerun-25.md`, `.json`, and the captured screenshots/DOM snapshots in the same directory.
- Safety and cost: exactly one visible `直接运行` click was issued through the in-app browser. This slice used the managed `astra` lane on `qwen / qwen3.7-plus`, so it consumed one real provider-backed run attempt. Usage and cost remain `not_available` because the run never reached a terminal usage projection. No plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: completed.
- Next entry: repair the bounded task-graph observed-turn-start drift so `turn/start` target turn ids, observed notification turns, `no_tools` enforcement, and live-run manifest/worker-artifact persistence stay coherent across provider handoff; then rerun one bounded visible task-graph live session on `4181 + 8852`.

### 2026-07-15 - Step 21 observed-turn fail-closed repair 26 completed

- Runtime defect focus: the strongest remaining Step 21 blocker had shifted earlier than terminal reconciliation. In the latest visible rerun, `turn/start` returned a canonical bounded turn id, but provider notifications and blocked command-execution items immediately continued on a different observed turn id before the bounded node could terminalize. AstraBridge still logged `turn_execution_policy_tool_blocked`, but it only auto-declined approvals after the observed turn had already entered the prohibited tool path, leaving the lane vulnerable to `waitingOnApproval` stalls and weakening token-usage attribution for the real graph turn.
- Runtime repair: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py` now binds observed turn ids onto the active bounded execution policy as soon as pre-terminal notifications arrive on the same provider thread. The runtime records explicit observed-turn aliases, accepts token-usage notifications from aliased observed turns when reconciling graph live-run usage, and immediately fail-closes `no_tools` violations on `item/started` by interrupting the observed turn instead of only recording the violation and waiting for approval denial.
- Runtime hygiene: the bounded execution-policy start and clear paths now also clear stale observed-turn aliases plus prior fail-closed interrupt dedupe state for the same thread, so a new bounded worker turn cannot inherit stale alias state from an earlier provider handoff.
- Regression coverage: `apps/astrabridge-sidecar/tests/test_task_graph_worker_runtime.py` now adds `test_no_tools_observed_turn_alias_accepts_usage_and_fail_closed_interrupts_started_item`, and the older `test_no_tools_graph_policy_omits_dynamic_tools_and_auto_declines_requests` is hardened with an interrupt stub so the new fail-closed path is exercised under test control.
- Verification: `python -m pytest D:\AstraBridge\apps\astrabridge-sidecar\tests\test_task_graph_worker_runtime.py -k "no_tools_graph_policy_omits_dynamic_tools_and_auto_declines_requests or no_tools_observed_turn_alias_accepts_usage_and_fail_closed_interrupts_started_item or no_tools_policy_survives_terminal_notification_until_follow_on_cleanup or wait_for_probe_turn_terminal_maps_observed_completed_turn_onto_target_turn_id or live_graph_salvages_structured_response_after_no_tools_policy_violation" -q` passed `5/5`; `python -m py_compile D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\runtime_service.py D:\AstraBridge\apps\astrabridge-sidecar\tests\test_task_graph_worker_runtime.py` passed.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260715-step21-observed-turn-fail-closed-repair-26/step21-observed-turn-fail-closed-repair-26.md` and `.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: completed.
- Next entry: rerun one bounded visible task-graph live session on `4181 + 8852` and verify that pre-terminal observed-turn drift now fails closed by interrupting the observed turn, while the run-check UI and live-run manifest advance past the initial queued snapshot instead of hanging in `waitingOnApproval`.

### 2026-07-15 - Step 21 run-toolbar precondition repair 27 completed

- Visible blocker evidence: on the current-source `4181 + 8852` task-graph surface, visible activation of `直接运行` reached `TaskGraphWorkspace` and opened the run inspector, but the sidecar log still showed no fresh `/api/task-graphs/run` or `/api/task-graphs/dry-run` request. That proved the failure had shifted from browser hit-targeting to a frontend precondition short-circuit: the toolbar interaction could succeed visually while the App-level dispatch path still returned early without operator-visible feedback.
- Product repair: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx` now hardens the run toolbar with deduped `click` / `pointerup` / `Enter` / `Space` activation fallback for the key run buttons, and accepts a shared blocked-run reason so the toolbar can disable known-bad run states instead of inviting a silent no-op. `apps/astrabridge-desktop/src/features/runtime/taskGraphRunDispatch.ts` now exposes `resolveTaskGraphRunPrecondition(...)`, and `apps/astrabridge-desktop/src/App.tsx` uses it to surface explicit blocked-run messages for live, dry-run, fixture, and cancellable-fixture attempts instead of returning silently.
- Regression coverage: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx` now proves pointer and keyboard fallback activation stay single-fire and that blocked-run reasons disable the toolbar; `apps/astrabridge-desktop/src/features/runtime/taskGraphRunDispatch.test.ts` now covers missing-graph, route-unavailable, and missing-graph-id precondition messages.
- Verification: `node .\\node_modules\\vitest\\vitest.mjs run src\\features\\runtime\\TaskGraphWorkspace.test.tsx src\\features\\runtime\\taskGraphRunDispatch.test.ts` passed `88/88`, and `node .\\node_modules\\typescript\\bin\\tsc --noEmit -p tsconfig.json` passed in `D:\\AstraBridge\\apps\\astrabridge-desktop`.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260715-step21-run-toolbar-precondition-repair-27/step21-run-toolbar-precondition-repair-27.md` and `.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; this slice was frontend-only plus browser reproduction, with no plaintext secret source, raw provider payload, cookie, authorization material, or external writeback.
- Step 21 follow-up status: completed.
- Next entry: reclaim a stable in-app browser tab on `4181 + 8852`, confirm that the repaired toolbar now surfaces a blocked reason instead of failing silently, then rerun one bounded visible task-graph live session and continue the remaining post-handoff runtime validation line.

### 2026-07-15 - Step 21 sidebar current-task switch guard 28 completed

- Visible blocker evidence: on the same `4181 + 8852` surface, a visible click on the already-current `DG Graph Parallel 01 Fresh` row could still produce `任务切换失败：The desktop sidecar did not respond in time for /api/admin/session...` after the admin-session timeout window elapsed. This was a misleading sidebar-selection failure rather than a real task-graph run: `graph_run_refs_len` stayed `40`, the latest live run remained `graph-run-live-20260715T031052194730-08e179`, and the sidecar log still showed no fresh `/api/task-graphs/run` or `/api/task-graphs/save`.
- Product repair: `apps/astrabridge-desktop/src/features/navigation/sidebarTaskSelection.ts` now exposes a focused same-project + same-task guard, and `apps/astrabridge-desktop/src/App.tsx` uses it to short-circuit redundant `api.switchTask(...)` calls before any admin-token mutation path is touched. The same App slice now also passes `currentTask?.task_id` through `ProjectTaskTree` when no optimistic selection is pending, so the real current task stays highlighted instead of making the active row look unselected.
- Regression coverage: `apps/astrabridge-desktop/src/features/navigation/sidebarTaskSelection.test.ts` now proves the guard only fires for the current task inside the current project (or an explicitly current sidebar project) and does not suppress real cross-project selections. `apps/astrabridge-desktop/src/features/navigation/ProjectTaskTree.test.tsx` stayed green with the current-task highlight path.
- Verification: `node .\\node_modules\\vitest\\vitest.mjs run src\\features\\navigation\\sidebarTaskSelection.test.ts src\\features\\navigation\\ProjectTaskTree.test.tsx` passed `13/13`, and `node .\\node_modules\\typescript\\bin\\tsc --noEmit -p tsconfig.json` passed in `D:\\AstraBridge\\apps\\astrabridge-desktop`.
- Evidence: browser reproduction artifacts under `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260715-step21-visible-rerun-28/`, plus the repair report `PRIVATE/app-standardization-ui-dogfood/repairs/20260715-step21-sidebar-current-task-switch-guard-28/step21-sidebar-current-task-switch-guard-28.md` and `.json`.
- Browser-readiness note: the post-repair refreshed tabs bounced through the launcher/open-project surface before the task tree rehydrated cleanly on a stable tab, so same-path visible acceptance of the new bundle remains pending and is classified as `session_or_route_mismatch`, not as a sidecar failure.
- Process hygiene: listener audit during this slice confirmed only `4181 -> PID 9200` and `8852/8787 -> PID 11544` were actively bound. No clearly stale listener-owning AstraBridge process was killed because the duplicate `cmd/python` wrapper chain still belonged to the active detached sidecar ancestry rather than a dead orphan.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no new live task-graph run was created, and no plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: completed.
- Next entry: reopen `Provider Switch Live 20260622-224524 -> DG Graph Parallel 01 Fresh` on a fresh hydrated `4181 + 8852` tab, confirm that redundant current-task clicks no longer surface `/api/admin/session` timeout UI, then rerun one bounded visible `直接运行` task-graph session and continue the post-handoff runtime validation line.

### 2026-07-15 - Step 21 visible rerun 30 completed

- Visible execution: on the hydrated `4181 + 8852` in-app browser tab, reopened `DG Graph Parallel 01 Fresh`, clicked the already-current task row once, waited 14 seconds, and confirmed no redundant `/api/admin/session` timeout UI surfaced. Then clicked visible `direct-run` exactly once and observed the task-graph toolbar enter an optimistic pending state.
- Fixed behavior verified: the sidebar current-task switch guard held under the same visible path that previously raised a misleading task-switch timeout. No fresh `任务切换失败` banner appeared during the guarded current-task click.
- Fresh authoritative run: the direct-run click created `graph-run-live-20260715T062621003037-ebf48d`. During the visible wait window, persisted task state advanced to `node_started` with `worker_count=1` and `artifact_count=3`, proving the live request no longer disappears before runtime execution begins.
- Stronger blocker evidence: the browser-facing request still hit `POST /api/task-graphs/run HTTP/1.1" 400 -`, leaving the UI stuck in optimistic pending state. Current authoritative artifacts now show that this same run later terminalized as `failed`: `summary.json` reports `run_status=failed`, `failure.json` reports `failure_kind=terminal_collection_timeout`, `report.md` reports `Planner: failed / policy_violated`, and turn reconciliation records `terminal_result_committed=true`. The persisted recovery reason still says `The terminal worker result was not committed to the graph run.`
- Interpretation: the dominant Step 21 defect has narrowed to live-run response / terminal-commit synchronization. A visible direct-run can now create a real provider-backed execution and later persist terminal artifacts on disk, but the frontend does not receive a coherent settled payload and the graph-run failure does not reconcile cleanly enough to clear the pending UI state.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260715-step21-visible-rerun-30/step21-visible-rerun-30.md`, `.json`, the screenshot/DOM artifacts in the same directory, `PRIVATE/task-graph/live-run/graph-run-live-20260715T062621003037-ebf48d/{summary.json,failure.json,report.md,run-manifest.json,run-export.json}`, and the matching `tmp/sidecar-8852.out.log` request records.
- Safety and cost: exactly one visible `direct-run` click was issued through the in-app browser on the managed `astra` route using `qwen / qwen3.7-plus`, so this slice consumed one real provider-backed run attempt. Usage and cost remain `not_available`; no plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: completed.
- Next entry: repair the task-graph live-run response and terminal-commit synchronization path so a bounded visible rerun on `4181 + 8852` either returns a stable success payload or fail-closed terminal error while clearing the pending UI state and keeping frontend task state synchronized with persisted live-run artifacts.

### 2026-07-15 - Step 21 live-run response sync repair 31 completed

- Runtime/handler repair: `apps/astrabridge-sidecar/astrabridge_sidecar/server.py` now keeps structured terminal live-run failure payloads on the `/api/task-graphs/run` route instead of collapsing them into a generic transport `400`. When runtime failure metadata already contains a terminal `live_run` status (`failed` or `cancelled`), the sidecar now returns an application-level response with `ok=false` plus the redacted live-run/task payload so the desktop app can reconcile the authoritative run state.
- Desktop synchronization repair: `apps/astrabridge-desktop/src/App.tsx` now polls the mounted task/sidebar/task-graph queries while a live task-graph mutation is pending, so persisted `run_ref` updates can reach the UI before the original request settles. `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx` now refuses to synthesize fake pending `running` chrome when `latestRunRef` already represents an authoritative terminal run, and the direct-run button label follows the same rule.
- Regression coverage: `apps/astrabridge-desktop/src/api.test.ts` now proves structured terminal live-run failures remain available through `ApiRequestError.data` even when the HTTP route returns `200` with `ok=false`; `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx` now proves a real failed run is not masked by synthetic live pending UI; `apps/astrabridge-sidecar/tests/test_task_graph_api.py` now proves the task-graph run endpoint returns the structured terminal failure payload for this path.
- Verification: `node .\node_modules\vitest\vitest.mjs run src\api.test.ts src\features\runtime\TaskGraphWorkspace.test.tsx` passed `86/86`; `node .\node_modules\typescript\bin\tsc --noEmit -p tsconfig.json` passed in `apps/astrabridge-desktop`; `python -m pytest D:\AstraBridge\apps\astrabridge-sidecar\tests\test_task_graph_api.py -k "live_task_graph_run_endpoint_returns_structured_terminal_failure_payload or http" -q` passed `3/3`; `python -m py_compile D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\server.py` passed.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260715-step21-live-run-response-sync-repair-31/step21-live-run-response-sync-repair-31.md` and `.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: completed.
- Next entry: reload the current-source `4181 + 8852` stack, then rerun one bounded visible `direct-run` task-graph session and verify that terminal persisted run state no longer remains masked by synthetic pending UI and that fail-closed live-run errors round-trip as structured task-graph payloads.

### 2026-07-15 - Step 21 visible rerun 32 completed

- Runtime reload precondition: reused the healthy current-source `4181 + 8852` stack and reconfirmed `GET /health` on `8852` stayed `200` before the rerun.
- Visible execution: through only the in-app browser, reopened `DG Graph Parallel 01 Fresh`, entered the task-graph surface, and clicked visible `direct-run` exactly once.
- Visible blocker evidence: the toolbar immediately disabled `direct-run` and `fixture-run`, and the run-check dialog created a fresh optimistic live run rendered as `running`, `0 worker / 0 artifacts`, budget `pending`, with a visible `Cancel run` action. Repeated waits and screenshots never moved the UI out of that optimistic pending state, and no terminal failure banner or structured error payload became visible to the operator.
- Stronger authoritative evidence: no new `graph-run-live-*` directory appeared under `PRIVATE/demo-runs/provider-switch-live-20260622-224524/workspace/PRIVATE/task-graph/live-run`; the newest persisted live-run directory remained `graph-run-live-20260715T062621003037-ebf48d`. At the same time, `tmp/sidecar-8852.out.log` recorded fresh `POST /api/task-graphs/run HTTP/1.1" 400 -` entries for the visible click while the frontend continued polling `GET /api/task-graphs/graph?graph_id=graph-20260712T173804515139-e95d05 HTTP/1.1" 200 -`.
- Interpretation: this rerun proves the remaining Step 21 blocker has shifted earlier than terminal persisted-run reconciliation. On the current-source `8852` path, a visible `direct-run` can still enter optimistic pending chrome even when `/api/task-graphs/run` fails before any authoritative live-run directory is created. The current bundle therefore still masks a pre-persistence backend failure instead of failing closed into a visible structured terminal state.
- Acceptance impact: the required Step 21 verification remains unproven. This slice does not create a fresh authoritative live-run record and does not demonstrate that structured fail-closed run errors now clear the optimistic pending UI.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260715-step21-visible-rerun-32/step21-visible-rerun-32.md`, `.json`, and the screenshot artifacts in the same directory.
- Safety and cost: exactly one visible `direct-run` click was issued through the in-app browser on the managed `astra` session. No plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted. Because no fresh authoritative live-run directory was created, usage and cost remain `not_available`.
- Step 21 follow-up status: completed with a concrete blocker.
- Next entry: repair the current-source task-graph `direct-run` pre-persistence failure path so `/api/task-graphs/run` either creates an authoritative `graph-run-live-*` record or returns a fail-closed structured terminal payload that clears the optimistic pending UI; then rerun one bounded visible `direct-run` session on `4181 + 8852`.

### 2026-07-15 - Step 21 pre-persistence fail-closed repair 33 completed

- Runtime/handler repair: `apps/astrabridge-sidecar/astrabridge_sidecar/server.py` now fail-closes graph-scoped `/api/task-graphs/run` exceptions even before an authoritative `graph-run-live-*` directory exists. When the request carries a `graph_id`, the handler enriches the structured error with the graph definition and compact current-task payload when available, then returns `ok=false` / HTTP `200` instead of collapsing back to an opaque transport `400`.
- Desktop run-ref repair: `apps/astrabridge-desktop/src/features/runtime/taskGraphRunRefs.ts` now keeps cached active live refs only while the live-run mutation is still pending. Once pending settles, cached active refs without route/current-task corroboration no longer outrank authoritative emptiness, while cached terminal refs still remain available for failure inspection. `apps/astrabridge-desktop/src/App.tsx` now passes the live-mutation pending state through this selector.
- Desktop diagnostics: `apps/astrabridge-desktop/src/api.ts` now records `/api/task-graphs/run` request stages into `taskGraphDebug`, making future visible reruns distinguish token wait, fetch start, fetch throw, and response receipt without needing browser devtools.
- Regression coverage: `apps/astrabridge-sidecar/tests/test_task_graph_api.py` now adds `test_live_task_graph_run_endpoint_fail_closes_pre_persistence_failure`, and `apps/astrabridge-desktop/src/features/runtime/taskGraphRunRefs.test.ts` now covers the unconfirmed-cached-active suppression path plus cached-terminal fallback.
- Verification: `python -m pytest D:\AstraBridge\apps\astrabridge-sidecar\tests\test_task_graph_api.py -k "structured_terminal_failure_payload or fail_closes_pre_persistence_failure" -q` passed `2/2`; `python -m py_compile D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\server.py D:\AstraBridge\apps\astrabridge-sidecar\tests\test_task_graph_api.py` passed; `node .\node_modules\vitest\vitest.mjs run src\features\runtime\taskGraphRunRefs.test.ts` passed `14/14`; `node .\node_modules\typescript\bin\tsc --noEmit -p tsconfig.json` passed in `apps\astrabridge-desktop`.
- Visible rerun evidence: on a stale pre-reload `4181 + 8852` graph tab, one visible `direct-run` click still created an optimistic pending inspector entry (`optimistic-live... / running / 0 worker / 0 artifacts`) while `tmp/sidecar-8852.out.log` showed no `POST /api/task-graphs/run`, no `OPTIONS /api/task-graphs/run`, and no `POST /api/task-graphs/save`; no fresh authoritative live-run directory appeared on disk. After reloading the same tab onto the new bundle, the graph shell reopened with `graphWorkspaceOpen=true` but no authoritative graph loaded (`selectedTaskGraphId=null`, `activeTaskGraphId=null`, `currentTaskGraphId=null`, `routeTaskGraphIds=[]`), and all run buttons now surfaced the truthful blocked reason `任务图运行已被阻止：当前任务图尚未加载完成。请等待任务图加载后重试。`
- Interpretation: this slice clears the earlier fail-closed backend gap and the stale cached-active latest-run masking path, but it exposes a stronger current-source blocker earlier in the visible workflow: task-graph hydration / selection can still disappear across reload or stale tab reuse, and one stale graph surface could enter optimistic pending chrome before any live-dispatch request actually left the frontend.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260715-step21-pre-persistence-fail-closed-repair-33/step21-pre-persistence-fail-closed-repair-33.md` and `.json`; `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260715-step21-visible-rerun-33/step21-visible-rerun-33.md` and `.json`.
- Safety and cost: no fresh authoritative provider-backed live run was created in this slice, so usage and cost remain `not_available`. No plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: completed with a concrete blocker.
- Next entry: repair the current-source task-graph hydration / selection loss so the visible graph shell rebinds to the authoritative current-task graph after reload or stale-tab reuse, and prevent optimistic live-run placeholders unless a real `/api/task-graphs/run` dispatch begins; then rerun one bounded visible `direct-run` session on `4181 + 8852`.

### 2026-07-15 - Step 21 launcher current-project short-circuit repair 34 completed

- Visible blocker evidence: after reopening the healthy current-source `4181 + 8852` stack, the in-app browser still landed on the launcher instead of entering the already-current `Provider Switch Live 20260622-224524` project. A visible click on launcher `打开` with the exact current `.abproj` path remained stuck on `加载中…` and later returned to the misleading sidecar-unavailable state, which blocked re-entry into `DG Graph Parallel 01 Fresh` before any task-graph verification could resume.
- Desktop repair: `apps/astrabridge-desktop/src/api.ts` now normalizes project-file paths and short-circuits `api.openProject(...)` through `/api/projects/current` when the requested `.abproj` already matches the authoritative current project, so launcher re-entry no longer depends on an admin-session-backed mutation for this path. The same API slice now reads response bodies as `text()` plus `JSON.parse(...)` inside the timeout wrapper instead of relying directly on `Response.json()`, reducing dependence on the browser-native `json()` path during desktop-side response parsing.
- Regression coverage: `apps/astrabridge-desktop/src/api.test.ts` now proves the current-project short-circuit returns the already-open project without bootstrapping an admin session, and the existing admin-session retry / timeout / refresh tests were updated so the new read-only preflight stays covered when the project is not already current.
- Verification: `node .\node_modules\vitest\vitest.mjs run src\api.test.ts` passed `6/6`, and `node .\node_modules\typescript\bin\tsc --noEmit -p tsconfig.json` passed in `D:\AstraBridge\apps\astrabridge-desktop`.
- Stronger runtime evidence: after the repair, visible launcher rechecks on `4181 + 8852` no longer needed `/api/projects/open`; the sidecar log only showed fresh `GET /api/projects/current HTTP/1.1" 200 -` entries from the visible click path. Even so, the launcher still failed to transition into `AppShell`, which proves the dominant Step 21 blocker has moved earlier again: the current-project response is reaching the sidecar successfully, but the launcher/root bootstrap state still does not adopt that successful response into visible project entry.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260715-step21-launcher-current-project-short-circuit-34/step21-launcher-current-project-short-circuit-34.md` and `.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; this slice was desktop-only plus in-app browser launcher rechecks, with no plaintext secret source, raw provider payload, cookie, authorization material, or external writeback.
- Step 21 follow-up status: completed with a concrete blocker.
- Next entry: instrument and repair the launcher/root current-project bootstrap path so a successful `/api/projects/current` response visibly transitions into the already-open `Provider Switch Live 20260622-224524` workspace on `4181 + 8852`, then re-enter `DG Graph Parallel 01 Fresh` and resume the bounded task-graph live-run verification line.

### 2026-07-15 - Step 21 browser sidecar proxy live-run repair 35 completed

- Proxy recovery proof: the `4181` same-origin browser proxy now returns real sidecar payloads for `GET /health` and `GET /api/projects/current`, and the visible app bootstrap dataset on the in-app page advanced to `surface=app-shell`, `hasProject=true`, `storeProjectId=Provider-Switch-Live-20260622-224524`, `bootstrapProjectId=Provider-Switch-Live-20260622-224524`, `currentStatus=success`. This closes the launcher/root current-project bootstrap blocker on the healthy `4181 + 8852` stack.
- Visible re-entry: using only the in-app browser page bridge, the operator re-entered `Provider Switch Live 20260622-224524 -> DG Graph Parallel 01 Fresh -> 任务图` and preserved a visible pre-run screenshot at `PRIVATE/app-standardization-ui-dogfood/repairs/20260715-step21-browser-sidecar-proxy-run-35/step21-task-graph-pre-run-20260715.png`.
- Stronger blocker evidence from the visible pre-fix live-run click: clicking visible `direct-run` exactly once created an optimistic `running` panel, but the task-graph debug dataset froze at `stage=run_fetch_started` with `base=http://127.0.0.1:8852`, while the sidecar log showed `OPTIONS /api/task-graphs/run HTTP/1.1" 204 -` and no matching `POST /api/task-graphs/run`. The current desktop bundle was therefore still dispatching browser dogfood live-run mutations directly to the cross-origin sidecar instead of through the `4181` proxy.
- Desktop repair: `apps/astrabridge-desktop/src/api.ts` now resolves browser dogfood requests through `browserSidecarBaseUrl()` before honoring the raw `?sidecar=` base, so browser-mode calls stay on the same-origin `4181/__astrabridge_proxy__` path while still targeting the explicitly selected sidecar. The same API slice now adds `X-AstraBridge-Sidecar-Base` inside `fetchAdminSessionToken(...)`, aligning admin-session bootstrap with the same proxy contract.
- Regression coverage: `apps/astrabridge-desktop/src/api.test.ts` now proves browser dogfood `runTaskGraph(...)` and admin-session bootstrap both use `${window.location.origin}/__astrabridge_proxy__/*` and forward `X-AstraBridge-Sidecar-Base: http://127.0.0.1:8852`; `node .\node_modules\vitest\vitest.mjs run src\api.test.ts` passed `7/7`, and `node .\node_modules\typescript\bin\tsc --noEmit -p tsconfig.json` passed in `D:\AstraBridge\apps\astrabridge-desktop`.
- Acceptance impact: the dominant Step 21 blocker is no longer launcher/bootstrap adoption. It has narrowed to post-fix visible rerun recovery: same-turn visual confirmation of the new bundle is still pending because the active in-app browser tab started rejecting reload/evaluate actions under browser URL policy after the code/test repair. Record this as browser-control policy interference on the active tab, not as an AstraBridge frontend or sidecar outage.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260715-step21-browser-sidecar-proxy-run-35/step21-browser-sidecar-proxy-run-35.md` and `.json`.
- Safety and cost: the only visible `direct-run` click in this slice happened before the proxy-base repair and never produced a real `POST /api/task-graphs/run`, so no fresh authoritative `graph-run-live-*` directory was created and usage/cost remain `not_available`. No plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: completed with a concrete blocker.
- Next entry: reclaim a healthy in-app browser tab on `4181 + 8852`, verify that task-graph live-run requests now use the same-origin browser proxy instead of direct cross-origin sidecar fetches, then run one bounded visible `direct-run` rerun and continue the post-handoff runtime validation line.

### 2026-07-15 - Step 21 browser policy blocker 36 recorded

- Stack recovery: the desktop frontend was relaunched on `4181` and returned HTTP `200`; the current-source sidecar was relaunched cleanly on `8852` and `/health` returned `ok: true` with current-source provenance. This re-established a healthy product stack for the next visible rerun.
- Process-hygiene evidence: a manual `taskkill /T` attempt against stale detached wrapper `37024` also terminated the active sidecar child `37884` before the recovery relaunch. This reiterated the existing `AGENTS.md` rule that detached parent/child chains are unreliable ownership evidence for AstraBridge process cleanup; listener ports must remain primary.
- Browser-session blocker evidence: the in-app browser session still listed healthy AstraBridge tabs on `4181 + 8852`, including selected tab `43`, but every browser-control action against that healthy page failed immediately with the same URL-policy rejection: `Browser Use rejected this action due to browser security policy. Reason: Browser use cannot visit the requested page because its URL is blocked by the Browser use URL policy.` The rejection applied to Playwright reads, DOM-CUA reads, and a fresh in-app `goto(...)` to the same healthy URL.
- Interpretation: this round does not point to an AstraBridge frontend or sidecar defect. The remaining blocker is the Codex in-app browser control channel state for the active session; the healthy localhost page is being refused by browser policy even though host-side HTTP probes succeed.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260715-step21-browser-policy-blocker-36/step21-browser-policy-blocker-36.md` and `.json`.
- Safety and cost: no visible `direct-run` click was issued after the stack recovery because browser policy prevented normal task-graph interaction. No fresh authoritative `graph-run-live-*` directory was created, and no plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: completed with a concrete blocker.
- Next entry: recover or reset the in-app browser control channel so the healthy `4181 + 8852` AstraBridge page is inspectable again, then re-enter `DG Graph Parallel 01 Fresh -> 任务图`, verify that task-graph live-run requests use the same-origin browser proxy path, and continue the bounded visible runtime validation line.
### 2026-07-15 - Step 21 admin-session prewarm cache repair 37 completed

- Visible rerun evidence: after reclaiming a healthy in-app browser AstraBridge tab on `4181 + 8852`, the operator re-entered `Provider Switch Live 20260622-224524 -> DG Graph Parallel 01 Fresh -> 任务图` and clicked visible `直接运行` exactly once. `document.documentElement.dataset.taskGraphDebug` advanced to `{"stage":"run_token_requested","base":"http://127.0.0.1:4181/__astrabridge_proxy__","path":"/api/task-graphs/run",...}`. This proves the browser-dogfood live-run path is now targeting the same-origin `4181/__astrabridge_proxy__` base instead of the raw `8852` sidecar URL.
- Stronger blocker evidence: in the same visible run attempt, the UI later surfaced `The desktop sidecar did not respond in time for /api/admin/session...`, while no fresh sidecar request lines were appended during that click window. The mutation was therefore stuck before issuing a fresh runtime request, not on the sidecar `run` handler itself.
- Desktop repair: `apps/astrabridge-desktop/src/api.ts` now stores metadata-bearing admin-session cache entries instead of only `Promise<string>`. Visible mutations refuse to reuse a still-pending token promise that originated from background `ensureAdminSession()` prewarm, and any stale pending entry older than `ADMIN_SESSION_TIMEOUT_MS` is discarded before reuse. `api.ensureAdminSession()` now explicitly tags its request as `purpose: "prewarm"`.
- Regression coverage: `apps/astrabridge-desktop/src/api.test.ts` now adds a focused regression proving a hanging prewarm token bootstrap does not poison a later mutation path. `node .\node_modules\vitest\vitest.mjs run src\api.test.ts` passed `8/8`, and `node .\node_modules\typescript\bin\tsc --noEmit -p tsconfig.json` passed in `apps/astrabridge-desktop`.
- Post-fix browser blocker: after the repair, a visible hard reload of the active in-app browser tab produced an empty `#root` shell even though `4181` and `8852/health` both remained healthy. Record this as browser/webview instability on the current tab, not as evidence that the desktop or sidecar stack regressed.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260715-step21-admin-session-prewarm-cache-repair-37/step21-admin-session-prewarm-cache-repair-37.md` and `.json`.
- Safety and cost: this slice issued one visible `直接运行` click before the code repair; no fresh authoritative `graph-run-live-*` directory was confirmed in the slice, so provider usage and cost remain `not_available`. No plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: completed with a concrete blocker.
- Next entry: reclaim a healthy visible `4181 + 8852` task-graph tab after the empty-root reload glitch, then rerun one bounded `直接运行` click on `DG Graph Parallel 01 Fresh -> 任务图` and verify that the admin-session prewarm cache repair now advances the browser-dogfood run beyond `run_token_requested`.
### 2026-07-15 - Step 21 legacy admin-session cache compatibility repair 38 completed

- Visible blocker evidence before the repair: on the surviving healthy `4181 + 8852` task-graph page, a bounded visible `direct-run` click still left `taskGraphDebug` at `run_token_requested` with base `http://127.0.0.1:4181/__astrabridge_proxy__`, no fresh authoritative `graph-run-live-*` directory on disk, and no fresh `POST /api/task-graphs/run` in the sidecar tail. This proved the browser-visible stall remained pre-dispatch even after the earlier proxy and prewarm-cache repairs.
- Desktop compatibility repair: `apps/astrabridge-desktop/src/api.ts` now treats legacy bare admin-session cache promises as first-class compatibility inputs. Live mutations no longer trust that legacy record shape; they evict it and bootstrap a fresh `/api/admin/session` request instead. The test helper `seedLegacyAdminSessionTokenPromiseForTests(...)` was added so this upgrade path can be regression-tested directly.
- Regression coverage: `apps/astrabridge-desktop/src/api.test.ts` now proves a live task-graph mutation evicts a legacy bare admin-session promise and successfully issues a fresh `/api/admin/session` plus `/api/task-graphs/run`. `node .\node_modules\vitest\vitest.mjs run src\api.test.ts` passed `9/9`, and `node .\node_modules\typescript\bin\tsc --noEmit -p tsconfig.json` passed in `apps/astrabridge-desktop`.
- Fresh-page blocker evidence after the repair: even after restarting the Vite frontend on `4181`, newly created in-app browser tabs on the same `4181 + 8852` URL remained in an empty-root shell (`document.readyState=interactive`, title `AstraBridge`, empty `#root`). This prevented proving the repaired bundle on a truly fresh visible page in the same slice.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260715-step21-legacy-admin-session-cache-compat-repair-38/step21-legacy-admin-session-cache-compat-repair-38.md` and `.json`; `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260715-step21-visible-rerun-38/step21-visible-rerun-38.md` and `.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_available`; no plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: completed with a concrete blocker.
- Next entry: reuse the surviving hydrated page or restore a fresh visible page, then rerun one bounded visible `direct-run` session to determine whether the remaining `run_token_requested` stall is still a stale browser-session problem or a new product-side pre-dispatch failure.

### 2026-07-15 - Step 21 visible rerun 39 completed

- Visible execution after the compatibility repair: on the surviving hydrated `4181 + 8852` page, re-entered `DG Graph Parallel 01 Fresh -> 任务图`, confirmed `direct-run` was enabled, saved `pre-run.png`, clicked visible `direct-run` exactly once, waited eight seconds, and saved `post-run.png`.
- Strong blocker evidence: the visible page still ended with `taskGraphDebug={"stage":"run_token_requested","base":"http://127.0.0.1:4181/__astrabridge_proxy__","path":"/api/task-graphs/run",...}`. No fresh authoritative `graph-run-live-*` directory appeared on disk, and the sidecar tail still lacked a new `POST /api/task-graphs/run`.
- Interpretation: the Step 21 acceptance blocker is still not cleared. The surviving visible page behaves like a stale browser session even after the desktop compatibility repair, and fresh browser-created tabs still fail to hydrate into AppShell, so the repaired bundle has not yet been proven through a fresh visible task-graph rerun.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-GRAPH-PARALLEL-01/20260715-step21-visible-rerun-39/step21-visible-rerun-39.md` and `.json`, plus `pre-run.png` / `post-run.png` in the same directory.
- Safety and cost: exactly one additional visible `direct-run` click was issued through the in-app browser on the managed `astra` route. No fresh authoritative provider-backed live run was created, so usage and cost remain `not_available`. No plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: completed with a concrete blocker.
- Next entry: restore a fresh visible `4181 + 8852` page that hydrates correctly, or add a stronger fail-closed timeout path for `run_token_requested` stalls so the stale visible page cannot hang indefinitely, then rerun one bounded `direct-run` session on `DG Graph Parallel 01 Fresh -> 任务图`.

### 2026-07-15 - Step 21 bootstrap fail-closed repair 41 completed

- Root-cause tightening: the recurring white-page complaint on `4181 + 8852` remained product-visible because `apps/astrabridge-desktop/index.html` exposed only a bare `#root` while `src/main.tsx` assumed React would mount quickly. When bundle import, first paint, or webview draw lagged, the user could see a pure white content area with no recovery affordance.
- Desktop repair: `apps/astrabridge-desktop/index.html` now serves a static AstraBridge bootstrap shell with loading / stalled / error states, a reload affordance, and timeout-based fail-closed behavior through `window.__AB_BOOTSTRAP__`. `apps/astrabridge-desktop/src/main.tsx` now starts through guarded async bootstrap, dynamically imports `App`, reports visible bootstrap progress, and surfaces startup failures instead of leaving a silent white page. `apps/astrabridge-desktop/src/bootstrapShell.ts` centralizes the bridge and waits for a real visible surface (`[data-testid="app-shell"]`, `.launcher-shell`, or `.launch-isolation-shell`) before dismissing the shell.
- Regression coverage: `apps/astrabridge-desktop/src/bootstrapShell.test.ts` now proves bootstrap failure formatting, shell API proxying, and visible-surface gating. `node .\node_modules\vitest\vitest.mjs run src\bootstrapShell.test.ts src\api.test.ts` passed `12/12`, and `node .\node_modules\typescript\bin\tsc --noEmit -p tsconfig.json` passed in `apps\astrabridge-desktop`.
- Runtime evidence: a fresh HTTP fetch of the current `4181 + 8852` entry returned `bootstrap_shell_present`, proving the served document now contains the startup shell plus reload affordance. On an in-app browser reload of the active AstraBridge tab, Playwright evaluation returned `bootstrapState="ready"`, `hasAppShell=true`, `hasBootstrapShell=true`, and `readyState="complete"`, which proves the repaired bundle reached a real AstraBridge surface instead of remaining a blank root.
- Process hygiene evidence: listener audit showed exactly one active frontend listener on `127.0.0.1:4181` and one active current-source sidecar listener on `127.0.0.1:8852`; no older Step 21 listener remained active in this slice.
- Remaining blocker: after the successful reload verification, the in-app browser control bridge still degraded into `Timed out waiting for the Browser webview to attach for this browser-use page` / `target closed while handling command`. Record this as a Codex webview-attach / screenshot-channel blocker, not as AstraBridge frontend or sidecar regression.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260715-step21-bootstrap-fail-closed-repair-41/step21-bootstrap-fail-closed-repair-41.md` and `.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: completed with a concrete blocker.
- Next entry: recover the in-app browser webview attach path on the healthy `4181 + 8852` stack, close broken AstraBridge tabs so only one active tab remains, then resume the bounded Step 21 visible task-graph rerun.

### 2026-07-15 - Step 21 browser attach recovery 42 completed

- Root-cause tightening: the browser-side failure was not only an AstraBridge bootstrap problem. This workstation lacked `C:\Users\cyz19\.codex\plugins\cache\openai-bundled\browser\latest`, even though older Codex sessions repeatedly imported `browser/latest/scripts/browser-client.mjs` to recover the in-app browser runtime after resets. The missing junction made the browser-use bridge brittle across kernel resets and recoveries.
- Browser-bridge repair: recreated `C:\Users\cyz19\.codex\plugins\cache\openai-bundled\browser\latest -> ...\browser\26.707.72221`, reset the Node REPL browser kernel, re-imported `browser/latest/scripts/browser-client.mjs`, and reattached the in-app browser runtime cleanly through the repaired path.
- Visible runtime recovery: on a fresh controlled tab to the healthy `4181 + 8852` stack, AstraBridge first rendered the new static bootstrap shell instead of a silent white page, then mounted the real AppShell after a bounded wait. This proves the frontend bootstrap repair and the recovered browser bridge work together on a truly fresh visible page rather than only on a surviving stale tab.
- Screenshot-channel correction: the current in-app browser runtime returns `tab.screenshot()` as a raw byte-array object rather than `{ bytes }`. The Step 21 evidence writer now persisted the raw bytes correctly, which produced fresh visible evidence at `PRIVATE/app-standardization-ui-dogfood/repairs/20260715-step21-browser-attach-recovery-42/post-repair-visible-tab50.png` and `graph-dispatch-running-tab50.png`.
- Bounded visible rerun: re-entered `DG Graph Parallel 01 Fresh -> 任务图` through visible DOM/CUA click, confirmed `直接运行` was enabled, issued exactly one visible `直接运行` click, and observed the authoritative UI mutation: `直接运行` and `夹具运行` became disabled, `取消运行` appeared, and `最近一次运行 running 0 个 worker / 0 个产物` became visible. This clears the earlier `run_token_requested` pre-dispatch blocker because the live mutation now dispatches visibly again.
- Remaining blocker: the recovered direct-run path still stalled in an ambiguous `running / 0 个 worker / 0 个产物` state with no compact terminal diagnostic after the bounded wait. The conversation surface showed generated task output and right-rail status, so the UI is no longer blank or silent, but the task-graph runtime still needs a follow-on slice to turn this state into either explicit worker progress or explicit fail-closed diagnostics.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260715-step21-browser-attach-recovery-42/step21-browser-attach-recovery-42.md` and `.json`, plus `post-repair-visible-tab50.png` and `graph-dispatch-running-tab50.png`.
- Safety and cost: one bounded visible `直接运行` click was issued through the in-app browser on the managed `astra` route. Usage and cost remain `not_available`. No plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: completed with a narrowed blocker.
- Next entry: inspect the current authoritative run and compact runtime projection for the `running / 0 worker` state, then surface explicit progress or explicit fail-closed diagnostics on the same visible rerun path.

### 2026-07-15 - Step 21 latest-run pending clarity 43 completed

- Root-cause tightening: the bounded visible rerun from slice 42 was not a pre-dispatch failure. The runtime had already persisted an authoritative live run and only later failed during terminal collection, but the latest-run dock still summarized that active window exclusively as `0 workers / 0 artifacts`. That made a real queued run look indistinguishable from a broken launch.
- Desktop repair: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx` now formats compact authoritative node-status-count summaries, prioritizes execution semantics (`queued`, `running`, `waiting_on_dependencies`, `paused_for_review`, `blocked`, `failed`, ...) over raw count order, and surfaces the newest authoritative timeline summary directly in the expanded latest-run panel. Active runs that are real but still pre-worker now show compact progress such as `1 queued / 4 waiting` instead of collapsing to `0 workers / 0 artifacts`.
- Regression coverage: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx` now includes a focused authoritative queued-run case and confirms the dock surfaces both the compact queued/waiting summary and the newest event while preserving the synthetic pending and authoritative failed-run behaviors. `pnpm vitest run src/features/runtime/TaskGraphWorkspace.test.tsx` passed `82/82`, and `pnpm exec tsc --noEmit -p tsconfig.json` passed in `D:\AstraBridge\apps\astrabridge-desktop`.
- Acceptance impact: the visible task-graph dock no longer misclassifies early authoritative queued execution as a likely dispatch failure. This closes the UI ambiguity isolated in slice 42 and narrows the remaining Step 21 blocker to backend/runtime behavior only.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260715-step21-latest-run-pending-clarity-43/step21-latest-run-pending-clarity-43.md` and `.json`.
- Safety and cost: no new provider-backed visible rerun was issued in this slice; verification stayed local to code/test repair, so additional token/cost remained `not_applicable`. No plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: completed with a narrowed blocker.
- Next entry: reopen the bounded visible rerun path on the healthy `4181 + 8852` stack and repair the remaining runtime-side failure that still terminalizes the authoritative run with `thread/start` timeout / terminal-collection / interrupt-reconciliation errors after dispatch.

### 2026-07-15 - Step 21 reconcile recovery 44 completed

- Root-cause tightening: the remaining Step 21 backend/runtime defect was not only the later node's `thread/start` timeout. When a later node failed after at least one sibling had already started, `_reconcile_graph_live_started_turns(...)` could flatten that started sibling into `interrupt_failed` as soon as `turn/interrupt` cleanup timed out, without one more bounded attempt to read and commit a recoverable terminal result.
- Runtime repair: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py` now performs one extra bounded terminal probe after a reconcile-time exception. If the started execution is already terminal and `_commit_graph_live_reconciled_execution_result(...)` succeeds, the record is promoted to `terminal_result_committed_after_reconcile_error` instead of being discarded as `interrupt_failed`. The same slice also tightened strict-thread `no_tools` cleanup so deferred execution-policy clearing only applies to `turn/completed`, not to `turn/aborted`.
- Regression coverage: `apps/astrabridge-sidecar/tests/test_task_graph_worker_runtime.py` now includes a focused case proving a started node can still commit terminal output after `interrupt_turn(...)` times out during reconciliation, plus the existing aborted-terminal and timeout coverage. `python -m pytest apps/astrabridge-sidecar/tests/test_task_graph_worker_runtime.py -q` passed `39 passed, 3 subtests passed`. `python -m pytest apps/astrabridge-sidecar/tests/test_task_graph_api.py -k "live_task_graph_run_endpoint or exposes_live_task_graph_run_route or get_route_returns_compact_task_graph_refs" -q` passed `4 passed`.
- Acceptance impact: this slice does not claim to eliminate the visible rerun's later-node `thread/start` timeout. It does remove one concrete source of backend result lossiness, so the next bounded visible rerun should show whether already-started siblings now commit truthful terminal output while the remaining failure narrows to the still-failing node-start path.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260715-step21-reconcile-recovery-44/step21-reconcile-recovery-44.md` and `.json`.
- Safety and cost: no new provider-backed visible rerun was issued in this slice; verification stayed local to runtime/API tests, so additional token/cost remained `not_applicable`. No plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: completed with a narrowed blocker.
- Next entry: reopen the bounded visible rerun path on the healthy `4181 + 8852` stack, verify that started siblings now survive reconcile-time interrupt flakiness, and then isolate the remaining backend failure on the later node `thread/start` path if the run still ends as failed.

### 2026-07-15 - Step 21 bootstrap recovery 45 completed

- Root-cause tightening: the recurring visible white/startup-failure behavior was no longer just browser-bridge noise. The desktop bootstrap entry itself had become corrupted (`index.html` mojibake, malformed closing tags, broken startup interpolation), and the bootstrap-shell watcher stopped polling as soon as it entered `error`, which allowed a late-arriving AppShell to mount underneath a stale startup-failure overlay.
- Frontend repair: `apps/astrabridge-desktop/index.html` was rewritten into a clean valid bootstrap entry with corrected copy, valid markup, one-shot bounded self-recovery, and no-loop auto-reload behavior. `apps/astrabridge-desktop/src/main.tsx` startup copy was repaired. `apps/astrabridge-desktop/src/bootstrapShell.ts` now allows late-visible app surfaces to clear the bootstrap shell even after a temporary error-state transition instead of pinning the failure overlay forever.
- Regression coverage: `apps/astrabridge-desktop/src/bootstrapShell.test.ts` now proves that a late app-shell appearance still drives the bootstrap state to `ready` after an earlier error-state read. `node .\\node_modules\\vitest\\vitest.mjs run src\\bootstrapShell.test.ts` passed `4/4`. `node .\\node_modules\\vite\\bin\\vite.js build` also passed.
- Visible browser verification: through the in-app browser only, stale tabs were finalized so the page did not keep accumulating broken shells. A fresh clean tab on `4181 + 8852` reached `bootstrapState=ready`, `hasAppShell=true`, and `hasBootstrapRoot=false`, and the same clean tab could enter Task Graph again (`hasTaskGraphWorkspace=true`).
- Residual note: rapid repeated reloads can still degrade the Codex in-app browser CDP bridge even while `http://127.0.0.1:4181` and `http://127.0.0.1:8852/health` both remain healthy. Record that as browser-control transport instability, not as a fresh AstraBridge frontend outage.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260715-step21-bootstrap-recovery-45/step21-bootstrap-recovery-45.md` and `.json`.
- Safety and cost: no provider-backed visible rerun was dispatched in this slice; additional provider token/cost remained `not_applicable`. No plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: completed with a narrowed blocker.
- Next entry: return to the bounded visible task-graph rerun line on the cleaned single-tab `4181 + 8852` stack and continue isolating the remaining backend/runtime live-run failure.

### 2026-07-15 - Step 21 live-dispatch confirmation repair 46 completed

- Root-cause tightening: the strongest remaining Step 21 desktop defect was no longer the white-page/bootstrap path. On the cleaned single-tab `4181 + 8852` stack, a visible `direct-run` could still leave the task-graph UI in optimistic `running` chrome even when no fresh authoritative `graph-run-live-*` directory appeared and task state still pointed to the prior failed run. That meant the operator could see a fake active run instead of a fail-closed terminal diagnostic.
- Desktop repair: `apps/astrabridge-desktop/src/features/runtime/taskGraphRunDispatch.ts` now exposes `hasTaskGraphLiveDispatchTimedOut(...)`, and `apps/astrabridge-desktop/src/App.tsx` now computes the latest authoritative active run for the current graph, starts a bounded `4s` confirmation window once optimistic live dispatch begins, clears optimistic live refs when no authoritative active run appears in time, invalidates the task/sidebar/task-graph queries, and surfaces a structured visible error instead of leaving fake `running` chrome in place.
- Regression coverage: `apps/astrabridge-desktop/src/features/runtime/taskGraphRunDispatch.test.ts` now covers the bounded confirmation timeout behavior. `node .\\node_modules\\vitest\\vitest.mjs run src\\features\\runtime\\taskGraphRunDispatch.test.ts src\\features\\runtime\\taskGraphRunRefs.test.ts src\\api.test.ts` passed `35/35`, and `node .\\node_modules\\vite\\bin\\vite.js build` passed.
- Browser-control recheck: the in-app browser runtime reattached and stale AstraBridge tabs were closed before opening a fresh single tab on the same `4181 + 8852` URL. After that reset, `dom_cua.get_visible_dom()` returned empty content and screenshot was denied by the browser-use URL policy for that blocked page state. Record this as browser-control verification instability / URL-policy interference, not as proof that the product repair failed.
- Acceptance impact: this slice closes the misleading frontend state that could mask a missing authoritative live run as `running`. It does not yet claim the underlying backend live-run creation path is healthy. A fresh bounded visible rerun is still required to verify that the repaired frontend now fails closed on the real surface and then to isolate any remaining backend failure truthfully.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260715-step21-live-dispatch-confirmation-repair-46/step21-live-dispatch-confirmation-repair-46.md` and `.json`.
- Safety and cost: provider calls `0`, provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: completed with a narrowed blocker.
- Next entry: return to the cleaned single-tab `4181 + 8852` task-graph rerun line, issue one bounded visible `direct-run`, and verify that optimistic pending chrome now clears within the confirmation window when no authoritative live run appears before diagnosing any remaining backend failure.

### 2026-07-15 - Step 21 visible timeout + bootstrap recovery 47 completed

- Root-cause closure: one remaining visible Step 21 defect lived above the earlier `4s` fail-closed timeout. Even after optimistic live refs were cleared, the task-graph toolbar and latest-run projection could still stay pinned to a forever-pending `runTaskGraph` mutation. In parallel, slower in-app reloads could still show a stale bootstrap failure overlay even after the real `app-shell` had mounted.
- Desktop repair: `apps/astrabridge-desktop/src/App.tsx` now derives task-graph UI pending from `runTaskGraph.isPending && taskGraphLiveDispatchStarted`, so button disabling, cached-active projection, and refresh polling stop as soon as the visible dispatch-confirmation window closes. `apps/astrabridge-desktop/index.html` now installs a bootstrap `MutationObserver` that calls `ready(...)` as soon as `[data-testid='app-shell']`, `.launcher-shell`, or `.launch-isolation-shell` appears, even if the page previously entered `stalled` or `error`.
- Focused diagnostics: a headless capture first exposed the regression `Cannot access 'taskGraphLiveRunUiPending' before initialization`; that TDZ bug was then fixed and revalidated. The post-fix captures at `PRIVATE/app-standardization-ui-dogfood/captures/20260715-whitepage-diagnose-after-fix.json` and `.../20260715-bootstrap-overlay-after-fix.json` show normal content with no `console_issues`.
- Visible in-app verification: a stale task tab `55` was closed and verification continued in one fresh visible tab `56`. Through only visible UI, the operator re-entered `任务图`, clicked `直接运行`, waited `6500 ms`, and confirmed that `直接运行` / `夹具运行` were enabled again with no surviving `optimistic-live` residue in the visible DOM excerpt.
- Acceptance impact: the current Step 21 frontend/browser blocker is closed. The visible task-graph surface now fails closed instead of pinning fake `running` chrome, and the bootstrap overlay no longer blocks a mounted app shell on the recovered startup path.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260715-step21-visible-timeout-bootstrap-recovery-47/step21-visible-timeout-bootstrap-recovery-47.md` and `.json`.
- Safety and cost: provider-backed live-run confirmations `0`, additional provider tokens `0`, cost `not_applicable`; no plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 21 follow-up status: completed.
- Next entry: Step 22. Through the visible Automation UI only, run `DG-AUTOMATION-HANDOFF-01`, preserve screenshots plus token/cost signals, and record any remaining automation-surface defects.

### 2026-07-15 - Step 22 automation UI blocker recorded

- Visible progress: the Automation surface was reopened on the healthy `4181 + 8852` stack, the `收件箱与运行记录` disclosure was expanded, and the selected `step17-watchdog-stale` automation was visibly edited into a bounded Step 22 live check (`DG-AUTOMATION-HANDOFF-01 Live Repo Check`) with `deepseek-default`, a read-only repo/doc-drift prompt, and bounded finding keywords.
- Stronger diagnosis: the visible editor showed a timeout-style `自动化操作失败` banner after save, but authoritative evidence proved the save path itself succeeded. The sidecar log recorded `POST /api/automations/update HTTP/1.1 200`, and read-only `GET /api/automations` returned the updated Step 22 automation state.
- Product blocker: the UI did not reconcile that successful save back into a clean success/idle state, and the required visible `立即运行` path still did not yield a fresh authoritative automation run for the edited automation. Read-only `GET /api/automations/runs` still showed only the historical `step17-watchdog-stale-run-20260703` record.
- Consistency finding: during the same slice, the expected workspace file search under `PRIVATE/demo-runs/provider-switch-live-20260622-224524/workspace/.astrabridge/automations/automations.json` did not reflect the new Step 22 name/prompt even though the authoritative sidecar response did. Treat this as a persistence-path or flush-consistency defect until the canonical storage path is proven.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-AUTOMATION-HANDOFF-01/step22-automation-ui-blocker-20260715.md` and `.json`, plus captures `20260715-step22-automation-panel-current.png`, `20260715-step22-before-scroll.png`, and `20260715-step22-after-run-click.png`.
- Safety and cost: confirmed provider-backed run count this slice `0`; usage/cost remained `not_available`. No plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 22 follow-up status: blocked on product repair.
- Next entry: remain at Step 22. Repair automation save-state synchronization, visible run-now dispatch feedback, and canonical persistence reflection; then repeat the same visible `DG-AUTOMATION-HANDOFF-01` execution path and capture history/inbox/artifact plus token/cost evidence.

### 2026-07-15 - Step 22 automation feedback repair 48 recorded

- Desktop repair: the automation surface now clears stale mutation-error state before the next action, injects successful create/update/run/inbox responses directly into the local query cache, and surfaces a compact positive notice instead of waiting for the next polling round to prove that a save or run succeeded.
- Timeout repair: `run-now` now uses an explicit `300000 ms` request budget because the current sidecar endpoint executes the automation synchronously and can legitimately exceed the generic mutation timeout.
- Route-safety improvement: automation profile ordering now prefers providers whose secret is currently loaded in sidecar health, so newly created automations do not default to a provider that is present in catalog metadata but unavailable at runtime when a working option exists. In the current stack, `qwen` is the only provider with `secret_loaded: true`.
- Verification: `pnpm vitest run src/features/automations/automationQueryCache.test.ts src/features/automations/AutomationsPanel.test.tsx`, `pnpm exec tsc --noEmit -p tsconfig.json`, and `pnpm exec vite build` all passed.
- Residual blocker: visible acceptance is still blocked outside AstraBridge product HTTP health. A fresh in-app browser reconnect still fails on `iab.tabs.new() -> tab.goto(...)` with `Timed out waiting for the Browser webview to attach for this browser-use page`, even though `4181` serves the Vite entry and `8852/health` returns `ok: true`.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/repairs/20260715-step22-automation-feedback-repair-48/step22-automation-feedback-repair-48.md` and `.json`.
- Safety and cost: provider-backed live reruns this slice `0`; usage/cost remained `not_applicable`. No plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 22 follow-up status: still blocked on visible in-app browser recovery, but the product-side automation save/run feedback chain is materially narrowed.
- Next entry: remain at Step 22. Recover the Codex in-app browser attach path, then rerun the bounded Automation UI flow visibly with `qwen-default` and capture fresh history/inbox/artifact evidence plus token or `not_available` cost signals.

### 2026-07-15 - Step 22 automation fail-closed verification 49 completed

- Visible recovery: reclaimed the single visible `4181 + 8852` in-app browser tab after sidecar reload, reloaded it successfully, reopened `工具 -> 自动化`, waited for automation hydration, and reselected `DG-AUTOMATION-HANDOFF-01 Live Repo Check` through visible UI only. No extra broken tabs were left behind.
- Product acceptance result: the selected standalone automation now fails closed on the visible surface. With `qwen-default`, the inline guard notice remained visible and the `立即运行` button stayed disabled with the explicit authority reason `Model has no verified structured tool-calling surface.` No provider-backed standalone run was issued.
- Additional hardening completed in source: frontend standalone automation gating now also blocks providers whose managed-runtime key is not loaded, and backend standalone execution now requires a loaded provider key before dispatch. That closes the earlier hole where a read-only automation could remain clickable and only fail later inside the runner.
- Verification: `pnpm vitest run src/features/automations/automationProfileGate.test.ts src/features/automations/AutomationsPanel.test.tsx`, `pnpm exec tsc --noEmit -p tsconfig.json`, `pnpm exec vite build`, and `python -m pytest apps/astrabridge-sidecar/tests/test_automation_api.py -q` all passed.
- Environment truth recorded: on the live `8852` stack, `qwen` is the only provider with `secret_loaded: true`, but it remains authority-tier `C`; the other listed providers currently show `secret_loaded: false`. Under this real managed-runtime state, the correct Step 22 acceptance is a visible pre-dispatch block, not a token-consuming standalone run.
- Evidence: `PRIVATE/app-standardization-ui-dogfood/runs/DG-AUTOMATION-HANDOFF-01/20260715-step22-visible-rerun-49/step22-visible-rerun-49.md`, `.json`, and screenshots `preflight.png`, `automation-form.png`, `post-fix-qwen-blocked.png`.
- Safety and cost: provider-backed automation requests `0`; usage/cost remained `not_available`. No plaintext secret source, raw provider payload, cookie, authorization material, or external writeback was read or persisted.
- Step 22 follow-up status: completed.
- Next entry: Step 23. Use the now-stable automation fail-closed evidence together with the Step 16/18/20 findings to close the remaining release-gate repairs, then prepare the independent verifier pass.

### 2026-07-15 - Step 23 final release gate completed

- Completed: repaired the full sidecar regression baseline exposed by the prior gate. `Pillow` is now declared as a runtime dependency for asset crop/resize promotion; `pytest` and `jsonschema` are declared in the development dependency group; `uv.lock` was regenerated; and generated `*.egg-info` metadata is excluded from governance source scanning and git staging. A regression test protects the generated-metadata boundary.
- Full verification: `scripts/run_local_gate.py --full` passed. Governance and secret scan both reported zero errors and zero warnings; the contract boundary audit passed; sidecar unittest discovery passed `884` tests; desktop tests passed `61` files / `448` tests; and the production build passed with only the existing Vite chunk-size warning. The independent sidecar pytest breakdown was `382` service tests plus `501` tests and `98` subtests.
- Visible verification: the stale zero-viewport tab was closed instead of retained. Exactly one replacement in-app tab was opened on `4181 + 8852`; the managed `astra` session was visible; Task Graph and Dry-run were opened and triggered through native visible clicks; and the run-check modal showed `pass 11 / 0 / 0` with no blocked or warning checks. Final screenshot: `PRIVATE/app-standardization-ui-dogfood/final/20260715-step23-release-gate/task-graph-dry-run-final.png`.
- Process and safety: the owned stale high-CPU sidecar was reaped before relaunch; the final listener audit found only the expected frontend `4181` and sidecar/router `8852/8787` instances. Provider calls and token/cost were `0`; no key file, Vault password, cookie, authorization header, provider secret, or raw provider payload was read or persisted.
- Remaining risk: the current route visibly reports unverified structured/MCP tool capability warnings and the Vite chunk-size warning; both are intentionally surfaced and fail closed. Rapid repeated reloads can still destabilize the external browser-control transport, but the final single-tab screenshot gate passed. These are documented residual risks, not Step 23 blockers.
- Step 23 follow-up status: completed.
- Next entry: no remaining step in this plan. Start a new independent plan for later provider expansion, live dogfood, browser transport hardening, or chunk-splitting work.
