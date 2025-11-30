import json
from datetime import date
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .scoring import prioritize, build_dependency_graph

def parse_body(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return None, JsonResponse({"error": "Invalid JSON body."}, status=400)
    return data, None

@csrf_exempt
@require_http_methods(["POST", "OPTIONS"]) 
def analyze_tasks(request):
    if request.method == "OPTIONS":
        return JsonResponse({}, status=200) 
    
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed."}, status=405)

    data, error = parse_body(request)
    if error:
        return error

    tasks = data.get("tasks")
    strategy = data.get("strategy", "smart_balance")
    if not isinstance(tasks, list) or not tasks:
        return JsonResponse({"error": "Field 'tasks' must be non-empty list."}, status=400)

    prioritized = prioritize(tasks, strategy)
    return JsonResponse({"tasks": prioritized}, status=200)

@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])  
def suggest_tasks(request):
    if request.method == "OPTIONS":
        return JsonResponse({}, status=200) 
    
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed."}, status=405)

    data, error = parse_body(request)
    if error:
        return error

    tasks = data.get("tasks")
    strategy = data.get("strategy", "smart_balance")
    if not isinstance(tasks, list) or not tasks:
        return JsonResponse({"error": "Field 'tasks' must be non-empty list."}, status=400)

    prioritized = prioritize(tasks, strategy)
    today = date.today()

    def within_window(t):
        due = t.get("due_date")
        if not due: return False
        try:
            y, m, d = map(int, due.split("-"))
            diff = (date(y, m, d) - today).days
            return diff <= 3
        except Exception:
            return False

    window_tasks = [t for t in prioritized if within_window(t)]
    chosen = (window_tasks or prioritized)[:3]
    return JsonResponse({"tasks": chosen}, status=200)

@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def dependency_graph(request):
    if request.method == "OPTIONS":
        return JsonResponse({}, status=200)
    
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed."}, status=405)

    data, error = parse_body(request)
    if error:
        return error

    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        return JsonResponse({"error": "Field 'tasks' must be a list."}, status=400)

    graph_data = build_dependency_graph(tasks)
    return JsonResponse(graph_data, status=200)
