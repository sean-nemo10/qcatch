# build.ps1 — qcatch.exe をビルドして Windows Search ショートカットを更新する
#
# 実行方法:
#   .\build.ps1
#
# 生成物:
#   qcatch.exe (~39MB)  ← プロジェクトルートに生成（Windows Search ショートカット用）
#   build\              ← PyInstaller の中間ファイル（.gitignore 済み）
#
# アーキテクチャ:
#   qcatch.py を直接ビルド。google-genai が軽量（TensorFlow 依存なし）なため
#   sort / toast 含む全機能を 1 つの exe に統合できる。

$ErrorActionPreference = "Stop"

$ScriptDir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExePath      = Join-Path $ScriptDir "qcatch.exe"
$ShortcutName = "qcatch Task Capture"
$Description  = "qcatch - 爆速タスクキャッチ（トースト通知）"

Write-Host ""
Write-Host "=== qcatch ビルド ===" -ForegroundColor Cyan


# ① 依存パッケージの確認・インストール
Write-Host "`n[1/4] 依存パッケージを確認中..." -ForegroundColor Yellow

$packages = @("pyinstaller", "google-genai", "win11toast", "pydantic")
foreach ($pkg in $packages) {
    $installed = pip show $pkg 2>$null
    if (-not $installed) {
        Write-Host "  インストール中: $pkg" -ForegroundColor DarkGray
        pip install $pkg -q
    } else {
        Write-Host "  OK: $pkg" -ForegroundColor DarkGray
    }
}


# ② PyInstaller でビルド
Write-Host "`n[2/4] PyInstaller でビルド中（初回は数分かかります）..." -ForegroundColor Yellow

Push-Location $ScriptDir

# qcatch.py を直接ビルド（google-genai が軽量のため全機能を統合可能）
pyinstaller --onefile --name qcatch --distpath . --workpath "build\work" --specpath "build" qcatch.py

Pop-Location

if (-not (Test-Path $ExePath)) {
    Write-Host "  ERROR: qcatch.exe の生成に失敗しました。" -ForegroundColor Red
    exit 1
}
$size = [math]::Round((Get-Item $ExePath).Length / 1MB, 1)
Write-Host "  OK: $ExePath  ($size MB)" -ForegroundColor Green


# ③ Windows Search ショートカットを更新（.exe → toast モード）
Write-Host "`n[3/4] Windows Search ショートカットを更新中..." -ForegroundColor Yellow

$StartMenu = [Environment]::GetFolderPath("Programs")
$LinkPath  = Join-Path $StartMenu "$ShortcutName.lnk"

$sc = (New-Object -ComObject WScript.Shell).CreateShortcut($LinkPath)
$sc.TargetPath       = $ExePath
$sc.Arguments        = "toast"        # トースト通知からの入力モード
$sc.WorkingDirectory = $ScriptDir
$sc.Description      = $Description
$sc.WindowStyle      = 1
$sc.IconLocation     = "$env:SystemRoot\System32\imageres.dll, 114"
$sc.Save()

Write-Host "  OK: ショートカット更新 → $LinkPath" -ForegroundColor Green
Write-Host "  検索キーワード: 「qcatch」（Windows Search に反映まで数分）" -ForegroundColor DarkGray


# ④ PowerShell コマンド登録
Write-Host "`n[4/4] PowerShell コマンドを更新中..." -ForegroundColor Yellow

if (-not (Test-Path $PROFILE)) {
    New-Item -ItemType File -Force -Path $PROFILE | Out-Null
}

$funcLine = "function qcatch { & `"$ExePath`" @args }"
$content  = Get-Content $PROFILE -Raw -ErrorAction SilentlyContinue

if ($content -notmatch "function qcatch") {
    Add-Content -Path $PROFILE -Value "`n$funcLine"
} else {
    $newContent = ($content -split "`n" |
        Where-Object { $_ -notmatch "^function qcatch" }) -join "`n"
    [System.IO.File]::WriteAllText($PROFILE, $newContent.TrimEnd() + "`n$funcLine`n")
}
. $PROFILE
Write-Host "  OK: qcatch コマンド更新済み" -ForegroundColor Green


Write-Host ""
Write-Host "=== ビルド完了 ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "起動方法:" -ForegroundColor White
Write-Host "  Windows Search  : 「qcatch」で検索 → Enter → トースト通知が出る" -ForegroundColor Green
Write-Host "  PowerShell      : qcatch add `"タスク内容`"" -ForegroundColor Green
Write-Host "  PowerShell      : qcatch sort  （GEMINI_API_KEY 設定後）" -ForegroundColor Green
Write-Host ""
Write-Host "Gemini API キーの設定:" -ForegroundColor Yellow
Write-Host '  [Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "AIzaSy...", "User")' -ForegroundColor DarkGray
Write-Host "  → Google Cloud で billing 登録後、aistudio.google.com でキー発行（無料枠内は $0）" -ForegroundColor DarkGray
Write-Host ""
