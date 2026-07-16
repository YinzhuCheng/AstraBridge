# Capability Runtime Implementation Plan

Last updated: 2026-06-24

## 总目标

把 AstraBridge 的内置能力整理成稳定的 capability runtime，使调用方优先面向 capability 接口，而不是直接面向某个 provider 或某个 model。

本计划聚焦的目标边界如下：

- 保留现有生图接口与现有联网搜索接口，不做破坏式替换。
- 联网搜索继续单列为 standalone web lane，不把搜索服务做成 model-backed capability。
- 每个 capability 可以挂接多个 provider / model，只要模型能力满足且 adapter 合同兼容。
- 统一支持并持续完善以下能力面：
  - `image.generate`
  - `vision.analyze`
  - `speech.transcribe`
  - `speech.synthesize`
- capability runtime 对外继续通过 MCP 暴露，但内部以 capability 为主键完成路由、适配、验证与观测。
- 后续 agent 执行时，每轮从下一未完成步骤开始，只完成一步，然后更新本文件。

## 注意事项

- 不得把 API key、Bearer token、Cookie、原始鉴权头、provider raw secret 写入 git、文档、日志、报告或测试产物。
- 默认保留 `PRIVATE/**`、验证报告、原始请求记录、原始响应记录与烟测产物，但必须脱敏。
- 联网搜索保持为 standalone web lane：搜索结果的判断、筛选、归纳由调用方 LLM 负责，不在搜索服务内部内置 LLM 推理。
- capability runtime 不要强行把所有 provider 压成同一种 provider schema；adapter 层必须保留 provider-specific 协议差异。
- 新增 capability 时，必须同时补齐：
  - capability schema
  - provider adapter 合同
  - route / eligibility 规则
  - smoke case
  - MCP 暴露或 surface map 记录
- 默认优先复用现有 runtime config、provider profile、model catalog、desktop 设置面，不另起一套平行配置系统。
- 每轮对话只推进一个编号步骤；完成后必须更新本文件的“当前进度”和“完成记录”。

## 细节

### 1. 目标分层

- Capability layer：
  - 定义 capability id、输入输出 schema、错误语义、artifact 约定、可观测字段。
- Adapter layer：
  - 处理 provider / model 协议差异、请求构造、流式解析、artifact 落盘与错误归一化。
- Routing layer：
  - 负责 capability -> candidate adapters -> selected provider/model 的选择与失败回退。
- MCP exposure layer：
  - 对外暴露稳定工具名；工具内部按 capability 调用 runtime。

### 2. Web lane 与 capability runtime 的边界

- 以下接口保持为 standalone web lane，不进入 model-backed capability router：
  - `web.search`
  - `web.fetch`
  - `web.research_brief`
- 后续如果新增 `deep_search` 或更重的 research 工作流，也应建立在 web lane 之上，由外层 agent 或 LLM 组织多轮检索和结论生成。

### 3. 当前基线

- 已有 legacy / standalone surface：
  - web lane
  - image lane
- 已有 capability 方向的代码与实验基础，但需要进一步收敛成稳定执行面，而不是停留在一次性实现或烟测状态。
- 本计划不是从零开始重做，而是把已有能力整理成可持续扩展、可被后续 agent 连续落实的执行路线。

### 4. 推荐的 capability 元数据

每个 capability 至少应有：

- `capability_id`
- `display_name`
- `lane_type`
- `input_schema`
- `output_schema`
- `transport_mode`
- `artifact_policy`
- `provider_eligibility_rule`
- `default_timeout_sec`
- `smoke_case_id`
- `status`

### 5. 推荐的 adapter 元数据

每个 adapter 至少应有：

- `adapter_id`
- `capability_id`
- `provider_id`
- `model_selector`
- `supports_streaming`
- `request_builder`
- `response_parser`
- `artifact_persister`
- `error_normalizer`
- `smoke_case_id`
- `status`

## 实现步骤

- [x] 1. 固化 capability runtime 执行计划与步骤边界
  - 目标：
    - 把 capability runtime 的后续工作改写为可连续接力的 git 追踪计划。
    - 明确总目标、边界、顺序步骤、当前进度和单步执行规则。
  - 交付物：
    - `PLAN/CAPABILITY_RUNTIME_IMPLEMENTATION_PLAN.md`
  - 完成标准：
    - 后续 agent 能直接从本文件读取下一步入口。
    - 文档明确 web lane 单列、image 接口保留、多模型 capability 挂接这三个核心约束。
  - 验证方式：
    - 本文件存在且包含总目标、注意事项、细节、实现步骤、当前进度几个部分。

- [ ] 2. 盘点现有 capability surface、legacy surface 与缺口
  - 目标：
    - 建立当前 capability / legacy / MCP surface 的事实基线。
    - 区分“已实现但未规范化”和“尚未实现”的部分。
  - 交付物：
    - 更新 `PLAN/CAPABILITY_RUNTIME_SURFACE_MAP.md`
    - 补一份 gap 列表到本计划或同目录文档
  - 完成标准：
    - 能回答每个 capability 当前走哪条链路、缺什么、风险在哪。
  - 验证方式：
    - surface map 与 gap 记录已更新，且能覆盖 web / image / vision / ASR / TTS。

- [ ] 3. 收紧 capability schema 与 adapter 合同
  - 目标：
    - 把 capability 输入输出、错误语义、artifact 约定从“能跑”收紧到“稳定合同”。
    - 明确 provider-specific 字段如何隔离在 adapter 层。
  - 交付物：
    - sidecar capability specs / adapter contract 更新
    - 对应单元测试
  - 完成标准：
    - 新增或修改 adapter 不再靠零散 dict 约定字段。
  - 验证方式：
    - capability spec 相关测试通过。

- [ ] 4. 收紧 capability registry、eligibility 与 route 解析
  - 目标：
    - 让 runtime 能稳定回答“某 capability 当前有哪些候选 provider/model/adapter，默认选谁，为什么”。
    - 把 auto / pinned / unavailable 的错误语义做明确。
  - 交付物：
    - registry / route 逻辑更新
    - 对应测试
  - 完成标准：
    - capability 选择逻辑不再依赖零散静态判断。
  - 验证方式：
    - registry / route 测试通过。

- [ ] 5. 固化 `image.generate` capability 与 legacy image surface 的兼容边界
  - 目标：
    - 保持现有生图接口稳定，同时让 capability 侧成为正式入口之一。
    - 明确 image capability 的 artifact、编辑模式、透明素材模式合同。
  - 交付物：
    - image capability / adapter / surface map 更新
    - 对应回归测试
  - 完成标准：
    - legacy image tools 不回退，capability image path 合同明确。
  - 验证方式：
    - image 相关回归测试通过。

- [ ] 6. 固化 `vision.analyze` 的多模型接入面
  - 目标：
    - 把 `Qwen`、`Kimi` 这类视觉模型的接入差异稳定收敛到 adapter 层。
    - 让 capability 调用方不需要自己感知 provider 差异。
  - 交付物：
    - vision adapter / route / smoke 规则更新
    - 对应测试
  - 完成标准：
    - `vision.analyze` 能按 capability 路由切换候选模型。
  - 验证方式：
    - vision 单测和 smoke 记录通过。

- [ ] 7. 固化 `speech.transcribe` 的多模型接入面
  - 目标：
    - 把 ASR 输入、语言信息、时间戳、注释与 artifact 规则稳定下来。
    - 把已知的 provider 请求约束编码进 adapter 合同。
  - 交付物：
    - ASR adapter / route / smoke 规则更新
    - 对应测试
  - 完成标准：
    - `speech.transcribe` 的输入输出和错误语义稳定。
  - 验证方式：
    - ASR 单测和 smoke 记录通过。

- [ ] 8. 固化 `speech.synthesize` 的多模型接入面
  - 目标：
    - 把 TTS 文本输入、voice 选择、音频格式、流式组装和 artifact 规则稳定下来。
    - 为后续新增 provider 保留 adapter 扩展位。
  - 交付物：
    - TTS adapter / route / smoke 规则更新
    - 对应测试
  - 完成标准：
    - `speech.synthesize` 的能力合同稳定且可扩展。
  - 验证方式：
    - TTS 单测和 smoke 记录通过。

- [ ] 9. 打通 runtime 配置、desktop 管理面与 MCP 暴露
  - 目标：
    - 让 capability 默认路由、候选模型和可用状态能在 runtime 与 desktop 中被管理和观察。
    - 保持 MCP 暴露稳定，并把 web lane 与 capability lane 的差异明确给调用方。
  - 交付物：
    - runtime config / desktop / MCP surface 更新
    - 对应测试
  - 完成标准：
    - 调用方可以面向 capability 配置和调用，而不是手工硬编码 provider/model。
  - 验证方式：
    - desktop / runtime / MCP 相关测试通过。

- [ ] 10. 完成 smoke matrix、文档收尾与执行闭环
  - 目标：
    - 补齐 capability smoke matrix、收尾文档和后续维护规则。
    - 给后续新增 capability 留下明确模板。
  - 交付物：
    - 更新 smoke matrix
    - 更新 surface map / handoff / runbook
  - 完成标准：
    - capability runtime 的扩展方式、验证方式、兼容边界可追踪。
  - 验证方式：
    - smoke matrix 与收尾文档已更新并脱敏保存。

## 当前进度

- 当前阶段：`step_1_completed`
- 已完成步骤：`1 / 10`
- 下一步入口：`2. 盘点现有 capability surface、legacy surface 与缺口`
- 当前结论：
  - capability runtime 应以 capability 为主键，而不是以 provider/model 为主键。
  - web 搜索必须继续保持 standalone web lane。
  - 现有 image 接口应保留，并通过 capability 包装逐步规范化，而不是先做破坏式替换。
  - 后续执行不从零开始重做，而是基于当前仓库已有能力继续收紧接口、路由、观测与文档。

## 完成记录

- 2026-06-24：完成步骤 `1`。重写 `PLAN/CAPABILITY_RUNTIME_IMPLEMENTATION_PLAN.md`，把 capability runtime 后续工作整理为新的 10 步执行计划，明确了总目标、注意事项、分层细节、顺序步骤、当前进度，以及“每轮从下一未完成步骤开始且每轮只完成一步”的执行约束。

## Stability Plan Delegation (2026-07-16)

The capability runtime plan remains the capability-specific reference for capability schemas, provider eligibility, modality adapters, smoke coverage, and the standalone web-lane boundary. Its historical `2..10` steps must not be used to schedule work that changes the shared MCP protocol, cross-provider Agent Envelope, artifact contract, durable graph scheduler, or run-state semantics.

Those overlapping concerns are now owned by `PLAN/ASTRABRIDGE_STABILITY_PROTOCOL_AND_AGENT_RUNTIME_EXECUTION_PLAN.md`, which is the single active execution source for the stability/protocol upgrade. Capability-specific work may continue only when it does not create a second MCP, envelope, artifact, scheduler, or run-state contract. This is a routing clarification, not a reset of the completed capability step or its preserved evidence.
