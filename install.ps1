# BobBurn Installer for Windows
# Installs Bob Shell + Python dependencies, then prints run instructions.

Write-Host ""
Write-Host "  BobBurn Installer" -ForegroundColor Cyan
Write-Host "  Real-time Bobcoin metering for IBM Bob" -ForegroundColor DarkCyan
Write-Host ""

# 1. Check Python
Write-Host "Checking Python..." -ForegroundColor Yellow
$py = $null
foreach ($cmd in @("py", "python", "python3")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3") { $py = $cmd; break }
    } catch {}
}
if (-not $py) {
    Write-Host "ERROR: Python 3 not found. Install from https://python.org" -ForegroundColor Red
    exit 1
}
Write-Host "  Found: $(& $py --version)" -ForegroundColor Green

# 2. Install Python deps
Write-Host ""
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
& $py -m pip install -r "$PSScriptRoot\requirements.txt" -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: pip install failed." -ForegroundColor Red
    exit 1
}
Write-Host "  rich, python-dotenv, requests installed." -ForegroundColor Green

# 3. Install Bob Shell
Write-Host ""
Write-Host "Installing Bob Shell..." -ForegroundColor Yellow
try {
    $bobCheck = cmd /c "bob --version 2>&1"
    Write-Host "  Bob Shell already installed: $bobCheck" -ForegroundColor Green
} catch {
    try {
        $ps1 = (Invoke-WebRequest -Uri "https://bob.ibm.com/download/bobshell.ps1" -UseBasicParsing).Content
        $tmpScript = "$env:TEMP\bobshell-install.ps1"
        Set-Content -Path $tmpScript -Value $ps1
        & powershell -ExecutionPolicy Bypass -File $tmpScript -pm npm
        if ($LASTEXITCODE -ne 0) { throw "install failed" }
        Write-Host "  Bob Shell installed successfully." -ForegroundColor Green
    } catch {
        Write-Host "ERROR: Could not install Bob Shell automatically." -ForegroundColor Red
        Write-Host "  Run manually: powershell -c `"irm https://bob.ibm.com/download/bobshell.ps1 | iex`"" -ForegroundColor Yellow
        exit 1
    }
}

# 4. Done
Write-Host ""
Write-Host "All done! To run BobBurn:" -ForegroundColor Cyan
Write-Host ""
Write-Host '  $env:BOB_API_KEY="bob_prod_bob-apikey_..."' -ForegroundColor White
Write-Host "  $py `"$PSScriptRoot\bob_terminal.py`"" -ForegroundColor White
Write-Host ""
Write-Host "Get your Inference API key at: https://bob.ibm.com/admin/api-keys" -ForegroundColor DarkCyan
Write-Host ""
