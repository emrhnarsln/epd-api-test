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

FastAPI publishes the OpenAPI schema at:

```text
http://localhost:8000/openapi.json
```

For a Custom GPT Action, your API must be reachable from the internet. Localhost will not work directly from ChatGPT. Deploy the API to a public host, or use a tunnel such as ngrok for testing.

## GPT Action setup

1. Open the GPT editor.
2. Go to `Configure`.
3. Open `Actions`.
4. Create a new action.
5. Import the schema from your public `/openapi.json` URL, or paste the schema manually.
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
