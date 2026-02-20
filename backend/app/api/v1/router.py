from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.servers import router as servers_router
from app.api.v1.instances import router as instances_router
from app.api.v1.domains import router as domains_router
from app.api.v1.backups import router as backups_router
from app.api.v1.git_repos import router as git_repos_router
from app.api.v1.tasks import router as tasks_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(servers_router)
api_router.include_router(instances_router)
api_router.include_router(domains_router)
api_router.include_router(backups_router)
api_router.include_router(git_repos_router)
api_router.include_router(tasks_router)
