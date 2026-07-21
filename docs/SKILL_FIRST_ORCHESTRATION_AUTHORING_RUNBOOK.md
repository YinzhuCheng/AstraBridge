# Skill-first 编排作者 Runbook

状态：规范性作者流程（`no-new-GUI` 轨道）<br>
适用版本：`astrabridge-skill-first-boundary-v1` / `astrabridge-skill-to-graph-v1`<br>
最后更新：2026-07-21

## 目的与边界

本 runbook 面向编写、改造、审查 AstraBridge 编排 skill 的 agent 和维护者。
它回答“何时做成 skill、如何安全地绑定一个既有图模板、如何证明它可运行”，不
提供第二套调度器，也不把 `SKILL.md` 的自然语言变成隐式执行引擎。

权威关系如下：

1. [Skill-first 边界契约](../PLAN/ASTRABRIDGE_SKILL_FIRST_ORCHESTRATION_BOUNDARY_CONTRACT.md)
   冻结产品边界、MCP-only、内部 envelope、A2A 网关、预算和不支持项。
2. [Skill-to-Graph 契约](../PLAN/ASTRABRIDGE_SKILL_TO_GRAPH_CONTRACT.md)及其
   [机器 schema](../PLAN/schemas/astrabridge-skill-to-graph-manifest-v1.schema.json)
   冻结 manifest、参数绑定、策略合并和生命周期。
3. [Canonical graph 契约](../PLAN/AGENT_ORCHESTRATION_GRAPH_CONTRACT.md)拥有图的
   拓扑、节点、边和编译语义；skill 不得复制这些语义。
4. [Skill-backed MCP surface 契约](../PLAN/ASTRABRIDGE_SKILL_BACKED_ORCHESTRATION_MCP_SURFACE_CONTRACT.md)
   拥有 `astrabridge-orchestration` 的九个控制工具和请求/响应规则。
5. 运行时实现由
   `apps/astrabridge-sidecar/astrabridge_sidecar/skill_orchestration_validation.py`、
   `skill_orchestration_mcp_service.py`、canonical compiler、scheduler、MCP broker、
   protocol envelope 和 A2A gateway 各自负责。skill 只能声明策略，不能接管这些 owner。

本轨道刻意不新增 GUI authoring。已有 GUI 只能作为兼容性投影或只读操作投影；它
不是 skill 的来源，也不能改变运行时策略。

## 读取顺序和开始条件

开始 authoring 前按以下顺序阅读：

1. 边界契约中的 “Non-negotiable invariants” 和 “What counts as productized”。
2. Skill-to-Graph 契约中的 “Manifest shape”、“Resolution contract” 和
   “Policy precedence and tightening rules”。
3. MCP surface 契约中的 `propose -> validate -> dry_run -> launch -> inspect`
   语义，以及 `cancel` / `recover` 的失败闭环。
4. 要复用的 graph template、同类 skill 的 `SKILL.md` 和
   `orchestration-manifest.json`。
5. [操作者 Runbook](./SKILL_FIRST_ORCHESTRATION_OPERATOR_RUNBOOK.md)；作者必须
   能交给另一位操作者完成一次 fixture 流程。

如果目标需要运行时递归、无限 fan-out、直接 peer message、provider SDK、GUI
拖拽或第二个图 runtime，应先停在设计审查，不要通过 prose 或未声明参数绕过契约。

## 初始 pattern 选择

先选择已有 pattern，再决定是否需要新 skill。pattern 的名称是稳定的 graph
template ref；skill id 是可审查、可版本化的产品入口。

| Skill ID | Graph template | 适合的任务 | 最小输入方向 |
| --- | --- | --- | --- |
| `astrabridge.supervisor-worker-synthesizer` | `supervisor_worker_synthesizer` | 先拆解，再由有限 worker 执行，最后 typed synthesis | `task_goal`、上下文范围、结果契约 |
| `astrabridge.review-fix-verify` | `code_fix_test_review` | 代码审查、修复、测试/复核闭环 | 变更目标、允许的工作区、验证命令 |
| `astrabridge.fanout-research-synthesis` | `fanout_fanin_research` | 有界资料分发、独立调查、合并结论 | 研究问题、来源/工具策略、合并格式 |
| `astrabridge.provider-update-smoke` | `provider_update_smoke_gate` | provider/model 更新后的兼容性 smoke 和人工 gate | 变更 ref、候选路由、回滚/审批要求 |
| `astrabridge.multimodal-capability-adapter` | `multimodal_capability_adapter` | 通过 MCP 适配图像、文档或其他模态输入输出 | 输入 artifact、MCP 能力、fallback 契约 |

provider-update 和多模态 pattern 在没有对应 catalog、能力快照或人工批准时只能
保持 `candidate` / `validated`，不能从 fixture 成功推导出 live qualification。

## Skill 包结构

推荐一个 skill 包只包含可审查、可复现的声明和参考资料：

```text
apps/astrabridge-sidecar/skills/<skill-directory>/
  SKILL.md                         # 给 agent/操作者的意图、示例和限制
  orchestration-manifest.json      # 机器权威；必须符合 schema
  agents/                           # 可选：角色提示/输入输出说明，不得是 scheduler
  references/                       # 可选：静态契约或领域资料
  assets/                           # 可选：非敏感 fixture/模板资产
```

`SKILL.md` 可以解释选择理由和人类可读的提示，但不能单独声明一个可发布的
编排。不要在包内保存凭据、cookies、授权材料、私有 transcript、未脱敏 provider
回包或指向个人密钥文件的路径。实验原始结果放到约定的 `PRIVATE/**` 证据目录，
先脱敏再保留。

## Manifest authoring checklist

提交前逐项检查 `orchestration-manifest.json`：

- `schema_version` 精确为 `astrabridge-skill-to-graph-manifest-v1`；`skill_id`、
  semantic `version`、`kind=orchestration_skill`、lifecycle `status` 稳定且有 owner。
- `resolution` 只有一个 `builtin_template`、`project_graph` 或 `inline_graph` 来源；
  graph schema version、source ref 和 digest 可追溯。
- `parameter_schema` 是封闭、带类型和必填项的对象；`bindings` 只允许明确的
  canonical graph paths。参数不得改变拓扑、MCP server/tool、approval、A2A trust、
  private context 或预算上限。
- `prompt` 只渲染声明的变量；不能执行代码、调度 agent 或发起 provider 请求。
- `contracts` 声明 typed input/output、必需 message parts、artifact 类型和 lineage。
- `policies.routing` 只列允许的 provider/model/profile、能力需求和显式 fallback /
  downgrade；没有能力快照时保持降级状态。
- `policies.mcp` 声明 server/tool/preset、effect class、approval 和 call budget；
  所有 tool/resource/multimodal 路径都经 MCP（包括 loopback）。
- `policies.communication`、`subagent`、`approval` 明确历史/私有记忆投影、
  envelope、typed edges、`allow_nested_subagents=false` 和
  `allow_direct_teammate_messages=false`。
- `policies.budget` 给出正数且有限的 `max_depth`、总 agent、并行 agent、总 token、
  provider calls、retries 及 provider/model concurrency；深度默认/上限为 `2`。
- `policies.a2a` 只引用批准的 `a2a_card:`，并要求现有 external A2A gateway；不能
  另造 peer registry 或 wire schema。
- `composition.allow_runtime_nesting=false`，模板引用无环，`max_expansion_depth`
  只表示 compile-time 展开。
- `compatibility` 和 `evidence` 给出最低 runtime、fixture ref、证据级别和脱敏 artifact
  root。`productized` 至少需要 canonical fixture、typed envelope、guardrail 负例、
  MCP 生命周期和操作者 runbook 证据。

## 一次 authoring 流程

### 1. 写意图，不写执行器

在 `SKILL.md` 先写目标、适用/不适用任务、输入输出、人工审批点、失败恢复和
预算理由。把角色称为 graph node，把 handoff 称为 typed edge；不要说“skill 再
启动一个 skill”或“agent 自己无限派生团队”。

### 2. 复用并最小化改动

选择表中的 template，复制同类 manifest 的最小形状，只添加必要参数和绑定。请求
级 override 只能单调收紧：降低预算、缩小路由、增加审批、减少上下文可见性都可以；
扩大任何权限都必须新建并审查 manifest 版本。

### 3. 静态验证、编译和 dry-run

在仓库根目录执行（PowerShell）：

```powershell
$env:PYTHONPATH = "apps/astrabridge-sidecar"
python -m astrabridge_sidecar.agent_orchestration_cli skill-validate `
  astrabridge-supervisor-worker-synthesizer `
  --parameters-json '{"task_goal":"写入一个有界的任务目标"}' `
  --markdown-out PRIVATE/skill-first-orchestration/authoring/latest-validation.md
```

也可以按问题缩小为 `skill-lint`、`skill-compile` 或 `skill-dry-run`。命令只做
resolver、canonical graph、compile、policy 和 fixture 检查；它不会调用 provider、
启动 agent 或写 live run state。将输出放入脱敏的 `PRIVATE/**` 证据目录，保留失败
报告而不是覆盖旧报告。

### 4. 通过 canonical MCP admission

需要完整生命周期时，调用 `astrabridge-orchestration` 的 MCP 工具：

1. `astrabridge_orchestration_propose` 取得 immutable `resolution_ref`。
2. `astrabridge_orchestration_validate` 让 manifest、graph、compile、policy、MCP、
   A2A 和 secret checks 给出 blockers/warnings。
3. `astrabridge_orchestration_dry_run` 带完整有限 budget，保存 digest-bound receipt。
4. 先以 `mode=fixture` 调用 launch；live 还需生命周期、provider/A2A 快照、approval、
   idempotency key 和未过期且 digest 匹配的 receipt。
5. 以 `astrabridge_orchestration_inspect` 读取 compact/summary/events 投影。

工具调用必须经 MCP broker；不要直接调用 graph HTTP route、scheduler、provider client
或 filesystem capability。具体字段和九个工具的必填项以 [MCP surface 契约](../PLAN/ASTRABRIDGE_SKILL_BACKED_ORCHESTRATION_MCP_SURFACE_CONTRACT.md)
为准。

### 5. 评估、dogfood 和晋级

对单个或全部内置 skill 保存可重放证据：

```powershell
python scripts/run_skill_orchestration_evaluation_gate.py `
  --mode evaluate `
  --skill-id astrabridge.supervisor-worker-synthesizer `
  --artifact-root PRIVATE/skill-first-orchestration/step14-authoring/20260721 `
  --run-id authoring-supervisor

python scripts/run_skill_orchestration_dogfood.py `
  --artifact-root PRIVATE/skill-first-orchestration/step14-authoring/20260721 `
  --run-id authoring-patterns
```

`evaluate`/dogfood 的 provider 和网络发现调用应为零；这是结构、fixture、MCP 和
guardrail 证据，不是 live provider qualification。`promotion` 只能由有权限的
发布流程调用，并且会对 `candidate`、manual review、未验证 route/A2A 和缺失证据
fail closed。

### 6. 安全与审查收尾

在提交前运行：

```powershell
python scripts/agent_orchestration_secret_scan.py `
  apps/astrabridge-sidecar/skills/<skill-directory> `
  docs/SKILL_FIRST_ORCHESTRATION_AUTHORING_RUNBOOK.md
git diff --check
```

审查者应能从 manifest 找到唯一 graph source、所有参数 binding、每个 typed artifact、
MCP effect/approval、A2A gateway、有限预算和证据目录；如果只能从 prose 猜出其中一项，
该 skill 仍是 `candidate`。

## 生命周期和证据门槛

| 状态 | 作者可以声称什么 | 必须保留的证据 |
| --- | --- | --- |
| `candidate` | 意图和 manifest 草案存在 | manifest、graph/template ref、owner、意图说明 |
| `validated` | 结构上可安全测试 | schema、lint、compile、dry-run、secret scan、policy snapshot |
| `productized` | 是受支持的 AstraBridge skill-backed pattern | MCP loopback fixture、typed edge/envelope、guardrail 负例、运行/恢复 artifacts、两份 runbook |
| `provider-qualified` | 某个真实 provider/model route 已验证 | 授权 bounded smoke、能力/降级证据、脱敏 usage、rollback/recovery |
| `external-a2a-qualified` | 可向外部 peer 提供 | gateway negotiation、trust、replay、artifact/cancel 和 negative conformance |

fixture 通过、GUI 能显示、某个 prompt 看起来可用，都不能跳过状态门槛。warnings
必须随报告保留；release blocker 必须修复或明确升级给对应 owner。

## 变更、回滚和升级

- 修改拓扑、typed contract、MCP policy、A2A trust、approval 或预算语义时，提高
  manifest 版本并重新生成 resolution digest；不要就地覆盖旧 resolution。
- 用 `skill-diff` 或 MCP `diff` 比较 manifest、parameter、graph、compiled-plan、
  route、MCP、approval、budget、context 和 artifact 变化。
- 失败的 fixture/provider run 保留原始 redacted attempt 和 recovery artifact；回滚
  指向上一份已验证的 manifest/graph digest，不把运行时状态写回定义。
- provider catalog 或模型能力更新属于 provider owner 的审查，不在 skill prompt 中
  “猜测支持”。必要时引用 [Provider Model Compatibility Runbook](./PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md)
  和 [Agentic Update Pipeline Runbook](./AGENTIC_UPDATE_PIPELINE_RUNBOOK.md)。

## 不支持路径与升级请求

本轨道明确不支持：net-new GUI authoring、运行时 skill nesting、递归/无限 agent
team、直接 peer/A2A message、provider-direct tool/resource/multimodal、provider-specific
second runtime、绕过 MCP 的 loopback、外部 writeback、官方账号登录路径，以及把
ComfyUI/LangGraph/LangChain/其他团队 DSL 当作 AstraBridge 第二运行时。

若确有必要，提交一个带证据的 contract change proposal，至少说明：需求、唯一 owner、
预算和深度上限、审批/恢复、内部 envelope/MCP/A2A 兼容性、负例测试、迁移和回滚。未
获批准前保持 `candidate` 或 `validated`，不得用未声明参数或 GUI 透传实现临时绕行。
