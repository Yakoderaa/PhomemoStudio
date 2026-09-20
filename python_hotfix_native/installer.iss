#define MyAppName "Phomemo Studio"
#ifndef MyAppVersion
#define MyAppVersion "4.1.0"
#endif
#define MyAppExeName "PhomemoStudio.exe"
[Setup]
AppId={{A08E6C21-7B96-4B1C-BC30-1EE59E3C693C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\PhomemoStudio
DefaultGroupName={#MyAppName}
OutputDir=dist
OutputBaseFilename=PhomemoStudioSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=assets\sr-gato.ico
[Files]
Source: "dist\PhomemoStudio.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\PhomemoBleBridge.exe"; DestDir: "{app}"; Flags: ignoreversion\nSource: "dist\PhomemoStudioUpdater.exe"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked
[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent
Filename: "{app}\{#MyAppExeName}"; Flags: nowait skipifnotsilent
