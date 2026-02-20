from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import encrypt_value
from app.models.git_repo import GitRepo
from app.schemas.git_repo import GitRepoCreate, GitRepoUpdate


async def get_git_repo(db: AsyncSession, repo_id: int) -> GitRepo | None:
    result = await db.execute(select(GitRepo).where(GitRepo.id == repo_id))
    return result.scalar_one_or_none()


async def get_git_repo_by_instance(db: AsyncSession, instance_id: int) -> GitRepo | None:
    result = await db.execute(
        select(GitRepo).where(GitRepo.instance_id == instance_id)
    )
    return result.scalar_one_or_none()


async def create_git_repo(
    db: AsyncSession, instance_id: int, data: GitRepoCreate
) -> GitRepo:
    repo = GitRepo(
        instance_id=instance_id,
        repo_url=data.repo_url,
        branch=data.branch,
        deploy_key_encrypted=encrypt_value(data.deploy_key) if data.deploy_key else None,
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)
    return repo


async def update_git_repo(db: AsyncSession, repo: GitRepo, data: GitRepoUpdate) -> GitRepo:
    if data.repo_url is not None:
        repo.repo_url = data.repo_url
    if data.branch is not None:
        repo.branch = data.branch
    if data.deploy_key is not None:
        repo.deploy_key_encrypted = encrypt_value(data.deploy_key) if data.deploy_key else None
    await db.commit()
    await db.refresh(repo)
    return repo


async def delete_git_repo(db: AsyncSession, repo: GitRepo) -> None:
    await db.delete(repo)
    await db.commit()
