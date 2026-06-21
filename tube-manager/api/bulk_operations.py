"""Bulk operations API endpoints."""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Request
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
import csv
import io
from datetime import datetime
import base64
import asyncio

from api.bulk_operations_impl import BulkOperationsService
from core.config_manager import ConfigManager
from models.config import TubeManagerConfig

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bulk", tags=["bulk"])

# ============================================================================
# Dependency Functions
# ============================================================================

async def get_config(request: Request) -> TubeManagerConfig:
    """Dependency to get current config from app state."""
    return request.app.state.config_manager.config

async def get_config_manager(request: Request) -> ConfigManager:
    """Dependency to get config manager from app state."""
    return request.app.state.config_manager


# =============================================================================
# Request/Response Models
# =============================================================================

class BulkMoveRequest(BaseModel):
    """Request for bulk move operation."""
    video_ids: List[str]
    target_playlist_id: str
    source_playlist_id: Optional[str] = None


class BulkDeleteRequest(BaseModel):
    """Request for bulk delete operation."""
    video_ids: List[str]
    playlist_id: str


class BulkTagRequest(BaseModel):
    """Request for bulk tag operation."""
    video_ids: List[str]
    tags: List[str]
    action: str  # "add" or "remove"


class ExportRequest(BaseModel):
    """Request for export operation."""
    resource_type: str  # "playlists", "subscriptions", "mappings"
    format: str  # "json", "csv"
    filters: Optional[Dict[str, Any]] = None


class ImportRequest(BaseModel):
    """Request for import operation."""
    resource_type: str  # "playlists", "subscriptions", "mappings"
    format: str  # "json", "csv"
    data: str  # Base64 encoded data
    options: Optional[Dict[str, Any]] = None


class BulkOperationResponse(BaseModel):
    """Response for bulk operations."""
    operation_id: str
    operation_type: str
    total_items: int
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    status: str  # "pending", "in_progress", "completed", "failed"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    errors: List[str] = []


class OperationStatusResponse(BaseModel):
    """Response for operation status."""
    operation_id: str
    status: str
    progress: float  # 0.0 to 1.0
    processed: int
    total_items: int
    succeeded: int
    failed: int
    errors: List[str] = []


# =============================================================================
# Persistent Storage for Operations
# =============================================================================

OPERATIONS_FILE = Path(os.getenv("TUBE_MANAGER_DATA_DIR", "/app/data")) / "operations.json"

class OperationsStorage:
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self._operations: Dict[str, BulkOperationResponse] = {}
        self._lock = asyncio.Lock()

    async def load(self) -> None:
        async with self._lock:
            if await asyncio.to_thread(self.file_path.exists):
                try:
                    content = await asyncio.to_thread(self.file_path.read_text)
                    data = json.loads(content)
                    for k, v in data.items():
                        if "started_at" in v and isinstance(v["started_at"], str):
                            v["started_at"] = datetime.fromisoformat(v["started_at"])
                        if "completed_at" in v and isinstance(v["completed_at"], str):
                            v["completed_at"] = datetime.fromisoformat(v["completed_at"])
                        self._operations[k] = BulkOperationResponse(**v)
                except Exception as e:
                    log.warning("Failed to load operations: %s", e)
            

    async def save(self) -> None:
        async with self._lock:
            try:
                self.file_path.parent.mkdir(parents=True, exist_ok=True)
                serializable = {}
                for k, v in self._operations.items():
                    d = v.model_dump()
                    if isinstance(d.get("started_at"), datetime):
                        d["started_at"] = d["started_at"].isoformat()
                    if isinstance(d.get("completed_at"), datetime):
                        d["completed_at"] = d["completed_at"].isoformat()
                    serializable[k] = d
                await asyncio.to_thread(self.file_path.write_text, json.dumps(serializable, indent=2))
            except Exception as e:
                log.error("Failed to save operations: %s", e)

    def get(self, operation_id: str) -> Optional[BulkOperationResponse]:
        return self._operations.get(operation_id)

    def set(self, operation_id: str, operation: BulkOperationResponse) -> None:
        self._operations[operation_id] = operation

    def delete(self, operation_id: str) -> None:
        if operation_id in self._operations:
            del self._operations[operation_id]

    def list_all(self) -> List[BulkOperationResponse]:
        return list(self._operations.values())
    
    async def update_and_save(self, operation: BulkOperationResponse) -> None:
        """Update an operation in memory and save all operations to disk."""
        self._operations[operation.operation_id] = operation
        await self.save()


operations_storage = OperationsStorage(OPERATIONS_FILE)

# Modify lifespan to load operations at startup
@router.on_event("startup")
async def startup_event():
    await operations_storage.load()


# Helper for dependency injection in routes
async def get_operations_storage():
    return operations_storage

# =============================================================================
# Bulk Operation Endpoints
# =============================================================================

@router.post("/move", response_model=BulkOperationResponse)
async def bulk_move_videos(
    request: BulkMoveRequest,
    background_tasks: BackgroundTasks,
    config: TubeManagerConfig = Depends(get_config),
    config_manager: ConfigManager = Depends(get_config_manager),
    ops_storage: OperationsStorage = None,)
):
    """Bulk move videos between playlists."""
    operation_id = f"move_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    operation = BulkOperationResponse(
        operation_id=operation_id,
        operation_type="bulk_move",
        total_items=len(request.video_ids),
        status="pending",
        started_at=datetime.now()
    )

    ops_storage.set(operation_id, operation)
    await ops_storage.save() # Save initial status

    # Add to background tasks
    background_tasks.add_task(
        process_bulk_move,
        operation_id,
        request.video_ids,
        request.target_playlist_id,
        request.source_playlist_id,
        config,
        config_manager,
        ops_storage # Pass operations storage to background task
    )

    return operation


@router.post("/delete", response_model=BulkOperationResponse)
async def bulk_delete_videos(
    request: BulkDeleteRequest,
    background_tasks: BackgroundTasks,
    config: TubeManagerConfig = Depends(get_config),
    config_manager: ConfigManager = Depends(get_config_manager),
    ops_storage: OperationsStorage = Depends(get_operations_storage)
):
    """Bulk delete videos from playlist."""
    operation_id = f"delete_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    operation = BulkOperationResponse(
        operation_id=operation_id,
        operation_type="bulk_delete",
        total_items=len(request.video_ids),
        status="pending",
        started_at=datetime.now()
    )

    ops_storage.set(operation_id, operation)
    await ops_storage.save() # Save initial status

    # Add to background tasks
    background_tasks.add_task(
        process_bulk_delete,
        operation_id,
        request.video_ids,
        request.playlist_id,
        config,
        config_manager,
        ops_storage # Pass operations storage to background task
    )

    return operation


@router.post("/tag", response_model=BulkOperationResponse)
async def bulk_tag_videos(
    request: BulkTagRequest,
    background_tasks: BackgroundTasks,
    config: TubeManagerConfig = Depends(get_config),
    config_manager: ConfigManager = Depends(get_config_manager),
    ops_storage: OperationsStorage = Depends(get_operations_storage)
):
    """Bulk add or remove tags from videos."""
    operation_id = f"tag_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    operation = BulkOperationResponse(
        operation_id=operation_id,
        operation_type=f"bulk_tag_{request.action}",
        total_items=len(request.video_ids),
        status="pending",
        started_at=datetime.now()
    )

    ops_storage.set(operation_id, operation)
    await ops_storage.save() # Save initial status

    # Add to background tasks
    background_tasks.add_task(
        process_bulk_tag,
        operation_id,
        request.video_ids,
        request.tags,
        request.action,
        config,
        config_manager,
        ops_storage # Pass operations storage to background task
    )

    return operation


# =============================================================================
# Export/Import Endpoints
# =============================================================================

@router.post("/export")
async def export_data(
    request: ExportRequest,
    config: TubeManagerConfig = Depends(get_config),
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Export data in specified format."""
    # Create service instance
    service = BulkOperationsService(config, config_manager)

    if request.resource_type == "playlists":
        data = await service.export_playlists(request.filters)
    elif request.resource_type == "subscriptions":
        data = await service.export_subscriptions(request.filters)
    elif request.resource_type == "mappings":
        data = await service.export_mappings(request.filters)
    else:
        raise HTTPException(status_code=400, detail="Invalid resource type")

    if request.format == "json":
        return {
            "format": "json",
            "data": data,
            "exported_at": datetime.now().isoformat()
        }
    elif request.format == "csv":
        # Convert to CSV
        output = io.StringIO()
        if isinstance(data, dict):
            # Mappings - convert to list of dicts
            data = [{"channel": k, "playlist": v} for k, v in data.items()]

        if data:
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)

        csv_data = output.getvalue()
        return {
            "format": "csv",
            "data": csv_data,
            "exported_at": datetime.now().isoformat()
        }
    else:
        raise HTTPException(status_code=400, detail="Invalid format")


@router.post("/import")
async def import_data(
    request: ImportRequest,
    background_tasks: BackgroundTasks,
    config: TubeManagerConfig = Depends(get_config),
    config_manager: ConfigManager = Depends(get_config_manager),
    ops_storage: OperationsStorage = Depends(get_operations_storage)
):
    """Import data in specified format."""
    operation_id = f"import_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    operation = BulkOperationResponse(
        operation_id=operation_id,
        operation_type="bulk_import",
        total_items=0,  # Will be updated after parsing
        status="pending",
        started_at=datetime.now()
    )

    ops_storage.set(operation_id, operation)
    await ops_storage.save() # Save initial status

    # Add to background tasks
    background_tasks.add_task(
        process_import,
        operation_id,
        request.resource_type,
        request.format,
        request.data,
        request.options,
        config,
        config_manager,
        ops_storage # Pass operations storage to background task
    )

    return operation


# =============================================================================
# Operation Status Endpoints
# =============================================================================

@router.get("/operations/{operation_id}", response_model=OperationStatusResponse)
async def get_operation_status(operation_id: str, ops_storage: OperationsStorage = Depends(get_operations_storage)):
    """Get status of a bulk operation."""
    operation = ops_storage.get(operation_id)
    if not operation:
        raise HTTPException(status_code=404, detail="Operation not found")

    progress = operation.processed / operation.total_items if operation.total_items > 0 else 0.0

    return OperationStatusResponse(
        operation_id=operation.operation_id,
        status=operation.status,
        progress=progress,
        processed=operation.processed,
        total_items=operation.total_items,
        succeeded=operation.succeeded,
        failed=operation.failed,
        errors=operation.errors
    )


@router.get("/operations")
async def list_operations(limit: int = 20, offset: int = 0, ops_storage: OperationsStorage = Depends(get_operations_storage)):
    """List recent bulk operations."""
    operation_list = ops_storage.list_all()
    operation_list.sort(key=lambda x: x.started_at or datetime.min, reverse=True)

    return {
        "total": len(operation_list),
        "operations": operation_list[offset:offset + limit]
    }


@router.delete("/operations/{operation_id}")
async def cancel_operation(operation_id: str, ops_storage: OperationsStorage = Depends(get_operations_storage)):
    """Cancel a bulk operation."""
    operation = ops_storage.get(operation_id)
    if not operation:
        raise HTTPException(status_code=404, detail="Operation not found")

    if operation.status in ["completed", "failed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Cannot cancel completed or already cancelled operation")

    operation.status = "cancelled"
    operation.completed_at = datetime.now()
    await ops_storage.update_and_save(operation)

    return {"message": f"Operation {operation_id} cancelled"}


# =============================================================================
# Background Task Processors
# =============================================================================

async def process_bulk_move(
    operation_id: str,
    video_ids: List[str],
    target_playlist_id: str,
    source_playlist_id: Optional[str] = None,
    config: Optional[TubeManagerConfig] = None,
    config_manager: Optional[ConfigManager] = None,
    ops_storage: OperationsStorage = None
):
    """Process bulk move operation."""
    if not config or not config_manager:
        log.error("Config not provided for bulk move operation")
        operation = ops_storage.get(operation_id)
        if operation:
            operation.status = "failed"
            operation.completed_at = datetime.now()
            await ops_storage.update_and_save(operation)
        return

    operation = ops_storage.get(operation_id)
    if not operation: # Handle case where operation was deleted before starting
        log.warning(f"Operation {operation_id} not found for processing.")
        return

    operation.status = "in_progress"
    await ops_storage.update_and_save(operation)

    service = BulkOperationsService(config, config_manager)

    try:
        for i, video_id in enumerate(video_ids):
            current_operation_status = ops_storage.get(operation_id)
            if current_operation_status and current_operation_status.status == "cancelled": # Check for cancellation
                operation.errors.append("Operation cancelled by user.")
                break

            try:
                success = await service.move_video(video_id, target_playlist_id, source_playlist_id)
                if success:
                    operation.succeeded += 1
                else:
                    operation.failed += 1
                    operation.errors.append(f"Failed to move {video_id}")
            except Exception as e:
                operation.failed += 1
                operation.errors.append(f"Failed to move {video_id}: {str(e)}")

            operation.processed += 1

            # Update progress every 10 items (or if last item)
            if i % 10 == 0 or i == len(video_ids) - 1:
                await ops_storage.update_and_save(operation)

        if operation.status != "cancelled": # Don't change status if cancelled
            operation.status = "completed"
    except Exception as e:
        operation.status = "failed"
        operation.errors.append(f"Operation failed: {str(e)}")
    finally:
        operation.completed_at = datetime.now()
        await ops_storage.update_and_save(operation)


async def process_bulk_delete(
    operation_id: str,
    video_ids: List[str],
    playlist_id: str,
    config: Optional[TubeManagerConfig] = None,
    config_manager: Optional[ConfigManager] = None,
    ops_storage: OperationsStorage = None
):
    """Process bulk delete operation."""
    if not config or not config_manager:
        log.error("Config not provided for bulk delete operation")
        operation = ops_storage.get(operation_id)
        if operation:
            operation.status = "failed"
            operation.completed_at = datetime.now()
            await ops_storage.update_and_save(operation)
        return

    operation = ops_storage.get(operation_id)
    if not operation: # Handle case where operation was deleted before starting
        log.warning(f"Operation {operation_id} not found for processing.")
        return

    operation.status = "in_progress"
    await ops_storage.update_and_save(operation)

    service = BulkOperationsService(config, config_manager)

    try:
        for i, video_id in enumerate(video_ids):
            current_operation_status = ops_storage.get(operation_id)
            if current_operation_status and current_operation_status.status == "cancelled": # Check for cancellation
                operation.errors.append("Operation cancelled by user.")
                break

            try:
                success = await service.delete_video(video_id, playlist_id)
                if success:
                    operation.succeeded += 1
                else:
                    operation.failed += 1
                    operation.errors.append(f"Failed to delete {video_id}")
            except Exception as e:
                operation.failed += 1
                operation.errors.append(f"Failed to delete {video_id}: {str(e)}")

            operation.processed += 1
            if i % 10 == 0 or i == len(video_ids) - 1:
                await ops_storage.update_and_save(operation)

        if operation.status != "cancelled": # Don't change status if cancelled
            operation.status = "completed"
    except Exception as e:
        operation.status = "failed"
        operation.errors.append(f"Operation failed: {str(e)}")
    finally:
        operation.completed_at = datetime.now()
        await ops_storage.update_and_save(operation)


async def process_bulk_tag(
    operation_id: str,
    video_ids: List[str],
    tags: List[str],
    action: str,
    config: Optional[TubeManagerConfig] = None,
    config_manager: Optional[ConfigManager] = None,
    ops_storage: OperationsStorage = None
):
    """Process bulk tag operation."""
    if not config or not config_manager:
        log.error("Config not provided for bulk tag operation")
        operation = ops_storage.get(operation_id)
        if operation:
            operation.status = "failed"
            operation.completed_at = datetime.now()
            await ops_storage.update_and_save(operation)
        return

    operation = ops_storage.get(operation_id)
    if not operation: # Handle case where operation was deleted before starting
        log.warning(f"Operation {operation_id} not found for processing.")
        return

    operation.status = "in_progress"
    await ops_storage.update_and_save(operation)

    service = BulkOperationsService(config, config_manager)

    try:
        for i, video_id in enumerate(video_ids):
            current_operation_status = ops_storage.get(operation_id)
            if current_operation_status and current_operation_status.status == "cancelled": # Check for cancellation
                operation.errors.append("Operation cancelled by user.")
                break

            try:
                success = await service.tag_video(video_id, tags, action)
                if success:
                    operation.succeeded += 1
                else:
                    operation.failed += 1
                    operation.errors.append(f"Failed to {action} tag for {video_id}")
            except Exception as e:
                operation.failed += 1
                operation.errors.append(f"Failed to {action} tag for {video_id}: {str(e)}")

            operation.processed += 1
            if i % 10 == 0 or i == len(video_ids) - 1:
                await ops_storage.update_and_save(operation)

        if operation.status != "cancelled": # Don't change status if cancelled
            operation.status = "completed"
    except Exception as e:
        operation.status = "failed"
        operation.errors.append(f"Operation failed: {str(e)}")
    finally:
        operation.completed_at = datetime.now()
        await ops_storage.update_and_save(operation)


async def process_import(
    operation_id: str,
    resource_type: str,
    format: str,
    data: str,
    options: Optional[Dict[str, Any]] = None,
    config: Optional[TubeManagerConfig] = None,
    config_manager: Optional[ConfigManager] = None,
    ops_storage: OperationsStorage = None
):
    """Process bulk import operation."""
    if not config or not config_manager:
        log.error("Config not provided for bulk import operation")
        operation = ops_storage.get(operation_id)
        if operation:
            operation.status = "failed"
            operation.completed_at = datetime.now()
            await ops_storage.update_and_save(operation)
        return

    operation = ops_storage.get(operation_id)
    if not operation: # Handle case where operation was deleted before starting
        log.warning(f"Operation {operation_id} not found for processing.")
        return

    operation.status = "in_progress"
    await ops_storage.update_and_save(operation)

    service = BulkOperationsService(config, config_manager)

    try:
        decoded_data = base64.b64decode(data).decode('utf-8')
        processed_count = 0
        if resource_type == "playlists":
            if format == "json":
                items = json.loads(decoded_data)
                operation.total_items = len(items)
                for i, item in enumerate(items):
                    current_operation_status = ops_storage.get(operation_id)
                    if current_operation_status and current_operation_status.status == "cancelled": break
                    success = await service.import_playlist(item)
                    if success: operation.succeeded += 1
                    else: operation.failed += 1; operation.errors.append(f"Failed to import playlist {item.get('title', '')}")
                    operation.processed += 1
                    if i % 10 == 0 or i == len(items) - 1: await ops_storage.update_and_save(operation)

            elif format == "csv":
                reader = csv.DictReader(io.StringIO(decoded_data))
                items = list(reader)
                operation.total_items = len(items)
                for i, item in enumerate(items):
                    current_operation_status = ops_storage.get(operation_id)
                    if current_operation_status and current_operation_status.status == "cancelled": break
                    success = await service.import_playlist_from_csv_row(item)
                    if success: operation.succeeded += 1
                    else: operation.failed += 1; operation.errors.append(f"Failed to import playlist from CSV row: {item}")
                    operation.processed += 1
                    if i % 10 == 0 or i == len(items) - 1: await ops_storage.update_and_save(operation)

        elif resource_type == "subscriptions":
            if format == "json":
                items = json.loads(decoded_data)
                operation.total_items = len(items)
                for i, item in enumerate(items):
                    current_operation_status = ops_storage.get(operation_id)
                    if current_operation_status and current_operation_status.status == "cancelled": break
                    success = await service.import_subscription(item)
                    if success: operation.succeeded += 1
                    else: operation.failed += 1; operation.errors.append(f"Failed to import subscription {item.get('title', '')}")
                    operation.processed += 1
                    if i % 10 == 0 or i == len(items) - 1: await ops_storage.update_and_save(operation)

            elif format == "csv":
                reader = csv.DictReader(io.StringIO(decoded_data))
                items = list(reader)
                operation.total_items = len(items)
                for i, item in enumerate(items):
                    current_operation_status = ops_storage.get(operation_id)
                    if current_operation_status and current_operation_status.status == "cancelled": break
                    success = await service.import_subscription_from_csv_row(item)
                    if success: operation.succeeded += 1
                    else: operation.failed += 1; operation.errors.append(f"Failed to import subscription from CSV row: {item}")
                    operation.processed += 1
                    if i % 10 == 0 or i == len(items) - 1: await ops_storage.update_and_save(operation)

        elif resource_type == "mappings":
            if format == "json":
                items = json.loads(decoded_data)
                # Mappings can be dict or list of dicts. Normalize to list.
                if isinstance(items, dict): items = [{"channel": k, "playlist": v} for k,v in items.items()]
                
                operation.total_items = len(items)
                current_mappings = config.channel_mappings.copy() # Load existing
                for i, item in enumerate(items):
                    current_operation_status = ops_storage.get(operation_id)
                    if current_operation_status and current_operation_status.status == "cancelled": break
                    if "channel" in item and "playlist" in item:
                        current_mappings[item["channel"]] = item["playlist"]
                        operation.succeeded += 1
                    else:
                        operation.failed += 1
                        operation.errors.append(f"Invalid mapping entry: {item}")
                    operation.processed += 1
                    if i % 10 == 0 or i == len(items) - 1: await ops_storage.update_and_save(operation)
                # Save only once at the end
                config.channel_mappings = current_mappings
                await config_manager.save(config)
            elif format == "csv":
                reader = csv.DictReader(io.StringIO(decoded_data))
                items = list(reader)
                operation.total_items = len(items)
                current_mappings = config.channel_mappings.copy()
                for i, item in enumerate(items):
                    current_operation_status = ops_storage.get(operation_id)
                    if current_operation_status and current_operation_status.status == "cancelled": break
                    if "channel" in item and "playlist" in item:
                        current_mappings[item["channel"]] = item["playlist"]
                        operation.succeeded += 1
                    else:
                        operation.failed += 1
                        operation.errors.append(f"Invalid mapping entry: {item}")
                    operation.processed += 1
                    if i % 10 == 0 or i == len(items) - 1: await ops_storage.update_and_save(operation)
                config.channel_mappings = current_mappings
                await config_manager.save(config)

        else:
            raise HTTPException(status_code=400, detail="Invalid resource type")

        if operation.status != "cancelled":
            operation.status = "completed"

    except Exception as e:
        operation.status = "failed"
        operation.errors.append(f"Operation failed: {str(e)}")
    finally:
        operation.completed_at = datetime.now()
        await ops_storage.update_and_save(operation)


# =============================================================================
# Export Functions (Removed - now in service)
# =============================================================================
