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

REQUIRED_WORKSHEETS = (
    WORKSHEET_RESPONSES,
    WORKSHEET_ANALYSIS,
    WORKSHEET_DEMOGRAPHICS,
)


def is_configured() -> bool:
    try:
        has_account = bool(st.secrets.get("gcp_service_account"))
        has_target = bool(st.secrets.get("spreadsheet_id") or st.secrets.get("spreadsheet_name"))
        return has_account and has_target
    except Exception:
        return False


def _require_config():
    if not is_configured():
        raise RuntimeError(
            "Google Sheets storage is not configured. Add spreadsheet_name (or spreadsheet_id) "
            "and gcp_service_account to Streamlit secrets (see GOOGLE_SHEETS_SETUP.md)."
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
    spreadsheet_id = st.secrets.get("spreadsheet_id")
    if spreadsheet_id:
        return client.open_by_key(spreadsheet_id)
    return client.open(st.secrets["spreadsheet_name"])


@st.cache_resource(show_spinner=False)
def _drive_service():
    from googleapiclient.discovery import build

    return build("drive", "v3", credentials=_credentials(), cache_discovery=False)


def _format_api_error(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            return json.dumps(response.json(), indent=2)
        except Exception:
            return getattr(response, "text", str(exc))
    return str(exc)


def _find_worksheet(spreadsheet, name: str):
    from gspread.exceptions import WorksheetNotFound

    try:
        return spreadsheet.worksheet(name)
    except WorksheetNotFound:
        pass

    target = name.strip().lower()
    for worksheet in spreadsheet.worksheets():
        if worksheet.title.strip().lower() == target:
            return worksheet
    return None


def _worksheet(name: str, headers: list[str] | None = None):
    from gspread.exceptions import APIError

    spreadsheet = _spreadsheet()
    worksheet = _find_worksheet(spreadsheet, name)
    if worksheet is None:
        try:
            worksheet = spreadsheet.add_worksheet(
                title=name,
                rows=max(1000, 2),
                cols=max(len(headers or []), 26),
            )
        except APIError as exc:
            spreadsheet_label = st.secrets.get("spreadsheet_name") or st.secrets.get("spreadsheet_id")
            raise RuntimeError(
                f"Worksheet '{name}' was not found in spreadsheet '{spreadsheet_label}', "
                f"and the app could not create it automatically.\n\n"
                "Fix:\n"
                "1. Open the Google Sheet and manually add tabs named "
                "`responses`, `responses_analysis`, and `demographics`.\n"
                "2. Share the spreadsheet with your service account email as Editor.\n"
                "3. Confirm Google Sheets API is enabled for the service account project.\n\n"
                f"Google API response:\n{_format_api_error(exc)}"
            ) from exc

    if headers:
        existing = worksheet.row_values(1)
        if not existing:
            worksheet.update(
                values=[headers],
                range_name="A1",
                value_input_option="USER_ENTERED",
            )
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
