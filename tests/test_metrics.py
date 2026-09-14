import pytest
import yaml

from src.models import ScheduleConfig, ShiftAssignment
from src.solver import KindergartenScheduler
from src.metrics import calculate_metrics, format_report_summary


@pytest.fixture
def sample_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return ScheduleConfig(**data)


def test_metrics_calculation(sample_config):
    scheduler = KindergartenScheduler(sample_config)
    assignments = scheduler.solve()

    report = calculate_metrics(assignments, sample_config)

    assert len(report.assignments) == 24
    assert len(report.parent_metrics) == len(sample_config.parents)

    # Verify total shifts assigned across all parents matches active shifts * 2 parents
    active_assignments = [a for a in report.assignments if not a.disabled]
    total_assigned = sum(pm.total_shifts for pm in report.parent_metrics)
    assert total_assigned == len(active_assignments) * 2

    # Verify morning + evening shifts equal total shifts for each parent
    for pm in report.parent_metrics:
        assert pm.morning_shifts + pm.evening_shifts == pm.total_shifts

    # Check that fairness variance is reasonably low (< 0.5)
    assert report.fairness_variance < 0.5
    assert report.morning_evening_balance_score >= 0.0

    # Check report string formatting
    summary_text = format_report_summary(report)
    assert "SCHEDULING METRICS & FAIRNESS REPORT" in summary_text
    assert "Morning vs Evening Balance" in summary_text
    assert "Vit" in summary_text
