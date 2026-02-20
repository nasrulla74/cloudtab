import { useEffect } from "react";
import { onApiError } from "../api/client";
import { useToast } from "../components/shared/Toast";

/**
 * Hook that subscribes to the Axios error event bus and shows toast notifications
 * for API errors. Mount once in a top-level component (e.g., MainLayout).
 */
export function useApiErrorToast() {
  const { addToast } = useToast();

  useEffect(() => {
    const unsubscribe = onApiError((message, status) => {
      // Choose toast type based on HTTP status
      if (status && status >= 500) {
        addToast("error", message, 8000);
      } else if (status === 409) {
        addToast("warning", message, 6000);
      } else if (status === 503) {
        addToast("error", "Service temporarily unavailable. Please try again.", 8000);
      } else {
        addToast("error", message, 5000);
      }
    });

    return unsubscribe;
  }, [addToast]);
}
