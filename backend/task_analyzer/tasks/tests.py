from django.test import TestCase
from .scoring import prioritize
from datetime import date

class ScoringTests(TestCase):
    def test_overdue_blocker_highest(self):
        tasks = [
            {"title": "Overdue blocker", "due_date": "2025-11-25", "estimated_hours": 2, "importance": 7, "dependencies": []},
            {"title": "Blocked task", "due_date": "2025-12-01", "estimated_hours": 3, "importance": 9, "dependencies": [1]},
        ]
        result = prioritize(tasks, "smart_balance")
        self.assertEqual(result[0]["title"], "Overdue blocker")

    def test_cycle_detection(self):
        tasks = [
            {"title": "A", "due_date": "2025-12-01", "estimated_hours": 1, "importance": 10, "dependencies": [2]},
            {"title": "B", "due_date": "2025-12-01", "estimated_hours": 1, "importance": 10, "dependencies": [1]},
        ]
        result = prioritize(tasks, "smart_balance")
        self.assertEqual(len(result), 2)
        self.assertTrue(all("score" in t for t in result))

    def test_shortest_deadline_first(self):
        tasks = [
            {"title": "Long task", "due_date": "2025-12-05", "estimated_hours": 15, "importance": 8, "dependencies": []},
            {"title": "Short task", "due_date": "2025-12-02", "estimated_hours": 2, "importance": 6, "dependencies": []},
        ]
        result = prioritize(tasks, "deadline_driven")
        self.assertEqual(result[0]["title"], "Short task")
