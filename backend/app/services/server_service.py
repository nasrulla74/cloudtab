from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import encrypt_value
from app.models.server import Server
from app.models.task_log import TaskLog
from app.models.user import User
from app.schemas.server import ServerCreate, ServerUpdate


async def list_servers(db: AsyncSession, user: User) -> list[Server]:
    result = await db.execute(
        select(Server).where(Server.owner_id == user.id).order_by(Server.created_at.desc())
    )
    return list(result.scalars().all())


async def get_server(db: AsyncSession, server_id: int, user: User) -> Server | None:
    result = await db.execute(
        select(Server).where(Server.id == server_id, Server.owner_id == user.id)
    )
    return result.scalar_one_or_none()


async def create_server(db: AsyncSession, data: ServerCreate, user: User) -> Server:
    server = Server(
        owner_id=user.id,
        name=data.name,
        host=data.host,
        port=data.port,
        ssh_user=data.ssh_user,
        ssh_key_encrypted=encrypt_value(data.ssh_key),
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return server


async def update_server(db: AsyncSession, server: Server, data: ServerUpdate) -> Server:
    if data.name is not None:
        server.name = data.name
    if data.host is not None:
        server.host = data.host
    if data.port is not None:
        server.port = data.port
    if data.ssh_user is not None:
        server.ssh_user = data.ssh_user
    if data.ssh_key is not None:
        server.ssh_key_encrypted = encrypt_value(data.ssh_key)
    await db.commit()
    await db.refresh(server)
    return server


async def delete_server(db: AsyncSession, server: Server) -> None:
    await db.delete(server)
    await db.commit()


async def create_task_log(
    db: AsyncSession,
    celery_task_id: str,
    user: User,
    task_type: str,
    target_id: int,
    target_type: str,
) -> TaskLog:
    task_log = TaskLog(
        celery_task_id=celery_task_id,
        user_id=user.id,
        task_type=task_type,
        target_id=target_id,
        target_type=target_type,
        status="pending",
    )
    db.add(task_log)
    await db.commit()
    await db.refresh(task_log)
    return task_log
