# 五类能力真实场景 Dogfood 执行记录

Last updated: 2026-06-27

## 总目标

用真实但受控的场景验证 AstraBridge 的五类能力入口：

- 自动化
- 插件
- 技能
- 多模态能力路由
- 联网

本计划已经完成。它现在是历史执行记录和复核入口，不再是待执行计划。后续 agent 不应从本文档继续找未完成步骤；如果要做新一轮 dogfood，应另建或更新新的执行计划，并引用本文档作为基线。

## 注意事项

- 保留所有已生成截图、JSON 报告、raw run 记录和失败证据。
- 不读取、不保存、不提交桌面明文 key、API key、bearer token、cookie、Authorization header 或其他可复用秘密。
- 真实 provider 调用只能在用户明确授权的轮次执行；未授权时用 dry-run、fixture 或公开无敏感联网任务。
- 失败证据优先级不低于成功证据；失败场景必须保留截图、结构化报告、失败原因和下一步建议。
- 本文档中的旧完成记录已被压缩为可读摘要；详细原始证据仍在各步骤报告和截图路径中。

## 当前进度

- 当前阶段：`complete`
- 已完成步骤：`24 / 24`
- 下一入口：`complete`
- 汇总状态：`partial`

`partial` 的原因不是计划未完成，而是 dogfood 真实暴露了一个仍需产品后续修复的问题：自动化项目健康巡检场景中，`codex exec` 拒绝 reasoning effort `max`，导致该自动化场景保持失败；跨能力组合场景因此保持 `partial`。

## 统一证据

- 截图和前端报告根：`apps/astrabridge-desktop/output/playwright/real-scenario-dogfood/`
- 结构化报告 schema：`docs/REAL_SCENARIO_DOGFOOD_REPORT_SCHEMA.json`
- 证据说明：`docs/REAL_SCENARIO_DOGFOOD_EVIDENCE.md`
- dogfood ledger：
  - `apps/astrabridge-desktop/output/playwright/real-scenario-dogfood/step22-dogfood-ledger-summary.json`
  - `apps/astrabridge-desktop/output/playwright/real-scenario-dogfood/step22-dogfood-ledger-summary.md`
- 私有和运行时证据保留在 `PRIVATE/**`、workspace-local `.astrabridge/` 和 app runtime 根中，不应自动清理。

## 场景结果

| 场景 | 结果 | 关键证据 |
| --- | --- | --- |
| 插件 fixture 生命周期 | `pass` | 受控 fixture 插件可发现、可安装/apply、可引用、可复核。 |
| Plugin Creator 技能场景 | `pass` | 生成受控插件脚手架、报告种子和校验产物。 |
| 自动化项目健康巡检 | `fail` | UI 链路可创建/运行/回看，但 runtime 因 reasoning effort `max` 被 `codex exec` 拒绝。 |
| 多模态能力路由 dry-run | `pass` | `vision.analyze` 与语音相关 dry-run smoke 通过；未授权 provider smoke 被记录为跳过而不是失败。 |
| 联网普通搜索与深度搜索 | `pass` | 公开 OpenAI 文档任务通过，来源和 record id 可复核。 |
| 跨能力组合任务 | `partial` | 技能、多模态、联网证据可用；自动化失败被纳入组合报告。 |

## 实现步骤

- [x] 1. 建立五类能力入口与已知阻塞基线。
- [x] 2. 修复深度搜索直接渲染崩溃。
- [x] 3. 强化深度搜索运行态、失败态和 stale-result UI。
- [x] 4. 定义统一证据目录、命名规则和 dogfood 报告 schema。
- [x] 5. 设计并落地插件 fixture 契约。
- [x] 6. 打通插件安装或注册的幂等基础链路。
- [x] 7. 完善插件 UI 的真实可用状态。
- [x] 8. 完成插件生命周期真实验收。
- [x] 9. 设计技能真实任务 fixture 与产物规范。
- [x] 10. 打通技能任务报告链路。
- [x] 11. 完善技能 UI 的执行证据呈现。
- [x] 12. 完成技能真实验收。
- [x] 13. 设计自动化“项目健康巡检”场景。
- [x] 14. 打通自动化创建、运行与回看链路。
- [x] 15. 完成自动化真实验收，并保留 reasoning effort `max` 失败证据。
- [x] 16. 设计多模态能力路由 dry-run 与可选真实 smoke 场景。
- [x] 17. 打通多模态 smoke 报告与状态展示。
- [x] 18. 完成多模态能力路由真实验收。
- [x] 19. 定义联网真实任务白名单与失败判定规则。
- [x] 20. 完成联网真实验收与深度搜索复验。
- [x] 21. 设计并执行端到端组合 dogfood 任务。
- [x] 22. 汇总五类场景证据到 dogfood ledger。
- [x] 23. 运行全量测试、构建、Tauri check、sidecar unittest 和秘密扫描。
- [x] 24. 关闭本计划，记录残留风险和复核入口。

## 完成记录摘要

- 2026-06-26：步骤 1-4 建立五类能力 dogfood 基线，修复深度搜索白屏和状态表达，新增统一报告 schema 与证据说明。
- 2026-06-26：步骤 5-8 落地受控插件 fixture、安装/apply 幂等链路和插件 UI 生命周期验收。
- 2026-06-26：步骤 9-12 固化 Plugin Creator 技能场景，打通后端报告链路和 UI 证据呈现。
- 2026-06-26：步骤 13-15 设计并执行自动化项目健康巡检；UI 链路成立，但保留 `codex exec` reasoning effort `max` 失败证据。
- 2026-06-26：步骤 16-18 设计并验收多模态 dry-run smoke；真实 provider smoke 仍受用户授权门控。
- 2026-06-26：步骤 19-20 完成联网公开文档搜索与深度搜索验收；来源、record id、截图和报告已落盘。
- 2026-06-26：步骤 21-22 完成跨能力组合任务和 dogfood ledger；整体状态因自动化失败保持 `partial`。
- 2026-06-26：步骤 23-24 完成验证和关闭；前端测试、前端 build、Tauri `cargo check`、sidecar unittest、`git diff --check` 和秘密扫描均在当轮通过，只有既有 Vite chunk-size warning 被保留。
- 2026-06-27：修复本文档 mojibake，将不可读历史记录压缩为可复核摘要；证据路径和残留问题不删除。

## 残留问题

- 自动化项目健康巡检仍需要后续修复 reasoning effort `max` 与当前 Codex kernel 可接受枚举不一致的问题。
- 跨能力组合任务依赖自动化场景，因此仍应被理解为 `partial`，不能包装成全绿。
- 后续如果继续 dogfood，应优先从新的 app hardening 或 capability follow-up 计划开始，不要重新打开本文档的 24 步执行流。
