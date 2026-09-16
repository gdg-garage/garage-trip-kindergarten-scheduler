import os
import csv
import json
from typing import List, Dict, Tuple, Optional
import gspread
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.oauth2.credentials import Credentials as UserCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from src.models import (
    ScheduleConfig,
    ShiftAssignment,
    ShiftBlock
)


def _generate_30min_slots_for_shift(shift: ShiftBlock) -> List[Tuple[str, str]]:
    """
    Generates 30-minute (start_time, end_time) tuples for a 2-hour shift block.
    Example: 09:00-11:00 -> [('09:00', '09:30'), ('09:30', '10:00'), ('10:00', '10:30'), ('10:30', '11:00')]
    """
    start_h, start_m = map(int, shift.start.split(":"))
    end_h, end_m = map(int, shift.end.split(":"))

    slots = []
    curr_h, curr_m = start_h, start_m

    while (curr_h < end_h) or (curr_h == end_h and curr_m < end_m):
        next_h = curr_h
        next_m = curr_m + 30
        if next_m >= 60:
            next_h += 1
            next_m -= 60

        slot_start_str = f"{curr_h:02d}:{curr_m:02d}"
        slot_end_str = f"{next_h:02d}:{next_m:02d}"
        slots.append((slot_start_str, slot_end_str))

        curr_h, curr_m = next_h, next_m

    return slots


def assignments_to_30min_rows(
    assignments: List[ShiftAssignment],
    config: ScheduleConfig
) -> List[Dict[str, str]]:
    """
    Converts 2-hour shift assignments into 30-minute interval table rows suitable for Google Sheets / CSV export.
    Includes lunch break rows (13:00 - 14:00) with empty/Lunch parent cells.
    """
    rows: List[Dict[str, str]] = []
    assignment_map = {(a.day, a.shift_id): a for a in assignments}

    for day in config.schedule.days:
        for s in sorted(config.schedule.shift_blocks, key=lambda b: b.id):
            # If there is a gap before this shift (e.g. lunch break 13:00 - 14:00)
            if s.id == 2:  # Shift 3 starts at 14:00, Shift 2 ended at 13:00
                rows.append({
                    "Day": day,
                    "Time": "13:00 - 13:30",
                    "Parent 1": "LUNCH BREAK",
                    "Parent 2": "LUNCH BREAK",
                    "Parent 3": "LUNCH BREAK"
                })
                rows.append({
                    "Day": day,
                    "Time": "13:30 - 14:00",
                    "Parent 1": "LUNCH BREAK",
                    "Parent 2": "LUNCH BREAK",
                    "Parent 3": "LUNCH BREAK"
                })

            assignment = assignment_map.get((day, s.id))
            p1 = assignment.parent1 if assignment else ""
            p2 = assignment.parent2 if assignment else ""
            p3 = assignment.parent3 if assignment else ""
            if assignment and assignment.parents:
                p1 = assignment.parents[0] if len(assignment.parents) > 0 else ""
                p2 = assignment.parents[1] if len(assignment.parents) > 1 else ""
                p3 = assignment.parents[2] if len(assignment.parents) > 2 else ""

            sub_slots = _generate_30min_slots_for_shift(s)
            for start_t, end_t in sub_slots:
                rows.append({
                    "Day": day,
                    "Time": f"{start_t} - {end_t}",
                    "Parent 1": p1,
                    "Parent 2": p2,
                    "Parent 3": p3
                })

    return rows


def parse_30min_rows_to_assignments(
    rows: List[Dict[str, str]],
    config: ScheduleConfig
) -> List[ShiftAssignment]:
    """
    Parses 30-minute interval table rows (e.g. from Google Sheet or CSV) back into 2-hour shift assignments.
    Detects pre-filled/locked slots vs unassigned/empty slots.
    """
    # Group rows by Day and Shift ID based on time range
    slot_parents: Dict[Tuple[str, int], List[Tuple[str, str, str]]] = {}

    for row in rows:
        day = row.get("Day", "").strip()
        time_slot = row.get("Time", "").strip()
        p1 = row.get("Parent 1", "").strip()
        p2 = row.get("Parent 2", "").strip()
        p3 = row.get("Parent 3", "").strip()

        if (
            not day
            or any(kw in p1.upper() for kw in ["LUNCH", "PUZZLE", "CANCELLED", "NO SHIFT"])
            or any(kw in p2.upper() for kw in ["LUNCH", "PUZZLE", "CANCELLED", "NO SHIFT"])
            or any(kw in p3.upper() for kw in ["LUNCH", "PUZZLE", "CANCELLED", "NO SHIFT"])
        ):
            continue

        # Extract start time from Time string (e.g., "09:00 - 09:30" -> "09:00")
        start_time = time_slot.split("-")[0].strip() if "-" in time_slot else time_slot

        # Match start time to shift block
        matched_shift: Optional[ShiftBlock] = None
        for s in config.schedule.shift_blocks:
            if s.start <= start_time < s.end:
                matched_shift = s
                break

        if matched_shift:
            key = (day, matched_shift.id)
            if key not in slot_parents:
                slot_parents[key] = []
            slot_parents[key].append((p1, p2, p3))

    disabled_map = {}
    for d_rule in config.schedule.disabled_shifts:
        for s_id in d_rule.shift_ids:
            disabled_map[(d_rule.day, s_id)] = d_rule.reason or "NO SHIFT"

    assignments: List[ShiftAssignment] = []

    for day in config.schedule.days:
        for s in config.schedule.shift_blocks:
            key = (day, s.id)
            if key in disabled_map:
                reason_text = disabled_map[key]
                assignments.append(
                    ShiftAssignment(
                        day=day,
                        shift_id=s.id,
                        shift_name=s.name,
                        start=s.start,
                        end=s.end,
                        parent1=reason_text,
                        parent2=reason_text,
                        parent3=reason_text,
                        parents=[reason_text, reason_text],
                        locked=True,
                        disabled=True,
                        reason=reason_text
                    )
                )
                continue

            parent_pairs = slot_parents.get(key, [])

            # Aggregate parents from 30min rows
            p1_candidates = [
                pair[0] for pair in parent_pairs
                if len(pair) > 0 and pair[0] and not any(kw in pair[0].upper() for kw in ["LUNCH", "PUZZLE", "CANCELLED", "NO SHIFT"])
            ]
            p2_candidates = [
                pair[1] for pair in parent_pairs
                if len(pair) > 1 and pair[1] and not any(kw in pair[1].upper() for kw in ["LUNCH", "PUZZLE", "CANCELLED", "NO SHIFT"])
            ]
            p3_candidates = [
                pair[2] for pair in parent_pairs
                if len(pair) > 2 and pair[2] and not any(kw in pair[2].upper() for kw in ["LUNCH", "PUZZLE", "CANCELLED", "NO SHIFT"])
            ]

            p1 = p1_candidates[0] if p1_candidates else ""
            p2 = p2_candidates[0] if p2_candidates else ""
            p3 = p3_candidates[0] if p3_candidates else ""
            parents_list = [p for p in [p1, p2, p3] if p]

            is_locked = bool(parents_list)

            assignments.append(
                ShiftAssignment(
                    day=day,
                    shift_id=s.id,
                    shift_name=s.name,
                    start=s.start,
                    end=s.end,
                    parent1=p1,
                    parent2=p2,
                    parent3=p3,
                    parents=parents_list,
                    locked=is_locked,
                    disabled=False
                )
            )

    return assignments


def export_to_csv(assignments: List[ShiftAssignment], file_path: str, config: ScheduleConfig):
    """Exports assignments to a CSV file structured by 30-minute rows."""
    rows = assignments_to_30min_rows(assignments, config)
    has_p3 = any(r.get("Parent 3") for r in rows) or any(
        config.schedule.get_parents_per_shift_for_day(d) > 2 for d in config.schedule.days
    )
    fieldnames = ["Day", "Time", "Parent 1", "Parent 2"]
    if has_p3:
        fieldnames.append("Parent 3")

    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_from_csv(file_path: str, config: ScheduleConfig) -> List[ShiftAssignment]:
    """Reads assignments from a CSV file structured by 30-minute rows."""
    if not os.path.exists(file_path):
        return []

    rows = []
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    return parse_30min_rows_to_assignments(rows, config)


class GoogleSheetHandler:
    """
    Handles read/write operations with Google Sheets API via gspread.
    Supports both Google OAuth 2.0 User Authentication and Service Account credentials.
    """

    def __init__(self, credentials_path: Optional[str] = None):
        self.credentials_path = credentials_path or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
        self.client = None

    def _authenticate(self):
        if self.client:
            return

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        token_path = "token.json"
        creds = None

        # 1. Try loading existing OAuth user token if available
        if os.path.exists(token_path):
            try:
                creds = UserCredentials.from_authorized_user_file(token_path, scopes)
            except Exception:
                creds = None

        # Refresh expired token if possible
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        # 2. If no valid user token, check credentials_path
        if not creds:
            if not os.path.exists(self.credentials_path):
                raise FileNotFoundError(
                    f"Google credentials file not found at: '{self.credentials_path}'. "
                    "Please provide credentials.json (OAuth Client Secrets or Service Account Key). "
                    "Alternatively, use --export-csv / --input-csv for local file operations."
                )

            with open(self.credentials_path, "r", encoding="utf-8") as f:
                creds_json = json.load(f)

            if "type" in creds_json and creds_json["type"] == "service_account":
                # Service Account Authentication
                creds = ServiceAccountCredentials.from_service_account_file(self.credentials_path, scopes=scopes)
            elif "installed" in creds_json or "web" in creds_json:
                # OAuth 2.0 User Authentication Flow
                print("Initiating Google OAuth 2.0 User Authentication...")
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, scopes)
                creds = flow.run_local_server(port=0)
                # Save authorized user credentials to token.json
                with open(token_path, "w", encoding="utf-8") as token_file:
                    token_file.write(creds.to_json())
                print(f"OAuth 2.0 authorization successful! User token saved to '{token_path}'.")
            else:
                raise ValueError(f"Unrecognized credentials format in '{self.credentials_path}'.")

        self.client = gspread.authorize(creds)

    def write_schedule(
        self,
        assignments: List[ShiftAssignment],
        config: ScheduleConfig,
        spreadsheet_id: Optional[str] = None,
        sheet_name: str = "Schedule"
    ):
        """Writes assignments to the specified Google Sheet."""
        self._authenticate()
        sheet_id = spreadsheet_id or (config.google_sheets.spreadsheet_id if config.google_sheets else "")
        if not sheet_id:
            raise ValueError("No spreadsheet_id provided in configuration or arguments.")

        spreadsheet = self.client.open_by_key(sheet_id)
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="200", cols="10")

        rows = assignments_to_30min_rows(assignments, config)
        has_p3 = any(r.get("Parent 3") for r in rows) or any(
            config.schedule.get_parents_per_shift_for_day(d) > 2 for d in config.schedule.days
        )
        header = ["Day", "Time", "Parent 1", "Parent 2"]
        if has_p3:
            header.append("Parent 3")
            table_data = [header] + [[r["Day"], r["Time"], r["Parent 1"], r["Parent 2"], r.get("Parent 3", "")] for r in rows]
        else:
            table_data = [header] + [[r["Day"], r["Time"], r["Parent 1"], r["Parent 2"]] for r in rows]

        worksheet.clear()
        worksheet.update("A1", table_data)

    def read_schedule(
        self,
        config: ScheduleConfig,
        spreadsheet_id: Optional[str] = None,
        sheet_name: str = "Schedule"
    ) -> List[ShiftAssignment]:
        """Reads existing schedule from the specified Google Sheet."""
        self._authenticate()
        sheet_id = spreadsheet_id or (config.google_sheets.spreadsheet_id if config.google_sheets else "")
        if not sheet_id:
            raise ValueError("No spreadsheet_id provided in configuration or arguments.")

        spreadsheet = self.client.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)

        records = worksheet.get_all_records()
        return parse_30min_rows_to_assignments(records, config)
