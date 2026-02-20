import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listServers, type Server } from "../api/servers";
import { statusDot } from "../lib/utils";

export default function DashboardPage() {
  const [servers, setServers] = useState<Server[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listServers()
      .then(setServers)
      .finally(() => setLoading(false));
  }, []);

  const connectedCount = servers.filter((s) => s.status === "connected").length;

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Dashboard</h2>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div className="bg-white rounded-lg shadow p-6">
              <p className="text-sm text-gray-500">Total Servers</p>
              <p className="text-3xl font-bold text-gray-900 mt-1">{servers.length}</p>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <p className="text-sm text-gray-500">Connected</p>
              <p className="text-3xl font-bold text-green-600 mt-1">{connectedCount}</p>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <p className="text-sm text-gray-500">Docker Ready</p>
              <p className="text-3xl font-bold text-gray-900 mt-1">
                {servers.filter((s) => s.docker_version).length}
              </p>
            </div>
          </div>

          <h3 className="text-lg font-semibold text-gray-900 mb-4">Servers</h3>
          {servers.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-6 text-center text-gray-500">
              No servers yet.{" "}
              <Link to="/servers" className="text-blue-600 hover:underline">
                Add your first server
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {servers.map((server) => (
                <Link
                  key={server.id}
                  to={`/servers/${server.id}`}
                  className="bg-white rounded-lg shadow p-4 hover:shadow-md transition-shadow"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`inline-block w-2.5 h-2.5 rounded-full ${statusDot(server.status)}`} />
                    <span className="font-medium text-gray-900">{server.name}</span>
                  </div>
                  <p className="text-sm text-gray-500">{server.host}:{server.port}</p>
                  {server.os_version && (
                    <p className="text-xs text-gray-400 mt-1">{server.os_version}</p>
                  )}
                </Link>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
