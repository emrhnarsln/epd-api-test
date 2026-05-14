# EPD Content API

This API exposes `EPD_Content_Data.xlsx` for ChatGPT Custom GPT Actions.

## Run locally

```powershell
pip install -r requirements.txt
uvicorn epd_api:app --reload --host 0.0.0.0 --port 8000
```

Optional API key:

```powershell
$env:EPD_API_KEY="change-me"
uvicorn epd_api:app --reload --host 0.0.0.0 --port 8000
```

For GPT Actions, set the public API URL so the OpenAPI schema includes a valid `servers` entry:

```powershell
$env:EPD_PUBLIC_BASE_URL="https://your-render-service.onrender.com"
```

Optional custom Excel path:

```powershell
$env:EPD_EXCEL_PATH="EPD_Content_Data.xlsx"
```

## Useful endpoints

- `GET /health`
- `GET /metadata`
- `GET /courses?language=EN&q=ecology`
- `GET /search?q=carrying capacity&language=EN&limit=5`
- `GET /lessons/101?language=EN`
- `GET /quiz?folder_id=101&language=EN&reveal_answers=false`
- `POST /reload`

FastAPI publishes the full OpenAPI schema at:

```text
http://localhost:8000/openapi.json
```

For Custom GPT Actions, prefer the smaller action-specific schema:

```text
http://localhost:8000/actions/openapi.json
```

For a Custom GPT Action, your API must be reachable from the internet. Localhost will not work directly from ChatGPT. Deploy the API to a public host, or use a tunnel such as ngrok for testing.

## Deploy to Google Cloud Run

Install and authenticate the Google Cloud CLI:

```powershell
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

Enable the required APIs:

```powershell
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

Deploy from the repository root:

```powershell
gcloud run deploy epd-api --source . --region europe-west1 --allow-unauthenticated
```

After deployment, Cloud Run prints a service URL like:

```text
https://epd-api-xxxxx-ew.a.run.app
```

Set this URL for the OpenAPI `servers` field:

```powershell
gcloud run services update epd-api --region europe-west1 --set-env-vars EPD_PUBLIC_BASE_URL=https://epd-api-xxxxx-ew.a.run.app
```

Optional API key:

```powershell
gcloud run services update epd-api --region europe-west1 --set-env-vars EPD_API_KEY=change-me
```

Test:

```text
https://epd-api-xxxxx-ew.a.run.app/health
https://epd-api-xxxxx-ew.a.run.app/metadata
https://epd-api-xxxxx-ew.a.run.app/openapi.json
https://epd-api-xxxxx-ew.a.run.app/actions/openapi.json
```

## GPT Action setup

1. Open the GPT editor.
2. Go to `Configure`.
3. Open `Actions`.
4. Create a new action.
5. Import the schema from your public `/actions/openapi.json` URL, or paste the schema manually.
6. If `EPD_API_KEY` is enabled, configure authentication as an API key with header name:

```text
x-api-key
```

## Suggested GPT instructions

```text
You are an EPD course assistant. Use the EPD Content API action whenever the user asks about course content, lesson summaries, quiz questions, assignments, languages, folder IDs, or course titles.

Use /metadata to understand available data.
Use /courses to find course titles.
Use /lessons/{folder_id} when the user mentions a folder or lesson number.
Use /search when the user asks about a topic or keyword.
Use /quiz when the user asks for quiz questions.

Do not invent course content. If the API returns no relevant result, say that no matching record was found.
By default, hide quiz answers. Only request reveal_answers=true when the user explicitly asks for the answer key or wants answers shown.
Answer in Turkish unless the user asks for another language.
When possible, cite the Folder_ID and File_Name from API results.
```
