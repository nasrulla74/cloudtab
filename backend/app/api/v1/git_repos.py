from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.git_repo import GitRepoCreate, GitRepoRead, GitRepoUpdate
from app.schemas.task import TaskTriggerResponse
from sqlalchemy import select

from app.models.git_repo import GitRepo
from app.services.git_service import (
    create_git_repo,
    delete_git_repo,
    get_git_repo,
    update_git_repo,
)
from app.services.odoo_service import get_instance
from app.services.server_service import create_task_log, get_server
from app.workers.git_tasks import deploy_git_modules

router = APIRouter(tags=["git"])


async def _verify_instance_ownership(instance_id: int, db: AsyncSession, user: User):
    instance = await get_instance(db, instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    server = await get_server(db, instance.server_id, user)
    if not server:
        raise HTTPException(status_code=404, detail="Instance not found")
    return instance


@router.get("/instances/{instance_id}/git-repo")
async def get_instance_git_repo(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_instance_ownership(instance_id, db, current_user)
    result = await db.execute(select(GitRepo).where(GitRepo.instance_id == instance_id))
    repo = result.scalar_one_or_none()
    if repo is None:
        return None
    return GitRepoRead.model_validate(repo)


@router.post(
    "/instances/{instance_id}/git-repo",
    response_model=GitRepoRead,
    status_code=status.HTTP_201_CREATED,
)
async def link_git_repo(
    instance_id: int,
    data: GitRepoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_instance_ownership(instance_id, db, current_user)
    return await create_git_repo(db, instance_id, data)


@router.patch("/git-repos/{repo_id}", response_model=GitRepoRead)
async def update_git_repo_endpoint(
    repo_id: int,
    data: GitRepoUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = await get_git_repo(db, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Git repo not found")
    await _verify_instance_ownership(repo.instance_id, db, current_user)
    return await update_git_repo(db, repo, data)


@router.delete("/git-repos/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_git_repo_endpoint(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = await get_git_repo(db, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Git repo not found")
    await _verify_instance_ownership(repo.instance_id, db, current_user)
    await delete_git_repo(db, repo)


@router.post("/git-repos/{repo_id}/deploy", response_model=TaskTriggerResponse)
async def deploy_modules_endpoint(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = await get_git_repo(db, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Git repo not found")
    await _verify_instance_ownership(repo.instance_id, db, current_user)
    task = deploy_git_modules.delay(repo.id)
    await create_task_log(db, task.id, current_user, "deploy_modules", repo.id, "git_repo")
    return TaskTriggerResponse(task_id=task.id, message="Module deployment started")
