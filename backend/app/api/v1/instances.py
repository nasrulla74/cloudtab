from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.odoo_instance import InstanceCreate, InstanceRead, InstanceUpdate, OdooConfigApply
from app.schemas.task import TaskTriggerResponse
from app.services.odoo_service import (
    create_instance,
    get_instance,
    list_instances,
    update_instance,
)
from app.services.server_service import create_task_log, get_server
from app.workers.odoo_tasks import (
    apply_odoo_config,
    deploy_odoo_instance,
    destroy_odoo_instance,
    get_odoo_logs,
    read_odoo_config,
    restart_odoo_instance,
    start_odoo_instance,
    stop_odoo_instance,
)

router = APIRouter(tags=["instances"])


async def _verify_server_ownership(server_id: int, db: AsyncSession, user: User):
    """Verify the server exists and belongs to the current user."""
    server = await get_server(db, server_id, user)
    if server is None:
        raise HTTPException(status_code=404, detail="Server not found")
    return server


async def _verify_instance_ownership(instance_id: int, db: AsyncSession, user: User):
    """Verify the instance exists and its server belongs to the current user."""
    instance = await get_instance(db, instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Instance not found")
    server = await get_server(db, instance.server_id, user)
    if server is None:
        raise HTTPException(status_code=404, detail="Instance not found")
    return instance


@router.get("/servers/{server_id}/instances", response_model=list[InstanceRead])
async def list_instances_endpoint(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_server_ownership(server_id, db, current_user)
    return await list_instances(db, server_id)


@router.post(
    "/servers/{server_id}/instances",
    response_model=TaskTriggerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_and_deploy_instance(
    server_id: int,
    data: InstanceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    server = await _verify_server_ownership(server_id, db, current_user)
    instance = await create_instance(db, server, data)
    task = deploy_odoo_instance.delay(instance.id)
    await create_task_log(db, task.id, current_user, "deploy_instance", instance.id, "instance")
    return TaskTriggerResponse(task_id=task.id, message="Odoo instance deployment started")


@router.get("/instances/{instance_id}", response_model=InstanceRead)
async def get_instance_endpoint(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _verify_instance_ownership(instance_id, db, current_user)


@router.patch("/instances/{instance_id}", response_model=InstanceRead)
async def update_instance_endpoint(
    instance_id: int,
    data: InstanceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    instance = await _verify_instance_ownership(instance_id, db, current_user)
    return await update_instance(db, instance, data)


@router.delete("/instances/{instance_id}", response_model=TaskTriggerResponse)
async def delete_instance_endpoint(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    instance = await _verify_instance_ownership(instance_id, db, current_user)
    # Stop containers, remove network/data, then delete DB record
    task = destroy_odoo_instance.delay(instance.id)
    await create_task_log(
        db, task.id, current_user, "destroy_instance", instance.id, "instance"
    )
    return TaskTriggerResponse(
        task_id=task.id, message="Instance destruction started"
    )


@router.post("/instances/{instance_id}/deploy", response_model=TaskTriggerResponse)
async def redeploy_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    instance = await _verify_instance_ownership(instance_id, db, current_user)
    task = deploy_odoo_instance.delay(instance.id)
    await create_task_log(db, task.id, current_user, "deploy_instance", instance.id, "instance")
    return TaskTriggerResponse(task_id=task.id, message="Redeployment started")


@router.post("/instances/{instance_id}/start", response_model=TaskTriggerResponse)
async def start_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    instance = await _verify_instance_ownership(instance_id, db, current_user)
    task = start_odoo_instance.delay(instance.id)
    await create_task_log(db, task.id, current_user, "start_instance", instance.id, "instance")
    return TaskTriggerResponse(task_id=task.id, message="Instance start initiated")


@router.post("/instances/{instance_id}/stop", response_model=TaskTriggerResponse)
async def stop_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    instance = await _verify_instance_ownership(instance_id, db, current_user)
    task = stop_odoo_instance.delay(instance.id)
    await create_task_log(db, task.id, current_user, "stop_instance", instance.id, "instance")
    return TaskTriggerResponse(task_id=task.id, message="Instance stop initiated")


@router.post("/instances/{instance_id}/restart", response_model=TaskTriggerResponse)
async def restart_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    instance = await _verify_instance_ownership(instance_id, db, current_user)
    task = restart_odoo_instance.delay(instance.id)
    await create_task_log(db, task.id, current_user, "restart_instance", instance.id, "instance")
    return TaskTriggerResponse(task_id=task.id, message="Instance restart initiated")


@router.get("/instances/{instance_id}/logs", response_model=TaskTriggerResponse)
async def get_instance_logs(
    instance_id: int,
    tail: int = 200,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    instance = await _verify_instance_ownership(instance_id, db, current_user)
    task = get_odoo_logs.delay(instance.id, tail)
    await create_task_log(db, task.id, current_user, "get_logs", instance.id, "instance")
    return TaskTriggerResponse(task_id=task.id, message="Log fetch started")


@router.post("/instances/{instance_id}/config/read", response_model=TaskTriggerResponse)
async def read_instance_config(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger a task to read the current odoo.conf from the instance server."""
    instance = await _verify_instance_ownership(instance_id, db, current_user)
    task = read_odoo_config.delay(instance.id)
    await create_task_log(db, task.id, current_user, "read_config", instance.id, "instance")
    return TaskTriggerResponse(task_id=task.id, message="Config read started")


@router.post("/instances/{instance_id}/config/apply", response_model=TaskTriggerResponse)
async def apply_instance_config(
    instance_id: int,
    data: OdooConfigApply,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger a task to apply updated config to odoo.conf and restart the container."""
    instance = await _verify_instance_ownership(instance_id, db, current_user)
    task = apply_odoo_config.delay(instance.id, data.updates)
    await create_task_log(db, task.id, current_user, "apply_config", instance.id, "instance")
    return TaskTriggerResponse(task_id=task.id, message="Config apply started")
