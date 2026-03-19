# qcatch セットアップスクリプト
# PowerShell コマンド登録 + Windows Search ショートカット作成
#
# 実行方法（実行ポリシーでブロックされる場合）:
#   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
#   その後このスクリプトを右クリック → PowerShell で実行
#   または、このファイルの内容を PowerShell に直接貼り付けて実行

# ── 変数：必要に応じて変更 ────────────────────────────────────────────────
$AppPath      = "C:\dev\ZzzMemo\qcatch.py"
$WorkDir      = "C:\dev\ZzzMemo"
$CmdName      = "qcatch"
$ShortcutName = "qcatch Task Capture"
$Description  = "qcatch - 爆速タスクキャッチ (CLI)"
# ─────────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "=== qcatch セットアップ ===" -ForegroundColor Cyan


# ① PowerShell プロファイルに qcatch 関数を登録（即時有効）
Write-Host "`n[1/3] PowerShell コマンドを登録中..." -ForegroundColor Yellow

if (-not (Test-Path $PROFILE)) {
    New-Item -ItemType File -Force -Path $PROFILE | Out-Null
}

$funcLine = "function $CmdName { python `"$AppPath`" @args }"
$content  = Get-Content $PROFILE -Raw -ErrorAction SilentlyContinue

if ($content -notmatch "function $CmdName") {
    Add-Content -Path $PROFILE -Value "`n$funcLine"
} else {
    $newContent = ($content -split "`n" |
        Where-Object { $_ -notmatch "^function $CmdName" }) -join "`n"
    [System.IO.File]::WriteAllText($PROFILE, $newContent.TrimEnd() + "`n$funcLine`n")
}

. $PROFILE
Write-Host "  OK: '$CmdName' コマンドが使えるようになりました（例: qcatch add `"牛乳を買う`"）" -ForegroundColor Green


# ② Windows Search / スタートメニューにショートカット登録
# 注意: .bat を TargetPath にすると Windows 11 Search に表示されない。
#       python.exe を TargetPath にすることで「アプリ」として認識される。
Write-Host "`n[2/3] Windows Search ショートカットを作成中..." -ForegroundColor Yellow

$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) {
    Write-Host "  ERROR: python が見つかりません。PATH を確認してください。" -ForegroundColor Red
} else {
    $StartMenu = [Environment]::GetFolderPath("Programs")
    $LinkPath  = Join-Path $StartMenu "$ShortcutName.lnk"

    $sc = (New-Object -ComObject WScript.Shell).CreateShortcut($LinkPath)
    $sc.TargetPath       = $PythonExe
    $sc.Arguments        = "`"$AppPath`" prompt"
    $sc.WorkingDirectory = $WorkDir
    $sc.Description      = $Description
    $sc.WindowStyle      = 1
    $sc.IconLocation     = "$env:SystemRoot\System32\imageres.dll, 114"
    $sc.Save()

    Write-Host "  OK: ショートカット作成 → $LinkPath" -ForegroundColor Green
    Write-Host "  Windows Search に反映されるまで数分かかる場合があります。" -ForegroundColor DarkGray
    Write-Host "  検索キーワード: 「qcatch」または「task capture」" -ForegroundColor DarkGray
}


# ③ Win+R 用ランチャー（%USERPROFILE%\bin に .bat を配置して PATH 登録）
Write-Host "`n[3/3] Win+R ランチャーをセットアップ中..." -ForegroundColor Yellow

$BinDir       = Join-Path $env:USERPROFILE "bin"
$LauncherPath = Join-Path $BinDir "qcatch-add.bat"

if (-not (Test-Path $BinDir)) {
    New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
}

$UserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($UserPath -notmatch [regex]::Escape($BinDir)) {
    [Environment]::SetEnvironmentVariable("PATH", "$UserPath;$BinDir", "User")
    Write-Host "  OK: PATH に追加しました → $BinDir" -ForegroundColor Green
} else {
    Write-Host "  既に PATH に存在: $BinDir" -ForegroundColor DarkGray
}

$bat = "@echo off`r`nchcp 65001 > nul`r`ntitle qcatch - タスク追加`r`ncd /d `"$WorkDir`"`r`npython `"$AppPath`" prompt`r`n"
[System.IO.File]::WriteAllText($LauncherPath, $bat, [System.Text.Encoding]::UTF8)
Write-Host "  OK: ランチャー作成 → $LauncherPath" -ForegroundColor Green
Write-Host "  Win+R → 'qcatch-add' は PC 再起動後に有効になります。" -ForegroundColor DarkGray


Write-Host ""
Write-Host "=== セットアップ完了 ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "起動方法まとめ:" -ForegroundColor White
Write-Host "  PowerShell    : qcatch add `"タスク内容`"  （即時）" -ForegroundColor Green
Write-Host "  PowerShell    : qcatch list / qcatch sort  " -ForegroundColor Green
Write-Host "  Windows Search: 「qcatch」で検索           （数分後）" -ForegroundColor Green
Write-Host "  Win+R         : qcatch-add                  （再起動後）" -ForegroundColor Green
Write-Host ""
