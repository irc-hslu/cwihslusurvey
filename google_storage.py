"""Persist study results to Google Sheets and Google Drive."""

from __future__ import annotations

import io
import json
from functools import lru_cache

import streamlit as st

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

WORKSHEET_RESPONSES = "responses"
WORKSHEET_ANALYSIS = "responses_analysis"
WORKSHEET_DEMOGRAPHICS = "demographics"
WORKSHEET_METADATA = "_metadata"
METADATA_COUNTER_CELL = "A1"


def is_configured() -> bool:
    try:
        return bool(st.secrets.get("spreadsheet_name")) and bool(st.secrets.get("gcp_service_account"))
    except Exception:
        return False


def _require_config():
    if not is_configured():
        raise RuntimeError(
            "Google Sheets storage is not configured. Add spreadsheet_name and "
            "gcp_service_account to Streamlit secrets (see GOOGLE_SHEETS_SETUP.md)."
        )


@lru_cache(maxsize=1)
def _credentials():
    from google.oauth2.service_account import Credentials

    _require_config()
    return Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=SCOPES,
    )


@st.cache_resource(show_spinner=False)
def _spreadsheet():
    import gspread

    client = gspread.authorize(_credentials())
    return client.open(st.secrets["spreadsheet_name"])


@st.cache_resource(show_spinner=False)
def _drive_service():
    from googleapiclient.discovery import build

    return build("drive", "v3", credentials=_credentials(), cache_discovery=False)


def _worksheet(name: str, headers: list[str] | None = None):
    from gspread.exceptions import WorksheetNotFound

    spreadsheet = _spreadsheet()
    try:
        worksheet = spreadsheet.worksheet(name)
    except WorksheetNotFound:
        rows = 1
        cols = max(len(headers or []), 1)
        worksheet = spreadsheet.add_worksheet(title=name, rows=rows, cols=cols)

    if headers:
        existing = worksheet.row_values(1)
        if not existing:
            worksheet.update("A1", [headers], value_input_option="USER_ENTERED")
        elif existing != headers:
            worksheet.update("A1", [headers], value_input_option="USER_ENTERED")
    return worksheet


def _row_values(row: dict, columns: list[str]) -> list:
    values = []
    for column in columns:
        value = row.get(column, "")
        if value is None:
            value = ""
        values.append(value)
    return values


def append_row(worksheet_name: str, row: dict, columns: list[str]) -> None:
    worksheet = _worksheet(worksheet_name, headers=columns)
    worksheet.append_row(
        _row_values(row, columns),
        value_input_option="USER_ENTERED",
    )


def next_participant_index() -> int:
    worksheet = _worksheet(WORKSHEET_METADATA)
    raw_value = worksheet.acell(METADATA_COUNTER_CELL).value
    current = int(raw_value) if raw_value and str(raw_value).strip().isdigit() else 0
    next_index = current + 1
    worksheet.update_acell(METADATA_COUNTER_CELL, str(next_index))
    return current


def save_participant_json(participant_id: str, participant_data: dict) -> None:
    folder_id = st.secrets.get("drive_folder_id")
    if not folder_id:
        return

    drive = _drive_service()
    filename = f"{participant_id}.json"
    payload = json.dumps(participant_data, indent=2).encode("utf-8")
    media = io.BytesIO(payload)

    query = (
        f"name = '{filename}' and '{folder_id}' in parents and trashed = false"
    )
    existing = (
        drive.files()
        .list(q=query, spaces="drive", fields="files(id)", pageSize=1)
        .execute()
        .get("files", [])
    )

    from googleapiclient.http import MediaIoBaseUpload

    upload = MediaIoBaseUpload(media, mimetype="application/json", resumable=False)

    if existing:
        drive.files().update(fileId=existing[0]["id"], media_body=upload).execute()
        return

    drive.files().create(
        body={"name": filename, "parents": [folder_id]},
        media_body=upload,
        fields="id",
    ).execute()
