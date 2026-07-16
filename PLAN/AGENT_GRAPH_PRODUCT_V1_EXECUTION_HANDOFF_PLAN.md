# Agent Graph Product V1 Execution Handoff Plan

## Total Objective

把 AstraBridge 当前的 Agent Graph 收敛成一个真正可交付的 V1 产品切片：它既要像 ComfyUI 一样以画布为中心、通过 GUI 进行节点编排，也要像现代 coding/agent workflow 系统一样支持代码式编排、受控 subagent 并行、默认上下文隔离、结构化 handoff、能力感知的多模型多模态路由，以及可验证、可回滚、可维护的运行时。

这份计划不是再造一套新系统，而是要求 GUI、代码编排、dry-run、runtime、run inspection、recovery、evidence preservation 全部共用同一份 canonical graph contract。

## Deliverables

- 一份冻结后的 Agent Graph V1 产品切片定义与验收矩阵。
- 一份共享给 GUI / code / runtime 的 canonical graph contract 收敛结果。
- 一条可用的代码式编排入口，支持 lint、dry-run、import/export、diff、migration。
- 一套画布优先的 GUI 编排工作台，支持节点添加、连线、编辑、运行、检查、恢复。
- 一套受控 subagent 并行与 typed handoff 的 runtime 路径。
- 一套多模态、多 provider、多模型能力感知的节点能力暴露与阻断机制。
- 一份供后续 agent 使用的维护/修复 skill 或 runbook。
- 一套 click-driven、screenshot-driven 的验收证据，保存到 `PRIVATE/agent-graph-product-v1/**`。

## Related Context Files

- `D:\AstraBridge\PLAN\AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md`
- `D:\AstraBridge\PLAN\AGENT_GRAPH_GUI_RUNTIME_HANDOFF_EXECUTION_PLAN.md`
- `D:\AstraBridge\PLAN\AGENT_GRAPH_MULTIMODAL_PRODUCT_EXECUTION_PLAN.md`
- `D:\AstraBridge\PLAN\AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
- `D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\agent_orchestration_contract.py`
- `D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\agent_orchestration_file_format.py`
- `D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\agent_orchestration_compiler.py`
- `D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\task_service.py`
- `D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\runtime_service.py`
- `D:\AstraBridge\apps\astrabridge-desktop\src\features\runtime\TaskGraphWorkspace.tsx`
- `D:\AstraBridge\apps\astrabridge-desktop\src\features\runtime\TaskGraphWorkspace.test.tsx`
- `D:\AstraBridge\apps\astrabridge-desktop\src\App.tsx`
- `D:\AstraBridge\apps\astrabridge-desktop\src\styles.css`

## Constraints And Attention Notes

1. 不允许再分裂出 GUI 专用 graph shape、code 专用 graph shape、runtime 专用 graph shape。
2. 主路径必须是 `Project -> Task -> Graph`，不能绕开产品边界做一套隐藏工作流系统。
3. 默认上下文隔离必须成立；跨节点通信只能通过显式 edge contract、artifact contract、summary contract 或 typed payload 发生。
4. visible UI 的验收必须通过真实产品表面的模拟点击、输入、拖拽、悬停、滚动、收起、展开、resize、reload 来完成。
5. 禁止把 API 写入、store patch、fixture preload、console injection、直接 sidecar 状态突变当作 GUI 成功证据。
6. 每个 GUI 步骤都必须高频截图，并在截图审查中主动检查以下问题：
   - 卡片堆叠
   - 字体过大
   - 低语义文本占据主空间
   - 无意义图标
   - 多余外框
   - 侧栏过宽或不可拉伸
   - inspector 溢出
   - 画布不再是主区域
   - 控件脱离对象上下文
7. 画布必须是主工作区；说明性文案、运行摘要、低价值 metadata、调试信息默认应退到 inspector、tooltip、折叠区或 hover 卡片。
8. 主 agent 编排默认保持浅层结构：一层 supervisor，加若干 worker，加 synthesizer/validator/reviewer。更深嵌套必须记录理由。
9. 多模态和 provider/model 能力暴露必须以官方文档、capability metadata、或已保存 smoke evidence 为依据，不得凭想当然开放能力。
10. 保留日志、截图、run manifest、dry-run 输出、validation note、失败痕迹；未经用户点名不得清理。
11. 不得在计划、报告、截图、日志、工件中保存 API key、token、cookie、auth header、vault 原始内容或其他秘密。
12. 未来 agent 可以调整子步骤和实现顺序，但不得降低目标、移除 click-driven 验收、弱化 context isolation、或把硬问题替换成表层美化。

## Adjustment Policy

后续执行 agent 可以根据仓库现状调整子步骤、文件名、命令、测试入口、证据目录、UI 控件实现方式与执行顺序，但这些调整不能：

- 改变总目标；
- 把 GUI 验收偷换成 API 验收；
- 新造一套与 canonical graph contract 脱节的执行路径；
- 取消默认上下文隔离；
- 用纯文档、纯样式、纯 fixture 替代 runtime 和真实产品路径。

如果发现当前路线陈旧或失焦，必须先在本计划中记录 evidence、diagnosis、route change、what must not be weakened、exact next step，再继续。

## Evidence Review And Plan Revision Policy

执行每一步前都要检查是否需要修订计划。出现以下任一情况，先修计划再执行：

1. 代码、runtime、UI 证据表明当前下一步不是最高杠杆阻塞点。
2. 测试通过，但真实产品表面走不通。
3. GUI 截图仍明显暴露卡片大战、信息冗余、字体过大、画布被挤压等问题。
4. 多模态/能力矩阵与当前 graph UI 或 runtime 表达不一致。
5. 已完成步骤的验收标准不足以支撑 V1 产品切片。
6. 后续步骤开始偏向包装或修饰，而真正缺的是 contract、runtime、inspection 或 authoring 核心链路。

每次修订都必须记录：

- evidence inspected
- diagnosis
- route change
- what must not be weakened
- exact next step

## Execution Rules

1. 每次执行前先读本计划，并检查是否触发计划修订。
2. 默认一次只完成一个编号步骤，除非用户明确要求多做。
3. 每次执行结束前必须更新本计划。
4. 步骤只有在所有 acceptance criteria 满足后才能标记为 `completed`。
5. GUI 相关步骤必须先走 visible product path，再允许用底层接口做诊断。
6. 每次 GUI 验收至少保留：
   - 起始截图
   - 进入目标面的截图
   - 每个关键交互后的截图
   - 最终状态截图
   - reload/reopen 后截图
   - 至少一个 constrained-width 或侧栏压力测试截图
   - 一份 validation note，写清楚具体点击路径与剩余摩擦
7. Runtime 相关步骤必须保留 deterministic test 和至少一份 durable artifact，例如 compiled plan、run manifest、typed envelope、recovery manifest 或 event trace。
8. 最终交接必须明确：完成内容、修改文件、验证命令、证据路径、阻塞点、下一步入口。

## Evidence Convention

- 默认证据根目录：`PRIVATE/agent-graph-product-v1/<step-id>/<YYYYMMDD>/`
- GUI 步骤至少保存：
  - `01-start.png`
  - `02-entry.png`
  - `03-...png` 系列关键交互截图
  - `final.png`
  - `reload.png`
  - `narrow.png`
  - `validation-note.md`
- Runtime 步骤至少保存：
  - `report.md`
  - `validation-summary.json`
  - 对应测试输出摘要
  - sanitized manifests / traces / envelopes

## Current Progress

- Current status: In progress
- Completed steps: Step 0, Create Durable Plan
- Current step: Step 1, Freeze V1 Product Slice And Acceptance Matrix
- Next step: Step 1, Freeze V1 Product Slice And Acceptance Matrix
- Last updated: 2026-07-09

## Execution Steps

### 0. Create Durable Plan

Goal: 创建这份可交接、可验收、可持续更新的执行计划。

Main actions:

- 定义 V1 目标、约束、验收方式和证据规则。
- 将 GUI、code、runtime、skill、multimodal、subagent 等要求收敛到一个执行框架中。
- 给出明确的下一步入口。

Acceptance criteria:

- 计划文件已经写入仓库。
- 计划包含 objective、constraints、adjustment policy、evidence policy、current progress、execution steps、acceptance criteria、progress log。
- 下一步入口明确。

Status: completed

### 1. Freeze V1 Product Slice And Acceptance Matrix

Goal: 把“像 ComfyUI 一样的多模型多模态 agent graph 产品”收敛成一个可交付 V1 切片与明确验收矩阵。

Main actions:

- 审视现有仓库和产品表面，列出 must-have、nice-to-have、deferred、out-of-scope。
- 定义 V1 必须闭环的用户路径：graph authoring、node/edge editing、fixture run、run inspection、recovery、code round-trip、capability-aware blocking。
- 写出 V1 acceptance matrix 和非目标列表。

Acceptance criteria:

- 产出一份 V1 acceptance matrix 报告。
- 明确至少 3 条必须跑通的真实用户路径。
- 明确至少 3 条暂不进入 V1 的非目标。
- 明确后续实现的最高杠杆阻塞点。

Status: not started

### 2. Consolidate Canonical Graph Contract

Goal: 锁定 GUI / code / runtime 共用的 canonical graph contract。

Main actions:

- 对齐 node、edge、port、artifact、handoff、context policy、execution policy、approval policy、output schema。
- 明确 schema version、migration、import/export round-trip 要求。
- 消除不同路径对同一 graph 的字段漂移。

Acceptance criteria:

- 合同定义和现有实现对齐，且有差异清单。
- 至少一组 graph 示例可以 round-trip 不丢关键字段。
- 不再存在 GUI/runtime/code 各自发明核心结构字段的情况。

Status: not started

### 3. Harden Code-First Orchestration Interface

Goal: 提供和 GUI 对等的代码编排入口，而不是第二套暗门。

Main actions:

- 收敛 graph file / JSON / DSL 入口。
- 提供 lint、dry-run、diff、migration、import/export 命令或 API。
- 补齐典型示例：代码修复流、研究 fan-out/fan-in、多模态能力 gate。

Acceptance criteria:

- 代码定义的 graph 可以被 GUI 导入、编辑、导出、再导入。
- 关键 contract 字段不会在 round-trip 中丢失。
- 命令或接口具备明确的错误反馈与校验输出。

Status: not started

### 4. Rebuild Node Library And Typed Wiring Entry

Goal: 让用户能通过可见 UI 快速发现并创建节点、连线和端口关系。

Main actions:

- 重新组织左侧 library，collapsed 模式只保留高信号图标和 hover 提示。
- expanded 模式突出模板、节点类型、端口/能力语义，而不是大段说明文字。
- 为常见 agent 类型和 edge 属性建立稳定图标系统。

Acceptance criteria:

- 用户可通过 visible UI 添加至少 3 类常用节点。
- 常见连线语义在默认画布上可通过图标/简写识别，细节通过 hover 或 inspector 查看。
- 左侧 rail 收起后明显为画布腾出空间。

Status: not started

### 5. Make The Canvas The Primary Workspace

Goal: 修正当前 task graph 页面的“卡片大战”和主次颠倒问题。

Main actions:

- 清理多余背景卡片、冗余标题块、重复摘要块、无意义边框。
- 把低价值信息迁移到 tooltip、hover 卡片、折叠区或 inspector。
- 让顶部控制、底部运行状态、左右侧栏都退居次位。

Acceptance criteria:

- 画布成为任务图页面最显著的主空间。
- 说明性文字不再占据 prime space。
- 截图审查中看不到明显的 stacked cards、oversized text、redundant frames。

Status: not started

### 6. Make Left And Right Sidebars Resizable And Secondary

Goal: 让任务图左右侧边栏真正变成用户可控的辅助面板。

Main actions:

- 为左侧 library 和右侧 inspector 提供可见的 resize 行为。
- 默认宽度收敛，支持 collapse / expand。
- 修复 overflow、滚动、挤压画布、控件断裂等问题。

Acceptance criteria:

- 用户可以通过可见控件拖拽左右侧栏宽度。
- collapsed 后真正腾出空间，而不是留下一条浪费区域。
- constrained-width 截图下仍然可用。

Status: not started

### 7. Redesign The Inspector As Object-Context Editing

Goal: 让 inspector 成为和当前选中对象强绑定的编辑与检查面板。

Main actions:

- 将节点、边、run、artifact 的详细编辑与检查收敛到右侧 inspector。
- 清理漂浮在画布或底部的低价值详情块。
- 优化 typography、section hierarchy、advanced settings、save/reset 位置。

Acceptance criteria:

- 选中 node/edge/run 后 inspector 呈现出明确的对象上下文。
- 重要控件不再脱离对象语境。
- inspector 在常见宽度下没有严重溢出和字体失衡。

Status: not started

### 8. Finish Node And Edge Contract Editing

Goal: 让用户能通过 GUI 编辑 prompt、provider/model、output schema、handoff、context policy。

Main actions:

- 补齐节点配置：prompt template、provider/model、tool policy、output contract、subagent policy、execution settings。
- 补齐边配置：context policy、artifact inclusion、summary strategy、typed handoff。
- 加入 inline validation 和持久化校验。

Acceptance criteria:

- 用户可通过 GUI 编辑代表性 node 和 edge，并保存成功。
- 非法配置会被显式阻断并给出可理解反馈。
- reload/reopen 后编辑结果仍存在。

Status: not started

### 9. Harden Runtime Semantics For Bounded Subagents

Goal: 把 subagent 并行执行、合流、恢复做成受控 runtime 能力。

Main actions:

- 收敛 fan-out、fan-in、retry、cancel、resume、partial rerun、approval gate 行为。
- 保留 worker lineage、typed input/output envelope、event trace、recovery manifest。
- 明确阻断不支持的深层嵌套或危险共享模式。

Acceptance criteria:

- deterministic tests 覆盖至少 success、parallel、join、cancel、retry、resume。
- runtime 产生 durable run artifacts 且不覆盖旧 run。
- unsupported 模式会显式失败而不是静默通过。

Status: not started

### 10. Land Capability-Aware Multimodal Surface

Goal: 把多模态能力暴露成可理解、可阻断、可扩展的 graph 能力面。

Main actions:

- 定义 text、image、audio、video、document、structured result、tool result、agent report 等 typed ports。
- 将 provider/model capability metadata 和 graph authoring/dry-run/runtime 对齐。
- 对不支持的组合在 authoring 或 dry-run 阶段就阻断。

Acceptance criteria:

- 用户能看出一个节点支持哪些输入输出模态。
- 至少一条多模态路径能通过 fixture/typed artifact 跑通。
- 至少一条不支持路径会被明确阻断并解释原因。

Status: not started

### 11. Build A Usable Run Monitor And Recovery Surface

Goal: 让运行、检查、恢复在产品表面可理解，而不是靠日志猜。

Main actions:

- 收敛 run summary、timeline、node outputs、edge handoffs、artifact access、diagnostics。
- 让 cancel、retry、resume、partial rerun 有 visible controls 和结果反馈。
- 避免 run 面板把画布重新挤成次要区域。

Acceptance criteria:

- 用户可以从 GUI 检查至少一个 node output、一个 edge handoff、一个 artifact。
- 用户可以完成至少一个 cancel/recovery 路径。
- 运行信息高信号、可理解、不过度占画布。

Status: not started

### 12. Create The Agent Repair And Operation Skill

Goal: 让后续 agent 能以规范方式维护和修复这套产品。

Main actions:

- 创建或更新 skill/runbook，约束 graph 修改、runtime 修复、能力适配修复、UI 验收。
- 强制要求 GUI claim 通过 simulated clicks 和截图证明。
- 记录新增 provider/model/node type 的标准扩展流程。

Acceptance criteria:

- 技能或 runbook 已写入仓库。
- 其内容足够让另一个 agent 不看聊天也能继续工作。
- 明确禁止用 hidden state 伪造 UI 成功。

Status: not started

### 13. Run End-To-End Click-Driven V1 Dogfood

Goal: 用真实产品表面证明 V1 核心路径已经闭环。

Main actions:

- 从 visible UI 完成至少 3 条代表性工作流：代码修复、研究 fan-out/fan-in、多模态/能力 gate。
- 覆盖 graph authoring 或 template instantiate、编辑、运行、检查、恢复、reload/reopen。
- 保留完整截图链、click transcript、run artifacts、validation note。

Acceptance criteria:

- 3 条代表性路径都能从真实产品表面完成。
- 证据能把 GUI 操作和后端 durable artifacts 对应起来。
- 剩余问题被明确记录，而不是模糊带过。

Status: not started

### 14. Final Regression Gate And Release Handoff

Goal: 把这条 V1 产品切片收尾成一个可维护交付物。

Main actions:

- 跑 focused tests、UI click 验证、secret-safety 检查。
- 写 final report，总结 supported、blocked、deferred。
- 更新本计划以及相关上位计划的状态与下一步入口。

Acceptance criteria:

- `PRIVATE/agent-graph-product-v1/final/<YYYYMMDD>/` 下存在最终报告。
- 报告区分已证明、被阻断、后续再做的能力。
- 未来 agent 无需回看聊天即可继续。

Status: not started

## Progress Log

### 2026-07-09 - Step 0

- Completed: 创建了收敛版 Agent Graph Product V1 执行交接计划，覆盖 GUI、code、runtime、multimodal、subagent、skill、evidence 几个主轴。
- Files changed:
  - `D:\AstraBridge\PLAN\AGENT_GRAPH_PRODUCT_V1_EXECUTION_HANDOFF_PLAN.md`
- Validation:
  - 重新阅读 durable handoff plan skill 与模板。
  - 对照仓库现有 agent-graph / orchestration / multimodal 计划，避免继续堆叠重复计划。
  - 本回合只落计划，不做产品代码变更。
- Blockers: None.
- Next step: Step 1, Freeze V1 Product Slice And Acceptance Matrix.
