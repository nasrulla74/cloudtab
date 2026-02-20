import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { listServers, createServer, type Server, type ServerCreate } from "../api/servers";
import { statusDot, formatDate } from "../lib/utils";
import Modal from "../components/shared/Modal";

export default function ServersPage() {
  const [servers, setServers] = useState<Server[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [formData, setFormData] = useState<ServerCreate>({
    name: "",
    host: "",
    port: 22,
    ssh_user: "root",
    ssh_key: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const loadServers = useCallback(() => {
    listServers()
      .then(setServers)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadServers(); }, [loadServers]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await createServer(formData);
      setShowModal(false);
      setFormData({ name: "", host: "", port: 22, ssh_user: "root", ssh_key: "" });
      loadServers();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create server";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Servers</h2>
        <button
          onClick={() => setShowModal(true)}
          className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 text-sm transition-colors"
        >
          Add Server
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        </div>
      ) : servers.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
          No servers connected yet. Click "Add Server" to get started.
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Host</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">OS</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Docker</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Last Connected</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {servers.map((s) => (
                <tr key={s.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4">
                    <span className={`inline-block w-2.5 h-2.5 rounded-full ${statusDot(s.status)}`} />
                  </td>
                  <td className="px-6 py-4">
                    <Link to={`/servers/${s.id}`} className="text-blue-600 hover:underline font-medium">
                      {s.name}
                    </Link>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">{s.host}:{s.port}</td>
                  <td className="px-6 py-4 text-sm text-gray-500">{s.os_version || "—"}</td>
                  <td className="px-6 py-4 text-sm text-gray-500">{s.docker_version || "—"}</td>
                  <td className="px-6 py-4 text-sm text-gray-500">{formatDate(s.last_connected_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={showModal} onClose={() => setShowModal(false)} title="Add Server">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
              placeholder="My Server"
              required
            />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Host / IP</label>
              <input
                type="text"
                value={formData.host}
                onChange={(e) => setFormData({ ...formData, host: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                placeholder="192.168.1.100"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Port</label>
              <input
                type="number"
                value={formData.port}
                onChange={(e) => setFormData({ ...formData, port: parseInt(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                required
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">SSH User</label>
            <input
              type="text"
              value={formData.ssh_user}
              onChange={(e) => setFormData({ ...formData, ssh_user: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">SSH Private Key</label>
            <textarea
              value={formData.ssh_key}
              onChange={(e) => setFormData({ ...formData, ssh_key: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm font-mono"
              rows={6}
              placeholder="-----BEGIN OPENSSH PRIVATE KEY-----&#10;..."
              required
            />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={() => setShowModal(false)}
              className="px-4 py-2 text-sm text-gray-700 border rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {submitting ? "Adding..." : "Add Server"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
