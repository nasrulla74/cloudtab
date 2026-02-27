import { useEffect, useState, useCallback } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import {
  getServer,
  testConnection,
  fetchSystemInfo,
  installDeps,
  deleteServer,
  type Server,
} from "../api/servers";
import { listInstances, type OdooInstance } from "../api/instances";
import { formatBytes, formatDate, statusDot, statusColor } from "../lib/utils";
import TaskProgress from "../components/shared/TaskProgress";

export default function ServerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [server, setServer] = useState<Server | null>(null);
  const [instances, setInstances] = useState<OdooInstance[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [taskLabel, setTaskLabel] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);

  const isTaskActive = activeTaskId !== null;

  const loadData = useCallback(async () => {
    if (!id) return;
    try {
      const [s, inst] = await Promise.all([
        getServer(parseInt(id)),
        listInstances(parseInt(id)),
      ]);
      setServer(s);
      setInstances(inst);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleTestConnection = async () => {
    if (!server || isTaskActive) return;
    setActionError(null);
    try {
      const t = await testConnection(server.id);
      setTaskLabel("Test Connection");
      setActiveTaskId(t.task_id);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Failed to start connection test");
    }
  };

  const handleSystemInfo = async () => {
    if (!server || isTaskActive) return;
    setActionError(null);
    try {
      const t = await fetchSystemInfo(server.id);
      setTaskLabel("System Info");
      setActiveTaskId(t.task_id);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Failed to start system info fetch");
    }
  };

  const handleInstallDeps = async () => {
    if (!server || isTaskActive) return;
    setActionError(null);
    try {
      const t = await installDeps(server.id);
      setTaskLabel("Install Dependencies");
      setActiveTaskId(t.task_id);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Failed to start installation");
    }
  };

  const handleDelete = async () => {
    if (!server || !confirm("Delete this server and all its instances?")) return;
    try {
      await deleteServer(server.id);
      navigate("/servers");
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Failed to delete server");
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (!server) {
    return <div className="text-center py-12 text-gray-500">Server not found</div>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Link to="/servers" className="text-gray-400 hover:text-gray-600">←</Link>
          <span className={`inline-block w-3 h-3 rounded-full ${statusDot(server.status)}`} />
          <h2 className="text-2xl font-bold text-gray-900">{server.name}</h2>
          <span className={`text-sm ${statusColor(server.status)}`}>{server.status}</span>
        </div>
        <button onClick={handleDelete} className="text-sm text-red-600 hover:text-red-800">
          Delete Server
        </button>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-2 mb-4">
        <button
          onClick={handleTestConnection}
          disabled={isTaskActive}
          className="px-3 py-1.5 text-sm bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Test Connection
        </button>
        <button
          onClick={handleSystemInfo}
          disabled={isTaskActive}
          className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Refresh System Info
        </button>
        <button
          onClick={handleInstallDeps}
          disabled={isTaskActive}
          className="px-3 py-1.5 text-sm bg-purple-600 text-white rounded-md hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Install Docker/Nginx/Certbot
        </button>
      </div>

      {actionError && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-600">
          {actionError}
        </div>
      )}

      <TaskProgress
        taskId={activeTaskId}
        onComplete={() => { setActiveTaskId(null); loadData(); }}
        label={taskLabel}
      />

      {/* Server Info */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6 mb-8">
        <div className="bg-white rounded-lg shadow p-5">
          <h3 className="text-sm font-semibold text-gray-500 uppercase mb-3">Connection</h3>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between"><dt className="text-gray-500">Host</dt><dd>{server.host}:{server.port}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">SSH User</dt><dd>{server.ssh_user}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Last Connected</dt><dd>{formatDate(server.last_connected_at)}</dd></div>
          </dl>
        </div>
        <div className="bg-white rounded-lg shadow p-5">
          <h3 className="text-sm font-semibold text-gray-500 uppercase mb-3">System</h3>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between"><dt className="text-gray-500">OS</dt><dd>{server.os_version || "—"}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">CPU Cores</dt><dd>{server.cpu_cores ?? "—"}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">RAM</dt><dd>{formatBytes(server.ram_total_bytes)}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Disk</dt><dd>{formatBytes(server.disk_total_bytes)}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Docker</dt><dd>{server.docker_version || "Not installed"}</dd></div>
          </dl>
        </div>
      </div>

      {/* Instances */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">Odoo Instances</h3>
        <Link
          to={`/servers/${server.id}/deploy`}
          className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          Deploy Instance
        </Link>
      </div>

      {instances.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-6 text-center text-gray-500">
          No Odoo instances on this server yet.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {instances.map((inst) => (
            <Link
              key={inst.id}
              to={`/instances/${inst.id}`}
              className="bg-white rounded-lg shadow p-4 hover:shadow-md transition-shadow"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className={`inline-block w-2.5 h-2.5 rounded-full ${statusDot(inst.status)}`} />
                  <span className="font-medium">{inst.name}</span>
                </div>
                <span className="text-xs bg-gray-100 px-2 py-0.5 rounded">Odoo {inst.odoo_version}</span>
              </div>
              <div className="text-sm text-gray-500 flex items-center justify-between">
                <span>Port {inst.host_port}</span>
                <span className={statusColor(inst.status)}>{inst.status}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
