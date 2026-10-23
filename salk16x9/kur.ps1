# Beyin Kodu Lab - 16:9 motor kurulumu (DENEME SURUMU)
# KUR.bat ile calistirin. Bilgisayarda kalici bir sistem ayari degistirmez;
# sadece bu klasore .venv ve fonts ekler, eksikse Python ve FFmpeg'i winget ile kurar (onayinizi ister).
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$Engine = $PSScriptRoot
$Root = Split-Path $Engine -Parent
$Log = Join-Path $Engine "kurulum_log.txt"
Start-Transcript -Path $Log -Force | Out-Null

function Adim($m) { Write-Host ""; Write-Host "==> $m" -ForegroundColor Yellow }
function Tamam($m) { Write-Host "    [OK] $m" -ForegroundColor Green }
function RefreshPath {
  $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
}

try {
  Adim "1/6 Python kontrol ediliyor"
  $py = $null
  foreach ($c in @("py -3", "python")) {
    try { $v = & cmd /c "$c --version" 2>$null; if ($LASTEXITCODE -eq 0 -and $v -match "Python 3\.(\d+)") { if ([int]$Matches[1] -ge 10) { $py = $c; break } } } catch {}
  }
  if (-not $py) {
    Write-Host "    Python 3.10+ bulunamadi. winget ile Python 3.12 kurulacak (onay penceresi cikabilir)."
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    RefreshPath
    $py = "py -3"
  }
  $pyExe = (& cmd /c "$py -c ""import sys;print(sys.executable)""").Trim()
  if (-not (Test-Path $pyExe)) { throw "Python yolu bulunamadi." }
  Tamam "Python: $pyExe"

  Adim "2/6 FFmpeg kontrol ediliyor"
  $ff = (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source
  if (-not $ff) {
    Write-Host "    FFmpeg bulunamadi. winget ile kurulacak."
    winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
    RefreshPath
    $ff = (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source
    if (-not $ff) {
      $ff = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
    }
  }
  if (-not $ff) { throw "FFmpeg kurulamadi." }
  [IO.File]::WriteAllText((Join-Path $Engine "ffmpeg_yolu.txt"), $ff, (New-Object Text.UTF8Encoding($false)))
  Tamam "FFmpeg: $ff"

  Adim "3/6 Sanal ortam ve kutuphaneler (numpy, opencv, pillow, scipy)"
  $venv = Join-Path $Engine ".venv"
  if (-not (Test-Path "$venv\Scripts\python.exe")) { & $pyExe -m venv $venv }
  $vpy = "$venv\Scripts\python.exe"
  & $vpy -m pip install --upgrade pip --quiet
  & $vpy -m pip install numpy opencv-python pillow scipy --quiet
  if ($LASTEXITCODE -ne 0) { throw "pip kurulumu basarisiz." }
  Tamam "Kutuphaneler kuruldu"

  Adim "4/6 Inter fontlari (SIL Open Font License)"
  $fonts = Join-Path $Engine "fonts"
  $need = @("InterDisplay-Black.otf","Inter-Bold.otf","Inter-SemiBold.otf","Inter-Medium.otf")
  New-Item -ItemType Directory -Force -Path $fonts | Out-Null
  if (($need | Where-Object { -not (Test-Path (Join-Path $fonts $_)) }).Count -gt 0) {
    $zip = Join-Path $env:TEMP "inter_font.zip"; $ex = Join-Path $env:TEMP "inter_font"
    $ok = $false
    foreach ($ver in @("4.1","4.0")) {
      try { Invoke-WebRequest "https://github.com/rsms/inter/releases/download/v$ver/Inter-$ver.zip" -OutFile $zip -UseBasicParsing; $ok = $true; break } catch {}
    }
    if (-not $ok) { throw "Inter fontu indirilemedi." }
    if (Test-Path $ex) { Remove-Item $ex -Recurse -Force }
    Expand-Archive $zip -DestinationPath $ex -Force
    foreach ($n in $need) {
      $f = Get-ChildItem $ex -Recurse -Filter $n | Select-Object -First 1
      if (-not $f) { throw "Fontta $n bulunamadi." }
      Copy-Item $f.FullName (Join-Path $fonts $n) -Force
    }
  }
  Tamam "Fontlar hazir"

  Adim "5/6 Deneme projesi hazirlaniyor"
  $proj = Join-Path $Root "JonasSalk_16x9_deneme"
  $src = Join-Path $proj "src"
  New-Item -ItemType Directory -Force -Path $src | Out-Null
  $gz = Join-Path $Root "Jonas_Salk_gorseller.zip"
  if (-not (Test-Path (Join-Path $src "06_salk_portre_1959.jpg"))) {
    if (-not (Test-Path $gz)) { throw "Jonas_Salk_gorseller.zip bulunamadi: $gz" }
    Expand-Archive $gz -DestinationPath $src -Force
  }
  $logo = Join-Path $Root "beyinkodulab_profil_led3.png"
  if (Test-Path $logo) { Copy-Item $logo (Join-Path $src "logo.png") -Force }
  Tamam "Proje: $proj"

  Adim "6/6 Test: 540p onizleme render ediliyor (birkac dakika surebilir)"
  $env:BKL_FFMPEG = $ff
  Push-Location $proj
  & $vpy (Join-Path $Engine "render.py") --onizleme
  $code = $LASTEXITCODE
  Pop-Location
  if ($code -ne 0) { throw "Render basarisiz (kod $code)." }
  $out = Get-ChildItem (Join-Path $proj "renders") -Filter "*540p_onizleme.mp4" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  Tamam "Video: $($out.FullName)"
  Write-Host ""
  Write-Host "KURULUM TAMAM. Video aciliyor..." -ForegroundColor Green
  Start-Process $out.FullName
}
catch {
  Write-Host ""
  Write-Host "HATA: $($_.Exception.Message)" -ForegroundColor Red
  Write-Host "Ayrintilar: $Log  (bu dosyayi Claude'a gonderin)"
}
finally {
  Stop-Transcript | Out-Null
  Read-Host "Kapatmak icin Enter'a basin"
}
