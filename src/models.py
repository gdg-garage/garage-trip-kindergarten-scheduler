from typing import List, Dict, Optional, Tuple
from pydantic import BaseModel, Field


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
    disabled_shifts: List[ShiftRestriction] = Field(default_factory=list)


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
    parent1: str
    parent2: str
    locked: bool = False
    disabled: bool = False
    reason: Optional[str] = None


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
