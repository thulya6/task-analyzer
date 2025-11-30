from __future__ import annotations
try:
    from dataclasses import dataclass, field
except ImportError:
    dataclass = None
from datetime import date, datetime
from typing import List, Dict, Any, Optional, Tuple

HOURS_PER_DAY = 10.0

@dataclass
class Task:
    id: int
    title: str
    due_date: Optional[str]
    estimated_hours: float
    importance: int
    dependencies: List[int] = field(default_factory=list)


def parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def days_until(d: Optional[date]) -> Optional[int]:
    if not d:
        return None
    return (d - date.today()).days

def urgency_score(days: Optional[int]) -> float:
    if days is None:
        return 0.2
    if days <= 0:
        overdue = max(days, -7)
        return 1.0 + (-overdue) * 0.08
    if days >= 30:
        return 0.1
    return max(0.2, 1.0 - days / 30.0)


def importance_score(importance: int) -> float:
    importance = max(1, min(10, int(importance)))
    return importance / 10.0


def effort_score(hours: float) -> float:
    if hours <= 0:
        return 1.0
    return 1.0 / (1.0 + min(hours, 12.0))

def build_tasks(raw_tasks: List[Dict[str, Any]]) -> Dict[int, Task]:
    tasks: Dict[int, Task] = {}
    for idx, item in enumerate(raw_tasks, start=1):
        deps = item.get("dependencies") or []
        if isinstance(deps, str):
            deps = [int(x) for x in deps.split(",") if x.strip().isdigit()]
        tasks[idx] = Task(
            id=idx,
            title=item.get("title") or f"Task {idx}",
            due_date=item.get("due_date"),
            estimated_hours=float(item.get("estimated_hours") or 0.0),
            importance=int(item.get("importance") or 1),
            dependencies=list(map(int, deps)),
        )
    return tasks


def detect_cycles(tasks: Dict[int, Task]) -> set[int]:
    state: Dict[int, str] = {}
    cycle_nodes: set[int] = set()

    def dfs(tid: int, stack: List[int]):
        s = state.get(tid, "unseen")
        if s == "visiting":
            i = stack.index(tid)
            cycle_nodes.update(stack[i:])
            return
        if s == "done":
            return
        state[tid] = "visiting"
        stack.append(tid)
        for dep in tasks[tid].dependencies:
            if dep in tasks:
                dfs(dep, stack)
        stack.pop()
        state[tid] = "done"

    for tid in tasks:
        if state.get(tid, "unseen") == "unseen":
            dfs(tid, [])
    return cycle_nodes


def blocked_counts(tasks: Dict[int, Task]) -> Dict[int, int]:
    counts = {tid: 0 for tid in tasks}
    for t in tasks.values():
        for dep in t.dependencies:
            if dep in counts:
                counts[dep] += 1
    return counts


def earliest_dependent_due(task_id: int, tasks: Dict[int, Task]) -> Optional[date]:
    earliest: Optional[date] = None
    for t in tasks.values():
        if task_id in t.dependencies:
            d = parse_date(t.due_date)
            if not d:
                continue
            if earliest is None or d < earliest:
                earliest = d
    return earliest


def per_task_feasible(task: Task) -> bool:
    """
    Can this task be finished by its own deadline given HOURS_PER_DAY,
    assuming we start now and can use all days up to and including due_date?
    """
    d = parse_date(task.due_date)
    if not d:
        return True
    du = days_until(d)
    if du is None:
        return True
    days_window = max(0, du + 1) 
    available = days_window * HOURS_PER_DAY
    return task.estimated_hours <= available

def _latest_finish_hours(d: Optional[date]) -> Optional[float]:
    if not d:
        return None
    du = days_until(d)
    if du is None:
        return None
    return max(0, du) * HOURS_PER_DAY


def compute_feasible_order_if_possible(
    tasks: Dict[int, Task],
) -> Optional[List[int]]:
    """
    Returns a list of task IDs in an order that can finish all *deadline* tasks
    before their deadlines, assuming HOURS_PER_DAY capacity, or None if
    that's impossible.
    """
    enriched: List[Dict[str, Any]] = []
    for t in tasks.values():
        d = parse_date(t.due_date)
        enriched.append(
            {
                "id": t.id,
                "due": d,
                "hours": max(0.0, t.estimated_hours),
            }
        )

    with_deadline = [e for e in enriched if e["due"] is not None]
    without_deadline = [e for e in enriched if e["due"] is None]

    with_deadline.sort(key=lambda x: x["due"])

    cumulative_hours = 0.0
    for e in with_deadline:
        cumulative_hours += e["hours"]
        latest_finish = _latest_finish_hours(e["due"])
        if latest_finish is not None and cumulative_hours > latest_finish:
            return None

    order_ids = [e["id"] for e in with_deadline] + [e["id"] for e in without_deadline]
    return order_ids

def base_score_and_label(
    task: Task, strategy: str, du: Optional[int]
) -> Tuple[float, str]:
    u = urgency_score(du)
    i = importance_score(task.importance)
    e = effort_score(task.estimated_hours)

    s = (strategy or "smart_balance").lower()
    if s == "fastest_wins":
        base = 0.2 * u + 0.2 * i + 0.6 * e
        label = "Fastest Wins"
    elif s == "high_impact":
        base = 0.1 * u + 0.8 * i + 0.1 * e
        label = "High Impact"
    elif s == "deadline_driven":
        base = 0.85 * u + 0.10 * i + 0.05 * e
        label = "Deadline Driven"
    else:
        base = 0.35 * u + 0.40 * i + 0.25 * e
        label = "Smart Balance"

    explanation = (
        f"Strategy: {label}. "
        f"Urgency={u:.2f} (days until due: {du}). "
        f"Importance={i:.2f} (raw {task.importance}). "
        f"EffortScore={e:.2f} (hours {task.estimated_hours})."
    )
    return base, explanation

def score_task(
    task: Task,
    blocked: Dict[int, int],
    strategy: str,
    in_cycle: bool,
    earliest_dep_due: Optional[date],
) -> Tuple[float, str]:
    d = parse_date(task.due_date)
    du = days_until(d)
    base, explanation = base_score_and_label(task, strategy, du)

    blocks = blocked.get(task.id, 0)
    dep_mult = 1.0
    dep_note = ""

    if blocks > 0:
        dep_mult += 0.3 * min(blocks, 4)
        dep_note = f" Blocks {blocks} other task(s)."

    if in_cycle:
        dep_mult = 1.0
        dep_note = " Dependency cycle detected; dependency bonus ignored."

    s = (strategy or "").lower()

    if s in ("deadline_driven", "smart_balance"):
        if du is not None:
            if du <= 0:
                base += 1.0
            elif du <= 2:
                base += 0.6
            elif du <= 5:
                base += 0.3

        if blocks > 0 and d is not None and earliest_dep_due is not None:
            if d <= earliest_dep_due:
                base += 0.4
                dep_note += " Earlier than its dependents; boosted for schedule feasibility."

    score = max(0.0, min(base * dep_mult, 2.0))

    if dep_note:
        explanation = explanation + " " + dep_note
    return score, explanation

def time_status(du: Optional[int]) -> str:
    if du is None:
        return "future"
    if du < 0:
        return "overdue"
    if du == 0:
        return "today"
    return "future"


def overdue_today_priority(
    tid: int,
    tasks: Dict[int, Task],
    blocked: Dict[int, int],
) -> Tuple[int, int]:
    t = tasks[tid]
    du = days_until(parse_date(t.due_date))
    status = time_status(du)
    has_deps = blocked.get(tid, 0) > 0
    importance = t.importance

    if status == "overdue" and has_deps:
        special = 0
    elif status == "today":
        special = 1
    elif status == "overdue":
        special = 2
    else:
        special = 3

    bias = 2
    if status == "overdue" and not has_deps:
        if importance >= 9:
            bias = 0
        elif importance >= 6:
            bias = 1
    elif status == "today":
        if importance >= 5:
            bias = 0
        else:
            bias = 1

    return special, bias

def prioritize(raw_tasks: List[Dict[str, Any]], strategy: str) -> List[Dict[str, Any]]:
    tasks = build_tasks(raw_tasks)
    cycles = detect_cycles(tasks)
    blocked = blocked_counts(tasks)
    s = (strategy or "smart_balance").lower()

    feasible_order: Optional[List[int]] = None
    if s in ("smart_balance", "deadline_driven"):
        feasible_order = compute_feasible_order_if_possible(tasks)

    def build_output_from_order(order_ids: List[int]) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        max_score = 2.0
        step = 2.0 / max(1, len(order_ids))
        current = max_score
        for tid in order_ids:
            t = tasks[tid]
            du = days_until(parse_date(t.due_date))
            base, expl = base_score_and_label(t, strategy, du)
            result.append(
                {
                    "id": t.id,
                    "title": t.title,
                    "due_date": t.due_date,
                    "estimated_hours": t.estimated_hours,
                    "importance": t.importance,
                    "dependencies": t.dependencies,
                    "score": round(current, 2),
                    "explanation": expl
                    + " Ordered by feasibility-aware schedule (can finish all tasks).",
                }
            )
            current = max(0.0, current - step)
        return result

    if feasible_order is not None:
        buckets: Dict[Optional[str], List[int]] = {}
        for tid in feasible_order:
            key = tasks[tid].due_date
            buckets.setdefault(key, []).append(tid)

        ordered: List[int] = []
        keys_sorted = sorted(
            [k for k in buckets.keys() if k is not None],
            key=lambda x: parse_date(x),
        )
        if None in buckets:
            keys_sorted.append(None)

        for key in keys_sorted:
            ids = buckets[key]
            if s == "smart_balance":
                ids.sort(
                    key=lambda tid: (
                        -blocked.get(tid, 0),
                        -tasks[tid].importance,
                        tasks[tid].estimated_hours,
                    )
                )
            elif s == "deadline_driven":
                ids.sort(
                    key=lambda tid: (
                        -blocked.get(tid, 0),
                        tasks[tid].estimated_hours,
                        -tasks[tid].importance,
                    )
                )
            ordered.extend(ids)

        return build_output_from_order(ordered)

    individually_feasible: Dict[int, bool] = {
        tid: per_task_feasible(t) for tid, t in tasks.items()
    }

    scored: List[Tuple[float, Dict[str, Any]]] = []
    for tid, t in tasks.items():
        in_cycle = tid in cycles
        earliest_dep = earliest_dependent_due(tid, tasks)
        score, expl = score_task(t, blocked, strategy, in_cycle, earliest_dep)

        scored.append(
            (
                score,
                {
                    "id": t.id,
                    "title": t.title,
                    "due_date": t.due_date,
                    "estimated_hours": t.estimated_hours,
                    "importance": t.importance,
                    "dependencies": t.dependencies,
                    "score": round(score, 2),
                    "explanation": expl,
                },
            )
        )

    if s == "fastest_wins":
        scored.sort(
            key=lambda item: (
                tasks[item[1]["id"]].estimated_hours,
                -item[0],
            )
        )
    elif s == "high_impact":
        scored.sort(
            key=lambda item: (
                -tasks[item[1]["id"]].importance,
                -item[0],
            )
        )
    else:
        def sort_key(item: Tuple[float, Dict[str, Any]]):
            tid = item[1]["id"]
            t = tasks[tid]
            du = days_until(parse_date(t.due_date))
            feasible = individually_feasible[tid]

            blocks = blocked.get(tid, 0)
            status = time_status(du)

            if status == "overdue" and blocks > 0:
                blocker_rank = 0
            elif blocks > 0:
                blocker_rank = 1
            else:
                blocker_rank = 2

            feasible_flag = 0 if feasible else 1
            special, bias = overdue_today_priority(tid, tasks, blocked)

            return (
                blocker_rank,              
                feasible_flag,             
                special,
                -blocks, 
                bias,  
                -t.importance,   
                -item[0], 
                parse_date(t.due_date) or date.max,
                t.estimated_hours,
            )

        scored.sort(key=sort_key)

    return [item[1] for item in scored]

def build_dependency_graph(raw_tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build { nodes, edges } from raw_tasks for frontend graph visualization.
    Reuses existing build_tasks() and detect_cycles().
    """
    tasks = build_tasks(raw_tasks)
    cycles = detect_cycles(tasks)

    nodes = []
    edges = []

    for tid, task in tasks.items():
        node = {
            "id": tid,
            "label": task.title[:30] + ("..." if len(task.title) > 30 else ""),
            "title": task.title, 
            "importance": task.importance,
            "hours": round(task.estimated_hours, 1),
            "due": task.due_date or "No due date",
            "inCycle": tid in cycles,
            "hasDeps": len(task.dependencies) > 0,
            "blockedBy": len([d for d in task.dependencies if d in tasks]),
        }
        nodes.append(node)

        for dep_id in task.dependencies:
            if dep_id in tasks:
                edges.append({
                    "from": dep_id,
                    "to": tid,
                    "label": "depends on"
                })

    return {
        "nodes": nodes,
        "edges": edges,
        "cycles": list(cycles),
        "taskCount": len(tasks)
    }
