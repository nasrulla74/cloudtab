from datetime import datetime

from pydantic import BaseModel, Field


class GitRepoCreate(BaseModel):
    repo_url: str = Field(max_length=500)
    branch: str = Field(default="main", max_length=100)
    deploy_key: str | None = None  # Optional SSH deploy key


class GitRepoUpdate(BaseModel):
    repo_url: str | None = Field(default=None, max_length=500)
    branch: str | None = Field(default=None, max_length=100)
    deploy_key: str | None = None


class GitRepoRead(BaseModel):
    id: int
    instance_id: int
    repo_url: str
    branch: str
    last_deployed_at: datetime | None
    last_commit_sha: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
