# Agent Bench Dogfood Task Pool

## Purpose

This task pool is the first small-sample benchmark set for the AstraBridge dogfood plan. It is inspired by SWE-bench, AgentBench, OSWorld, WebArena, BrowserGym, GAIA, ToolBench, and tau-bench task shapes, but it is scoped to AstraBridge product validation rather than external leaderboard scoring.

The tasks are designed to exercise real AstraBridge capabilities with real provider calls where useful, while keeping evidence reproducible and redacted. Later execution rounds should select the task mapped to their numbered step unless the plan is dynamically adjusted for product reasons.

## Execution Rules

- Do not execute this pool during step 3. Step 3 only defines and validates the pool.
- Preserve raw and intermediate experiment artifacts under `PRIVATE/agent-bench-dogfood/`.
- Do not save raw credentials, authorization headers, cookies, bearer tokens, or platform tokens.
- Do not write back to external benchmark platforms or third-party accounts.
- If a task fails because the product experience is unclear, improve the AstraBridge harness, context, UI, routing, or recovery path before classifying the task as an agent capability failure.
- Capture screenshots whenever the UI, browser, report view, model/provider state, automation state, or generated asset is part of the evidence.

## Recommended Step Mapping

- Step 5: `AB-CODE-001`
- Step 7: `AB-SHELL-001`
- Step 9: `AB-BROWSER-001`
- Step 11: `AB-WEB-001`
- Step 13: `AB-VISION-001`
- Step 14: `AB-ASSET-001`
- Step 15: `AB-PLUGIN-001`
- Step 16: `AB-MCP-001`
- Step 17: `AB-AUTO-001`
- Step 19: `AB-ROUTE-001`

## Tasks

### AB-CODE-001: Local Bugfix With Tests

- benchmark_shape: SWE-bench / HumanEval
- purpose: Validate whether an AstraBridge agent can inspect a small local bug, make a minimal patch, and run targeted tests.
- prompt_outline: Give the agent a failing local test or small bug report inside the AstraBridge repo and ask it to diagnose, patch, test, and summarize the result.
- real_api_policy: Real provider call allowed.
- expected_evidence: patch diff, test command output, task report, optional UI screenshot of the run monitor.
- failure_criteria: Agent changes unrelated files without justification, cannot identify the failing behavior, does not run a relevant test, or leaves the repo in an unverified state.
- success_criteria:
  - The final diff is scoped to the bug.
  - A relevant test command passes, or a clear product-level blocker is recorded.
  - The report includes changed files, commands run, and residual risk.
  - No credentials or raw provider payloads are persisted.
- allowed_tools:
  - repo_search
  - file_read
  - apply_patch
  - shell
  - local_tests
  - git_diff
  - screenshot

### AB-SHELL-001: Windows File And Command Chain

- benchmark_shape: AgentBench / OSWorld
- purpose: Validate local file navigation, command execution, Windows path handling, and failure recovery.
- prompt_outline: Ask the agent to inspect a nested local artifact directory, generate a short inventory report, run a validation command, and repair one harmless formatting or schema issue if found.
- real_api_policy: Real provider call optional.
- expected_evidence: command summaries, created or updated local report, validation output, screenshot if UI status is involved.
- failure_criteria: Agent loses the working directory, mishandles Windows paths, hides command failures, or edits unrelated artifacts.
- success_criteria:
  - The report lists inspected paths and validation commands.
  - Windows paths are displayed accurately and readably.
  - Command failures, if any, are preserved with actionable recovery notes.
  - The final artifact can be re-opened and verified.
- allowed_tools:
  - shell
  - file_read
  - apply_patch
  - report_writer
  - screenshot

### AB-BROWSER-001: In-App Browser Navigation And State Proof

- benchmark_shape: WebArena / BrowserGym
- purpose: Validate browser control, product navigation, screenshot capture, and UI/API state consistency.
- prompt_outline: Use the in-app browser to open AstraBridge, navigate through settings, provider/API key, model, and runtime views, then capture the state and compare it with sidecar API state.
- real_api_policy: No new provider call required.
- expected_evidence: browser screenshots, redacted sidecar status summary, UI/API consistency report.
- failure_criteria: Browser cannot reach the target view, screenshots miss the relevant state, UI state contradicts sidecar API state without diagnosis, or visual defects are ignored.
- success_criteria:
  - Screenshots show the key UI state needed for review.
  - The report compares UI state with sidecar API state.
  - Any layout, overflow, or unclear status issue is either fixed or explicitly recorded.
  - No raw credentials are captured in screenshots or reports.
- allowed_tools:
  - in_app_browser
  - screenshot
  - sidecar_api
  - report_writer

### AB-WEB-001: Multi-Source Research Brief

- benchmark_shape: GAIA / WebArena
- purpose: Validate web search, source selection, date awareness, citation handling, and uncertainty reporting.
- prompt_outline: Ask the agent to answer a small current-facts question using multiple public sources, then produce a brief that separates sourced facts, inference, and unknowns.
- real_api_policy: Real provider call allowed.
- expected_evidence: source URLs, access dates, short cited answer, task report.
- failure_criteria: Uses stale or weak sources for current claims, omits dates, blends inference with fact, or over-quotes a source.
- success_criteria:
  - At least two independent relevant sources are cited.
  - Dates are recorded for time-sensitive facts.
  - The final answer separates facts, inference, and unresolved uncertainty.
  - Source attribution is visible in the report.
- allowed_tools:
  - web_search
  - web_fetch
  - browser
  - report_writer

### AB-VISION-001: Screenshot Understanding And UI QA

- benchmark_shape: GAIA multimodal / OSWorld visual QA
- purpose: Validate image input, OCR-like inspection, visual reasoning, and UI quality assessment.
- prompt_outline: Provide one or more AstraBridge screenshots and ask the agent to identify visible state, summarize issues, and decide whether a UI fix is needed.
- real_api_policy: Real provider call allowed if the selected model supports vision.
- expected_evidence: input screenshot paths, visual findings, pass/fail judgment, UI fix notes if needed.
- failure_criteria: Agent invents invisible details, misses obvious overflow or unreadable text, or cannot cite the screenshot used.
- success_criteria:
  - The report references the exact screenshot paths.
  - Visible status is described without exposing or inventing credentials.
  - UI issues are classified by severity and actionability.
  - The result can be manually checked against the screenshots.
- allowed_tools:
  - image_view
  - vision_model
  - screenshot
  - report_writer

### AB-ASSET-001: Small Multimodal Asset Generation

- benchmark_shape: Multimodal generation / product asset workflow
- purpose: Validate image or asset generation, artifact preview, manifest/registry handling, and path reporting.
- prompt_outline: Generate a small non-sensitive asset for a dogfood fixture, save it to a controlled artifact path, and verify that the UI or report can preview or link it.
- real_api_policy: Real image or asset provider call allowed.
- expected_evidence: generated asset path, preview screenshot or rendered image, manifest or report entry, redacted call summary.
- failure_criteria: Asset path is wrong, preview is broken, generated content is not inspectable, or raw provider payloads with sensitive headers are persisted.
- success_criteria:
  - The generated asset is visible and stored under the planned artifact path.
  - The report includes provider/model and rough cost/token signal where available.
  - The preview or screenshot proves the artifact can be inspected.
  - Durable records contain no raw credentials.
- allowed_tools:
  - image_generation
  - file_read
  - screenshot
  - report_writer
  - sidecar_api

### AB-PLUGIN-001: Plugin And Skill Discovery Fixture

- benchmark_shape: ToolBench / AstraBridge extension flow
- purpose: Validate plugin/skill discovery, instruction loading, fixture execution, and UI/API consistency.
- prompt_outline: Ask the agent to discover an installed or fixture plugin/skill, read its instructions, run a safe fixture action, and compare UI state with sidecar state.
- real_api_policy: Real provider call optional.
- expected_evidence: plugin or skill ID, instruction source, fixture result, UI/API status screenshot.
- failure_criteria: Agent skips instruction loading, confuses plugin and skill identity, cannot recover from missing fixture state, or UI and API disagree without diagnosis.
- success_criteria:
  - The report names the plugin or skill ID and source.
  - Instructions are read before executing the fixture.
  - UI status and sidecar/API status are compared.
  - Any missing or failed fixture path has a recovery note.
- allowed_tools:
  - plugin_discovery
  - skill_reader
  - sidecar_api
  - in_app_browser
  - screenshot
  - report_writer

### AB-MCP-001: Low-Risk MCP Tool Call

- benchmark_shape: ToolBench
- purpose: Validate MCP tool discovery, argument passing, result capture, and error display.
- prompt_outline: Select a low-risk local MCP tool, call it with deterministic arguments, capture the result, and verify that the result and any errors are visible in the product surface.
- real_api_policy: No provider call required unless the harness needs a model to plan the tool use.
- expected_evidence: tool name, sanitized arguments, result summary, UI or report screenshot.
- failure_criteria: Tool discovery fails without recovery, arguments are malformed, result is not surfaced, or errors are hidden.
- success_criteria:
  - The selected MCP tool and arguments are recorded.
  - The result is deterministic enough to verify manually.
  - UI/report state matches the tool result.
  - Error recovery is recorded if the first call fails.
- allowed_tools:
  - tool_search
  - mcp_tool
  - sidecar_api
  - screenshot
  - report_writer

### AB-AUTO-001: Short Automation Run

- benchmark_shape: AstraBridge automation / OSWorld
- purpose: Validate automation creation, execution history, inbox or artifact review, and user-facing recovery.
- prompt_outline: Create a short one-shot or short-interval automation in a controlled workspace mode, run it, and verify history, artifacts, and completion or failure state.
- real_api_policy: Real provider call allowed if automation task requires it.
- expected_evidence: automation ID, run history, artifact links, inbox or report screenshot, final state.
- failure_criteria: Automation cannot be inspected after running, status is ambiguous, artifacts are missing, or failure lacks actionable recovery.
- success_criteria:
  - The automation run has a visible final state.
  - Run history and artifacts can be opened by a user.
  - Failure or success status is explained in the report.
  - UI issues found during review are fixed or recorded for the paired repair step.
- allowed_tools:
  - automation_api
  - in_app_browser
  - screenshot
  - file_read
  - report_writer

### AB-ROUTE-001: Cross-Provider Routing And Recovery

- benchmark_shape: tau-bench / AstraBridge router flow
- purpose: Validate managed key injection, model/provider routing, health signals, router preview, and fallback behavior.
- prompt_outline: Run a small deterministic prompt through at least two configured providers or models, compare redacted response summaries, and capture router/UI/provider consistency.
- real_api_policy: Real provider calls expected.
- expected_evidence: provider/model pairs, router base URL, redacted response summaries, token/cost signal where available, UI screenshots.
- failure_criteria: Calls go to the wrong provider, model identity is unclear, health signals disagree with the actual call, or fallback behavior is not visible.
- success_criteria:
  - At least two provider/model pairs are recorded.
  - UI state, router state, and task report agree on provider/model identity.
  - Responses are summarized without raw secrets or sensitive headers.
  - Any failed provider route has a recovery or fallback note.
- allowed_tools:
  - sidecar_api
  - router_endpoint
  - in_app_browser
  - screenshot
  - report_writer

## Validation Checklist

Before using this pool, verify that every task includes:

- `success_criteria`
- `allowed_tools`
- failure criteria
- evidence requirements
- an external-writeback-free execution path

## Round 2 Adjustments After First Dogfood Round

The first dogfood round completed all planned capability families, but the next round should raise the bar rather than re-run the same smoke paths unchanged.

Recommended additions:

- Add a `AB-VISION-CHAT-002` task focused on the normal chat attachment path, including timeout messaging, final-answer detection, and artifact linkage for local image prompts.
- Add token and cost accounting requirements to every real provider task, especially automation runs, image generation, Web/network lanes, and runtime handoffs.
- Add a current-source sidecar launch requirement for selected live validations so reports can distinguish app-managed launcher state from the code under test.
- Extend `AB-ROUTE-001` with a failure/fallback variant that intentionally exercises unavailable or unhealthy provider routes and verifies user-facing recovery.
- Extend `AB-PLUGIN-001` beyond discovery to cover install approval, enablement, and post-approval fixture execution.
- Extend `AB-AUTO-001` with a clean success-path finalization case in addition to cancel, interrupted-run, and recovery cases.
- Add a standard screenshot QA checklist for overflow, clipped paths, empty states, misleading provider/runtime labels, and unreadable narrow-panel content.

These adjustments must preserve the original constraints: no external writeback without explicit approval, no persisted secrets, screenshots and raw reports preserved by default, and product-layer fixes preferred over merely marking agent tasks as failed.
