import os
from functools import lru_cache
from typing import Annotated, Any

import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field


EXCEL_PATH = os.getenv("EPD_EXCEL_PATH", "EPD_Content_Data.xlsx")
API_KEY = os.getenv("EPD_API_KEY")
PUBLIC_BASE_URL = os.getenv("EPD_PUBLIC_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL")
LANGUAGE_ALIASES = {
    "english": "EN",
    "en": "EN",
    "turkish": "TR",
    "turkce": "TR",
    "türkçe": "TR",
    "tr": "TR",
    "portuguese": "PT",
    "portekizce": "PT",
    "pt": "PT",
    "czech": "CZ",
    "çekçe": "CZ",
    "cekce": "CZ",
    "cz": "CZ",
    "cs": "CS",
    "slovak": "SK",
    "slovakça": "SK",
    "slovakca": "SK",
    "sk": "SK",
    "latvian": "LV",
    "letonca": "LV",
    "lv": "LV",
}


class SearchResult(BaseModel):
    folder_id: str | None = None
    file_name: str | None = None
    file_type: str | None = None
    language: str | None = None
    course_title: str | None = None
    content: str | None = None
    question: str | None = None
    option_a: str | None = None
    option_b: str | None = None
    option_c: str | None = None
    option_d: str | None = None
    option_e: str | None = None
    correct_answer: str | None = None


class Metadata(BaseModel):
    rows: int
    folders: int
    languages: list[str]
    file_types: list[str]
    course_titles: int


class StatusResponse(BaseModel):
    status: str = Field(description="Current operation status.")


class QuizQuestion(BaseModel):
    folder_id: str | None = None
    language: str | None = None
    course_title: str | None = None
    question: str
    options: dict[str, str]
    correct_answer: str | None = None
    source_file: str | None = None


app_settings = {
    "title": "EPD Content API",
    "description": (
        "API for searching EPD course content, transcripts, assignments, and quiz "
        "questions from EPD_Content_Data.xlsx. Designed for use with ChatGPT GPT Actions."
    ),
    "version": "1.0.0",
}

if PUBLIC_BASE_URL:
    app_settings["servers"] = [{"url": PUBLIC_BASE_URL.rstrip("/")}]

app = FastAPI(**app_settings)


def public_base_url() -> str:
    return PUBLIC_BASE_URL or "https://epd-api-653466732834.europe-west1.run.app"


@app.get("/actions/openapi.json", include_in_schema=False)
def actions_openapi_schema() -> dict[str, Any]:
    """Small OpenAPI schema tailored for ChatGPT GPT Actions."""
    language_schema = {
        "type": "string",
        "enum": ["EN", "TR", "PT", "CS", "SK", "LV", "CZ"],
        "description": "Use a language code, not the full language name.",
    }
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "EPD Content API Actions",
            "description": "Search and retrieve EPD course content and quiz questions.",
            "version": "1.0.0",
        },
        "servers": [{"url": public_base_url().rstrip("/")}],
        "paths": {
            "/actions/metadata": {
                "get": {
                    "operationId": "getMetadata",
                    "summary": "Get dataset metadata",
                    "description": "Returns row counts, available languages, file types, and course title count.",
                    "responses": {
                        "200": {
                            "description": "Dataset metadata",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "rows": {"type": "integer"},
                                            "folders": {"type": "integer"},
                                            "languages": {"type": "array", "items": {"type": "string"}},
                                            "file_types": {"type": "array", "items": {"type": "string"}},
                                            "course_titles": {"type": "integer"},
                                        },
                                        "required": ["rows", "folders", "languages", "file_types", "course_titles"],
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/actions/courses": {
                "get": {
                    "operationId": "listCourses",
                    "summary": "List course titles",
                    "description": "Lists course titles, optionally filtered by language and text query.",
                    "parameters": [
                        {"name": "language", "in": "query", "required": False, "schema": language_schema},
                        {"name": "q", "in": "query", "required": False, "schema": {"type": "string"}},
                        {
                            "name": "limit",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Course titles",
                            "content": {
                                "application/json": {
                                    "schema": {"type": "array", "items": {"type": "string"}}
                                }
                            },
                        }
                    },
                }
            },
            "/actions/search": {
                "get": {
                    "operationId": "searchContent",
                    "summary": "Search course content",
                    "description": "Searches course titles, content, and quiz questions.",
                    "parameters": [
                        {"name": "q", "in": "query", "required": True, "schema": {"type": "string"}},
                        {"name": "folder_id", "in": "query", "required": False, "schema": {"type": "string"}},
                        {"name": "language", "in": "query", "required": False, "schema": language_schema},
                        {"name": "file_type", "in": "query", "required": False, "schema": {"type": "string"}},
                        {"name": "course_title", "in": "query", "required": False, "schema": {"type": "string"}},
                        {
                            "name": "limit",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
                        },
                    ],
                    "responses": {"200": {"description": "Search results", "content": {"application/json": {"schema": search_result_array_schema()}}}},
                }
            },
            "/actions/lessons/{folder_id}": {
                "get": {
                    "operationId": "getLessonByFolder",
                    "summary": "Get records for a lesson folder",
                    "description": "Returns records for a specific Folder_ID.",
                    "parameters": [
                        {"name": "folder_id", "in": "path", "required": True, "schema": {"type": "string"}},
                        {"name": "language", "in": "query", "required": False, "schema": language_schema},
                        {"name": "file_type", "in": "query", "required": False, "schema": {"type": "string"}},
                        {
                            "name": "limit",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
                        },
                    ],
                    "responses": {"200": {"description": "Lesson records", "content": {"application/json": {"schema": search_result_array_schema()}}}},
                }
            },
            "/actions/quiz": {
                "get": {
                    "operationId": "getQuizQuestions",
                    "summary": "Get quiz questions",
                    "description": "Returns quiz questions. Keep reveal_answers false unless the user explicitly asks for answers.",
                    "parameters": [
                        {"name": "folder_id", "in": "query", "required": False, "schema": {"type": "string"}},
                        {"name": "language", "in": "query", "required": False, "schema": language_schema},
                        {"name": "course_title", "in": "query", "required": False, "schema": {"type": "string"}},
                        {
                            "name": "reveal_answers",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "boolean", "default": False},
                        },
                        {
                            "name": "limit",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Quiz questions",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "folder_id": {"type": "string"},
                                                "language": {"type": "string"},
                                                "course_title": {"type": "string"},
                                                "question": {"type": "string"},
                                                "option_a": {"type": "string"},
                                                "option_b": {"type": "string"},
                                                "option_c": {"type": "string"},
                                                "option_d": {"type": "string"},
                                                "option_e": {"type": "string"},
                                                "correct_answer": {"type": "string"},
                                                "source_file": {"type": "string"},
                                            },
                                            "required": [
                                                "folder_id",
                                                "language",
                                                "course_title",
                                                "question",
                                                "option_a",
                                                "option_b",
                                                "option_c",
                                                "option_d",
                                                "option_e",
                                                "correct_answer",
                                                "source_file",
                                            ],
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
        },
    }


def search_result_array_schema() -> dict[str, Any]:
    text_or_null = {"type": "string"}
    return {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "folder_id": text_or_null,
                "file_name": text_or_null,
                "file_type": text_or_null,
                "language": text_or_null,
                "course_title": text_or_null,
                "content_preview": text_or_null,
                "question": text_or_null,
                "option_a": text_or_null,
                "option_b": text_or_null,
                "option_c": text_or_null,
                "option_d": text_or_null,
                "option_e": text_or_null,
                "correct_answer": text_or_null,
            },
        },
    }


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def clean_value(value: Any) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def action_value(value: Any) -> str:
    return clean_value(value) or ""


def normalize_language(language: str | None) -> str | None:
    if not language:
        return None
    normalized = LANGUAGE_ALIASES.get(language.strip().casefold())
    return normalized or language.strip().upper()


def clamp_limit(limit: int, maximum: int) -> int:
    return max(1, min(limit, maximum))


def row_to_result(row: pd.Series) -> SearchResult:
    return SearchResult(
        folder_id=clean_value(row.get("Folder_ID")),
        file_name=clean_value(row.get("File_Name")),
        file_type=clean_value(row.get("File_Type")),
        language=clean_value(row.get("Language")),
        course_title=clean_value(row.get("Course_Title")),
        content=clean_value(row.get("Content")),
        question=clean_value(row.get("Question")),
        option_a=clean_value(row.get("Option_A")),
        option_b=clean_value(row.get("Option_B")),
        option_c=clean_value(row.get("Option_C")),
        option_d=clean_value(row.get("Option_D")),
        option_e=clean_value(row.get("Option_E")),
        correct_answer=clean_value(row.get("Correct_Answer")),
    )


def compact_text(value: Any, max_chars: int = 1200) -> str | None:
    text = clean_value(value)
    if not text:
        return None
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def row_to_compact_result(row: pd.Series, max_content_chars: int = 1200) -> dict[str, str]:
    return {
        "folder_id": action_value(row.get("Folder_ID")),
        "file_name": action_value(row.get("File_Name")),
        "file_type": action_value(row.get("File_Type")),
        "language": action_value(row.get("Language")),
        "course_title": action_value(row.get("Course_Title")),
        "content_preview": compact_text(row.get("Content"), max_content_chars) or "",
        "question": action_value(row.get("Question")),
        "option_a": action_value(row.get("Option_A")),
        "option_b": action_value(row.get("Option_B")),
        "option_c": action_value(row.get("Option_C")),
        "option_d": action_value(row.get("Option_D")),
        "option_e": action_value(row.get("Option_E")),
        "correct_answer": action_value(row.get("Correct_Answer")),
    }


@lru_cache(maxsize=1)
def load_data() -> pd.DataFrame:
    df = pd.read_excel(EXCEL_PATH, dtype=str).fillna("")
    for column in df.columns:
        df[column] = df[column].astype(str).str.strip()
    return df


def apply_filters(
    df: pd.DataFrame,
    folder_id: str | None = None,
    language: str | None = None,
    file_type: str | None = None,
    course_title: str | None = None,
) -> pd.DataFrame:
    filtered = df
    language = normalize_language(language)
    if folder_id:
        filtered = filtered[filtered["Folder_ID"].str.casefold() == folder_id.casefold()]
    if language:
        filtered = filtered[filtered["Language"].str.casefold() == language.casefold()]
    if file_type:
        filtered = filtered[filtered["File_Type"].str.casefold() == file_type.casefold()]
    if course_title:
        filtered = filtered[
            filtered["Course_Title"].str.casefold().str.contains(course_title.casefold(), na=False)
        ]
    return filtered


@app.get("/health", response_model=StatusResponse, dependencies=[Depends(require_api_key)])
def health() -> StatusResponse:
    return StatusResponse(status="ok")


@app.get("/", response_model=StatusResponse, dependencies=[Depends(require_api_key)])
def root() -> StatusResponse:
    return StatusResponse(status="ok")


@app.get("/metadata", response_model=Metadata, dependencies=[Depends(require_api_key)])
def metadata() -> Metadata:
    df = load_data()
    return Metadata(
        rows=len(df),
        folders=df["Folder_ID"].replace("", pd.NA).dropna().nunique(),
        languages=sorted(df["Language"].replace("", pd.NA).dropna().unique().tolist()),
        file_types=sorted(df["File_Type"].replace("", pd.NA).dropna().unique().tolist()),
        course_titles=df["Course_Title"].replace("", pd.NA).dropna().nunique(),
    )


@app.get("/actions/metadata", include_in_schema=False, dependencies=[Depends(require_api_key)])
def actions_metadata() -> Metadata:
    return metadata()


@app.post("/reload", response_model=StatusResponse, dependencies=[Depends(require_api_key)])
def reload_data() -> StatusResponse:
    load_data.cache_clear()
    load_data()
    return StatusResponse(status="reloaded")


@app.get("/search", response_model=list[SearchResult], dependencies=[Depends(require_api_key)])
def search(
    q: Annotated[str, Query(description="Text to search in course titles, content, and questions.")] = "",
    folder_id: str | None = None,
    language: Annotated[str | None, Query(description="Language code such as EN, TR, PT, CS, SK, LV, CZ.")] = None,
    file_type: Annotated[
        str | None,
        Query(description="Assignment, Transcript, Quiz, Youtube Link, Other, or Lecture Notes."),
    ] = None,
    course_title: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[SearchResult]:
    df = apply_filters(load_data(), folder_id, language, file_type, course_title)
    query = q.casefold()
    haystack = (
        df["Course_Title"].str.casefold()
        + " "
        + df["Content"].str.casefold()
        + " "
        + df["Question"].str.casefold()
    )
    matches = df[haystack.str.contains(query, na=False)].head(limit)
    return [row_to_result(row) for _, row in matches.iterrows()]


@app.get("/actions/search", include_in_schema=False, dependencies=[Depends(require_api_key)])
def actions_search(
    q: Annotated[str, Query(description="Text to search in course titles, content, and questions.")] = "",
    folder_id: str | None = None,
    language: Annotated[str | None, Query(description="Language code such as EN, TR, PT, CS, SK, LV, CZ.")] = None,
    file_type: Annotated[
        str | None,
        Query(description="Assignment, Transcript, Quiz, Youtube Link, Other, or Lecture Notes."),
    ] = None,
    course_title: str | None = None,
    limit: Annotated[int, Query(ge=1)] = 5,
) -> list[dict[str, str]]:
    limit = clamp_limit(limit, 10)
    df = apply_filters(load_data(), folder_id, language, file_type, course_title)
    query = q.casefold()
    haystack = (
        df["Course_Title"].str.casefold()
        + " "
        + df["Content"].str.casefold()
        + " "
        + df["Question"].str.casefold()
    )
    matches = df[haystack.str.contains(query, na=False)].head(limit)
    return [row_to_compact_result(row) for _, row in matches.iterrows()]


@app.get("/lessons/{folder_id}", response_model=list[SearchResult], dependencies=[Depends(require_api_key)])
def lesson(
    folder_id: str,
    language: Annotated[str | None, Query(description="Optional language code.")] = None,
    file_type: Annotated[str | None, Query(description="Optional file type filter.")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[SearchResult]:
    df = apply_filters(load_data(), folder_id=folder_id, language=language, file_type=file_type)
    return [row_to_result(row) for _, row in df.head(limit).iterrows()]


@app.get("/actions/lessons/{folder_id}", include_in_schema=False, dependencies=[Depends(require_api_key)])
def actions_lesson(
    folder_id: str,
    language: Annotated[str | None, Query(description="Optional language code.")] = None,
    file_type: Annotated[str | None, Query(description="Optional file type filter.")] = None,
    limit: Annotated[int, Query(ge=1)] = 5,
) -> list[dict[str, str]]:
    limit = clamp_limit(limit, 10)
    df = apply_filters(load_data(), folder_id=folder_id, language=language, file_type=file_type)
    if not file_type:
        transcript_df = df[df["File_Type"].str.casefold() == "transcript"]
        if not transcript_df.empty:
            df = transcript_df
    return [row_to_compact_result(row) for _, row in df.head(limit).iterrows()]


@app.get("/quiz", response_model=list[QuizQuestion], dependencies=[Depends(require_api_key)])
def quiz(
    folder_id: str | None = None,
    language: Annotated[str | None, Query(description="Optional language code.")] = None,
    course_title: str | None = None,
    reveal_answers: Annotated[bool, Query(description="Set true only when the user asks for answers.")] = False,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[QuizQuestion]:
    df = apply_filters(
        load_data(),
        folder_id=folder_id,
        language=language,
        file_type="Quiz",
        course_title=course_title,
    )
    df = df[df["Question"].astype(bool)].head(limit)
    questions: list[QuizQuestion] = []
    for _, row in df.iterrows():
        options = {
            key: value
            for key, value in {
                "A": clean_value(row.get("Option_A")),
                "B": clean_value(row.get("Option_B")),
                "C": clean_value(row.get("Option_C")),
                "D": clean_value(row.get("Option_D")),
                "E": clean_value(row.get("Option_E")),
            }.items()
            if value
        }
        questions.append(
            QuizQuestion(
                folder_id=clean_value(row.get("Folder_ID")),
                language=clean_value(row.get("Language")),
                course_title=clean_value(row.get("Course_Title")),
                question=clean_value(row.get("Question")) or "",
                options=options,
                correct_answer=clean_value(row.get("Correct_Answer")) if reveal_answers else None,
                source_file=clean_value(row.get("File_Name")),
            )
        )
    return questions


@app.get("/actions/quiz", include_in_schema=False, dependencies=[Depends(require_api_key)])
def actions_quiz(
    folder_id: str | None = None,
    language: Annotated[str | None, Query(description="Optional language code.")] = None,
    course_title: str | None = None,
    reveal_answers: Annotated[bool, Query(description="Set true only when the user asks for answers.")] = False,
    limit: Annotated[int, Query(ge=1)] = 5,
) -> list[dict[str, Any]]:
    limit = clamp_limit(limit, 10)
    questions = quiz(folder_id, language, course_title, reveal_answers, limit)
    response: list[dict[str, Any]] = []
    for question in questions:
        item = {
            "folder_id": question.folder_id or "",
            "language": question.language or "",
            "course_title": question.course_title or "",
            "question": question.question,
            "option_a": question.options.get("A", ""),
            "option_b": question.options.get("B", ""),
            "option_c": question.options.get("C", ""),
            "option_d": question.options.get("D", ""),
            "option_e": question.options.get("E", ""),
            "correct_answer": (question.correct_answer or "") if reveal_answers else "",
            "source_file": question.source_file or "",
        }
        response.append(item)
    return response


@app.get("/courses", response_model=list[str], dependencies=[Depends(require_api_key)])
def courses(
    language: str | None = None,
    q: Annotated[str | None, Query(description="Optional text filter for course titles.")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[str]:
    df = apply_filters(load_data(), language=language)
    titles = df["Course_Title"].replace("", pd.NA).dropna().drop_duplicates()
    if q:
        titles = titles[titles.str.casefold().str.contains(q.casefold(), na=False)]
    return titles.sort_values().head(limit).tolist()


@app.get("/actions/courses", include_in_schema=False, dependencies=[Depends(require_api_key)])
def actions_courses(
    language: str | None = None,
    q: Annotated[str | None, Query(description="Optional text filter for course titles.")] = None,
    limit: Annotated[int, Query(ge=1)] = 20,
) -> list[str]:
    limit = clamp_limit(limit, 50)
    return courses(language, q, limit)
