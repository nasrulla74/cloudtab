import { useEffect, useState, useCallback, createContext, useContext } from "react";

type ToastType = "success" | "error" | "warning" | "info";

interface ToastMessage {
  id: string;
  type: ToastType;
  message: string;
  duration?: number;
}

interface ToastContextValue {
  addToast: (type: ToastType, message: string, duration?: number) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
}

function ToastItem({ toast, onRemove }: { toast: ToastMessage; onRemove: (id: string) => void }) {
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setExiting(true);
      setTimeout(() => onRemove(toast.id), 300);
    }, toast.duration || 5000);
    return () => clearTimeout(timer);
  }, [toast, onRemove]);

  const colors: Record<ToastType, string> = {
    success: "bg-green-50 border-green-400 text-green-800",
    error: "bg-red-50 border-red-400 text-red-800",
    warning: "bg-yellow-50 border-yellow-400 text-yellow-800",
    info: "bg-blue-50 border-blue-400 text-blue-800",
  };

  const icons: Record<ToastType, string> = {
    success: "\u2713",
    error: "\u2717",
    warning: "\u26A0",
    info: "\u2139",
  };

  return (
    <div
      className={`flex items-start gap-3 px-4 py-3 rounded-lg border shadow-lg max-w-md transition-all duration-300 ${colors[toast.type]} ${exiting ? "opacity-0 translate-x-4" : "opacity-100 translate-x-0"}`}
    >
      <span className="text-lg leading-none mt-0.5">{icons[toast.type]}</span>
      <p className="text-sm flex-1">{toast.message}</p>
      <button
        onClick={() => {
          setExiting(true);
          setTimeout(() => onRemove(toast.id), 300);
        }}
        className="text-current opacity-50 hover:opacity-100 text-sm leading-none"
      >
        &times;
      </button>
    </div>
  );
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = useCallback((type: ToastType, message: string, duration?: number) => {
    const id = Math.random().toString(36).slice(2, 10);
    setToasts((prev) => [...prev, { id, type, message, duration }]);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      {/* Toast container — fixed top-right */}
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} onRemove={removeToast} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}
