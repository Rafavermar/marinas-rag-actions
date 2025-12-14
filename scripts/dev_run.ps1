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

python -m uvicorn api.main:app --host 0.0.0.0 --port ${env:PORT}
