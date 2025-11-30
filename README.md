# Smart Task Analyzer

Task prioritization with dependency graphs and 4 strategies.

## Setup Instructions

1. Clone the repository

git clone https://github.com/thulya6/task-analyzer.git
cd task-analyzer

2. Install Python dependencies

pip install -r requirements.txt

3. Setup Django backend

cd backend/task_analyzer
python manage.py migrate
python manage.py runserver

4. Open in browser (leave server running)

- Option A: Via Django server  
  [http://127.0.0.1:8000/frontend/index.html](http://127.0.0.1:8000/frontend/index.html)
- Option B: Direct file (works standalone)  
  `frontend/index.html`

## Algorithm Explanation

The `prioritize()` algorithm combines **Eisenhower Matrix** principles with **dependency-aware topological sorting** and **feasibility constraints**.

### 1. Base Score Calculation (0.0-2.0 range)

Urgency = max(1.0, 1.0 - (days_until_due / 30))
Importance = raw_importance / 10 (scale 1-10 → 0.1-1.0)
Effort = 1.0 / (1.0 + min(estimated_hours, 12))

Strategy Weights:

- Smart Balance: 35% urgency, 40% importance, 25% effort
- Deadline Driven: 85% urgency, 10% importance, 5% effort
- High Impact: 10% urgency, 80% importance, 10% effort
- Fastest Wins: 20% urgency, 20% importance, 60% effort

### 2. Dependency Multipliers

- Blocker Bonus: +0.3 per blocked task (max +1.2 for 4+ dependents)
- Cycle Penalty: Tasks in cycles get neutral multiplier (1.0)
- Feasibility Boost: +0.4 if due before all dependents

### 3. Final Multi-level Sort

- Overdue blockers first
- Blocker status (# dependents)
- Days until due (overdue > today > future)
- Individual feasibility score
- Base priority score

**3 unit tests verify**: overdue blocker priority, cycle neutralization, deadline-driven ordering.
