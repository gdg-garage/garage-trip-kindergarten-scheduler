import math
from typing import List, Dict, Tuple, Optional
from ortools.sat.python import cp_model

from src.models import (
    ScheduleConfig,
    ShiftAssignment,
    ParentConfig,
    ShiftBlock
)


class KindergartenScheduler:
    """
    CP-SAT constraint programming scheduler for kindergarten shift assignment.
    Handles hard constraints, soft optimization objectives, and partial schedule locking.
    """

    def __init__(self, config: ScheduleConfig):
        self.config = config
        self.parents = [p.name for p in config.parents]
        self.parent_map: Dict[str, ParentConfig] = {p.name: p for p in config.parents}
        self.days = config.schedule.days
        self.shifts = config.schedule.shift_blocks
        self.parents_per_shift = config.schedule.parents_per_shift

    def solve(
        self,
        locked_assignments: Optional[List[ShiftAssignment]] = None,
        time_limit_seconds: float = 2.0
    ) -> List[ShiftAssignment]:
        """
        Solves the shift scheduling problem.

        Args:
            locked_assignments: Existing shift assignments to preserve/lock.
            time_limit_seconds: Maximum time allowed for solver in seconds.

        Returns:
            List of ShiftAssignment objects representing the schedule.
        """
        model = cp_model.CpModel()

        # Decision variables: x[d, s, p] = 1 if parent p is assigned to day d, shift s
        x: Dict[Tuple[str, int, str], cp_model.IntVar] = {}
        for d in self.days:
            for s in self.shifts:
                for p in self.parents:
                    x[(d, s.id, p)] = model.NewBoolVar(f"x_{d}_{s.id}_{p}")

        # Map locked assignments for fast lookup
        locked_map: Dict[Tuple[str, int], List[str]] = {}
        if locked_assignments:
            for assignment in locked_assignments:
                if not assignment.locked:
                    continue
                key = (assignment.day, assignment.shift_id)
                parents_in_slot = []
                assigned_candidates = assignment.parents if assignment.parents else [assignment.parent1, assignment.parent2, assignment.parent3]
                for p in assigned_candidates:
                    if p and p in self.parents and p not in parents_in_slot:
                        parents_in_slot.append(p)
                if parents_in_slot:
                    locked_map[key] = parents_in_slot

        # Map disabled/cancelled shifts
        disabled_map: Dict[Tuple[str, int], str] = {}
        for disabled_rule in self.config.schedule.disabled_shifts:
            for s_id in disabled_rule.shift_ids:
                reason = disabled_rule.reason or "NO SHIFT"
                disabled_map[(disabled_rule.day, s_id)] = reason

        # HARD CONSTRAINTS

        # 1. Capacity: Exactly required parents assigned to active shifts, 0 for disabled shifts
        for d in self.days:
            req_parents = self.config.schedule.get_parents_per_shift_for_day(d)
            for s in self.shifts:
                if (d, s.id) in disabled_map:
                    model.Add(sum(x[(d, s.id, p)] for p in self.parents) == 0)
                elif (d, s.id) in locked_map:
                    model.Add(sum(x[(d, s.id, p)] for p in self.parents) == len(locked_map[(d, s.id)]))
                else:
                    model.Add(sum(x[(d, s.id, p)] for p in self.parents) == req_parents)

        # 2. Availability & Shift Restrictions constraint
        total_available_slots_per_parent = {}
        for p in self.parents:
            avail_days = set(self.parent_map[p].available_days)
            unavail_shifts_set = set()
            for restriction in self.parent_map[p].unavailable_shifts:
                for s_id in restriction.shift_ids:
                    unavail_shifts_set.add((restriction.day, s_id))

            avail_slot_count = 0
            for d in self.days:
                for s in self.shifts:
                    if d not in avail_days or (d, s.id) in unavail_shifts_set:
                        model.Add(x[(d, s.id, p)] == 0)
                    else:
                        avail_slot_count += 1
            total_available_slots_per_parent[p] = avail_slot_count

        # 3. Max shifts per day
        max_daily = self.config.constraints.max_shifts_per_day
        for d in self.days:
            for p in self.parents:
                model.Add(sum(x[(d, s.id, p)] for s in self.shifts) <= max_daily)

        # 4. No consecutive shifts
        if self.config.constraints.disallow_consecutive_shifts:
            sorted_shift_ids = [s.id for s in sorted(self.shifts, key=lambda b: b.id)]
            for d in self.days:
                for p in self.parents:
                    for i in range(len(sorted_shift_ids) - 1):
                        s1 = sorted_shift_ids[i]
                        s2 = sorted_shift_ids[i + 1]
                        model.Add(x[(d, s1, p)] + x[(d, s2, p)] <= 1)

        # 5. Couple policy
        couple_policy = self.config.constraints.couple_policy
        early_days = set(couple_policy.early_week_days)
        for p in self.parents:
            partner = self.parent_map[p].partner
            if partner and partner in self.parents:
                for d in self.days:
                    # Early week: strict separation
                    if couple_policy.early_week_disallow and d in early_days:
                        for s in self.shifts:
                            model.Add(x[(d, s.id, p)] + x[(d, s.id, partner)] <= 1)

        # 6. Apply locked / fixed assignments
        for (d, s_id), parents_in_slot in locked_map.items():
            if d in self.days and s_id in [s.id for s in self.shifts]:
                for p in parents_in_slot:
                    model.Add(x[(d, s_id, p)] == 1)

        # SOFT OPTIMIZATION OBJECTIVES

        weights = self.config.constraints.weights
        objective_terms = []

        # A. Fairness Objective: Minimize deviation from expected share of shifts
        total_slots_needed = 0
        for d in self.days:
            req_parents = self.config.schedule.get_parents_per_shift_for_day(d)
            for s in self.shifts:
                if (d, s.id) not in disabled_map:
                    if (d, s.id) in locked_map:
                        total_slots_needed += len(locked_map[(d, s.id)])
                    else:
                        total_slots_needed += req_parents
        total_all_avail_slots = sum(total_available_slots_per_parent.values())
        ratio = total_slots_needed / max(1, total_all_avail_slots)

        for p in self.parents:
            avail_slots = total_available_slots_per_parent[p]
            expected_shifts = math.ceil(ratio * avail_slots)
            total_shifts_p = sum(x[(d, s.id, p)] for d in self.days for s in self.shifts)

            # Deviation variable |TotalShifts - ExpectedShifts|
            diff = model.NewIntVar(-50, 50, f"diff_{p}")
            model.Add(diff == total_shifts_p - expected_shifts)
            abs_diff = model.NewIntVar(0, 50, f"abs_diff_{p}")
            model.AddAbsEquality(abs_diff, diff)

            objective_terms.append(abs_diff * weights.fairness_weight)

        # B. Pair Diversity: Minimize repeated pairings of same parents
        pair_counts: Dict[Tuple[str, str], cp_model.IntVar] = {}
        for i in range(len(self.parents)):
            for j in range(i + 1, len(self.parents)):
                p1, p2 = self.parents[i], self.parents[j]
                pair_key = (p1, p2)

                shift_together = []
                for d in self.days:
                    for s in self.shifts:
                        tog = model.NewBoolVar(f"together_{d}_{s.id}_{p1}_{p2}")
                        # Linear relaxation: tog >= x1 + x2 - 1 (since minimizing tog, it stays 0 unless x1=x2=1)
                        model.Add(tog >= x[(d, s.id, p1)] + x[(d, s.id, p2)] - 1)
                        shift_together.append(tog)

                        # Late week couple preference option
                        if (
                            self.parent_map[p1].partner == p2
                            and d not in early_days
                            and couple_policy.late_week_preference_weight > 0
                        ):
                            objective_terms.append(tog * (-couple_policy.late_week_preference_weight))

                count_var = model.NewIntVar(0, len(self.days) * len(self.shifts), f"pair_count_{p1}_{p2}")
                model.Add(count_var == sum(shift_together))
                pair_counts[pair_key] = count_var

                # Penalize counts >= 2
                over_one = model.NewIntVar(0, len(self.days) * len(self.shifts), f"over_one_{p1}_{p2}")
                model.Add(over_one >= count_var - 1)
                model.Add(over_one >= 0)

                objective_terms.append(over_one * weights.pair_diversity_weight * 3)

        # C. Daily Balance: Prefer 1 shift per day over 2 shifts
        for d in self.days:
            for p in self.parents:
                daily_shifts = sum(x[(d, s.id, p)] for s in self.shifts)
                is_two_shifts = model.NewBoolVar(f"two_shifts_{d}_{p}")
                model.Add(daily_shifts == 2).OnlyEnforceIf(is_two_shifts)
                model.Add(daily_shifts != 2).OnlyEnforceIf(is_two_shifts.Not())
                objective_terms.append(is_two_shifts * weights.daily_balance_weight)

        # D. Morning vs Evening Balance: Minimize |MorningShifts - EveningShifts| per parent
        for p in self.parents:
            morning_shifts = sum(x[(d, s.id, p)] for d in self.days for s in self.shifts if s.id in [0, 1])
            evening_shifts = sum(x[(d, s.id, p)] for d in self.days for s in self.shifts if s.id in [2, 3])

            me_diff = model.NewIntVar(-50, 50, f"me_diff_{p}")
            model.Add(me_diff == morning_shifts - evening_shifts)
            abs_me_diff = model.NewIntVar(0, 50, f"abs_me_diff_{p}")
            model.AddAbsEquality(abs_me_diff, me_diff)

            objective_terms.append(abs_me_diff * weights.morning_evening_balance_weight)

        # E. Tie-Breaker for Eva: Avoid over-scheduling Eva if there is a tie
        if "Eva" in self.parents and weights.eva_avoidance_tie_weight > 0:
            eva_total_shifts = sum(x[(d, s.id, "Eva")] for d in self.days for s in self.shifts)
            objective_terms.append(eva_total_shifts * weights.eva_avoidance_tie_weight)

        # Minimize sum of objective penalty terms
        model.Minimize(sum(objective_terms))

        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit_seconds
        solver.parameters.num_search_workers = 4
        status = solver.Solve(model)

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise RuntimeError(
                f"No feasible solution found by CP-SAT solver (status: {solver.StatusName(status)}). "
                "Check constraints or availability."
            )

        # Construct assignments list
        assignments: List[ShiftAssignment] = []
        for d in self.days:
            for s in self.shifts:
                if (d, s.id) in disabled_map:
                    reason_text = disabled_map[(d, s.id)]
                    assignments.append(
                        ShiftAssignment(
                            day=d,
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
                            reason=reason_text,
                        )
                    )
                else:
                    assigned_parents = [p for p in self.parents if solver.Value(x[(d, s.id, p)]) == 1]
                    p1 = assigned_parents[0] if len(assigned_parents) > 0 else ""
                    p2 = assigned_parents[1] if len(assigned_parents) > 1 else ""
                    p3 = assigned_parents[2] if len(assigned_parents) > 2 else ""

                    is_locked = (d, s.id) in locked_map and set(assigned_parents) == set(locked_map[(d, s.id)])

                    assignments.append(
                        ShiftAssignment(
                            day=d,
                            shift_id=s.id,
                            shift_name=s.name,
                            start=s.start,
                            end=s.end,
                            parent1=p1,
                            parent2=p2,
                            parent3=p3,
                            parents=assigned_parents,
                            locked=is_locked,
                            disabled=False,
                        )
                    )

        return assignments
