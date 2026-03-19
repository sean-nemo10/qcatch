# build.ps1 — qcatch.exe をビルドして Windows Search ショートカットを更新する
#
# 実行方法:
#   .\build.ps1
#
# 生成物:
#   qcatch.exe          ← プロジェクトルートに生成（Windows Search ショートカット用）
#   build\             ← PyInstaller の中間ファイル（.gitignore 済み）

$ErrorActionPreference = "Stop"

$ScriptDir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExePath      = Join-Path $ScriptDir "qcatch.exe"
$ShortcutName = "qcatch Task Capture"
$Description  = "qcatch - 爆速タスクキャッチ (CLI)"

Write-Host ""
Write-Host "=== qcatch ビルド ===" -ForegroundColor Cyan


# ① 依存パッケージの確認・インストール
Write-Host "`n[1/4] 依存パッケージを確認中..." -ForegroundColor Yellow

$packages = @("pyinstaller", "google-generativeai")
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

# qcatch_launcher.py をビルドする（標準ライブラリのみ・依存なし）
# qcatch.py は google-generativeai など大型ライブラリを含むため PyInstaller の
# 再帰制限に引っかかる。ランチャーは add/list/prompt のみの軽量版。
# --onefile       : 単一 .exe に圧縮（Windows Search に「アプリ」として認識させる）
# --distpath .    : qcatch.exe をプロジェクトルートに出力
# --workpath build\work : 中間ファイルを build\ に格納
# --specpath build : .spec ファイルを build\ に格納
pyinstaller `
    --onefile `
    --name qcatch `
    --distpath . `
    --workpath "build\work" `
    --specpath "build" `
    qcatch_launcher.py 2>&1 | Where-Object { $_ -match "(WARN|ERROR|building|completed)" }

Pop-Location

if (-not (Test-Path $ExePath)) {
    Write-Host "  ERROR: qcatch.exe の生成に失敗しました。" -ForegroundColor Red
    exit 1
}
Write-Host "  OK: $ExePath" -ForegroundColor Green


# ③ Windows Search ショートカットを更新（.exe を直接ターゲットに）
Write-Host "`n[3/4] Windows Search ショートカットを更新中..." -ForegroundColor Yellow

$StartMenu = [Environment]::GetFolderPath("Programs")
$LinkPath  = Join-Path $StartMenu "$ShortcutName.lnk"

$sc = (New-Object -ComObject WScript.Shell).CreateShortcut($LinkPath)
$sc.TargetPath       = $ExePath          # ← .exe を直接指定（python.exe 経由ではない）
$sc.Arguments        = "prompt"
$sc.WorkingDirectory = $ScriptDir
$sc.Description      = $Description
$sc.WindowStyle      = 1
$sc.IconLocation     = "$env:SystemRoot\System32\imageres.dll, 114"
$sc.Save()

Write-Host "  OK: ショートカット更新 → $LinkPath" -ForegroundColor Green
Write-Host "  検索キーワード: 「qcatch」（Windows Search に反映まで数分かかる場合あり）" -ForegroundColor DarkGray


# ④ PowerShell プロファイルのコマンドも .exe 使用に更新
Write-Host "`n[4/4] PowerShell コマンドを更新中..." -ForegroundColor Yellow

if (-not (Test-Path $PROFILE)) {
    New-Item -ItemType File -Force -Path $PROFILE | Out-Null
}

$funcLine = "function qcatch { `"$ExePath`" @args }"
$content  = Get-Content $PROFILE -Raw -ErrorAction SilentlyContinue

if ($content -notmatch "function qcatch") {
    Add-Content -Path $PROFILE -Value "`n$funcLine"
} else {
    $newContent = ($content -split "`n" |
        Where-Object { $_ -notmatch "^function qcatch" }) -join "`n"
    [System.IO.File]::WriteAllText($PROFILE, $newContent.TrimEnd() + "`n$funcLine`n")
}
. $PROFILE
Write-Host "  OK: qcatch コマンドが qcatch.exe を使うように更新しました。" -ForegroundColor Green


Write-Host ""
Write-Host "=== ビルド完了 ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "次のステップ:" -ForegroundColor White
Write-Host "  1. Google AI Studio で GEMINI_API_KEY を取得（無料・クレカ不要）" -ForegroundColor Green
Write-Host "     https://aistudio.google.com/app/apikey" -ForegroundColor DarkGray
Write-Host "  2. PowerShell で以下を実行:" -ForegroundColor Green
Write-Host '     [Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "AIzaSy...", "User")' -ForegroundColor DarkGray
Write-Host "  3. PowerShell を再起動して反映" -ForegroundColor Green
Write-Host ""
Write-Host "  sort コマンド: qcatch sort    （GEMINI_API_KEY が設定済みの場合）" -ForegroundColor White
Write-Host "  add コマンド:  qcatch add `"タスク`"" -ForegroundColor White
Write-Host ""
