import { Link } from "react-router-dom";
import type { OdooInstance } from "../api/instances";

interface InstanceCardProps {
  instance: OdooInstance & { server_name?: string };
}

export default function InstanceCard({ instance }: InstanceCardProps) {
  const status = instance.status || "unknown";

  return (
    <div className="bg-white rounded-lg border border-gray-200 hover:shadow-md transition-shadow p-4">
      <h3 className="font-semibold mb-2">{instance.name || "Unnamed Instance"}</h3>
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm text-gray-600">
          Server: {instance.server_name || "Unknown"}
        </div>
        <div
          className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs ${
            status === "running" ? "bg-green-100 text-green-800" :
            status === "stopped" ? "bg-gray-100 text-gray-800" :
            status === "deploying" ? "bg-blue-100 text-blue-800" :
            "bg-yellow-100 text-yellow-800"
          }`}
        >
          {status}
        </div>
      </div>
      <div className="text-sm text-gray-500 mb-2">
        Created: {new Date(instance.created_at || 0).toLocaleDateString()}
      </div>
      <div className="flex items-center gap-2">
        <Link
          to={`/instances/${instance.id}`}
          className="text-blue-600 hover:text-blue-800 text-sm"
        >
          Details
        </Link>
      </div>
    </div>
  );
}