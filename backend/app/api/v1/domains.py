from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.domain import DomainCreate, DomainRead
from app.schemas.task import TaskTriggerResponse
from app.services.domain_service import create_domain, delete_domain, get_domain, list_domains
from app.services.odoo_service import get_instance
from app.services.server_service import create_task_log, get_server
from app.workers.domain_tasks import issue_ssl_cert, setup_nginx_proxy

router = APIRouter(tags=["domains"])


async def _verify_instance_ownership(instance_id: int, db: AsyncSession, user: User):
    instance = await get_instance(db, instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    server = await get_server(db, instance.server_id, user)
    if not server:
        raise HTTPException(status_code=404, detail="Instance not found")
    return instance


@router.get("/instances/{instance_id}/domains", response_model=list[DomainRead])
async def list_domains_endpoint(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_instance_ownership(instance_id, db, current_user)
    return await list_domains(db, instance_id)


@router.post(
    "/instances/{instance_id}/domains",
    response_model=TaskTriggerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_domain_endpoint(
    instance_id: int,
    data: DomainCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_instance_ownership(instance_id, db, current_user)
    domain = await create_domain(db, instance_id, data)
    task = setup_nginx_proxy.delay(domain.id)
    await create_task_log(db, task.id, current_user, "setup_nginx", domain.id, "domain")
    return TaskTriggerResponse(task_id=task.id, message="Domain setup started")


@router.delete("/domains/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_domain_endpoint(
    domain_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    domain = await get_domain(db, domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    await _verify_instance_ownership(domain.instance_id, db, current_user)
    await delete_domain(db, domain)


@router.post("/domains/{domain_id}/issue-ssl", response_model=TaskTriggerResponse)
async def issue_ssl_endpoint(
    domain_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    domain = await get_domain(db, domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    await _verify_instance_ownership(domain.instance_id, db, current_user)
    task = issue_ssl_cert.delay(domain.id)
    await create_task_log(db, task.id, current_user, "issue_ssl", domain.id, "domain")
    return TaskTriggerResponse(task_id=task.id, message="SSL certificate issuance started")
