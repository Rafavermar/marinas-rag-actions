# Marinas RAG Actions

Proyecto FastAPI listo para despliegue en Google Cloud Run para exponer una API compatible con Actions de un Custom GPT. Realiza ingesta periódica de contenidos públicos, los indexa en MongoDB Atlas y expone búsquedas y recuperaciones de chunks.

## Requisitos
- Python 3.11+
- MongoDB Atlas (M0)
- Google Cloud CLI
- PowerShell (para scripts locales en Windows)

## Configuración local
1. Crea un entorno virtual y activa:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Instala dependencias:
   ```powershell
   pip install -r requirements.txt
   ```
3. Crea un fichero `.env` basado en `.env.example` con `MONGO_URI`, `ADMIN_TOKEN` y `PORT`.
4. Ejecuta el servidor localmente:
   ```powershell
   scripts/dev_run.ps1
   ```

## Estructura
- `api/`: Aplicación FastAPI y capa de datos.
- `ingest/`: Pipeline de ingesta (fetch → extracción → chunking → persistencia).
- `docker/`: Imagen para Cloud Run.
- `scripts/`: Utilidades locales y despliegue.

## Deploy en Cloud Run
Usa el script `scripts/gcloud_deploy.ps1` para construir y desplegar. Configura también un job de Cloud Scheduler diario/semanal que apunte a `/admin/ingest` con cabecera `Authorization: Bearer <ADMIN_TOKEN>`.

## OpenAPI
Consulta `openapi.yaml` y actualiza el `servers.url` con la URL de Cloud Run antes de registrar la acción en el Custom GPT.
