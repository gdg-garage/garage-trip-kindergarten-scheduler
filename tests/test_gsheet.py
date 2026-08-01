import os
import pytest
import yaml

from src.models import ScheduleConfig
from src.solver import KindergartenScheduler
from src.gsheet import (
    assignments_to_30min_rows,
    parse_30min_rows_to_assignments,
    export_to_csv,
    read_from_csv
)


@pytest.fixture
def sample_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return ScheduleConfig(**data)


def test_30min_row_conversion(sample_config):
    scheduler = KindergartenScheduler(sample_config)
    assignments = scheduler.solve()

    rows = assignments_to_30min_rows(assignments, sample_config)

    # 6 days * (16 half-hour shift slots + 2 lunch slots) = 108 rows
    assert len(rows) == 108

    # Verify lunch break rows exist
    lunch_rows = [r for r in rows if "LUNCH" in r["Parent 1"]]
    assert len(lunch_rows) == 12  # 2 slots per day * 6 days


def test_csv_roundtrip(sample_config, tmp_path):
    scheduler = KindergartenScheduler(sample_config)
    assignments = scheduler.solve()

    csv_file = os.path.join(tmp_path, "test_schedule.csv")
    export_to_csv(assignments, csv_file, sample_config)

    assert os.path.exists(csv_file)

    reloaded = read_from_csv(csv_file, sample_config)
    assert len(reloaded) == len(assignments)

    for orig, reload in zip(assignments, reloaded):
        assert orig.day == reload.day
        assert orig.shift_id == reload.shift_id
        assert set([orig.parent1, orig.parent2]) == set([reload.parent1, reload.parent2])
        assert reload.locked is True
