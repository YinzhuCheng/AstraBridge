# Migration From LCR

| LCR | AstraBridge |
| --- | --- |
| Local Codex Router | AstraBridge 鏄熸ˉ |
| local-codex-router | astrabridge |
| `.lcrproj` | `.abproj` |
| `.lcr/` | `.astrabridge/` |
| LocalCodexRouter app data | AstraBridge app data |
| LOCAL_CODEX_ROUTER_* / CODEX_SHELL_* | ASTRABRIDGE_* |
| openai_account mode | removed |

Legacy projects should be imported explicitly. New projects must create only `.abproj` and `.astrabridge/` state.
