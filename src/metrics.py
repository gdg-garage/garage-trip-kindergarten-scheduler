import statistics
from typing import List, Dict, Tuple
from tabulate import tabulate

from src.models import (
    ScheduleConfig,
    ShiftAssignment,
    ParentMetrics,
    ScheduleReport
)


def calculate_metrics(assignments: List[ShiftAssignment], config: ScheduleConfig) -> ScheduleReport:
    """
    Calculates schedule fairness, morning/evening distribution, and pairing metrics.

    Args:
        assignments: List of generated or updated shift assignments.
        config: Schedule configuration.

    Returns:
        ScheduleReport object containing parent metrics, pairing frequencies, and variance scores.
    """
    shift_counts: Dict[str, int] = {p.name: 0 for p in config.parents}
    morning_counts: Dict[str, int] = {p.name: 0 for p in config.parents}
    evening_counts: Dict[str, int] = {p.name: 0 for p in config.parents}
    shift_hours: Dict[str, float] = {p.name: 0.0 for p in config.parents}

    # Pairing matrix (unordered pair of parent names)
    pair_counts: Dict[Tuple[str, str], int] = {}
    parent_names = sorted([p.name for p in config.parents])
    for i in range(len(parent_names)):
        for j in range(i + 1, len(parent_names)):
            pair_counts[(parent_names[i], parent_names[j])] = 0

    for a in assignments:
        p1, p2 = a.parent1, a.parent2
        hours = 2.0
        is_morning = a.shift_id in [0, 1]
        is_evening = a.shift_id in [2, 3]

        if p1 in shift_counts:
            shift_counts[p1] += 1
            shift_hours[p1] += hours
            if is_morning:
                morning_counts[p1] += 1
            elif is_evening:
                evening_counts[p1] += 1

        if p2 in shift_counts:
            shift_counts[p2] += 1
            shift_hours[p2] += hours
            if is_morning:
                morning_counts[p2] += 1
            elif is_evening:
                evening_counts[p2] += 1

        if p1 and p2 and p1 != p2:
            pair_key = tuple(sorted([p1, p2]))
            if pair_key in pair_counts:
                pair_counts[pair_key] += 1

    parent_metrics_list: List[ParentMetrics] = []
    ratios: List[float] = []
    me_diffs: List[int] = []

    for p in config.parents:
        count = shift_counts[p.name]
        m_count = morning_counts[p.name]
        e_count = evening_counts[p.name]
        me_diffs.append(abs(m_count - e_count))
        hrs = shift_hours[p.name]

        # Calculate effective available days count (accounting for partial shift restrictions)
        unavail_count = sum(len(r.shift_ids) for r in p.unavailable_shifts)
        shifts_per_day_denom = len(config.schedule.shift_blocks)
        avail_count = round(len(p.available_days) - (unavail_count / max(1, shifts_per_day_denom)), 2)

        ratio = count / max(0.1, avail_count)
        ratios.append(ratio)

        parent_metrics_list.append(
            ParentMetrics(
                name=p.name,
                total_shifts=count,
                morning_shifts=m_count,
                evening_shifts=e_count,
                total_hours=hrs,
                available_days_count=avail_count,
                shifts_per_available_day=round(ratio, 2)
            )
        )

    fairness_var = statistics.pvariance(ratios) if len(ratios) > 1 else 0.0
    avg_me_diff = statistics.mean(me_diffs) if me_diffs else 0.0

    return ScheduleReport(
        assignments=assignments,
        parent_metrics=parent_metrics_list,
        pairing_counts=pair_counts,
        fairness_variance=round(fairness_var, 4),
        morning_evening_balance_score=round(avg_me_diff, 2)
    )


def format_report_summary(report: ScheduleReport) -> str:
    """
    Renders human-readable report summary.
    """
    lines = []
    lines.append("\n=== SCHEDULING METRICS & FAIRNESS REPORT ===\n")

    # Parent fairness table
    parent_table = []
    for pm in report.parent_metrics:
        parent_table.append([
            pm.name,
            pm.total_shifts,
            pm.morning_shifts,
            pm.evening_shifts,
            f"{pm.total_hours:.1f} hrs",
            pm.available_days_count,
            f"{pm.shifts_per_available_day:.2f}"
        ])
    lines.append("Parent Shift Distribution (Morning vs Evening Balance):")
    lines.append(tabulate(
        parent_table,
        headers=["Parent", "Total Shifts", "Morning (09-13)", "Evening (14-18)", "Hours", "Avail Days", "Shifts/Avail Day"],
        tablefmt="simple"
    ))
    lines.append(f"\nFairness Variance (lower is better): {report.fairness_variance}")
    lines.append(f"Morning vs Evening Imbalance Score (avg |Morning - Evening| per parent, lower is better): {report.morning_evening_balance_score}\n")

    # Pairing matrix table
    lines.append("Parent Pairing Counts:")
    pair_table = []
    for (p1, p2), count in sorted(report.pairing_counts.items(), key=lambda x: (-x[1], x[0])):
        pair_table.append([f"{p1} & {p2}", count])

    lines.append(tabulate(
        pair_table,
        headers=["Parent Pair", "Times Scheduled Together"],
        tablefmt="simple"
    ))

    return "\n".join(lines)
