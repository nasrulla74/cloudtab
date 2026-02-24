import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { listServers, createServer, generateSSHKey, type Server, type ServerCreate } from "../api/servers";
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
  const [generatingKey, setGeneratingKey] = useState(false);
  const [publicKey, setPublicKey] = useState("");
  const [copied, setCopied] = useState(false);

  const loadServers = useCallback(() => {
    listServers()
      .then(setServers)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadServers(); }, [loadServers]);

  const handleCloseModal = () => {
    setShowModal(false);
    setFormData({ name: "", host: "", port: 22, ssh_user: "root", ssh_key: "" });
    setPublicKey("");
    setError("");
    setCopied(false);
  };

  const handleGenerateKey = async () => {
    setGeneratingKey(true);
    setPublicKey("");
    try {
      const { private_key, public_key } = await generateSSHKey();
      setFormData((prev) => ({ ...prev, ssh_key: private_key }));
      setPublicKey(public_key);
    } catch {
      setError("Failed to generate SSH key.");
    } finally {
      setGeneratingKey(false);
    }
  };

  const handleCopyPublicKey = async () => {
    await navigator.clipboard.writeText(publicKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await createServer(formData);
      handleCloseModal();
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

      <Modal open={showModal} onClose={handleCloseModal} title="Add Server">
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

          {/* SSH Private Key */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-sm font-medium text-gray-700">SSH Private Key</label>
              <button
                type="button"
                onClick={handleGenerateKey}
                disabled={generatingKey}
                className="text-xs text-blue-600 hover:text-blue-800 disabled:opacity-50 flex items-center gap-1"
              >
                {generatingKey ? (
                  <>
                    <span className="animate-spin inline-block w-3 h-3 border border-blue-600 border-t-transparent rounded-full" />
                    Generating...
                  </>
                ) : (
                  "⚡ Generate SSH Key"
                )}
              </button>
            </div>
            <textarea
              value={formData.ssh_key}
              onChange={(e) => setFormData({ ...formData, ssh_key: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm font-mono"
              rows={5}
              placeholder="-----BEGIN RSA PRIVATE KEY-----&#10;Paste your private key here, or click Generate SSH Key above"
              required
            />
          </div>

          {/* Public Key Display */}
          {publicKey && (
            <div className="rounded-md border border-green-200 bg-green-50 p-3 space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold text-green-800">
                  📋 Add this public key to your server:
                </p>
                <button
                  type="button"
                  onClick={handleCopyPublicKey}
                  className="text-xs px-2 py-1 bg-green-600 text-white rounded hover:bg-green-700"
                >
                  {copied ? "Copied!" : "Copy"}
                </button>
              </div>
              <code className="block text-xs text-green-900 break-all font-mono leading-relaxed">
                {publicKey}
              </code>
              <p className="text-xs text-green-700">
                Run on your server:{" "}
                <code className="bg-green-100 px-1 rounded">
                  echo '{publicKey}' &gt;&gt; ~/.ssh/authorized_keys
                </code>
              </p>
            </div>
          )}

          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={handleCloseModal}
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
