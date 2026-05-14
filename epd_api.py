import os
from functools import lru_cache
from typing import Annotated, Any

import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field


EXCEL_PATH = os.getenv("EPD_EXCEL_PATH", "EPD_Content_Data.xlsx")
API_KEY = os.getenv("EPD_API_KEY")
PUBLIC_BASE_URL = os.getenv("EPD_PUBLIC_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL")


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


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def clean_value(value: Any) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


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


@app.get("/health", dependencies=[Depends(require_api_key)])
def health() -> dict[str, str]:
    load_data()
    return {"status": "ok"}


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


@app.post("/reload", dependencies=[Depends(require_api_key)])
def reload_data() -> dict[str, str]:
    load_data.cache_clear()
    load_data()
    return {"status": "reloaded"}


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


@app.get("/lessons/{folder_id}", response_model=list[SearchResult], dependencies=[Depends(require_api_key)])
def lesson(
    folder_id: str,
    language: Annotated[str | None, Query(description="Optional language code.")] = None,
    file_type: Annotated[str | None, Query(description="Optional file type filter.")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[SearchResult]:
    df = apply_filters(load_data(), folder_id=folder_id, language=language, file_type=file_type)
    return [row_to_result(row) for _, row in df.head(limit).iterrows()]


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
