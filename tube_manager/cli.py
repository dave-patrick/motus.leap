"""CLI entrypoints for Tube Manager."""

from __future__ import annotations

import json
from pathlib import Path

import click

from tube_manager.service import TubeManager


@click.group()
@click.option("--config", "config_path", default=None, help="Path to config.yaml")
@click.pass_context
def cli(ctx: click.Context, config_path: str | None = None):
    obj = TubeManager(Path(config_path) if config_path else None)
    ctx.obj = obj


@cli.command()
@click.option("--status", default=None)
@click.pass_context
def list(ctx: click.Context, status: str | None = None):
    tasks = ctx.obj.list_tasks(status=status)
    for task in tasks:
        click.echo(f"{task['id']} [{task['type']}] {task['title']} -> {task['status']}")


@cli.command()
@click.argument("title")
@click.option("--type", "task_type", required=True)
@click.option("--priority", default=None)
@click.option("--json", "payload_json", default=None)
@click.pass_context
def add(ctx: click.Context, title: str, task_type: str, priority: str | None = None, payload_json: str | None = None):
    payload = json.loads(payload_json) if payload_json else None
    task = ctx.obj.add_task(title=title, task_type=task_type, priority=priority, payload=payload)
    click.echo(f"created {task['id']}")


@cli.command()
@click.argument("task_id")
@click.pass_context
def run(ctx: click.Context, task_id: str):
    task = ctx.obj.run_task(task_id=task_id)
    click.echo(f"{task['id']} -> {task['status']}")


@cli.command()
@click.argument("task_id")
@click.pass_context
def remove(ctx: click.Context, task_id: str):
    ctx.obj.remove_task(task_id=task_id)
    click.echo("removed")
