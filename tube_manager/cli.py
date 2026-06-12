1|"""CLI entrypoints for Tube Manager."""
2|from __future__ import annotations
3|
4|import json
5|from pathlib import Path
6|
7|import click
8|
9|from tube_manager.service import TubeManager
10|
11|
12|@click.group()
13|@click.option("--config", "config_path", default=None, help="Path to config.yaml")
14|@click.pass_context
15|def cli(ctx: click.Context, config_path: Optional[str ]):
16|    obj = TubeManager(Path(config_path) if config_path else None)
17|    ctx.obj = obj
18|
19|
20|@cli.command()
21|@click.option("--status", default=None)
22|@click.pass_context
23|def list(ctx: click.Context, status: Optional[str ]):
24|    tasks = ctx.obj.list_tasks(status=status)
25|    for task in tasks:
26|        click.echo(f"{task['id']} [{task['type']}] {task['title']} -> {task['status']}")
27|
28|
29|@cli.command()
30|@click.argument("title")
31|@click.option("--type", "task_type", required=True)
32|@click.option("--priority", default=None)
33|@click.option("--json", "payload_json", default=None)
34|@click.pass_context
35|def add(ctx: click.Context, title: str, task_type: str, priority: Optional[str ], payload_json: Optional[str ]):
36|    payload = json.loads(payload_json) if payload_json else None
37|    task = ctx.obj.add_task(title=title, task_type=task_type, priority=priority, payload=payload)
38|    click.echo(f"created {task['id']}")
39|
40|
41|@cli.command()
42|@click.argument("task_id")
43|@click.pass_context
44|def run(ctx: click.Context, task_id: str):
45|    task = ctx.obj.run_task(task_id=task_id)
46|    click.echo(f"{task['id']} -> {task['status']}")
47|
48|
49|@cli.command()
50|@click.argument("task_id")
51|@click.pass_context
52|def remove(ctx: click.Context, task_id: str):
53|    ctx.obj.remove_task(task_id=task_id)
54|    click.echo("removed")
55|