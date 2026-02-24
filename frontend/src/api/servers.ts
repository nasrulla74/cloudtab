import client from "./client";

export interface Server {
  id: number;
  name: string;
  host: string;
  port: number;
  ssh_user: string;
  status: string;
  last_connected_at: string | null;
  os_version: string | null;
  cpu_cores: number | null;
  ram_total_bytes: number | null;
  disk_total_bytes: number | null;
  docker_version: string | null;
  created_at: string;
}

export interface ServerCreate {
  name: string;
  host: string;
  port: number;
  ssh_user: string;
  ssh_key: string;
}

export interface TaskTrigger {
  task_id: string;
  message: string;
}

export async function listServers(): Promise<Server[]> {
  const res = await client.get("/servers");
  return res.data;
}

export async function getServer(id: number): Promise<Server> {
  const res = await client.get(`/servers/${id}`);
  return res.data;
}

export async function createServer(data: ServerCreate): Promise<Server> {
  const res = await client.post("/servers", data);
  return res.data;
}

export interface ServerUpdate {
  name?: string;
  host?: string;
  port?: number;
  ssh_user?: string;
  ssh_key?: string;
}

export async function updateServer(id: number, data: ServerUpdate): Promise<Server> {
  const res = await client.patch(`/servers/${id}`, data);
  return res.data;
}

export async function deleteServer(id: number): Promise<void> {
  await client.delete(`/servers/${id}`);
}

export async function testConnection(id: number): Promise<TaskTrigger> {
  const res = await client.post(`/servers/${id}/test-connection`);
  return res.data;
}

export async function fetchSystemInfo(id: number): Promise<TaskTrigger> {
  const res = await client.post(`/servers/${id}/system-info`);
  return res.data;
}

export async function installDeps(id: number): Promise<TaskTrigger> {
  const res = await client.post(`/servers/${id}/install-deps`);
  return res.data;
}

export interface GeneratedSSHKey {
  private_key: string;
  public_key: string;
}

export async function generateSSHKey(): Promise<GeneratedSSHKey> {
  const res = await client.post("/servers/generate-key");
  return res.data;
}
