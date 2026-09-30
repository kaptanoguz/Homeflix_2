; Homeflix Windows Installer Script (NSIS)
; This script creates a Windows installer for Homeflix

!include "MUI2.nsh"
!include "x64.nsh"

; Basic Installer Information
Name "Homeflix"
OutFile "dist\HomeflixInstaller.exe"
InstallDir "$PROGRAMFILES\Homeflix"
InstallDirRegKey HKLM "Software\Homeflix" "Install_Dir"

; Request admin privileges
RequestExecutionLevel admin

; Version Information
VIProductVersion "2.0.0.0"
VIFileVersion "2.0.0.0"
VIAddVersionKey "ProductName" "Homeflix"
VIFileAddVersionKey "FileDescription" "Ev Sineması - Kişisel Video Platformu"
VIFileAddVersionKey "FileVersion" "2.0.0"
VIFileAddVersionKey "ProductVersion" "2.0.0"
VIFileAddVersionKey "CompanyName" "Homeflix"
VIFileAddVersionKey "LegalCopyright" "2024"

; MUI Settings
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_LANGUAGE "Turkish"
!insertmacro MUI_LANGUAGE "English"

; Installer Sections
Section "Homeflix Yükle" SecInstall
  SetOutPath "$INSTDIR"

  ; Copy all files from dist/Homeflix/
  File /r "dist\Homeflix\*.*"

  ; Create registry keys for uninstall
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Homeflix" "DisplayName" "Homeflix"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Homeflix" "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Homeflix" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Homeflix" "DisplayVersion" "2.0.0"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Homeflix" "Publisher" "Homeflix"

  ; Create uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Create Start Menu shortcut
  CreateDirectory "$SMPROGRAMS\Homeflix"
  CreateShortcut "$SMPROGRAMS\Homeflix\Homeflix.lnk" "$INSTDIR\Homeflix.exe" "" "$INSTDIR\Homeflix.exe" 0 SW_SHOWNORMAL
  CreateShortcut "$SMPROGRAMS\Homeflix\Kaldır.lnk" "$INSTDIR\Uninstall.exe" "" "$INSTDIR\Uninstall.exe" 0

  ; Create Desktop shortcut (optional)
  CreateShortcut "$DESKTOP\Homeflix.lnk" "$INSTDIR\Homeflix.exe" "" "$INSTDIR\Homeflix.exe" 0 SW_SHOWNORMAL

SectionEnd

; Uninstaller Section
Section "Uninstall"

  ; Remove Start Menu shortcuts
  Delete "$SMPROGRAMS\Homeflix\Homeflix.lnk"
  Delete "$SMPROGRAMS\Homeflix\Kaldır.lnk"
  RMDir "$SMPROGRAMS\Homeflix"

  ; Remove Desktop shortcut
  Delete "$DESKTOP\Homeflix.lnk"

  ; Remove installed files
  RMDir /r "$INSTDIR"

  ; Remove registry keys
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Homeflix"
  DeleteRegKey HKLM "Software\Homeflix"

SectionEnd

; Install success message
Function .onInstSuccess
  MessageBox MB_OK "Homeflix başarıyla yüklendi! Başlat Menüsünden bulabilirsiniz."
FunctionEnd

; Uninstall success message
Function un.onUninstSuccess
  MessageBox MB_OK "Homeflix kaldırıldı."
FunctionEnd
