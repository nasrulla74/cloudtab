from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import Domain
from app.schemas.domain import DomainCreate


async def list_domains(db: AsyncSession, instance_id: int) -> list[Domain]:
    result = await db.execute(
        select(Domain)
        .where(Domain.instance_id == instance_id)
        .order_by(Domain.created_at.desc())
    )
    return list(result.scalars().all())


async def get_domain(db: AsyncSession, domain_id: int) -> Domain | None:
    result = await db.execute(select(Domain).where(Domain.id == domain_id))
    return result.scalar_one_or_none()


async def create_domain(
    db: AsyncSession, instance_id: int, data: DomainCreate
) -> Domain:
    domain = Domain(
        instance_id=instance_id,
        domain_name=data.domain_name,
    )
    db.add(domain)
    await db.commit()
    await db.refresh(domain)
    return domain


async def delete_domain(db: AsyncSession, domain: Domain) -> None:
    await db.delete(domain)
    await db.commit()
