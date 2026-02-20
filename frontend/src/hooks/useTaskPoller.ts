import { useState, useEffect, useCallback, useRef } from "react";
import { getTaskStatus, type TaskStatus } from "../api/tasks";

interface PollerOptions {
  /** Initial polling interval in ms (default: 1000) */
  initialInterval?: number;
  /** Maximum polling interval in ms (default: 10000) */
  maxInterval?: number;
  /** Backoff multiplier (default: 1.5) */
  backoffFactor?: number;
  /** Stop polling after this many ms (default: 300000 = 5min) */
  timeout?: number;
  /** Max consecutive errors before stopping (default: 10) */
  maxErrors?: number;
}

interface UseTaskPollerResult {
  task: TaskStatus | null;
  isPolling: boolean;
  error: string | null;
  startPolling: (taskId: string) => void;
  reset: () => void;
}

const DEFAULTS: Required<PollerOptions> = {
  initialInterval: 1000,
  maxInterval: 10000,
  backoffFactor: 1.5,
  timeout: 300000,
  maxErrors: 10,
};

export function useTaskPoller(
  onComplete?: (task: TaskStatus) => void,
  options?: PollerOptions
): UseTaskPollerResult {
  const opts = { ...DEFAULTS, ...options };

  const [taskId, setTaskId] = useState<string | null>(null);
  const [task, setTask] = useState<TaskStatus | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Use refs for mutable values that shouldn't trigger re-renders
  const intervalRef = useRef(opts.initialInterval);
  const errorCountRef = useRef(0);
  const startTimeRef = useRef(0);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  const startPolling = useCallback(
    (id: string) => {
      setTaskId(id);
      setTask(null);
      setError(null);
      setIsPolling(true);
      intervalRef.current = opts.initialInterval;
      errorCountRef.current = 0;
      startTimeRef.current = Date.now();
    },
    [opts.initialInterval]
  );

  const reset = useCallback(() => {
    setTaskId(null);
    setTask(null);
    setError(null);
    setIsPolling(false);
  }, []);

  useEffect(() => {
    if (!taskId || !isPolling) return;

    let cancelled = false;
    let timerId: ReturnType<typeof setTimeout>;

    const poll = async () => {
      // Check timeout
      if (Date.now() - startTimeRef.current > opts.timeout) {
        setError("Task polling timed out");
        setIsPolling(false);
        return;
      }

      try {
        const status = await getTaskStatus(taskId);
        if (cancelled) return;

        setTask(status);
        errorCountRef.current = 0; // Reset error count on success

        if (status.status === "success" || status.status === "failed") {
          setIsPolling(false);
          onCompleteRef.current?.(status);
          return;
        }

        // Task is still running — use shorter interval
        // Once task moves to "running" from "pending", poll faster
        if (status.status === "running") {
          intervalRef.current = Math.max(opts.initialInterval, intervalRef.current * 0.8);
        }
      } catch (err) {
        if (cancelled) return;

        errorCountRef.current += 1;

        if (errorCountRef.current >= opts.maxErrors) {
          setError(`Task polling failed after ${opts.maxErrors} attempts`);
          setIsPolling(false);
          return;
        }

        // Apply backoff on errors
        intervalRef.current = Math.min(
          intervalRef.current * opts.backoffFactor,
          opts.maxInterval
        );
      }

      // Schedule next poll
      if (!cancelled) {
        timerId = setTimeout(poll, intervalRef.current);
      }
    };

    // Start first poll immediately
    poll();

    return () => {
      cancelled = true;
      clearTimeout(timerId);
    };
  }, [taskId, isPolling, opts.timeout, opts.maxErrors, opts.backoffFactor, opts.maxInterval, opts.initialInterval]);

  return { task, isPolling, error, startPolling, reset };
}
