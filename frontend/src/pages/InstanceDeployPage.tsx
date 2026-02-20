import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { createInstance, type InstanceCreate } from "../api/instances";
import TaskProgress from "../components/shared/TaskProgress";

const ODOO_VERSIONS = ["18.0", "17.0", "16.0", "15.0", "14.0"];

export default function InstanceDeployPage() {
  const { id: serverId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [form, setForm] = useState<InstanceCreate>({
    name: "",
    odoo_version: "17.0",
    edition: "community",
    host_port: 8069,
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [deployTaskId, setDeployTaskId] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!serverId) return;
    setError("");
    setSubmitting(true);
    try {
      const result = await createInstance(parseInt(serverId), form);
      setDeployTaskId(result.task_id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Deployment failed";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-xl">
      <div className="flex items-center gap-3 mb-6">
        <Link to={`/servers/${serverId}`} className="text-gray-400 hover:text-gray-600">←</Link>
        <h2 className="text-2xl font-bold text-gray-900">Deploy Odoo Instance</h2>
      </div>

      {deployTaskId ? (
        <div className="space-y-4">
          <TaskProgress
            taskId={deployTaskId}
            label="Deploying Odoo"
            onComplete={() => navigate(`/servers/${serverId}`)}
          />
          <p className="text-sm text-gray-500">
            This may take a few minutes while Docker images are pulled...
          </p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Instance Name</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
              placeholder="my-client-odoo"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Odoo Version</label>
              <select
                value={form.odoo_version}
                onChange={(e) => setForm({ ...form, odoo_version: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
              >
                {ODOO_VERSIONS.map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Edition</label>
              <select
                value={form.edition}
                onChange={(e) => setForm({ ...form, edition: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
              >
                <option value="community">Community</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Host Port</label>
            <input
              type="number"
              value={form.host_port}
              onChange={(e) => setForm({ ...form, host_port: parseInt(e.target.value) })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
              min={1024}
              max={65535}
              required
            />
            <p className="text-xs text-gray-400 mt-1">The port Odoo will be accessible on (e.g. 8069, 8070, 8071...)</p>
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="flex justify-end gap-3 pt-2">
            <Link to={`/servers/${serverId}`} className="px-4 py-2 text-sm text-gray-700 border rounded-md hover:bg-gray-50">
              Cancel
            </Link>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {submitting ? "Starting..." : "Deploy"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
