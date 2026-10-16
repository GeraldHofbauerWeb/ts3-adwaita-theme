; Windows-Installer für Adwaita Dark / Papirus Dark (TeamSpeak 3).
; Bauen: tools/build-windows.sh (Inno Setup 6 über Wine). Vorher erzeugt
; build.py --windows alles unter build\windows, auch accents.iss.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define Build "..\build\windows"

[Setup]
AppId={{25023665-3290-46C9-8674-5B67CEAFE88C}
AppName=Adwaita Dark für TeamSpeak 3
AppVersion={#AppVersion}
AppVerName=Adwaita Dark für TeamSpeak 3 {#AppVersion}
AppPublisher=Gerald Hofbauer
AppPublisherURL=https://github.com/GeraldHofbauerWeb/ts3-adwaita-theme
AppSupportURL=https://github.com/GeraldHofbauerWeb/ts3-adwaita-theme/issues
; Die Dateien landen im TS3-Profil; hier liegen nur Uninstaller und Hinweise.
DefaultDirName={localappdata}\ts3-adwaita-theme
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=ts3-adwaita-theme-setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=Adwaita Dark für TeamSpeak 3

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"

[Files]
Source: "{#Build}\payload\styles\*"; DestDir: "{userappdata}\TS3Client\styles"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Build}\payload\gfx\*"; DestDir: "{userappdata}\TS3Client\gfx"; Flags: ignoreversion
Source: "{#Build}\docs\*"; DestDir: "{app}"; Flags: ignoreversion

[Code]
#include "..\build\windows\accents.iss"

const
  StylePrefix = 'Adwaita-Dark-';
  IconPrefix = 'Papirus-Dark-';

var
  AccentPage: TWizardPage;
  AccentButtons: array of TNewRadioButton;
  ActivateCheck: TNewCheckBox;

function ProfileDir(): String;
begin
  Result := ExpandConstant('{userappdata}\TS3Client');
end;

// TeamSpeak liest diese Datei beim Start und aktiviert die eingetragenen Add-ons;
// genau so macht es TeamSpeaks eigener Installer.
function ActivationIni(): String;
begin
  Result := ProfileDir() + '\package_inst_temp.ini';
end;

function SelectedAccent(): Integer;
var
  I: Integer;
begin
  Result := 0;
  for I := 0 to AccentCount - 1 do
    if AccentButtons[I].Checked then
      Result := I;
end;

// /ACCENT=maia wählt die Farbe vor, auch für /VERYSILENT.
function InitialAccent(): Integer;
var
  Wanted: String;
  I: Integer;
begin
  Result := 0;
  Wanted := Lowercase(ExpandConstant('{param:ACCENT|blue}'));
  for I := 0 to AccentCount - 1 do
    if AccentName(I) = Wanted then
      Result := I;
end;

procedure SwatchClick(Sender: TObject);
begin
  AccentButtons[TPanel(Sender).Tag].Checked := True;
end;

procedure InitializeWizard();
var
  I, Initial, RowHeight: Integer;
  Swatch: TPanel;
  Hint: TNewStaticText;
begin
  AccentPage := CreateCustomPage(wpWelcome, 'Akzentfarbe',
    'Die Farbe für Auswahl, Knöpfe und die Sprechanzeige im Kanalbaum.');
  SetArrayLength(AccentButtons, AccentCount);
  Initial := InitialAccent();
  RowHeight := ScaleY(30);

  for I := 0 to AccentCount - 1 do
  begin
    Swatch := TPanel.Create(AccentPage);
    Swatch.Parent := AccentPage.Surface;
    Swatch.Left := (I div 5) * ScaleX(200);
    Swatch.Top := (I mod 5) * RowHeight;
    Swatch.Width := ScaleX(20);
    Swatch.Height := ScaleY(20);
    Swatch.BevelOuter := bvNone;
    Swatch.ParentBackground := False;
    Swatch.Color := AccentColor(I);
    Swatch.Tag := I;
    Swatch.Cursor := crHand;
    Swatch.OnClick := @SwatchClick;

    AccentButtons[I] := TNewRadioButton.Create(AccentPage);
    AccentButtons[I].Parent := AccentPage.Surface;
    AccentButtons[I].Left := Swatch.Left + ScaleX(30);
    AccentButtons[I].Top := Swatch.Top + ScaleY(2);
    AccentButtons[I].Width := ScaleX(160);
    AccentButtons[I].Caption := AccentLabel(I);
    AccentButtons[I].Checked := I = Initial;
  end;

  ActivateCheck := TNewCheckBox.Create(AccentPage);
  ActivateCheck.Parent := AccentPage.Surface;
  ActivateCheck.Top := 5 * RowHeight + ScaleY(14);
  ActivateCheck.Width := AccentPage.SurfaceWidth;
  ActivateCheck.Caption := 'Stil und passende Symbole beim nächsten Start von TeamSpeak aktivieren';
  ActivateCheck.Checked := ExpandConstant('{param:ACTIVATE|1}') <> '0';

  Hint := TNewStaticText.Create(AccentPage);
  Hint.Parent := AccentPage.Surface;
  Hint.Top := ActivateCheck.Top + ScaleY(30);
  Hint.Width := AccentPage.SurfaceWidth;
  Hint.AutoSize := False;
  Hint.Height := ScaleY(40);
  Hint.WordWrap := True;
  Hint.Caption := 'Installiert werden alle zehn Farben. Wechseln geht später in TeamSpeak unter ' +
    'Extras → Optionen → Design.';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  // Inno Setup 6 zeigt keine Willkommensseite, die Farbseite ist die erste.
  if (CurPageID = AccentPage.ID) and not DirExists(ProfileDir()) then
    Result := MsgBox('Für diesen Windows-Benutzer gibt es noch kein TeamSpeak-3-Profil (' +
      ProfileDir() + '). Normalerweise legt TeamSpeak es beim ersten Start an.' + #13#10#13#10 +
      'Trotzdem installieren?', mbConfirmation, MB_YESNO) = IDYES;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  I: Integer;
begin
  if (CurStep = ssPostInstall) and ActivateCheck.Checked then
  begin
    I := SelectedAccent();
    SetIniString('General', 'styles', StylePrefix + AccentId(I), ActivationIni());
    SetIniString('General', 'gfx', IconPrefix + AccentId(I), ActivationIni());
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
var
  I: Integer;
begin
  if CurPageID <> wpFinished then
    exit;
  I := SelectedAccent();
  if ActivateCheck.Checked then
    WizardForm.FinishedLabel.Caption := 'Beim nächsten Start übernimmt TeamSpeak den Stil „' +
      StylePrefix + AccentId(I) + '“ und die Symbole „' + IconPrefix + AccentId(I) + '“.' + #13#10#13#10 +
      'Läuft TeamSpeak gerade, muss es dafür einmal beendet und neu gestartet werden.'
  else
    WizardForm.FinishedLabel.Caption := 'Stile und Symbole sind installiert. Ausgewählt werden sie ' +
      'in TeamSpeak unter Extras → Optionen → Design.';
end;

// Eine noch nicht abgeholte Aktivierung darf nach dem Entfernen nicht ins Leere zeigen.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep <> usPostUninstall then
    exit;
  if Pos(StylePrefix, GetIniString('General', 'styles', '', ActivationIni())) = 1 then
    DeleteIniEntry('General', 'styles', ActivationIni());
  if Pos(IconPrefix, GetIniString('General', 'gfx', '', ActivationIni())) = 1 then
    DeleteIniEntry('General', 'gfx', ActivationIni());
end;
