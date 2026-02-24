import io

from fastapi import APIRouter, Depends, HTTPException, status
from paramiko import RSAKey
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.server import ServerCreate, ServerRead, ServerUpdate
from app.schemas.task import TaskTriggerResponse
from app.services.server_service import (
    create_server,
    create_task_log,
    delete_server,
    get_server,
    list_servers,
    update_server,
)
from app.workers.server_tasks import (
    get_system_info,
    install_server_deps,
    test_server_connection,
)

router = APIRouter(prefix="/servers", tags=["servers"])


@router.post("/generate-key")
async def generate_ssh_key(current_user: User = Depends(get_current_user)):
    """Generate a new RSA 4096-bit SSH key pair and return both keys."""
    key = RSAKey.generate(bits=4096)

    private_key_buf = io.StringIO()
    key.write_private_key(private_key_buf)
    private_key = private_key_buf.getvalue()

    public_key = f"ssh-rsa {key.get_base64()} cloudtab-generated"

    return {"private_key": private_key, "public_key": public_key}


@router.get("", response_model=list[ServerRead])
async def list_servers_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_servers(db, current_user)


@router.post("", response_model=ServerRead, status_code=status.HTTP_201_CREATED)
async def create_server_endpoint(
    data: ServerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await create_server(db, data, current_user)


@router.get("/{server_id}", response_model=ServerRead)
async def get_server_endpoint(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    server = await get_server(db, server_id, current_user)
    if server is None:
        raise HTTPException(status_code=404, detail="Server not found")
    return server


@router.patch("/{server_id}", response_model=ServerRead)
async def update_server_endpoint(
    server_id: int,
    data: ServerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    server = await get_server(db, server_id, current_user)
    if server is None:
        raise HTTPException(status_code=404, detail="Server not found")
    return await update_server(db, server, data)


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server_endpoint(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    server = await get_server(db, server_id, current_user)
    if server is None:
        raise HTTPException(status_code=404, detail="Server not found")
    await delete_server(db, server)


@router.post("/{server_id}/test-connection", response_model=TaskTriggerResponse)
async def test_connection_endpoint(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    server = await get_server(db, server_id, current_user)
    if server is None:
        raise HTTPException(status_code=404, detail="Server not found")

    task = test_server_connection.delay(server.id)
    await create_task_log(db, task.id, current_user, "test_connection", server.id, "server")
    return TaskTriggerResponse(task_id=task.id, message="Connection test started")


@router.post("/{server_id}/system-info", response_model=TaskTriggerResponse)
async def system_info_endpoint(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    server = await get_server(db, server_id, current_user)
    if server is None:
        raise HTTPException(status_code=404, detail="Server not found")

    task = get_system_info.delay(server.id)
    await create_task_log(db, task.id, current_user, "get_system_info", server.id, "server")
    return TaskTriggerResponse(task_id=task.id, message="System info fetch started")


@router.post("/{server_id}/install-deps", response_model=TaskTriggerResponse)
async def install_deps_endpoint(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    server = await get_server(db, server_id, current_user)
    if server is None:
        raise HTTPException(status_code=404, detail="Server not found")

    task = install_server_deps.delay(server.id)
    await create_task_log(db, task.id, current_user, "install_deps", server.id, "server")
    return TaskTriggerResponse(task_id=task.id, message="Dependency installation started")
