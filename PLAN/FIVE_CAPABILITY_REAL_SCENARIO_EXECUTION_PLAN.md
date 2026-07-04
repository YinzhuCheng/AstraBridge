# 五类能力真实场景高覆盖计划（已取代）

Last updated: 2026-06-27

## 状态

本文件是早期 20 步高覆盖草案，已经被 [CAPABILITY_REAL_SCENARIO_DOGFOOD_PLAN.md](/D:/AstraBridge/PLAN/CAPABILITY_REAL_SCENARIO_DOGFOOD_PLAN.md) 的 24 步执行记录取代。

当前状态：

- 当前阶段：`superseded`
- 替代计划：`PLAN/CAPABILITY_REAL_SCENARIO_DOGFOOD_PLAN.md`
- 替代计划进度：`complete`
- 下一入口：`complete`

后续 agent 不应从本文件的旧 `step_11` 继续执行。需要复核五类能力 dogfood 时，读取替代计划和 dogfood ledger；需要开启新一轮真实场景验收时，新建或更新新的专项计划。

## 原目标摘要

早期草案的目标是覆盖以下五类能力：

- 自动化
- 插件
- 技能
- 多模态能力路由
- 联网

要求包括：

- 优先通过 in-app browser 做真实点击验收。
- 每个场景至少保留截图、JSON 报告、运行记录或产物路径。
- shell/API/单元测试只能作为补充证据或 blocker 定位。
- 不读取、不保存、不提交明文密钥、token、cookie、Authorization header 或其他可复用秘密。
- 失败证据优先级不低于成功证据。

这些原则已经并入 24 步替代计划。

## 被替代原因

原 20 步计划在步骤 10 后继续拆分时，后续工作被升级为更细的 24 步执行计划。新计划补充了：

- 更清晰的统一 dogfood 证据 schema。
- 受控插件 fixture 生命周期。
- Plugin Creator 技能场景。
- 自动化项目健康巡检真实验收。
- 多模态 dry-run 与授权 provider smoke 边界。
- 联网普通搜索和深度搜索复验。
- 跨能力组合任务和 dogfood ledger。
- 最终全量测试、构建、Tauri check、sidecar unittest 和秘密扫描。

## 复核入口

- 完整执行记录：[CAPABILITY_REAL_SCENARIO_DOGFOOD_PLAN.md](/D:/AstraBridge/PLAN/CAPABILITY_REAL_SCENARIO_DOGFOOD_PLAN.md)
- 证据规范：[REAL_SCENARIO_DOGFOOD_EVIDENCE.md](/D:/AstraBridge/docs/REAL_SCENARIO_DOGFOOD_EVIDENCE.md)
- 报告 schema：[REAL_SCENARIO_DOGFOOD_REPORT_SCHEMA.json](/D:/AstraBridge/docs/REAL_SCENARIO_DOGFOOD_REPORT_SCHEMA.json)
- dogfood ledger：
  - `apps/astrabridge-desktop/output/playwright/real-scenario-dogfood/step22-dogfood-ledger-summary.json`
  - `apps/astrabridge-desktop/output/playwright/real-scenario-dogfood/step22-dogfood-ledger-summary.md`

## 完成记录

- 2026-06-26：创建早期 20 步高覆盖计划，记录前 10 步已完成状态和后续入口。
- 2026-06-26：后续执行升级为 24 步计划，并在替代计划中完成全部场景验收与收尾。
- 2026-06-27：修复本文档 mojibake，将它降级为可读的历史说明，避免继续污染后续 agent 的执行入口判断。
