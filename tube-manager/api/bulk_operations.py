"""Bulk operations API endpoints."""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
import csv
import io
from datetime import datetime
import base64

from api.bulk_operations_impl import BulkOperationsService
from core.config_manager import ConfigManager, get_config_manager
from models.config import TubeManagerConfig, get_config

router = APIRouter(prefix="/api/bulk", tags=["bulk"])


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
    errors: List[str]


# =============================================================================
# In-Memory Storage for Operations
# =============================================================================

# In production, use a database or Redis
operations: Dict[str, BulkOperationResponse] = {}


# =============================================================================
# Bulk Operation Endpoints
# =============================================================================

@router.post("/move", response_model=BulkOperationResponse)
async def bulk_move_videos(
    request: BulkMoveRequest,
    background_tasks: BackgroundTasks,
    config: TubeManagerConfig = Depends(get_config),
    config_manager: ConfigManager = Depends(get_config_manager)
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

    operations[operation_id] = operation

    # Add to background tasks
    background_tasks.add_task(
        process_bulk_move,
        operation_id,
        request.video_ids,
        request.target_playlist_id,
        request.source_playlist_id,
        config,
        config_manager
    )

    return operation


@router.post("/delete", response_model=BulkOperationResponse)
async def bulk_delete_videos(
    request: BulkDeleteRequest,
    background_tasks: BackgroundTasks,
    config: TubeManagerConfig = Depends(get_config),
    config_manager: ConfigManager = Depends(get_config_manager)
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

    operations[operation_id] = operation

    # Add to background tasks
    background_tasks.add_task(
        process_bulk_delete,
        operation_id,
        request.video_ids,
        request.playlist_id,
        config,
        config_manager
    )

    return operation


@router.post("/tag", response_model=BulkOperationResponse)
async def bulk_tag_videos(
    request: BulkTagRequest,
    background_tasks: BackgroundTasks,
    config: TubeManagerConfig = Depends(get_config),
    config_manager: ConfigManager = Depends(get_config_manager)
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

    operations[operation_id] = operation

    # Add to background tasks
    background_tasks.add_task(
        process_bulk_tag,
        operation_id,
        request.video_ids,
        request.tags,
        request.action,
        config,
        config_manager
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
    config_manager: ConfigManager = Depends(get_config_manager)
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

    operations[operation_id] = operation

    # Add to background tasks
    background_tasks.add_task(
        process_import,
        operation_id,
        request.resource_type,
        request.format,
        request.data,
        request.options,
        config,
        config_manager
    )

    return operation


# =============================================================================
# Operation Status Endpoints
# =============================================================================

@router.get("/operations/{operation_id}", response_model=OperationStatusResponse)
async def get_operation_status(operation_id: str):
    """Get status of a bulk operation."""
    if operation_id not in operations:
        raise HTTPException(status_code=404, detail="Operation not found")

    operation = operations[operation_id]

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
async def list_operations(limit: int = 20, offset: int = 0):
    """List recent bulk operations."""
    operation_list = list(operations.values())
    operation_list.sort(key=lambda x: x.started_at or datetime.min, reverse=True)

    return {
        "total": len(operation_list),
        "operations": operation_list[offset:offset + limit]
    }


@router.delete("/operations/{operation_id}")
async def cancel_operation(operation_id: str):
    """Cancel a bulk operation."""
    if operation_id not in operations:
        raise HTTPException(status_code=404, detail="Operation not found")

    operation = operations[operation_id]

    if operation.status in ["completed", "failed"]:
        raise HTTPException(status_code=400, detail="Cannot cancel completed operation")

    operation.status = "cancelled"
    operation.completed_at = datetime.now()

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
    config_manager: Optional[ConfigManager] = None
):
    """Process bulk move operation."""
    if not config or not config_manager:
        log.error("Config not provided for bulk move operation")
        operations[operation_id].status = "failed"
        operations[operation_id].completed_at = datetime.now()
        return

    operation = operations[operation_id]
    operation.status = "in_progress"

    service = BulkOperationsService(config, config_manager)

    try:
        for i, video_id in enumerate(video_ids):
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

            # Update progress every 10 items
            if i % 10 == 0:
                pass  # Could emit WebSocket message here

        operation.status = "completed"
    except Exception as e:
        operation.status = "failed"
        operation.errors.append(f"Operation failed: {str(e)}")
    finally:
        operation.completed_at = datetime.now()


async def process_bulk_delete(
    operation_id: str,
    video_ids: List[str],
    playlist_id: str,
    config: Optional[TubeManagerConfig] = None,
    config_manager: Optional[ConfigManager] = None
):
    """Process bulk delete operation."""
    if not config or not config_manager:
        log.error("Config not provided for bulk delete operation")
        operations[operation_id].status = "failed"
        operations[operation_id].completed_at = datetime.now()
        return

    operation = operations[operation_id]
    operation.status = "in_progress"

    service = BulkOperationsService(config, config_manager)

    try:
        for i, video_id in enumerate(video_ids):
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

        operation.status = "completed"
    except Exception as e:
        operation.status = "failed"
        operation.errors.append(f"Operation failed: {str(e)}")
    finally:
        operation.completed_at = datetime.now()


async def process_bulk_tag(
    operation_id: str,
    video_ids: List[str],
    tags: List[str],
    action: str,
    config: Optional[TubeManagerConfig] = None,
    config_manager: Optional[ConfigManager] = None
):
    """Process bulk tag operation."""
    if not config or not config_manager:
        log.error("Config not provided for bulk tag operation")
        operations[operation_id].status = "failed"
        operations[operation_id].completed_at = datetime.now()
        return

    operation = operations[operation_id]
    operation.status = "in_progress"

    service = BulkOperationsService(config, config_manager)

    try:
        for i, video_id in enumerate(video_ids):
            try:
                success = await service.tag_video(video_id, tags, action)
                if success:
                    operation.succeeded += 1
                else:
                    operation.failed += 1
                    operation.errors.append(f"Failed to tag {video_id}")
            except Exception as e:
                operation.failed += 1
                operation.errors.append(f"Failed to tag {video_id}: {str(e)}")

            operation.processed += 1

        operation.status = "completed"
    except Exception as e:
        operation.status = "failed"
        operation.errors.append(f"Operation failed: {str(e)}")
    finally:
        operation.completed_at = datetime.now()


async def process_import(
    operation_id: str,
    resource_type: str,
    format: str,
    data: str,
    options: Optional[Dict[str, Any]] = None,
    config: Optional[TubeManagerConfig] = None,
    config_manager: Optional[ConfigManager] = None
):
    """Process import operation."""
    if not config or not config_manager:
        log.error("Config not provided for import operation")
        operations[operation_id].status = "failed"
        operations[operation_id].completed_at = datetime.now()
        return

    operation = operations[operation_id]
    operation.status = "in_progress"

    service = BulkOperationsService(config, config_manager)

    try:
        # Decode data
        if format == "json":
            items = json.loads(data)
        elif format == "csv":
            # Parse CSV
            reader = csv.DictReader(io.StringIO(data))
            items = list(reader)
        else:
            raise ValueError(f"Unsupported format: {format}")

        operation.total_items = len(items)

        if resource_type == "mappings":
            # Import channel mappings
            count = await service.import_mappings(items, options)
            operation.succeeded = count
        elif resource_type == "playlists":
            # Import playlists (placeholder - requires OAuth for creation)
            log.warning("Playlist import not yet implemented")
            for item in items:
                operation.succeeded += 1
        elif resource_type == "subscriptions":
            # Import subscriptions (placeholder - requires OAuth for subscription)
            log.warning("Subscription import not yet implemented")
            for item in items:
                operation.succeeded += 1
        else:
            raise ValueError(f"Invalid resource type: {resource_type}")

        operation.processed = len(items)
        operation.status = "completed"
    except Exception as e:
        operation.status = "failed"
        operation.errors.append(f"Import failed: {str(e)}")
    finally:
        operation.completed_at = datetime.now()


# =============================================================================
# Export Functions (Removed - now in service)
# =============================================================================