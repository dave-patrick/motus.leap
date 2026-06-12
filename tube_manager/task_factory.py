1|"""Task creation/update for Tube Manager tasks."""
2|from __future__ import annotations
3|
4|import uuid
5|from typing import Any
6|
7|
8|def new_task(
9|    title: str,
10|    task_type: str,
11|    payload: Optional[dict[str, Any] ] = None,
12|    priority: Optional[str ] = None,
13|) -> dict[str, Any]:
14|    return {
15|        "id": _make_id(),
16|        "type": task_type,
17|        "title": title,
18|        "status": "pending",
19|        "payload": payload,
20|        "priority": priority,
21|    }
22|
23|
24|def mark(task: dict[str, Any], status: str) -> dict[str, Any]:
25|    task["status"] = status
26|    return task
27|
28|
29|def complete(task: dict[str, Any]) -> dict[str, Any]:
30|    task["status"] = "completed"
31|    return task
32|
33|
34|def fail(task: dict[str, Any]) -> dict[str, Any]:
35|    task["status"] = "failed"
36|    return task
37|
38|
39|def _make_id() -> str:
40|    return uuid.uuid4().hex
41|