# AstraBridge Tier 1 Icon Replacement Matrix

Last updated: 2026-07-03

## Purpose

This matrix inventories the highest-priority icon surfaces that are already visible in current AstraBridge UI and need to converge on the Starbridge icon system.

Tier 1 means:

- first-viewport navigation
- high-frequency composer controls
- status/review/browser/files entry points
- workflow and permission mode switching
- visible legacy symbol cleanup

## Verification Scope

This matrix explicitly covers the Step 9 requirement areas:

1. primary navigation
2. high-frequency controls
3. status entry points
4. mode switching

## Tier 1 Matrix

| Area | Surface | Current asset | Current issue | Starbridge target family | Replacement direction | Priority | Code refs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Primary navigation | Left sidebar `New task` | `Plus` | Semantically acceptable but generic | Project / Task | Keep outline add metaphor, tighten into task-creation cluster style | P1 | `apps/astrabridge-desktop/src/App.tsx:7444-7447` |
| Primary navigation | Left sidebar `Search` | `Search` | Semantically acceptable but generic | Observatory | Keep search metaphor, unify stroke and surrounding nav treatment | P1 | `apps/astrabridge-desktop/src/App.tsx:7449-7452` |
| Primary navigation | Sidebar session status | raw `●` | Banned raw Unicode; no Starbridge identity | Relay / Bridge | Replace with managed-session beacon / relay-status glyph | P0 | `apps/astrabridge-desktop/src/App.tsx:7504-7510` |
| Primary navigation | Sidebar `Settings` | `Settings` | Acceptable but generic | Observatory | Keep utility/settings metaphor or shift to control-panel form | P2 | `apps/astrabridge-desktop/src/App.tsx:7511-7514` |
| Primary navigation | Project tree project row | `Folder` | Acceptable baseline, not yet branded | Project / Task | Keep project-folder metaphor with cleaner frame geometry | P1 | `apps/astrabridge-desktop/src/features/navigation/ProjectTaskTree.tsx:46-59` |
| Primary navigation | Project tree task row | `ListChecks` | Good semantic fit; should become canonical task glyph | Project / Task | Promote as base task icon or custom workboard variant | P1 | `apps/astrabridge-desktop/src/features/navigation/ProjectTaskTree.tsx:66-77` |
| Primary navigation | Project tree expand/collapse | `ChevronDown` / `ChevronRight` | Fine mechanically, but must stay visually thin | Observatory | Keep chevrons; do not over-brand expanders | P2 | `apps/astrabridge-desktop/src/features/navigation/ProjectTaskTree.tsx:131-160` |
| Primary navigation | Fallback legacy task list row | raw `□` | Banned raw Unicode fallback | Project / Task | Replace with same task glyph used in the project tree | P0 | `apps/astrabridge-desktop/src/App.tsx:7474-7489` |
| Primary navigation | Fallback legacy rename/archive actions | raw `✎` / `×` | Banned raw Unicode actions | Payload / Review | Replace with proper rename and archive icons | P0 | `apps/astrabridge-desktop/src/App.tsx:7490-7495` |
| Primary navigation | Pane toggles | `PanelLeftClose/Open`, `PanelRightClose/Open` | Good semantics; needs consistency as a layout-control family | Observatory | Keep panel metaphor as a matched left/right pair | P1 | `apps/astrabridge-desktop/src/App.tsx:7523-7531`, `7603-7620`; `apps/astrabridge-desktop/src/features/navigation/ViewWorkspacePanel.tsx:172-189` |
| Primary navigation | Setup landing actions | `Search`, `ListChecks`, `Panel*`, `MessageSquareText` | Good structure; must stay aligned with main shell | Observatory / Project / Task | Reuse the same final glyph family as shell nav | P2 | `apps/astrabridge-desktop/src/features/navigation/ViewWorkspacePanel.tsx:153-198` |
| High-frequency controls | Attachment add trigger | `Paperclip` | Strong baseline; needs to anchor the payload cluster | Payload and Capture | Keep clip/intake metaphor with cleaner Starbridge stroke | P1 | `apps/astrabridge-desktop/src/App.tsx:7928-7949` |
| High-frequency controls | Attachment menu items | `FileIcon`, `FolderOpen` | Good baseline; currently generic file-manager feel | Payload and Capture | Keep sheet/folder semantics, unify with attachment cards | P1 | `apps/astrabridge-desktop/src/App.tsx:7940-7948` |
| High-frequency controls | Attachment cards | `FolderOpen`, `ImageIcon`, `FileIcon`, `X`, `ChevronUp`, `ChevronDown` | Mixed transport/control semantics in one strip | Payload and Capture | Keep payload type icons, keep thin reorder/remove controls, avoid decorative variants | P2 | `apps/astrabridge-desktop/src/App.tsx:7803-7836` |
| High-frequency controls | Voice transcribe | `Mic` | Good baseline, but currently isolated from rest of composer cluster | Payload and Capture | Keep minimal mic; tune to the same stroke and active-state behavior | P1 | `apps/astrabridge-desktop/src/App.tsx:8030-8041` |
| High-frequency controls | Send | raw `↑` inside branded button | Banned raw Unicode; weak semantic specificity | Relay / Bridge | Replace with dispatch / route-launch glyph, likely custom | P0 | `apps/astrabridge-desktop/src/App.tsx:8052-8068` |
| High-frequency controls | Topbar `Compact context` | text-only | No icon support despite high frequency | Relay / Bridge | Add compact/condense route glyph later | P2 | `apps/astrabridge-desktop/src/App.tsx:7600-7608` |
| High-frequency controls | Topbar `Fork task` | text-only | No icon support despite task-branch semantics | Relay / Bridge | Add branch-task glyph later | P1 | `apps/astrabridge-desktop/src/App.tsx:7609-7611` |
| Status entry points | Inspector tabs `Status / Review / Browser / Files` | `ListChecks`, `GitCompare`, `Globe2`, `Files` | Good baseline set but mixed semantic weight | Observatory / Review | Normalize as one inspector-entry family | P1 | `apps/astrabridge-desktop/src/features/runtime/InspectorPanels.tsx:726-730` |
| Status entry points | Browser workbench controls | `ArrowLeft`, `ArrowRight`, `RefreshCw`, `ExternalLink`, `Grid2X2` | Good functional semantics; needs tighter browser cluster hierarchy | Observatory | Keep conventional browser controls, minimize novelty | P2 | `apps/astrabridge-desktop/src/features/runtime/InspectorPanels.tsx:1520-1534`, `1701` |
| Status entry points | Files panel counter and expand toggle | `Files`, `ChevronUp`, `ChevronDown` | Fine functionally, but should stay consistent with inspector entries | Observatory / Payload | Reuse the same files glyph and thin chevron system | P2 | `apps/astrabridge-desktop/src/features/runtime/InspectorPanels.tsx:1869-1884` |
| Mode switching | Permission `ask` | `CircleHelp` | Too generic; reads as help more than approval gate | Mode and Trust | Move toward review/approval gate metaphor | P1 | `apps/astrabridge-desktop/src/App.tsx:1099-1185` |
| Mode switching | Permission `auto` | `Bot` | Too assistant-branded; not specific to Starbridge automation | Mode and Trust | Replace with autonomous relay glyph | P1 | `apps/astrabridge-desktop/src/App.tsx:1099-1185` |
| Mode switching | Permission `full` | `Unlock` | Semantically correct, visually acceptable | Mode and Trust | Keep open-access metaphor, unify with other trust states | P1 | `apps/astrabridge-desktop/src/App.tsx:1099-1185` |
| Mode switching | Workflow `default` | `MessageSquareText` | Too chat-centric for a task-first product | Project / Task | Shift toward task-workflow baseline rather than generic chat | P1 | `apps/astrabridge-desktop/src/App.tsx:1228-1310` |
| Mode switching | Workflow `plan` | `ListChecks` | Good baseline, likely stable | Project / Task | Keep as canonical planning/checklist glyph | P1 | `apps/astrabridge-desktop/src/App.tsx:1228-1310` |
| Mode switching | Workflow `goal` | `SendHorizontal` | Too close to ordinary send; semantic collision risk | Relay / Bridge | Replace with trajectory / target-route glyph | P0 | `apps/astrabridge-desktop/src/App.tsx:1228-1310` |
| Mode switching | Selected row marker | `CheckCircle2` | Works, but should remain secondary to the actual mode glyph | Mode and Trust | Keep or simplify; do not make it the primary brand signifier | P2 | `apps/astrabridge-desktop/src/App.tsx:1174`, `1304` |

## Immediate P0 Cleanup Set

These should be removed first in Step 10 because they are already banned, highly visible, or semantically misleading:

1. raw sidebar session `●`
2. raw fallback task row `□`
3. raw fallback rename `✎`
4. raw fallback archive `×`
5. raw composer send `↑`
6. workflow `goal` reusing a send-like arrow

## Cluster Order For Step 10

Recommended execution order:

1. sidebar raw-symbol cleanup
2. composer send + workflow `goal`
3. permission-mode trio
4. primary nav cluster
5. inspector entry cluster

This ordering maximizes visible brand improvement without widening the scope beyond Tier 1.
