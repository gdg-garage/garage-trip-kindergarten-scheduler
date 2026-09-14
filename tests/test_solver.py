import pytest
import yaml

from src.models import ScheduleConfig, ShiftAssignment
from src.solver import KindergartenScheduler


@pytest.fixture
def sample_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return ScheduleConfig(**data)


def test_full_schedule_generation(sample_config):
    scheduler = KindergartenScheduler(sample_config)
    assignments = scheduler.solve()

    # 6 days * 4 shift blocks = 24 total shift assignments
    assert len(assignments) == 24


def test_availability_constraint(sample_config):
    scheduler = KindergartenScheduler(sample_config)
    assignments = scheduler.solve()

    for a in assignments:
        if a.day in ["Sun", "Mon", "Tue"] and not a.disabled:
            assert a.parent1 not in ["David", "Bara"]
            assert a.parent2 not in ["David", "Bara"]
        if a.day in ["Sun", "Mon"] and not a.disabled:
            assert a.parent1 not in ["Klarka", "Jask"]
            assert a.parent2 not in ["Klarka", "Jask"]


def test_monday_afternoon_disabled_shifts(sample_config):
    scheduler = KindergartenScheduler(sample_config)
    assignments = scheduler.solve()

    mon_afternoon_assignments = [a for a in assignments if a.day == "Mon" and a.shift_id in [2, 3]]
    assert len(mon_afternoon_assignments) == 2

    for a in mon_afternoon_assignments:
        assert a.disabled is True
        assert a.reason == "OUTDOOR PUZZLE HUNT"
        assert a.parent1 == "OUTDOOR PUZZLE HUNT"
        assert a.parent2 == "OUTDOOR PUZZLE HUNT"


def test_bara_exact_availability_window(sample_config):
    scheduler = KindergartenScheduler(sample_config)
    assignments = scheduler.solve()

    for a in assignments:
        if a.disabled:
            continue
        if a.day == "Wed" and a.shift_id in [0, 1, 2]:  # Arrives Wed 15:00
            assert a.parent1 != "Bara", "Bara scheduled before arrival on Wednesday"
            assert a.parent2 != "Bara", "Bara scheduled before arrival on Wednesday"
        if a.day == "Thu" and a.shift_id in [3]:  # Leaves Thu 17:00
            assert a.parent1 != "Bara", "Bara scheduled after departure on Thursday"
            assert a.parent2 != "Bara", "Bara scheduled after departure on Thursday"
        if a.day == "Fri":
            assert a.parent1 != "Bara", "Bara scheduled on Friday"
            assert a.parent2 != "Bara", "Bara scheduled on Friday"


def test_david_thursday_barcamp_restriction(sample_config):
    scheduler = KindergartenScheduler(sample_config)
    assignments = scheduler.solve()

    for a in assignments:
        if a.day == "Thu" and a.shift_id in [2, 3] and not a.disabled:
            assert a.parent1 != "David", "David scheduled during Barcamp on Thursday"
            assert a.parent2 != "David", "David scheduled during Barcamp on Thursday"


def test_max_shifts_per_day(sample_config):
    scheduler = KindergartenScheduler(sample_config)
    assignments = scheduler.solve()

    daily_counts = {}
    for a in assignments:
        if not a.disabled:
            for p in [a.parent1, a.parent2]:
                key = (a.day, p)
                daily_counts[key] = daily_counts.get(key, 0) + 1

    for (day, p), count in daily_counts.items():
        assert count <= 2, f"Parent {p} assigned {count} shifts on {day}"


def test_no_consecutive_shifts(sample_config):
    scheduler = KindergartenScheduler(sample_config)
    assignments = scheduler.solve()

    # Group by (day, parent) -> list of shift_ids
    shifts_by_day_parent = {}
    for a in assignments:
        if not a.disabled:
            for p in [a.parent1, a.parent2]:
                key = (a.day, p)
                if key not in shifts_by_day_parent:
                    shifts_by_day_parent[key] = []
                shifts_by_day_parent[key].append(a.shift_id)

    for (day, p), shift_ids in shifts_by_day_parent.items():
        sorted_ids = sorted(shift_ids)
        for i in range(len(sorted_ids) - 1):
            assert sorted_ids[i+1] - sorted_ids[i] > 1, f"Parent {p} has consecutive shifts {sorted_ids} on {day}"


def test_early_week_couple_policy(sample_config):
    scheduler = KindergartenScheduler(sample_config)
    assignments = scheduler.solve()

    couples = {
        "Vit": "Eva", "Eva": "Vit",
        "Ales": "Zuzka", "Zuzka": "Ales",
        "Harry": "Klara", "Klara": "Harry",
        "David": "Bara", "Bara": "David",
        "Klarka": "Jask", "Jask": "Klarka"
    }

    for a in assignments:
        if a.day in ["Sun", "Mon", "Tue"] and not a.disabled:
            partner_p1 = couples.get(a.parent1)
            assert a.parent2 != partner_p1, f"Couple {a.parent1} & {a.parent2} scheduled together on {a.day}"


def test_eva_not_overscheduled(sample_config):
    scheduler = KindergartenScheduler(sample_config)
    assignments = scheduler.solve()

    shift_counts = {}
    for a in assignments:
        if not a.disabled:
            shift_counts[a.parent1] = shift_counts.get(a.parent1, 0) + 1
            shift_counts[a.parent2] = shift_counts.get(a.parent2, 0) + 1

    # Eva should not have more shifts than other full-week parents due to tie-breaker
    six_day_parents = ["Vit", "Ales", "Zuzka", "Harry", "Klara"]
    max_other_shifts = max(shift_counts[p] for p in six_day_parents)
    assert shift_counts["Eva"] <= max_other_shifts, f"Eva ({shift_counts['Eva']}) over-scheduled compared to others ({max_other_shifts})"


def test_partial_regeneration_locked_slots(sample_config):
    # Lock Sunday Shift 0 (09:00-11:00) with Vit and Ales
    locked = [
        ShiftAssignment(
            day="Sun",
            shift_id=0,
            shift_name="Shift 1",
            start="09:00",
            end="11:00",
            parent1="Vit",
            parent2="Ales",
            locked=True
        )
    ]

    scheduler = KindergartenScheduler(sample_config)
    assignments = scheduler.solve(locked_assignments=locked)

    # Verify Sunday Shift 0 kept Vit and Ales
    sun_shift_0 = next(a for a in assignments if a.day == "Sun" and a.shift_id == 0)
    assert set([sun_shift_0.parent1, sun_shift_0.parent2]) == set(["Vit", "Ales"])
    assert sun_shift_0.locked is True


def test_locked_days_preservation(sample_config):
    scheduler = KindergartenScheduler(sample_config)
    baseline = scheduler.solve()

    # Lock Sunday and Monday
    locked = [a for a in baseline if a.day in ["Sun", "Mon"]]
    for a in locked:
        a.locked = True

    new_schedule = scheduler.solve(locked_assignments=locked)

    baseline_sun_mon = {(a.day, a.shift_id): (a.parent1, a.parent2) for a in baseline if a.day in ["Sun", "Mon"]}
    new_sun_mon = {(a.day, a.shift_id): (a.parent1, a.parent2) for a in new_schedule if a.day in ["Sun", "Mon"]}

    assert baseline_sun_mon == new_sun_mon

