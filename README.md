# Crowd-Sourced Kindergarten Shift Scheduler

An intelligent, constraint-optimized shift scheduler for crowd-sourced kindergarten events, powered by **Google OR-Tools CP-SAT** (Constraint Programming).

---

## 🎯 Algorithm Selection & Rationale

### Why Constraint Programming (OR-Tools CP-SAT)?
- **Mathematical Optimization**: Shift scheduling is a combinatorial Constraint Satisfaction and Optimization Problem (CSOP). CP-SAT guarantees 100% hard-constraint satisfaction while optimizing global soft-objective metrics (fairness and partner diversity).
- **Incremental Partial Regeneration**: When shift cancellations or changes occur during the week, CP-SAT allows existing/completed slots in Google Sheets or CSV to be locked as fixed constraints, generating optimal replacements for only the cleared/unassigned slots.
- **Speed**: Solves the 6-day, 8-parent schedule to global mathematical optimality in milliseconds.

---

## ⚙️ How It Works: Constraints & Optimization

### Hard Constraints (Must Always Be Satisfied)
1. **Shift Capacity**: Every 2-hour shift block is assigned **exactly 2 parents**.
2. **Day Availability**:
    - **Vit, Eva, Ales, Zuzka, Harry, Klara V**: Available Sunday through Friday (6 days).
    - **David, Bara**: Available Wednesday through Friday only (3 days).
    - **Klara P, Jask**: Available Tuesday through Friday (4 days).
3. **Daily Shift Limit**: A parent can work **at most 2 shifts per day**.
4. **No Consecutive Shifts**: A parent is **never scheduled for back-to-back shifts** on the same day.
5. **Early-Week Couple Separation**:
   - **Sunday – Tuesday**: Parents who are partners (e.g. *Vit & Eva*, *Ales & Zuzka*, *Harry & Klara V*, *Klara P & Jask*) are **never scheduled on the same shift together**, maximizing parent shuffling and adult-to-kid coverage.
   - **Wednesday – Friday**: Partners are allowed to share a shift if optimal for fairness/diversity.
6. **Locked Schedule Support**: Pre-filled slots in Google Sheets / CSV are preserved strictly as immutable constraints.

### Soft Constraints (Optimized via Objective Function)
1. **Hours Fairness**: Minimizes deviation in total shift hours normalized by available days ($T_{\text{shifts}} / A_{\text{days}}$).
2. **Morning vs. Evening Shift Balance**: Minimizes the absolute difference $|M_p - E_p|$ between Morning shifts (Shifts 1 & 2: 09:00-13:00) and Evening shifts (Shifts 3 & 4: 14:00-18:00) for every parent.
3. **Eva Tie-Breaker Preference**: In case of a tie between candidate parents, prefers assigning other parents over Eva so she is not over-scheduled (taking care of a small child).
4. **Pairing Diversity**: Minimizes repeat pairings of the same two parents across the week.
5. **Daily Spread**: Prefers 1 shift per day over 2 shifts where possible.

---

## 📁 Configuration (`config.yaml`)

Parent couples, availability, shift structure, and constraint weights are configured in `config.yaml`:

```yaml
parents:
  - name: "Vit"
    partner: "Eva"
    available_days: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri"]
  - name: "Eva"
    partner: "Vit"
    available_days: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri"]
  - name: "Ales"
    partner: "Zuzka"
    available_days: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri"]
  - name: "Zuzka"
    partner: "Ales"
    available_days: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri"]
  - name: "Harry"
    partner: "Klara V"
    available_days: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri"]
  - name: "Klara V"
    partner: "Harry"
    available_days: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri"]
  - name: "David"
    partner: "Bara"
    available_days: ["Wed", "Thu", "Fri"]
  - name: "Bara"
    partner: "David"
    available_days: ["Wed", "Thu"]  # Leaving Thursday evening, not present Friday
    unavailable_shifts:
      - day: "Thu"
        shift_ids: [2, 3]  # Not available after lunch on Thursday (Shifts 14-16 & 16-18)

schedule:
  days: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri"]
  shift_blocks:
    - id: 0
      name: "Shift 1"
      start: "09:00"
      end: "11:00"
    - id: 1
      name: "Shift 2"
      start: "11:00"
      end: "13:00"
    - id: 2
      name: "Shift 3"
      start: "14:00"
      end: "16:00"
    - id: 3
      name: "Shift 4"
      start: "16:00"
      end: "18:00"
  parents_per_shift: 2

constraints:
  max_shifts_per_day: 2
  disallow_consecutive_shifts: true
  couple_policy:
    early_week_disallow: true
    early_week_days: ["Sun", "Mon", "Tue"]

google_sheets:
  spreadsheet_id: "1o7tnLVmnRkw0-ZRX5nwLHS8n1dNtfe-AvP7hHmtz_2U"
  sheet_name: "Schedule"
```

---

## 🚀 Quick Start & Usage

### 1. Setup Virtual Environment
```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

### 2. Generate Initial Schedule (CSV Export)
```bash
./venv/bin/python3 run.py --export-csv schedule.csv
```

### 3. Partial Schedule Regeneration
If a parent cancels or slots need to be rescheduled:
1. Open `schedule.csv` (or the Google Sheet).
2. Delete the parent names for the shift slots you want to regenerate (leave fixed slots filled).
3. Run the scheduler referencing the modified CSV:
   ```bash
   ./venv/bin/python3 run.py --input-csv schedule.csv --export-csv schedule.csv
   ```
   The solver locks all existing entries and solves only the empty slots!

### 4. Syncing Directly with Google Sheets API (OAuth 2.0 or Service Account)
To read and write directly to Google Sheets:
- **OAuth 2.0 User Login (Recommended)**: Save your OAuth 2.0 Client Secret JSON file as `credentials.json` in the root directory. When you run `./venv/bin/python3 run.py --sync-gsheet`, a browser window opens for a 1-click Google sign-in. The authorized user token is saved locally to `token.json` for future seamless runs!
- **Service Account**: Save a Google Service Account key file as `credentials.json` and share your Google Sheet (`1o7tnLVmnRkw0-ZRX5nwLHS8n1dNtfe-AvP7hHmtz_2U`) with the service account email.
- **Execution Command**:
  ```bash
  ./venv/bin/python3 run.py --sync-gsheet
  ```

---

## 📊 Schedule Layout & Metrics Report

### Google Sheet / CSV Row Expansion
Although scheduling solver logic operates on **2-hour shift blocks**, the schedule output is expanded into **30-minute rows** (repeating names 4 times per shift block) from 09:00 to 18:00, with **Lunch (13:00 - 14:00)** automatically formatted.

### Sample Metrics Report Output
```
=== SCHEDULING METRICS & FAIRNESS REPORT ===

Parent Shift Distribution:
Parent      Shifts  Hours       Avail Days    Shifts/Avail Day
--------  --------  --------  ------------  ------------------
Vit              6  12.0 hrs             6                1
Eva              7  14.0 hrs             6                1.17
Ales             7  14.0 hrs             6                1.17
Zuzka            7  14.0 hrs             6                1.17
Harry            7  14.0 hrs             6                1.17
Klara            6  12.0 hrs             6                1
David            4  8.0 hrs              3                1.33
Bara             4  8.0 hrs              3                1.33

Fairness Variance (lower is better): 0.0139

Parent Pairing Counts:
Parent Pair      Times Scheduled Together
-------------  --------------------------
Eva & Klara                             2
Ales & Bara                             1
Ales & David                            1
...
```

---

## 🧪 Running Automated Tests

Run the test suite using pytest:
```bash
PYTHONPATH=. ./venv/bin/pytest
```
Tests cover:
- Solver hard constraints (capacity, availability, max 2 shifts/day, non-consecutive shifts, couple separation).
- Partial regeneration and locked slot preservation.
- Fairness variance & pair frequency computations.
- 30-minute Google Sheet format conversion & CSV roundtrip.
