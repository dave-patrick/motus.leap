1|"""Task handlers mapped by task type for Tube Manager."""
2|
3|from __future__ import annotations
4|
5|from typing import Any
6|
7|
8|def run_generic(payload: Optional[dict[str, Any] ]) -> str:
9|    return "generic ok"
10|
11|
12|def run_research(payload: Optional[dict[str, Any] ]) -> str:
13|    return "research ok"
14|
15|
16|def run_code(payload: Optional[dict[str, Any] ]) -> str:
17|    return "code ok"
18|
19|
20|def run_home(payload: Optional[dict[str, Any] ]) -> str:
21|    return "home ok"
22|
23|
24|from tube_manager.youtube_actions import execute as execute_youtube
25|
26|
27|HANDLERS = {
28|    "generic": run_generic,
29|    "research": run_research,
30|    "code": run_code,
31|    "home": run_home,
32|    "youtube": execute_youtube,
33|}
34|