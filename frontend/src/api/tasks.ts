import client from "./client";

export interface TaskStatus {
  id: number;
  celery_task_id: string;
  task_type: string;
  target_id: number | null;
  target_type: string | null;
  status: string;
  result: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export async function getTaskStatus(taskId: string): Promise<TaskStatus> {
  const res = await client.get(`/tasks/${taskId}`);
  return res.data;
}
