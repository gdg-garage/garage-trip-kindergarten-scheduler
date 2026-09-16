from typing import List, Dict, Optional, Tuple
from pydantic import BaseModel, Field, model_validator


class ShiftRestriction(BaseModel):
    day: str
    shift_ids: List[int]  # List of shift IDs affected
    reason: Optional[str] = None


class ParentConfig(BaseModel):
    name: str
    partner: Optional[str] = None
    available_days: List[str]
    unavailable_shifts: List[ShiftRestriction] = Field(default_factory=list)


class ShiftBlock(BaseModel):
    id: int
    name: str
    start: str
    end: str


class ScheduleSettings(BaseModel):
    days: List[str]
    shift_blocks: List[ShiftBlock]
    parents_per_shift: int = 2
    parents_per_shift_by_day: Dict[str, int] = Field(default_factory=dict)
    disabled_shifts: List[ShiftRestriction] = Field(default_factory=list)
    locked_days: List[str] = Field(default_factory=list)

    def get_parents_per_shift_for_day(self, day: str) -> int:
        return self.parents_per_shift_by_day.get(day, self.parents_per_shift)


class CouplePolicy(BaseModel):
    early_week_disallow: bool = True
    early_week_days: List[str] = Field(default_factory=lambda: ["Sun", "Mon", "Tue"])
    late_week_preference_weight: int = 0


class WeightsConfig(BaseModel):
    fairness_weight: int = 100
    pair_diversity_weight: int = 10
    daily_balance_weight: int = 5
    morning_evening_balance_weight: int = 15
    eva_avoidance_tie_weight: int = 1


class ConstraintConfig(BaseModel):
    max_shifts_per_day: int = 2
    disallow_consecutive_shifts: bool = True
    couple_policy: CouplePolicy = Field(default_factory=CouplePolicy)
    weights: WeightsConfig = Field(default_factory=WeightsConfig)


class GSheetConfig(BaseModel):
    spreadsheet_id: str
    sheet_name: str = "Schedule"
    time_col: str = "Time"
    parent1_col: str = "Parent 1"
    parent2_col: str = "Parent 2"
    parent3_col: str = "Parent 3"


class ScheduleConfig(BaseModel):
    parents: List[ParentConfig]
    schedule: ScheduleSettings
    constraints: ConstraintConfig = Field(default_factory=ConstraintConfig)
    google_sheets: Optional[GSheetConfig] = None


class ShiftAssignment(BaseModel):
    day: str
    shift_id: int
    shift_name: str
    start: str
    end: str
    parent1: str = ""
    parent2: str = ""
    parent3: str = ""
    parents: List[str] = Field(default_factory=list)
    locked: bool = False
    disabled: bool = False
    reason: Optional[str] = None

    @model_validator(mode="after")
    def sync_parents(self):
        if not self.parents:
            self.parents = [p for p in [self.parent1, self.parent2, self.parent3] if p]
        else:
            if len(self.parents) > 0 and not self.parent1:
                self.parent1 = self.parents[0]
            if len(self.parents) > 1 and not self.parent2:
                self.parent2 = self.parents[1]
            if len(self.parents) > 2 and not self.parent3:
                self.parent3 = self.parents[2]
        return self


class ParentMetrics(BaseModel):
    name: str
    total_shifts: int
    morning_shifts: int
    evening_shifts: int
    total_hours: float
    available_days_count: float
    shifts_per_available_day: float


class ScheduleReport(BaseModel):
    assignments: List[ShiftAssignment]
    parent_metrics: List[ParentMetrics]
    pairing_counts: Dict[Tuple[str, str], int]
    fairness_variance: float
    morning_evening_balance_score: float
