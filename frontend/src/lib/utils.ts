export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let val = bytes;
  while (val >= 1024 && i < units.length - 1) {
    val /= 1024;
    i++;
  }
  return `${val.toFixed(1)} ${units[i]}`;
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleString();
}

export function statusColor(status: string): string {
  switch (status) {
    case "connected":
    case "running":
    case "active":
    case "success":
      return "text-green-600";
    case "failed":
    case "error":
      return "text-red-600";
    case "deploying":
    case "pending":
    case "running":
      return "text-yellow-600";
    case "stopped":
      return "text-gray-500";
    default:
      return "text-gray-400";
  }
}

export function statusDot(status: string): string {
  switch (status) {
    case "connected":
    case "running":
    case "active":
      return "bg-green-500";
    case "failed":
      return "bg-red-500";
    case "deploying":
    case "pending":
      return "bg-yellow-500";
    case "stopped":
      return "bg-gray-400";
    default:
      return "bg-gray-300";
  }
}
