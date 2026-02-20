import { useTaskPoller } from "../../hooks/useTaskPoller";
import type { TaskStatus } from "../../api/tasks";
import { useEffect, useState } from "react";

interface TaskProgressProps {
  taskId: string | null;
  onComplete?: (task: TaskStatus) => void;
  label?: string;
  /** Auto-dismiss success after N ms (0 = never). Default: 3000 */
  autoDismissMs?: number;
}

export default function TaskProgress({
  taskId,
  onComplete,
  label,
  autoDismissMs = 3000,
}: TaskProgressProps) {
  const { task, isPolling, error, startPolling, reset } = useTaskPoller(onComplete);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (taskId) {
      startPolling(taskId);
      setVisible(true);
    } else {
      reset();
      setVisible(false);
    }
  }, [taskId, startPolling, reset]);

  // Auto-dismiss on success
  useEffect(() => {
    if (task?.status === "success" && autoDismissMs > 0) {
      const timer = setTimeout(() => setVisible(false), autoDismissMs);
      return () => clearTimeout(timer);
    }
  }, [task?.status, autoDismissMs]);

  if (!visible || !taskId) return null;

  const isSuccess = task?.status === "success";
  const isFailed = task?.status === "failed";
  const isRunning = isPolling && !isSuccess && !isFailed;

  // Determine banner style
  let bannerClass = "bg-blue-50 border-blue-200";
  if (isSuccess) bannerClass = "bg-green-50 border-green-200";
  if (isFailed || error) bannerClass = "bg-red-50 border-red-200";

  // Parse error from result
  let errorMessage = error || null;
  if (isFailed && task?.result && !errorMessage) {
    try {
      const parsed = JSON.parse(task.result);
      errorMessage = parsed.error || parsed.detail || task.result;
    } catch {
      errorMessage = task.result;
    }
  }

  return (
    <div className={`flex items-center gap-3 p-3 border rounded-md text-sm mb-4 ${bannerClass}`}>
      {/* Status indicator */}
      {isRunning && (
        <div className="flex-shrink-0">
          <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-600 border-t-transparent" />
        </div>
      )}
      {isSuccess && (
        <span className="flex-shrink-0 text-green-600 font-bold text-base">&#10003;</span>
      )}
      {(isFailed || error) && (
        <span className="flex-shrink-0 text-red-600 font-bold text-base">&#10007;</span>
      )}

      {/* Message */}
      <div className="flex-1 min-w-0">
        <span className="text-gray-700 font-medium">{label || "Task"}</span>
        <span className="text-gray-500 ml-1.5">
          {error
            ? "error"
            : task?.status === "running"
              ? "running..."
              : task?.status || "pending..."}
        </span>
        {errorMessage && (
          <p className="text-red-600 text-xs mt-1 truncate">{errorMessage}</p>
        )}
      </div>

      {/* Dismiss button for completed/failed tasks */}
      {(isSuccess || isFailed || error) && (
        <button
          onClick={() => setVisible(false)}
          className="flex-shrink-0 text-gray-400 hover:text-gray-600 text-lg leading-none"
          aria-label="Dismiss"
        >
          &times;
        </button>
      )}
    </div>
  );
}
