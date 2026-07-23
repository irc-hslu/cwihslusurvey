"""Persist study results to Google Sheets."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache

import streamlit as st

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

WORKSHEET_RESPONSES = "responses"
WORKSHEET_ANALYSIS = "responses_analysis"
WORKSHEET_DEMOGRAPHICS = "demographics"
WORKSHEET_PARTICIPANTS = "participants_json"

PARTICIPANT_JSON_COLUMNS = [
    "participant_id",
    "updated_at",
    "json_data",
]

REQUIRED_WORKSHEETS = (
    WORKSHEET_RESPONSES,
    WORKSHEET_ANALYSIS,
    WORKSHEET_DEMOGRAPHICS,
    WORKSHEET_PARTICIPANTS,
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
            "and gcp_service_account to Streamlit secrets."
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
                "`responses`, `responses_analysis`, `demographics`, and `participants_json`.\n"
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
    from gspread.exceptions import CellNotFound

    worksheet = _worksheet(WORKSHEET_PARTICIPANTS, headers=PARTICIPANT_JSON_COLUMNS)
    row = {
        "participant_id": participant_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "json_data": json.dumps(participant_data),
    }
    values = _row_values(row, PARTICIPANT_JSON_COLUMNS)

    try:
        cell = worksheet.find(participant_id, in_column=1)
        worksheet.update(
            values=[values],
            range_name=f"A{cell.row}",
            value_input_option="USER_ENTERED",
        )
    except CellNotFound:
        worksheet.append_row(values, value_input_option="USER_ENTERED")
