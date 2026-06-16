# 1. Input new GH_PAT
$newPat = Read-Host -Prompt "Enter the newly generated GitHub PAT (Personal Access Token)"
if (-not $newPat) {
    Write-Host "[Error] No token entered." -ForegroundColor Red
    Exit
}

# 2. Update GitHub Secrets using gh cli
Write-Host "[1/2] Updating GitHub Repository Secret (GH_PAT)..." -ForegroundColor Cyan
$repo = "ssul5-dev/mma-news-briefing"
& "c:\gemini\new\gh-cli\bin\gh.exe" secret set GH_PAT --body "$newPat" --repo $repo
if ($LASTEXITCODE -eq 0) {
    Write-Host "[Success] GitHub Secret (GH_PAT) has been updated." -ForegroundColor Green
} else {
    Write-Host "[Error] Failed to update GitHub Secrets. Please check if you are logged in to gh CLI." -ForegroundColor Red
}

# 3. Update GCP Cloud Scheduler using gcloud cli
Write-Host "[2/2] Updating GCP Cloud Scheduler (daily-mma-news-trigger) header..." -ForegroundColor Cyan

# Set CLOUDSDK_PYTHON if python can be located
$pythonPath = ""
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonPath = (Get-Command python).Source
} elseif (Test-Path "$env:USERPROFILE\AppData\Local\Programs\Python\Python310\python.exe") {
    $pythonPath = "$env:USERPROFILE\AppData\Local\Programs\Python\Python310\python.exe"
} elseif (Test-Path "C:\Program Files\Python310\python.exe") {
    $pythonPath = "C:\Program Files\Python310\python.exe"
}

if ($pythonPath) {
    $env:CLOUDSDK_PYTHON = $pythonPath
} else {
    Write-Host "[Warning] Python not found in common paths. Running gcloud might fail unless CLOUDSDK_PYTHON is set manually." -ForegroundColor Yellow
}

# Update GCP scheduler
& "c:\gemini\new\gcloud-cli\google-cloud-sdk\bin\gcloud.cmd" scheduler jobs update http daily-mma-news-trigger --location=asia-northeast3 --update-headers="Authorization=Bearer $newPat,Accept=application/vnd.github.v3+json,User-Agent=Google-Cloud-Scheduler"

if ($LASTEXITCODE -eq 0) {
    Write-Host "[Success] GCP Cloud Scheduler header has been updated." -ForegroundColor Green
} else {
    Write-Host "[Error] Failed to update GCP Cloud Scheduler." -ForegroundColor Red
    Write-Host "Manual Update Instruction: Go to Google Cloud Console > Cloud Scheduler > Edit 'daily-mma-news-trigger' > Update Authorization Header." -ForegroundColor Yellow
}
