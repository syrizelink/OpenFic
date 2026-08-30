!include FileFunc.nsh
!include LogicLib.nsh

; The installer runs the previous uninstaller first, so replace it before that step
; to make upgrades from versions without this macro preserve runtime as well.
!macro customInstallmode
  ${if} ${isUpdated}
    ${if} $installMode == "all"
      StrCpy $isForceMachineInstall "1"
    ${else}
      StrCpy $isForceCurrentInstall "1"
    ${endif}
  ${endif}
!macroend

!ifndef BUILD_UNINSTALLER
!macro customFinishPage
  Function openficUpdateFinishPagePre
    ${if} ${isUpdated}
      HideWindow
      ${StdUtils.ExecShellAsUser} $0 "$launchLink" "open" "--updated"
      Abort
    ${endif}
  FunctionEnd

  !ifndef HIDE_RUN_AFTER_FINISH
    Function openficStartApp
      ${if} ${isUpdated}
        StrCpy $1 "--updated"
      ${else}
        StrCpy $1 ""
      ${endif}
      ${StdUtils.ExecShellAsUser} $0 "$launchLink" "open" "$1"
    FunctionEnd

    !define MUI_FINISHPAGE_RUN
    !define MUI_FINISHPAGE_RUN_FUNCTION "openficStartApp"
  !endif

  !define MUI_PAGE_CUSTOMFUNCTION_PRE openficUpdateFinishPagePre
  !insertmacro MUI_PAGE_FINISH
!macroend
!endif

!macro customInit
  ${if} ${isUpdated}
    ${if} $installMode == "all"
      ${IfNot} ${UAC_IsAdmin}
        ShowWindow $HWNDPARENT ${SW_HIDE}
        !insertmacro UAC_RunElevated
        Quit
      ${EndIf}
    ${endif}
    InitPluginsDir
    File /oname=$PLUGINSDIR\openfic-update-uninstaller.exe "${UNINSTALLER_OUT_FILE}"
    ClearErrors
    CopyFiles /SILENT "$PLUGINSDIR\openfic-update-uninstaller.exe" "$INSTDIR\${UNINSTALL_FILENAME}"
    ${if} ${Errors}
      MessageBox MB_ICONSTOP "OpenFic cannot prepare the updater to protect the runtime directory."
      Abort
    ${endif}
  ${endif}
!macroend

!ifdef BUILD_UNINSTALLER
Var openficPreserveRuntime

Function un.openficAtomicRemove
  Exch $R0
  Push $R1
  Push $R2
  Push $R3
  Push $R4

  StrCpy $R3 "$INSTDIR$R0\*.*"
  ClearErrors
  FindFirst $R1 $R2 $R3
  IfErrors openfic_atomic_remove_error_no_close

  openfic_atomic_remove_loop:
    StrCmp $R2 "" openfic_atomic_remove_success
    StrCmp $R2 "." openfic_atomic_remove_next
    StrCmp $R2 ".." openfic_atomic_remove_next
    ${if} $openficPreserveRuntime == "1"
      ${if} $R0 == ""
        StrCmp $R2 "runtime" openfic_atomic_remove_next
      ${endif}
    ${endif}

    ClearErrors
    ${GetFileAttributes} "$INSTDIR$R0\$R2" "REPARSE_POINT" $R4
    IfErrors openfic_atomic_remove_error
    ${if} $R4 == "1"
      StrCpy $R3 "$INSTDIR$R0\$R2"
      Goto openfic_atomic_remove_error
    ${endif}

    IfFileExists "$INSTDIR$R0\$R2\*.*" openfic_atomic_remove_directory openfic_atomic_remove_file

  openfic_atomic_remove_directory:
    CreateDirectory "$PLUGINSDIR\old-install$R0\$R2"
    Push "$R0\$R2"
    Call un.openficAtomicRemove
    Pop $R3
    ${if} $R3 != 0
      Goto openfic_atomic_remove_done
    ${endif}
    Goto openfic_atomic_remove_next

  openfic_atomic_remove_file:
    ClearErrors
    Rename "$INSTDIR$R0\$R2" "$PLUGINSDIR\old-install$R0\$R2"
    StrCmp "$R0\$R2" "\Uninstall ${PRODUCT_FILENAME}.exe" 0 +2
      ClearErrors
    IfErrors 0 +3
      StrCpy $R3 "$INSTDIR$R0\$R2"
      Goto openfic_atomic_remove_error

  openfic_atomic_remove_next:
    FindNext $R1 $R2
    Goto openfic_atomic_remove_loop

  openfic_atomic_remove_success:
    StrCpy $R3 0
    Goto openfic_atomic_remove_done

  openfic_atomic_remove_error:
    FindClose $R1
    Goto openfic_atomic_remove_return

  openfic_atomic_remove_error_no_close:
    StrCpy $R3 "$INSTDIR$R0"
    Goto openfic_atomic_remove_return

  openfic_atomic_remove_done:
    FindClose $R1

  openfic_atomic_remove_return:
    StrCpy $R0 $R3
    Pop $R4
    Pop $R3
    Pop $R2
    Pop $R1
    Exch $R0
FunctionEnd

Function un.openficRemoveDirect
  Exch $R0
  Push $R1
  Push $R2
  Push $R3
  Push $R4

  IfFileExists "$INSTDIR$R0" openfic_direct_exists openfic_direct_success

  openfic_direct_exists:
    ClearErrors
    ${GetFileAttributes} "$INSTDIR$R0" "REPARSE_POINT" $R4
    IfErrors openfic_direct_error_no_close
    ${if} $R4 == "1"
      ${GetFileAttributes} "$INSTDIR$R0" "DIRECTORY" $R4
      IfErrors openfic_direct_error_no_close
      ${if} $R4 == "1"
        ClearErrors
        RMDir "$INSTDIR$R0"
      ${else}
        ClearErrors
        Delete "$INSTDIR$R0"
      ${endif}
      IfErrors openfic_direct_error_no_close
      Goto openfic_direct_success
    ${endif}

    ${GetFileAttributes} "$INSTDIR$R0" "DIRECTORY" $R4
    IfErrors openfic_direct_error_no_close
    ${if} $R4 != "1"
      ClearErrors
      Delete "$INSTDIR$R0"
      IfErrors openfic_direct_error_no_close
      Goto openfic_direct_success
    ${endif}

    StrCpy $R3 "$INSTDIR$R0\*.*"
    ClearErrors
    FindFirst $R1 $R2 $R3
    IfErrors openfic_direct_remove_empty

  openfic_direct_loop:
    StrCmp $R2 "" openfic_direct_done
    StrCmp $R2 "." openfic_direct_next
    StrCmp $R2 ".." openfic_direct_next

    Push "$R0\$R2"
    Call un.openficRemoveDirect
    Pop $R3
    ${if} $R3 != 0
      Goto openfic_direct_done
    ${endif}

  openfic_direct_next:
    ClearErrors
    FindNext $R1 $R2
    Goto openfic_direct_loop

  openfic_direct_done:
    FindClose $R1
    ${if} $R3 == 0
      ClearErrors
      RMDir "$INSTDIR$R0"
      IfErrors openfic_direct_error_no_close
    ${endif}
    Goto openfic_direct_return

  openfic_direct_remove_empty:
    ClearErrors
    RMDir "$INSTDIR$R0"
    IfErrors openfic_direct_error_no_close
    Goto openfic_direct_success

  openfic_direct_success:
    StrCpy $R3 0
    Goto openfic_direct_return

  openfic_direct_error_no_close:
    StrCpy $R3 "$INSTDIR$R0"
    Goto openfic_direct_return

  openfic_direct_return:
    StrCpy $R0 $R3
    Pop $R4
    Pop $R3
    Pop $R2
    Pop $R1
    Exch $R0
FunctionEnd
!endif

!macro customRemoveFiles
  SetOutPath $TEMP
  StrCpy $openficPreserveRuntime "1"
  CreateDirectory "$PLUGINSDIR\old-install"
  Push ""
  Call un.openficAtomicRemove
  Pop $R0
  ${if} $R0 != 0
    StrCpy $R4 $R0
    ${if} ${FileExists} "$PLUGINSDIR\old-install\*.*"
      Push ""
      Call un.restoreFiles
      Pop $R0
    ${endif}
    MessageBox MB_ICONSTOP "OpenFic cannot clean the installation directory while preserving runtime. Failed path: $R4"
    Abort
  ${endif}
  ${ifNot} ${isUpdated}
    Push "\runtime"
    Call un.openficRemoveDirect
    Pop $R0
    ${if} $R0 != 0
      StrCpy $R4 $R0
      ${if} ${FileExists} "$PLUGINSDIR\old-install\*.*"
        Push ""
        Call un.restoreFiles
        Pop $R0
      ${endif}
      MessageBox MB_ICONSTOP "OpenFic cannot remove the runtime during uninstall. Failed path: $R4"
      Abort
    ${endif}
    RMDir /r "$INSTDIR"
  ${endif}
!macroend
