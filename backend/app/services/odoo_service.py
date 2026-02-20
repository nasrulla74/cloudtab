import json
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.odoo_instance import OdooInstance
from app.models.server import Server
from app.schemas.odoo_instance import InstanceCreate, InstanceUpdate


def _generate_container_name(name: str, server_id: int) -> str:
    """Generate a safe Docker container name from instance name."""
    safe = re.sub(r"[^a-z0-9_-]", "-", name.lower().strip())
    safe = re.sub(r"-+", "-", safe).strip("-")
    return f"odoo-{safe}-s{server_id}"


async def list_instances(db: AsyncSession, server_id: int) -> list[OdooInstance]:
    result = await db.execute(
        select(OdooInstance)
        .where(OdooInstance.server_id == server_id)
        .order_by(OdooInstance.created_at.desc())
    )
    return list(result.scalars().all())


async def get_instance(db: AsyncSession, instance_id: int) -> OdooInstance | None:
    result = await db.execute(
        select(OdooInstance).where(OdooInstance.id == instance_id)
    )
    return result.scalar_one_or_none()


async def create_instance(
    db: AsyncSession, server: Server, data: InstanceCreate
) -> OdooInstance:
    container_name = _generate_container_name(data.name, server.id)
    pg_container_name = f"{container_name}-db"
    # Use port + 5432 offset for postgres container, but keep it internal
    pg_port = data.host_port + 1000  # Internal mapping for management

    instance = OdooInstance(
        server_id=server.id,
        name=data.name,
        odoo_version=data.odoo_version,
        edition=data.edition,
        container_name=container_name,
        host_port=data.host_port,
        odoo_config=json.dumps(data.odoo_config) if data.odoo_config else None,
        pg_container_name=pg_container_name,
        pg_port=pg_port,
        pg_password="odoo",  # Simple default for now; generated per-instance in prod
        addons_path=f"/opt/cloudtab/{container_name}/addons",
    )
    db.add(instance)
    await db.commit()
    await db.refresh(instance)
    return instance


async def update_instance(
    db: AsyncSession, instance: OdooInstance, data: InstanceUpdate
) -> OdooInstance:
    if data.name is not None:
        instance.name = data.name
    if data.odoo_config is not None:
        instance.odoo_config = json.dumps(data.odoo_config)
    await db.commit()
    await db.refresh(instance)
    return instance


async def delete_instance(db: AsyncSession, instance: OdooInstance) -> None:
    await db.delete(instance)
    await db.commit()
