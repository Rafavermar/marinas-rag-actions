param(
    [string]$ProjectId,
    [string]$Region = "us-central1",
    [string]$ServiceName = "marinas-rag-actions"
)

if (-not $ProjectId) { throw "ProjectId es obligatorio" }

Write-Host "Autenticando..." -ForegroundColor Cyan
gcloud auth login

gcloud config set project $ProjectId

gcloud services enable run.googleapis.com cloudbuild.googleapis.com cloudscheduler.googleapis.com

$tag = "gcr.io/$ProjectId/$ServiceName"
Write-Host "Construyendo imagen $tag" -ForegroundColor Cyan
gcloud builds submit --tag $tag

Write-Host "Desplegando en Cloud Run" -ForegroundColor Cyan
gcloud run deploy $ServiceName --image $tag --platform managed --region $Region --allow-unauthenticated --set-env-vars "MONGO_URI=$env:MONGO_URI,ADMIN_TOKEN=$env:ADMIN_TOKEN"

$url = gcloud run services describe $ServiceName --platform managed --region $Region --format='value(status.url)'
Write-Host "Servicio disponible en: $url" -ForegroundColor Green

Write-Host "Para crear el Scheduler diario:" -ForegroundColor Cyan
Write-Host "gcloud scheduler jobs create http ingest-job --schedule '0 6 * * *' --uri $url/admin/ingest --http-method POST --headers 'Authorization=Bearer $env:ADMIN_TOKEN' --message-body '{}' --location $Region" -ForegroundColor Yellow
