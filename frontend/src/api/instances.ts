import client from "./client";
import type { TaskTrigger } from "./servers";

export interface OdooInstance {
  id: number;
  server_id: number;
  name: string;
  odoo_version: string;
  edition: string;
  container_name: string;
  container_id: string | null;
  host_port: number;
  status: string;
  odoo_config: string | null;
  addons_path: string | null;
  pg_container_name: string | null;
  pg_port: number | null;
  created_at: string;
}

export interface InstanceCreate {
  name: string;
  odoo_version: string;
  edition: string;
  host_port: number;
  odoo_config?: Record<string, string>;
}

export async function listInstances(serverId: number): Promise<OdooInstance[]> {
  const res = await client.get(`/servers/${serverId}/instances`);
  return res.data;
}

export async function getInstance(id: number): Promise<OdooInstance> {
  const res = await client.get(`/instances/${id}`);
  return res.data;
}

export async function createInstance(serverId: number, data: InstanceCreate): Promise<TaskTrigger> {
  const res = await client.post(`/servers/${serverId}/instances`, data);
  return res.data;
}

export interface InstanceUpdate {
  name?: string;
  odoo_config?: Record<string, string>;
}

export async function updateInstance(id: number, data: InstanceUpdate): Promise<OdooInstance> {
  const res = await client.patch(`/instances/${id}`, data);
  return res.data;
}

export async function deleteInstance(id: number): Promise<TaskTrigger> {
  const res = await client.delete(`/instances/${id}`);
  return res.data;
}

export async function deployInstance(id: number): Promise<TaskTrigger> {
  const res = await client.post(`/instances/${id}/deploy`);
  return res.data;
}

export async function startInstance(id: number): Promise<TaskTrigger> {
  const res = await client.post(`/instances/${id}/start`);
  return res.data;
}

export async function stopInstance(id: number): Promise<TaskTrigger> {
  const res = await client.post(`/instances/${id}/stop`);
  return res.data;
}

export async function restartInstance(id: number): Promise<TaskTrigger> {
  const res = await client.post(`/instances/${id}/restart`);
  return res.data;
}

export async function getInstanceLogs(id: number, tail = 200): Promise<TaskTrigger> {
  const res = await client.get(`/instances/${id}/logs?tail=${tail}`);
  return res.data;
}
