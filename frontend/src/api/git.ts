import client from "./client";
import type { TaskTrigger } from "./servers";

export interface GitRepo {
  id: number;
  instance_id: number;
  repo_url: string;
  branch: string;
  last_deployed_at: string | null;
  last_commit_sha: string | null;
  created_at: string;
}

export async function getGitRepo(instanceId: number): Promise<GitRepo | null> {
  const res = await client.get(`/instances/${instanceId}/git-repo`);
  return res.data;
}

export async function linkGitRepo(
  instanceId: number,
  data: { repo_url: string; branch: string; deploy_key?: string }
): Promise<GitRepo> {
  const res = await client.post(`/instances/${instanceId}/git-repo`, data);
  return res.data;
}

export interface GitRepoUpdate {
  repo_url?: string;
  branch?: string;
  deploy_key?: string;
}

export async function updateGitRepo(id: number, data: GitRepoUpdate): Promise<GitRepo> {
  const res = await client.patch(`/git-repos/${id}`, data);
  return res.data;
}

export async function deleteGitRepo(id: number): Promise<void> {
  await client.delete(`/git-repos/${id}`);
}

export async function deployModules(id: number): Promise<TaskTrigger> {
  const res = await client.post(`/git-repos/${id}/deploy`);
  return res.data;
}
