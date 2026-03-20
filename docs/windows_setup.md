# Windows セットアップ手順

Python スクリプトを `study` コマンドおよび Windows Search から起動できるようにする手順。

---

## 前提

- Python がインストールされ PATH が通っていること
- PowerShell が使えること

---

## 手順（PowerShell に貼り付けて実行）

### ① PowerShell で `study` コマンドを使えるようにする（即時有効）

```powershell
# ── 変数：自分の環境に合わせて変更 ──────────────────────────────
$AppPath = "C:\dev\remember\flashcard.py"   # 起動したい Python スクリプト
$CmdName = "study"                          # 使いたいコマンド名
# ────────────────────────────────────────────────────────────────

# プロファイルファイルがなければ作成
if (-not (Test-Path $PROFILE)) {
    New-Item -ItemType File -Force -Path $PROFILE | Out-Null
}

$funcLine = "function $CmdName { python `"$AppPath`" }"
$content  = Get-Content $PROFILE -Raw -ErrorAction SilentlyContinue

if ($content -notmatch "function $CmdName") {
    Add-Content -Path $PROFILE -Value "`n$funcLine"
} else {
    $newContent = ($content -split "`n" |
        Where-Object { $_ -notmatch "^function $CmdName" }) -join "`n"
    [System.IO.File]::WriteAllText($PROFILE, $newContent.TrimEnd() + "`n$funcLine`n")
}

. $PROFILE   # 即時リロード
Write-Host "OK: '$CmdName' コマンドが使えるようになりました" -ForegroundColor Green
```

### ② Windows Search・スタートメニューに登録する

```powershell
# ── 変数：自分の環境に合わせて変更 ──────────────────────────────
$AppPath      = "C:\dev\remember\flashcard.py"   # 起動したい Python スクリプト
$WorkDir      = "C:\dev\remember"                # 作業ディレクトリ
$ShortcutName = "Study Flashcards"               # 検索に出る名前
$Description  = "Flashcard Study CUI App Spaced Repetition"
# ────────────────────────────────────────────────────────────────

$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) {
    Write-Host "ERROR: python が見つかりません" -ForegroundColor Red; exit
}

$StartMenu = [Environment]::GetFolderPath("Programs")
$LinkPath  = Join-Path $StartMenu "$ShortcutName.lnk"

$sc = (New-Object -ComObject WScript.Shell).CreateShortcut($LinkPath)
$sc.TargetPath       = $PythonExe
$sc.Arguments        = "`"$AppPath`""
$sc.WorkingDirectory = $WorkDir
$sc.Description      = $Description
$sc.WindowStyle      = 1
$sc.IconLocation     = "$env:SystemRoot\System32\imageres.dll, 114"
$sc.Save()

Write-Host "OK: ショートカット作成 → $LinkPath" -ForegroundColor Green
Write-Host "Windows Search に反映されるまで数分かかる場合があります"

# 確認
Get-ChildItem "$StartMenu\$ShortcutName*"
```

### ③ Win+R で使えるようにする（再起動後に有効）

```powershell
# ── 変数：自分の環境に合わせて変更 ──────────────────────────────
$AppPath = "C:\dev\remember\flashcard.py"
$WorkDir = "C:\dev\remember"
$CmdName = "study"
# ────────────────────────────────────────────────────────────────

$BinDir       = Join-Path $env:USERPROFILE "bin"
$LauncherPath = Join-Path $BinDir "$CmdName.bat"

if (-not (Test-Path $BinDir)) {
    New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
}

$UserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($UserPath -notmatch [regex]::Escape($BinDir)) {
    [Environment]::SetEnvironmentVariable("PATH", "$UserPath;$BinDir", "User")
    Write-Host "OK: PATH に追加しました → $BinDir" -ForegroundColor Green
} else {
    Write-Host "既に PATH に存在: $BinDir" -ForegroundColor DarkGray
}

$bat = "@echo off`r`ntitle $CmdName`r`ncd /d `"$WorkDir`"`r`npython `"$AppPath`"`r`necho.`r`npause"
[System.IO.File]::WriteAllText($LauncherPath, $bat, [System.Text.Encoding]::GetEncoding("shift_jis"))
Write-Host "OK: ランチャー作成 → $LauncherPath" -ForegroundColor Green
Write-Host "Win+R → '$CmdName' は PC 再起動後に有効になります"
```

---

## トラブルシューティング

### スクリプト (.ps1) が実行できない

PowerShell のデフォルト実行ポリシー (`Restricted`) でブロックされている。

```powershell
# 確認
Get-ExecutionPolicy

# 修正（CurrentUser のみに適用、安全）
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

`setup.ps1` を直接実行する代わりに、**上記の各コードブロックを PowerShell に貼り付けて実行する**のが最も確実。

### `study` コマンドが認識されない

プロファイルが反映されていない。新しい PowerShell ウィンドウを開くか、以下を実行：

```powershell
. $PROFILE
```

### Windows Search に出ない

- `.bat` や `cmd.exe` を TargetPath にしたショートカットは Windows 11 Search に「アプリ」として表示されない
- `python.exe` を TargetPath にする（手順②）のが唯一の確実な方法
- ショートカット作成直後は数分かかる場合がある

---

## 起動方法まとめ

| 方法 | コマンド | 有効タイミング |
|---|---|---|
| PowerShell | `study` | 手順①実行後、即時 |
| Win+R | `study` | 手順③実行後、再起動後 |
| Windows Search | `study` または `flashcard` | 手順②実行後、数分後 |
