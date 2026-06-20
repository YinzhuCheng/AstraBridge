!macro NSIS_HOOK_POSTUNINSTALL
  ; Only remove AstraBridge state when the user explicitly selects
  ; the installer checkbox. Official Codex lives under %USERPROFILE%\.codex
  ; and is intentionally not referenced here.
  ${If} $DeleteAppDataCheckboxState = 1
  ${AndIf} $UpdateMode <> 1
    SetShellVarContext current
    RMDir /r "$APPDATA\AstraBridge"
    RMDir /r "$LOCALAPPDATA\AstraBridge"
  ${EndIf}
!macroend

