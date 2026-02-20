import client from "./client";
import type { TaskTrigger } from "./servers";

export interface Domain {
  id: number;
  instance_id: number;
  domain_name: string;
  status: string;
  ssl_status: string;
  ssl_expires_at: string | null;
  created_at: string;
}

export async function listDomains(instanceId: number): Promise<Domain[]> {
  const res = await client.get(`/instances/${instanceId}/domains`);
  return res.data;
}

export async function createDomain(instanceId: number, domain_name: string): Promise<TaskTrigger> {
  const res = await client.post(`/instances/${instanceId}/domains`, { domain_name });
  return res.data;
}

export async function deleteDomain(id: number): Promise<void> {
  await client.delete(`/domains/${id}`);
}

export async function issueSSL(id: number): Promise<TaskTrigger> {
  const res = await client.post(`/domains/${id}/issue-ssl`);
  return res.data;
}
