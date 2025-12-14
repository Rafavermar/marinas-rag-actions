$ErrorActionPreference = "Stop"
$EnvFile = ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match "^#" -or $_ -eq "") { return }
        $parts = $_ -split "=",2
        if ($parts.Length -eq 2) {
            $name = $parts[0]
            $value = $parts[1]
            Set-Item -Path Env:\$name -Value $value
        }
    }
}
$baseUrl = $env:API_BASE_URL
if (-not $baseUrl) { $baseUrl = "http://localhost:${env:PORT}" }
$adminToken = $env:ADMIN_TOKEN

Write-Host "Checking /health" -ForegroundColor Cyan
$health = Invoke-RestMethod -Method Get -Uri "$baseUrl/health"
$health

Write-Host "Triggering /admin/ingest" -ForegroundColor Cyan
$ingest = Invoke-RestMethod -Method Post -Uri "$baseUrl/admin/ingest" -Headers @{"Authorization"="Bearer $adminToken"} -Body '{}' -ContentType "application/json"
$ingest

Start-Sleep -Seconds 5

Write-Host "Searching with /search" -ForegroundColor Cyan
$searchBody = @{query="marina"; k=3} | ConvertTo-Json
$search = Invoke-RestMethod -Method Post -Uri "$baseUrl/search" -Body $searchBody -ContentType "application/json"
$search

if ($search.results.Count -gt 0) {
    $ids = @()
    foreach ($r in $search.results) { $ids += $r.id }
    $fetchBody = @{ids=$ids} | ConvertTo-Json
    Write-Host "Fetching chunks with /fetch" -ForegroundColor Cyan
    $fetched = Invoke-RestMethod -Method Post -Uri "$baseUrl/fetch" -Body $fetchBody -ContentType "application/json"
    $fetched
} else {
    Write-Host "No results to fetch" -ForegroundColor Yellow
}
