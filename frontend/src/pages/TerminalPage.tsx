import { useEffect, useState } from "react";
import { listServers, type Server } from "../api/servers";

export default function TerminalPage() {
  const [servers, setServers] = useState<Server[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listServers()
      .then(setServers)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900" />
      </div>
    );
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Terminal</h1>
      <div className="grid gap-4 mb-6">
        <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
          <div className="text-sm text-gray-600 mb-2">
            Select a server to open terminal
          </div>
        </div>
      </div>

      {servers.length === 0 ? (
        <div className="text-center py-12">
          <div className="text-gray-400 mb-4">
            <svg width={64} height={64} fill="none" xmlns="http://www.w3.org/2000/svg">
              <path
                d="M6.364 12.727l12.121 12.122L30.303 12.727l12.122 12.122 12.122-12.122 6.061 6.061L36.364 25.303l12.122 12.122-6.061 6.061-12.122-12.122-12.122 12.122-6.061-6.061 12.122-12.122-12.122-12.122L6.363 12.727z"
                fill="#6B7280"
              />
            </svg>
          </div>
          <p className="text-gray-500">No servers available</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {servers.map((server) => (
            <div
              key={server.id}
              className="bg-gray-50 rounded-lg p-4 border border-gray-200 hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => {
                console.log("Open terminal for server:", server.id);
              }}
            >
              <h3 className="font-semibold mb-2">{server.name}</h3>
              <p className="text-sm text-gray-600">{server.host}:{server.port}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}