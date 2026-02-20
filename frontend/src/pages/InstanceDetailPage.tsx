import { useEffect, useState, useCallback } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import {
  getInstance,
  startInstance,
  stopInstance,
  restartInstance,
  deleteInstance,
  getInstanceLogs,
  type OdooInstance,
} from "../api/instances";
import { listDomains, createDomain, issueSSL, deleteDomain, type Domain } from "../api/domains";
import {
  listSchedules,
  createSchedule,
  deleteSchedule,
  triggerBackup,
  listBackupRecords,
  restoreBackup,
  type BackupSchedule,
  type BackupRecord,
} from "../api/backups";
import { getGitRepo, linkGitRepo, deleteGitRepo, deployModules, type GitRepo } from "../api/git";
import { statusDot, statusColor, formatDate, formatBytes } from "../lib/utils";
import TaskProgress from "../components/shared/TaskProgress";
import Modal from "../components/shared/Modal";

export default function InstanceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [instance, setInstance] = useState<OdooInstance | null>(null);
  const [domains, setDomains] = useState<Domain[]>([]);
  const [schedules, setSchedules] = useState<BackupSchedule[]>([]);
  const [records, setRecords] = useState<BackupRecord[]>([]);
  const [gitRepo, setGitRepo] = useState<GitRepo | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [taskLabel, setTaskLabel] = useState("");
  const [logs, setLogs] = useState<string | null>(null);

  // Modal states
  const [showDomainModal, setShowDomainModal] = useState(false);
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [showGitModal, setShowGitModal] = useState(false);

  // Form states
  const [domainName, setDomainName] = useState("");
  const [scheduleFrequency, setScheduleFrequency] = useState("daily");
  const [scheduleRetention, setScheduleRetention] = useState(30);
  const [scheduleStorageType, setScheduleStorageType] = useState("local");
  const [scheduleS3Bucket, setScheduleS3Bucket] = useState("");
  const [scheduleS3Prefix, setScheduleS3Prefix] = useState("");
  const [gitUrl, setGitUrl] = useState("");
  const [gitBranch, setGitBranch] = useState("main");
  const [gitDeployKey, setGitDeployKey] = useState("");

  // Active tab
  const [activeTab, setActiveTab] = useState<"domains" | "backups" | "git" | "logs">("domains");

  const loadData = useCallback(async () => {
    if (!id) return;
    try {
      const instanceId = parseInt(id);
      const [inst, doms, scheds, recs, repo] = await Promise.all([
        getInstance(instanceId),
        listDomains(instanceId),
        listSchedules(instanceId),
        listBackupRecords(instanceId),
        getGitRepo(instanceId),
      ]);
      setInstance(inst);
      setDomains(doms);
      setSchedules(scheds);
      setRecords(recs);
      setGitRepo(repo);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const runAction = async (action: () => Promise<{ task_id: string }>, label: string) => {
    const t = await action();
    setTaskLabel(label);
    setActiveTaskId(t.task_id);
  };

  const handleGetLogs = async () => {
    if (!instance) return;
    setLogs("Loading...");
    setActiveTab("logs");
    const t = await getInstanceLogs(instance.id);
    setTaskLabel("Fetching Logs");
    setActiveTaskId(t.task_id);
  };

  const handleDeleteInstance = async () => {
    if (!instance) return;
    if (
      !confirm(
        `Are you sure you want to delete "${instance.name}"? This will stop and remove all containers and data from the server. This action cannot be undone.`
      )
    )
      return;
    const t = await deleteInstance(instance.id);
    setTaskLabel("Destroying instance");
    setActiveTaskId(t.task_id);
  };

  // --- Domain handlers ---
  const handleAddDomain = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!instance || !domainName) return;
    const t = await createDomain(instance.id, domainName);
    setShowDomainModal(false);
    setDomainName("");
    setTaskLabel("Setting up domain");
    setActiveTaskId(t.task_id);
  };

  const handleIssueSSL = async (domainId: number) => {
    const t = await issueSSL(domainId);
    setTaskLabel("Issuing SSL");
    setActiveTaskId(t.task_id);
  };

  const handleDeleteDomain = async (domainId: number) => {
    if (!confirm("Delete this domain?")) return;
    await deleteDomain(domainId);
    loadData();
  };

  // --- Backup handlers ---
  const handleCreateSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!instance) return;
    await createSchedule(instance.id, {
      frequency: scheduleFrequency,
      retention_days: scheduleRetention,
      storage_type: scheduleStorageType,
      s3_bucket: scheduleStorageType === "s3" ? scheduleS3Bucket : undefined,
      s3_prefix: scheduleStorageType === "s3" ? scheduleS3Prefix : undefined,
    });
    setShowScheduleModal(false);
    setScheduleFrequency("daily");
    setScheduleRetention(30);
    setScheduleStorageType("local");
    setScheduleS3Bucket("");
    setScheduleS3Prefix("");
    loadData();
  };

  const handleDeleteSchedule = async (scheduleId: number) => {
    if (!confirm("Delete this backup schedule?")) return;
    await deleteSchedule(scheduleId);
    loadData();
  };

  const handleTriggerBackup = async () => {
    if (!instance) return;
    const t = await triggerBackup(instance.id);
    setTaskLabel("Running backup");
    setActiveTaskId(t.task_id);
  };

  const handleRestoreBackup = async (recordId: number) => {
    if (
      !confirm(
        "Are you sure you want to restore from this backup? " +
          "The instance will be stopped during restore and all current data will be replaced."
      )
    )
      return;
    const t = await restoreBackup(recordId);
    setTaskLabel("Restoring backup");
    setActiveTaskId(t.task_id);
  };

  // --- Git handlers ---
  const handleLinkGitRepo = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!instance || !gitUrl) return;
    await linkGitRepo(instance.id, {
      repo_url: gitUrl,
      branch: gitBranch,
      deploy_key: gitDeployKey || undefined,
    });
    setShowGitModal(false);
    setGitUrl("");
    setGitBranch("main");
    setGitDeployKey("");
    loadData();
  };

  const handleUnlinkGitRepo = async () => {
    if (!gitRepo || !confirm("Unlink this git repository?")) return;
    await deleteGitRepo(gitRepo.id);
    setGitRepo(null);
  };

  const handleDeployModules = async () => {
    if (!gitRepo) return;
    const t = await deployModules(gitRepo.id);
    setTaskLabel("Deploying modules");
    setActiveTaskId(t.task_id);
  };

  // --- Task complete ---
  const handleTaskComplete = useCallback(
    (task: { status: string; result: string | null }) => {
      setActiveTaskId(null);
      if (task.result) {
        try {
          const parsed = JSON.parse(task.result);
          // If instance was destroyed, navigate back to server page
          if (parsed.status === "destroyed" && instance) {
            navigate(`/servers/${instance.server_id}`);
            return;
          }
          if (parsed.logs) {
            setLogs(parsed.logs);
            return;
          }
        } catch {
          /* not log data */
        }
      }
      loadData();
    },
    [loadData, instance, navigate]
  );

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (!instance) {
    return <div className="text-center py-12 text-gray-500">Instance not found</div>;
  }

  const tabs = [
    { key: "domains" as const, label: "Domains", count: domains.length },
    { key: "backups" as const, label: "Backups", count: records.length },
    { key: "git" as const, label: "Git Repo", count: gitRepo ? 1 : 0 },
    { key: "logs" as const, label: "Logs", count: null },
  ];

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Link
            to={`/servers/${instance.server_id}`}
            className="text-gray-400 hover:text-gray-600"
          >
            &larr;
          </Link>
          <span className={`inline-block w-3 h-3 rounded-full ${statusDot(instance.status)}`} />
          <h2 className="text-2xl font-bold text-gray-900">{instance.name}</h2>
          <span className="text-xs bg-gray-100 px-2 py-0.5 rounded">
            Odoo {instance.odoo_version}
          </span>
          <span className={`text-sm ${statusColor(instance.status)}`}>{instance.status}</span>
        </div>
      </div>

      {/* Actions bar */}
      <div className="flex flex-wrap gap-2 mb-6">
        {instance.status === "stopped" && (
          <button
            onClick={() => runAction(() => startInstance(instance.id), "Starting")}
            className="px-3 py-1.5 text-sm bg-green-600 text-white rounded-md hover:bg-green-700"
          >
            Start
          </button>
        )}
        {instance.status === "running" && (
          <>
            <button
              onClick={() => runAction(() => stopInstance(instance.id), "Stopping")}
              className="px-3 py-1.5 text-sm bg-yellow-600 text-white rounded-md hover:bg-yellow-700"
            >
              Stop
            </button>
            <button
              onClick={() => runAction(() => restartInstance(instance.id), "Restarting")}
              className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              Restart
            </button>
          </>
        )}
        <button
          onClick={handleGetLogs}
          className="px-3 py-1.5 text-sm bg-gray-600 text-white rounded-md hover:bg-gray-700"
        >
          View Logs
        </button>
        <button
          onClick={handleDeleteInstance}
          className="px-3 py-1.5 text-sm bg-red-600 text-white rounded-md hover:bg-red-700 ml-auto"
        >
          Delete Instance
        </button>
      </div>

      <TaskProgress taskId={activeTaskId} onComplete={handleTaskComplete} label={taskLabel} />

      {/* Instance Info Card */}
      <div className="bg-white rounded-lg shadow p-5 mt-4 mb-6">
        <h3 className="text-sm font-semibold text-gray-500 uppercase mb-3">Instance Details</h3>
        <dl className="grid grid-cols-2 md:grid-cols-4 gap-y-2 gap-x-6 text-sm">
          <div>
            <dt className="text-gray-500">Container</dt>
            <dd className="font-mono text-xs mt-0.5">{instance.container_name}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Edition</dt>
            <dd className="capitalize mt-0.5">{instance.edition}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Port</dt>
            <dd className="mt-0.5">{instance.host_port}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Created</dt>
            <dd className="mt-0.5">{formatDate(instance.created_at)}</dd>
          </div>
        </dl>
      </div>

      {/* Tab navigation */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-6">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.label}
              {tab.count !== null && (
                <span className="ml-1.5 px-1.5 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600">
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* === DOMAINS TAB === */}
      {activeTab === "domains" && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Domains</h3>
            <button
              onClick={() => setShowDomainModal(true)}
              className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              Add Domain
            </button>
          </div>
          {domains.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500 text-sm">
              <p className="mb-2">No domains configured.</p>
              <p className="text-xs text-gray-400">
                Add a domain to set up Nginx reverse proxy and SSL for this instance.
              </p>
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                      Domain
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                      Status
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                      SSL
                    </th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {domains.map((d) => (
                    <tr key={d.id}>
                      <td className="px-4 py-3 text-sm font-medium">{d.domain_name}</td>
                      <td className="px-4 py-3 text-sm">
                        <span className={statusColor(d.status)}>{d.status}</span>
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {d.ssl_status === "active" ? (
                          <span className="text-green-600 font-medium">Active</span>
                        ) : (
                          <span className="text-gray-400">{d.ssl_status}</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right space-x-2">
                        {d.ssl_status !== "active" && d.status === "active" && (
                          <button
                            onClick={() => handleIssueSSL(d.id)}
                            className="text-xs text-blue-600 hover:underline"
                          >
                            Issue SSL
                          </button>
                        )}
                        <button
                          onClick={() => handleDeleteDomain(d.id)}
                          className="text-xs text-red-600 hover:underline"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* === BACKUPS TAB === */}
      {activeTab === "backups" && (
        <div>
          {/* Schedules section */}
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Backup Schedules</h3>
            <div className="flex gap-2">
              <button
                onClick={handleTriggerBackup}
                className="px-3 py-1.5 text-sm bg-green-600 text-white rounded-md hover:bg-green-700"
              >
                Backup Now
              </button>
              <button
                onClick={() => setShowScheduleModal(true)}
                className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                Add Schedule
              </button>
            </div>
          </div>

          {schedules.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-6 text-center text-gray-500 text-sm mb-6">
              <p className="mb-1">No backup schedules configured.</p>
              <p className="text-xs text-gray-400">
                Create a schedule for automated daily, weekly, or monthly backups.
              </p>
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow overflow-hidden mb-6">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                      Frequency
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                      Retention
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                      Storage
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                      Status
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                      Next Run
                    </th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {schedules.map((s) => (
                    <tr key={s.id}>
                      <td className="px-4 py-3 text-sm capitalize">{s.frequency}</td>
                      <td className="px-4 py-3 text-sm">{s.retention_days} days</td>
                      <td className="px-4 py-3 text-sm">
                        <span className="uppercase text-xs font-medium">{s.storage_type}</span>
                        {s.storage_type === "s3" && s.s3_bucket && (
                          <span className="text-xs text-gray-400 ml-1">({s.s3_bucket})</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {s.is_active ? (
                          <span className="text-green-600 font-medium">Active</span>
                        ) : (
                          <span className="text-gray-400">Paused</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500">
                        {formatDate(s.next_run_at)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => handleDeleteSchedule(s.id)}
                          className="text-xs text-red-600 hover:underline"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Backup records section */}
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Backup History</h3>
          {records.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-6 text-center text-gray-500 text-sm">
              No backups have been run yet.
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                      Date
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                      Status
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                      Size
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                      Storage
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                      Duration
                    </th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {records.map((r) => {
                    let duration = "";
                    if (r.started_at && r.completed_at) {
                      const secs = Math.round(
                        (new Date(r.completed_at).getTime() -
                          new Date(r.started_at).getTime()) /
                          1000
                      );
                      duration =
                        secs < 60 ? `${secs}s` : `${Math.floor(secs / 60)}m ${secs % 60}s`;
                    }
                    return (
                      <tr key={r.id}>
                        <td className="px-4 py-3 text-sm">{formatDate(r.created_at)}</td>
                        <td className="px-4 py-3 text-sm">
                          <span className={statusColor(r.status)}>{r.status}</span>
                          {r.error_message && (
                            <span className="block text-xs text-red-500 mt-0.5 max-w-xs truncate">
                              {r.error_message}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm">{formatBytes(r.file_size_bytes)}</td>
                        <td className="px-4 py-3 text-sm">
                          <span className={`uppercase text-xs font-medium ${r.storage_type === "s3" ? "text-yellow-600" : "text-gray-600"}`}>
                            {r.storage_type}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-500">{duration || "\u2014"}</td>
                        <td className="px-4 py-3 text-right">
                          {r.status === "success" && r.file_path && (
                            <button
                              onClick={() => handleRestoreBackup(r.id)}
                              className="text-xs text-orange-600 hover:underline font-medium"
                            >
                              Restore
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* === GIT REPO TAB === */}
      {activeTab === "git" && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Git Repository</h3>
            {!gitRepo && (
              <button
                onClick={() => setShowGitModal(true)}
                className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                Link Repository
              </button>
            )}
          </div>

          {!gitRepo ? (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500 text-sm">
              <p className="mb-2">No git repository linked.</p>
              <p className="text-xs text-gray-400">
                Link a git repository to deploy custom Odoo modules to this instance.
              </p>
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow p-5">
              <dl className="grid grid-cols-2 gap-y-3 gap-x-6 text-sm">
                <div>
                  <dt className="text-gray-500 text-xs uppercase font-medium">Repository URL</dt>
                  <dd className="font-mono text-xs mt-1 break-all">{gitRepo.repo_url}</dd>
                </div>
                <div>
                  <dt className="text-gray-500 text-xs uppercase font-medium">Branch</dt>
                  <dd className="mt-1">{gitRepo.branch}</dd>
                </div>
                <div>
                  <dt className="text-gray-500 text-xs uppercase font-medium">Last Deployed</dt>
                  <dd className="mt-1">{formatDate(gitRepo.last_deployed_at)}</dd>
                </div>
                <div>
                  <dt className="text-gray-500 text-xs uppercase font-medium">Last Commit</dt>
                  <dd className="font-mono text-xs mt-1">
                    {gitRepo.last_commit_sha
                      ? gitRepo.last_commit_sha.substring(0, 8)
                      : "\u2014"}
                  </dd>
                </div>
              </dl>
              <div className="flex gap-2 mt-5 pt-4 border-t border-gray-100">
                <button
                  onClick={handleDeployModules}
                  className="px-3 py-1.5 text-sm bg-green-600 text-white rounded-md hover:bg-green-700"
                >
                  Deploy Modules
                </button>
                <button
                  onClick={handleUnlinkGitRepo}
                  className="px-3 py-1.5 text-sm bg-red-600 text-white rounded-md hover:bg-red-700"
                >
                  Unlink Repo
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* === LOGS TAB === */}
      {activeTab === "logs" && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Container Logs</h3>
            <button
              onClick={handleGetLogs}
              className="px-3 py-1.5 text-sm bg-gray-600 text-white rounded-md hover:bg-gray-700"
            >
              Refresh
            </button>
          </div>
          {logs ? (
            <pre className="bg-gray-900 text-green-400 p-4 rounded-lg text-xs overflow-x-auto max-h-[600px] overflow-y-auto whitespace-pre-wrap">
              {logs}
            </pre>
          ) : (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500 text-sm">
              Click "View Logs" or "Refresh" to fetch container logs.
            </div>
          )}
        </div>
      )}

      {/* === MODALS === */}

      {/* Add Domain Modal */}
      <Modal open={showDomainModal} onClose={() => setShowDomainModal(false)} title="Add Domain">
        <form onSubmit={handleAddDomain} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Domain Name</label>
            <input
              type="text"
              value={domainName}
              onChange={(e) => setDomainName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
              placeholder="odoo.example.com"
              required
            />
            <p className="text-xs text-gray-400 mt-1">
              Make sure this domain's DNS A record points to your server.
            </p>
          </div>
          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={() => setShowDomainModal(false)}
              className="px-4 py-2 text-sm text-gray-700 border rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              Add Domain
            </button>
          </div>
        </form>
      </Modal>

      {/* Add Backup Schedule Modal */}
      <Modal
        open={showScheduleModal}
        onClose={() => setShowScheduleModal(false)}
        title="Add Backup Schedule"
      >
        <form onSubmit={handleCreateSchedule} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Frequency</label>
            <select
              value={scheduleFrequency}
              onChange={(e) => setScheduleFrequency(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Retention (days)
            </label>
            <input
              type="number"
              min={1}
              value={scheduleRetention}
              onChange={(e) => setScheduleRetention(parseInt(e.target.value) || 30)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            />
            <p className="text-xs text-gray-400 mt-1">
              Backups older than this will be automatically cleaned up.
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Storage</label>
            <select
              value={scheduleStorageType}
              onChange={(e) => setScheduleStorageType(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              <option value="local">Local (on server)</option>
              <option value="s3">S3 / S3-compatible</option>
            </select>
          </div>
          {scheduleStorageType === "s3" && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  S3 Bucket
                </label>
                <input
                  type="text"
                  value={scheduleS3Bucket}
                  onChange={(e) => setScheduleS3Bucket(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                  placeholder="my-cloudtab-backups"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  S3 Prefix (optional)
                </label>
                <input
                  type="text"
                  value={scheduleS3Prefix}
                  onChange={(e) => setScheduleS3Prefix(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                  placeholder="backups/production"
                />
                <p className="text-xs text-gray-400 mt-1">
                  Object key prefix in the bucket. Leave empty to store at the bucket root.
                </p>
              </div>
            </>
          )}
          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={() => setShowScheduleModal(false)}
              className="px-4 py-2 text-sm text-gray-700 border rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              Create Schedule
            </button>
          </div>
        </form>
      </Modal>

      {/* Link Git Repo Modal */}
      <Modal
        open={showGitModal}
        onClose={() => setShowGitModal(false)}
        title="Link Git Repository"
      >
        <form onSubmit={handleLinkGitRepo} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Repository URL</label>
            <input
              type="text"
              value={gitUrl}
              onChange={(e) => setGitUrl(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
              placeholder="git@github.com:org/odoo-modules.git"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Branch</label>
            <input
              type="text"
              value={gitBranch}
              onChange={(e) => setGitBranch(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
              placeholder="main"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Deploy Key (optional)
            </label>
            <textarea
              value={gitDeployKey}
              onChange={(e) => setGitDeployKey(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm font-mono"
              placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"
              rows={4}
            />
            <p className="text-xs text-gray-400 mt-1">
              SSH private key for accessing private repositories. Stored encrypted.
            </p>
          </div>
          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={() => setShowGitModal(false)}
              className="px-4 py-2 text-sm text-gray-700 border rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              Link Repository
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
