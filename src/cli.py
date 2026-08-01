import argparse
import sys
import os
import yaml

from src.models import ScheduleConfig
from src.solver import KindergartenScheduler
from src.metrics import calculate_metrics, format_report_summary
from src.gsheet import (
    export_to_csv,
    read_from_csv,
    GoogleSheetHandler
)


def main():
    parser = argparse.ArgumentParser(
        description="Crowd-Sourced Kindergarten Shift Scheduler (Google OR-Tools CP-SAT)"
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to YAML configuration file (default: config.yaml)"
    )
    parser.add_argument(
        "--input-csv",
        help="Path to existing CSV file to preserve locked slots and regenerate open slots."
    )
    parser.add_argument(
        "--export-csv",
        default="schedule.csv",
        help="Path to export output schedule CSV (default: schedule.csv)"
    )
    parser.add_argument(
        "--sync-gsheet",
        action="store_true",
        help="Sync directly with Google Sheets API (reads existing slots and writes updated schedule)."
    )
    parser.add_argument(
        "--creds",
        help="Path to Google Service Account credentials.json file."
    )
    parser.add_argument(
        "--force-fresh",
        action="store_true",
        help="Force full regeneration, ignoring any pre-filled or locked slots."
    )

    args = parser.parse_args()

    # Load configuration
    if not os.path.exists(args.config):
        print(f"Error: Configuration file '{args.config}' not found.")
        sys.exit(1)

    with open(args.config, "r", encoding="utf-8") as f:
        raw_cfg = yaml.safe_load(f)

    try:
        config = ScheduleConfig(**raw_cfg)
    except Exception as e:
        print(f"Error parsing configuration '{args.config}': {e}")
        sys.exit(1)

    existing_assignments = None

    # Handle Google Sheets sync or CSV input for partial regeneration
    gsheet_handler = None
    if args.sync_gsheet:
        gsheet_handler = GoogleSheetHandler(credentials_path=args.creds)
        if not args.force_fresh:
            print("Fetching existing schedule from Google Sheets...")
            try:
                existing_assignments = gsheet_handler.read_schedule(config)
                print(f"Loaded existing schedule from Google Sheet.")
            except Exception as e:
                print(f"Warning: Could not read existing Google Sheet: {e}")
    elif args.input_csv and os.path.exists(args.input_csv) and not args.force_fresh:
        print(f"Loading existing schedule from CSV '{args.input_csv}'...")
        existing_assignments = read_from_csv(args.input_csv, config)

    # Run CP-SAT Solver
    print("Solving shift schedule using Google OR-Tools CP-SAT...")
    try:
        scheduler = KindergartenScheduler(config)
        assignments = scheduler.solve(locked_assignments=existing_assignments)
        print("Successfully generated schedule!")
    except Exception as e:
        print(f"Failed to generate schedule: {e}")
        sys.exit(1)

    # Calculate metrics
    report = calculate_metrics(assignments, config)
    print(format_report_summary(report))

    # Export CSV
    if args.export_csv:
        export_to_csv(assignments, args.export_csv, config)
        print(f"Schedule exported to local CSV: '{args.export_csv}'")

    # Sync to Google Sheets if requested
    if args.sync_gsheet and gsheet_handler:
        print("Uploading updated schedule to Google Sheets...")
        try:
            gsheet_handler.write_schedule(assignments, config)
            print("Successfully updated Google Sheet!")
        except Exception as e:
            print(f"Error uploading to Google Sheet: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
