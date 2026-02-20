import client from "./client";
import type { TaskTrigger } from "./servers";

export interface BackupSchedule {
  id: number;
  instance_id: number;
  frequency: string;
  retention_days: number;
  storage_type: string;
  s3_bucket: string | null;
  s3_prefix: string | null;
  is_active: boolean;
  next_run_at: string | null;
  created_at: string;
}

export interface BackupRecord {
  id: number;
  instance_id: number;
  schedule_id: number | null;
  file_path: string | null;
  file_size_bytes: number | null;
  storage_type: string;
  status: string;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface BackupScheduleCreate {
  frequency: string;
  retention_days?: number;
  storage_type?: string;
  s3_bucket?: string;
  s3_prefix?: string;
}

export async function listSchedules(instanceId: number): Promise<BackupSchedule[]> {
  const res = await client.get(`/instances/${instanceId}/backup-schedules`);
  return res.data;
}

export async function createSchedule(
  instanceId: number,
  data: BackupScheduleCreate
): Promise<BackupSchedule> {
  const res = await client.post(`/instances/${instanceId}/backup-schedules`, data);
  return res.data;
}

export interface BackupScheduleUpdate {
  frequency?: string;
  retention_days?: number;
  is_active?: boolean;
  storage_type?: string;
  s3_bucket?: string;
  s3_prefix?: string;
}

export async function updateSchedule(
  id: number,
  data: BackupScheduleUpdate
): Promise<BackupSchedule> {
  const res = await client.patch(`/backup-schedules/${id}`, data);
  return res.data;
}

export async function deleteSchedule(id: number): Promise<void> {
  await client.delete(`/backup-schedules/${id}`);
}

export async function triggerBackup(instanceId: number): Promise<TaskTrigger> {
  const res = await client.post(`/instances/${instanceId}/backup-now`);
  return res.data;
}

export async function listBackupRecords(instanceId: number): Promise<BackupRecord[]> {
  const res = await client.get(`/instances/${instanceId}/backup-records`);
  return res.data;
}

export async function restoreBackup(recordId: number): Promise<TaskTrigger> {
  const res = await client.post(`/backup-records/${recordId}/restore`);
  return res.data;
}
