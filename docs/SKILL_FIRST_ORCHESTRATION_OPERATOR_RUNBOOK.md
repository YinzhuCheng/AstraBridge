# Skill-first 编排操作者 Runbook

状态：规范性操作流程（`no-new-GUI` 轨道）<br>
适用版本：`astrabridge-skill-backed-orchestration-mcp-v1`<br>
最后更新：2026-07-21

## 目的与安全前提

本 runbook 给执行、检查、取消和恢复 skill-backed orchestration 的 agent/操作者
使用。它假定 skill 已经由 [作者 Runbook](./SKILL_FIRST_ORCHESTRATION_AUTHORING_RUNBOOK.md)
生成机器 manifest；操作者不应通过聊天记忆补全缺失字段。

唯一正常控制面是 MCP broker 上的 `astrabridge-orchestration` server。其
`propose`、`patch`、`validate`、`dry_run`、`diff`、`launch`、`inspect`、`cancel`、
`recover` 九个工具的字段、状态和失败语义，以
[MCP surface 契约](../PLAN/ASTRABRIDGE_SKILL_BACKED_ORCHESTRATION_MCP_SURFACE_CONTRACT.md)
为准；本页不复制一份可漂移的 schema。skill 到 canonical graph 的解析以
[Skill-to-Graph 契约](../PLAN/ASTRABRIDGE_SKILL_TO_GRAPH_CONTRACT.md)为准，边界以
[Boundary 契约](../PLAN/ASTRABRIDGE_SKILL_FIRST_ORCHESTRATION_BOUNDARY_CONTRACT.md)为准。

GUI 不是本轨道的 authoring 或 admission 入口。需要 GUI 展示时，它只能读取同一
durable run projection；不能隐藏 blocker、修改 budget、绕过 approval 或创建第二个
runtime。

## 运行前检查

每轮操作开始前：

1. 确认 workspace 使用 `.abproj` 和 workspace-local `.astrabridge/`；下面的旧路径只
   作为明确的 `unsupported` guardrail，不是可恢复入口；不要创建或恢复
   `.lcr*`、`.codexproj`、`.codex-shell` 或官方登录状态作为产品路径。
2. 确认请求有稳定 `request_id`、`idempotency_key`、skill/version、参数和 trace；参数
   不含 private memory、provider-private reasoning、credential、cookie 或授权材料。
3. 确认 skill lifecycle：`candidate` 不能作为 product live feature；`validated` 只有
   在契约允许的 fixture/诊断语境使用；`productized` 才可进入产品化 fixture/live admission。
4. 确认完整且有限的 budget：`max_depth=2`，总 agent `1..16`，并行 `1..8` 且不超过总数，
   total tokens `1..1,000,000`，provider calls `1..64`，retries `0..8`，provider/model
   concurrency 每项 `1..8`，`allow_nested_subagents=false`，
   `allow_direct_teammate_messages=false`。
5. 确认 `approval`、MCP effect policy、A2A card/trust（如使用）和 recovery owner 已声明。
6. 在启动本地 sidecar/frontend 前，按项目要求审计 AstraBridge-owned listener 和
   `cmd`/`node`/`python` launcher；只清理有明确归属的 stale 实例。结束后再次检查，避免
   zombie 进程积累。

## Pattern 和状态决策

| 需求 | 首选 skill/template | 操作注意 |
| --- | --- | --- |
| 拆解任务并合成结果 | `astrabridge.supervisor-worker-synthesizer` / `supervisor_worker_synthesizer` | worker 数量显式计入 budget，结果走 typed synthesis |
| 代码审查到修复复核 | `astrabridge.review-fix-verify` / `code_fix_test_review` | 写操作、安装和测试命令按 approval，保留 diff/测试 artifacts |
| 独立资料分发再合并 | `astrabridge.fanout-research-synthesis` / `fanout_fanin_research` | fan-out 是有限 graph nodes，不是动态创建 root |
| provider/model 更新 smoke | `astrabridge.provider-update-smoke` / `provider_update_smoke_gate` | 没有能力快照或人工 review 时保持 pending/blocked，不宣称 qualified |
| 图像/文档/模态 fallback | `astrabridge.multimodal-capability-adapter` / `multimodal_capability_adapter` | 所有能力调用经 MCP；fallback/downgrade 必须可观测 |

如果没有匹配模板，先回到作者流程；不要直接拼一个聊天 prompt 当作运行计划。

## Canonical MCP 生命周期

以下是每次 operation 的安全顺序。每一步都保存 `operation_id`、resolution/graph
digest、policy snapshot、warnings、blockers 和 artifact refs。

### 1. Propose：解析不可变候选

调用 `astrabridge_orchestration_propose`，提供 skill ref/version、封闭参数和期望的
`evidence_mode`。成功只表示得到 `resolution_ref` 和 canonical graph；它不表示已
批准、已产品化或可 live launch。若出现多 graph source、未知参数、unsafe binding、
循环 template 或缺少 evidence，停止并交给 skill/contract owner。

### 2. Validate：先清 blocker

调用 `astrabridge_orchestration_validate`，至少选择 manifest、graph、compile、policy、
MCP、A2A、secrets checks。逐项处理 `blockers`；warnings 必须保留在报告中，不能由
操作者在 UI 或 prompt 中改成 pass。特别检查 typed input/output、artifact lineage、
MCP server/tool effect、approval、provider capability 和通信隔离。

### 3. Dry-run：生成 launch receipt

调用 `astrabridge_orchestration_dry_run`，携带完整有限 budget。dry-run 必须走既有
canonical compiler/fixture 路径，不调用真实 provider，不产生 live run。保存未过期且
digest-bound 的 `dry_run_receipt`；后续 launch/recover 若 graph 或 policy digest 不匹配，
必须重新 dry-run。

### 4. Launch：fixture 优先，live 受门禁

先用 `astrabridge_orchestration_launch` 的 `mode=fixture`。请求必须包含 resolution ref、
完整 budget、明确 approval、request fingerprint 绑定的 idempotency key 和匹配 receipt。
fixture 结果只能证明 canonical runtime、typed handoff 和 guardrail 行为。

`mode=live` 还要求 skill 已达到允许的 lifecycle、provider/model route 有验证快照、
MCP/A2A gateway policy 通过、审批已满足且风险/付费/外部写入有恢复证据。缺任何一项
就接受 `blocked`/`pending_review`，不要降级成“先试一下”。

### 5. Inspect：读取有限投影

用 `astrabridge_orchestration_inspect` 查询 `compact`（默认）、`summary` 或带 cursor
的 `events`（单页最多 200 条）。只依赖 durable run/event store；不要从 provider transcript、
私有内存或 GUI preview 推断机器结果。记录 run status、node status、attempt、typed
artifact refs、approval、budget usage、warnings、blockers 和下一步 owner。

### 6. Cancel：单调停止

对仍需停止的 run 调用 `astrabridge_orchestration_cancel`，给 bounded human reason、
idempotency key，必要时带 expected state version。取消是 monotonic 的；stale version、
terminal run 或重复 key 返回结构化冲突/终态，不使用 `force` 绕过 run store。保留取消
报告和事件 lineage。

### 7. Recover：显式选择，不扩大图

失败或暂停后只能选择 `resume_run`、`retry_failed_nodes`、`rerun_selected_nodes`、
`partial_execution`。后两者必须给有限的 selected node list，并验证依赖闭包和 typed
artifacts。recover 重新要求 budget、approval、idempotency key、mode 和 fresh receipt；
它创建新的 bounded recovery run，不覆盖原 attempt，也不偷偷变成 whole-graph rerun。

## 状态和 guardrail 解释

| 状态/信号 | 操作者含义 | 下一动作 |
| --- | --- | --- |
| `completed` | 当前 operation/run 的结果和 artifacts 完整 | 检查 warnings、typed outputs 和晋级证据，不自动宣称 provider qualified |
| `accepted` / `queued` | 已通过 admission，run 尚未完成 | 保存 run id，稍后 inspect；不重复提交不同 idempotency key |
| `pending` | 传输或外部状态不确定，operation identity 已保留 | 用原 operation/run inspect；不要并行重放造成重复执行 |
| `pending_review` / `paused_for_review` | 人工批准、provider catalog、A2A trust 或升级 gate 未决 | 记录 owner 和证据，保持停止；批准后重新 validate/dry-run |
| `blocked` | 违反硬边界或缺少必要输入 | 读取结构化 blockers，修 manifest/策略/批准，不强行 launch |
| `failed` | 运行或 operation 已失败，可能有可恢复 node | inspect 失败 attempt，选择合适 recover；保留原 artifacts |
| warning | 当前仍安全但能力/证据/便利性有限 | 在交接中原样记录；不要把 warning 当 qualification |

常见 blocker 的 owner 路由：

- `graph_depth`、agent/token/concurrency、nested/direct message：
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_guardrails.py` 与边界契约。
- envelope、typed parts、artifact lineage、private-memory leakage：
  `protocol.py`、`communication_isolation.py` 和 [Internal/A2A contract](../PLAN/ASTRABRIDGE_SKILL_FIRST_ORCHESTRATION_BOUNDARY_CONTRACT.md)。
- MCP server/tool、effect、loopback 或 multimodal bypass：
  `mcp_node_policy.py`、MCP broker 和 [MCP surface contract](../PLAN/ASTRABRIDGE_SKILL_BACKED_ORCHESTRATION_MCP_SURFACE_CONTRACT.md)。
- provider/model capability、fallback、catalog freshness、A2A card/trust：
  `skill_provider_a2a_binding.py`、existing external A2A gateway 和
  [Provider Model Compatibility Runbook](./PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md)。
- manifest、parameter binding、template source、compile/dry-run：
  `skill_orchestration_validation.py`、canonical compiler 和 [Skill-to-Graph contract](../PLAN/ASTRABRIDGE_SKILL_TO_GRAPH_CONTRACT.md)。
- launch receipt、idempotency、run state、cancel/recover：
  `skill_orchestration_mcp_service.py`、TaskService、durable scheduler/run store。

不要通过提高 budget、打开 nested、开启 direct message、替换 MCP、删除 approval 或
把 provider 警告改名来“修复” blocker；这些是 release-blocking policy violations。

## 证据、目录和无 provider 操作

workspace-local 状态由 runtime 写入 `.astrabridge/skill-orchestration/`，典型包括：

```text
.astrabridge/skill-orchestration/
  resolutions/     # immutable resolution refs/digests
  operations/      # idempotent MCP operation journal
  dry-runs/        # compiled plan, policy snapshot, receipt, diagnostics
```

跨轮审计和实验报告放在 `PRIVATE/skill-first-orchestration/step*/<date>/`；保留旧
bundle、失败 attempt 和 redacted raw reports。常用 provider-free 入口：

```powershell
python scripts/run_skill_orchestration_evaluation_gate.py `
  --mode evaluate `
  --artifact-root PRIVATE/skill-first-orchestration/operator/evaluation `
  --run-id operator-evaluation

python scripts/run_skill_orchestration_dogfood.py `
  --artifact-root PRIVATE/skill-first-orchestration/operator/dogfood `
  --run-id operator-dogfood
```

这两个入口验证结构和 fixture，不产生 provider/network discovery 调用。真实 provider、
付费调用、安装、危险 filesystem change 或 external writeback 必须有显式 approval，
并参考 [Runtime Rollout And Maintenance Runbook](./RUNTIME_ROLLOUT_AND_MAINTENANCE_RUNBOOK.md)
和 [Agentic Update Pipeline Runbook](./AGENTIC_UPDATE_PIPELINE_RUNBOOK.md)。

收尾时运行 secret scan 并确认报告不含 credential material：

```powershell
python scripts/agent_orchestration_secret_scan.py `
  apps/astrabridge-sidecar/skills/<skill-directory> `
  PRIVATE/skill-first-orchestration/operator
```

## 明确不支持的操作

以下路径在 no-new-GUI 轨道中必须拒绝或升级：

- GUI 新建/拖拽/隐式修改 skill 或 graph policy；
- 运行时 skill nesting、递归 agent team、无限 fan-out、超出 depth 2 或有限 budget；
- 直接 peer/A2A message、绕过 internal envelope 或 external A2A gateway；
- provider-direct HTTP/SDK、直接 filesystem/network capability，或非 MCP 的图像/音频/
  文档/视觉调用（first-party loopback 也必须保留 MCP shape）；
- 把 ComfyUI、LangGraph、LangChain、Claude-style team 等作为第二 scheduler/runtime；
- 以官方账号登录替代正常 provider credential boundary，或在项目写入官方配置；
- 未授权的外部写回、付费调用、安装、发布或删除 preserved evidence。

需要这些能力时，停在 `blocked`/`pending_review`，创建 contract change proposal，附
需求、owner、预算、approval、负例、迁移和回滚，而不是在运行中开后门。

## 交接模板

每轮操作结束，在交接记录中至少写下：

```text
run/operation id:
skill id + version + lifecycle:
resolution/graph/policy digest:
mode: fixture | live
status + node/attempt summary:
warnings (原样):
blockers (原样) + owner:
artifacts/evidence paths:
provider/network discovery calls:
process audit result:
next exact action / approval needed:
```

只有在 artifact、状态和 next action 可由下一位 agent 独立复现时，才算完成本轮。
