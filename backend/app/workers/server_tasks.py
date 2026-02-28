import logging
from datetime import UTC, datetime

import paramiko
from celery.exceptions import SoftTimeLimitExceeded

from app.core.database_sync import get_sync_db
from app.core.encryption import decrypt_value
from app.models.server import Server
from app.services.ssh_service import SSHService
from app.workers.celery_app import celery_app
from app.workers.utils import SSH_RETRYABLE, TaskLogger, update_task_log

logger = logging.getLogger(__name__)

# Only retry on transient network errors — auth/key failures should not be retried.
_TEST_CONN_RETRYABLE = (
    ConnectionRefusedError,
    ConnectionResetError,
    TimeoutError,
    OSError,
)


def _get_ssh_service(server: Server) -> SSHService:
    """Create an SSHService from a Server model, decrypting the SSH key."""
    return SSHService(
        host=server.host,
        port=server.port,
        username=server.ssh_user,
        private_key_pem=decrypt_value(server.ssh_key_encrypted),
    )


def _friendly_ssh_error(exc: Exception) -> str:
    """Convert raw SSH/network exceptions into user-readable messages."""
    msg = str(exc).lower()
    if isinstance(exc, paramiko.AuthenticationException):
        return (
            "SSH authentication failed. "
            "Make sure the public key is added to ~/.ssh/authorized_keys on the server."
        )
    if "connection refused" in msg:
        return (
            "Connection refused. "
            "Check that SSH is running on the server and the port number is correct."
        )
    if "timed out" in msg or "timeout" in msg:
        return (
            "Connection timed out. "
            "The server may be unreachable or the port may be blocked by a firewall."
        )
    if (
        "name or service not known" in msg
        or "nodename nor servname" in msg
        or "no address associated" in msg
        or "getaddrinfo failed" in msg
    ):
        return "Hostname not found. Check the server hostname or IP address."
    if "no route to host" in msg or "network is unreachable" in msg:
        return (
            "Cannot reach the server. "
            "Check the IP address and ensure the firewall allows SSH traffic."
        )
    if "unable to parse private key" in msg or "invalid key" in msg or "not a valid" in msg:
        return (
            "Invalid SSH private key. "
            "Regenerate the key pair and re-add the public key to the server."
        )
    if "host key" in msg:
        return "Host key verification failed. The server's host key may have changed."
    return str(exc)


@celery_app.task(
    bind=True,
    name="server.test_connection",
    time_limit=120,
    soft_time_limit=90,
    autoretry_for=_TEST_CONN_RETRYABLE,
    retry_backoff=5,
    retry_backoff_max=15,
    retry_kwargs={"max_retries": 1},
)
def test_server_connection(self, server_id: int) -> dict:
    """Test SSH connectivity to a server."""
    task_id = self.request.id
    tlog = TaskLogger(task_id, server_id=server_id)
    update_task_log(task_id, "running")

    db = get_sync_db()
    try:
        server = db.query(Server).filter(Server.id == server_id).first()
        if not server:
            result = {"error": "Server not found"}
            tlog.error("Server %d not found", server_id)
            update_task_log(task_id, "failed", result)
            return result

        try:
            tlog.info("Testing SSH connection to %s:%d", server.host, server.port)
            with _get_ssh_service(server) as ssh:
                stdout, _, exit_code = ssh.execute("echo ok")
                if exit_code == 0 and "ok" in stdout:
                    server.status = "connected"
                    server.last_connected_at = datetime.now(UTC)
                    db.commit()
                    result = {"status": "connected"}
                    tlog.info("Connection successful")
                    update_task_log(task_id, "success", result)
                    return result
                else:
                    server.status = "failed"
                    db.commit()
                    result = {"status": "failed", "error": f"Unexpected SSH response: {stdout!r}"}
                    tlog.warning("Unexpected SSH response: %s", stdout)
                    update_task_log(task_id, "failed", result)
                    return result
        except SoftTimeLimitExceeded:
            server.status = "failed"
            db.commit()
            result = {"status": "failed", "error": "Connection test timed out after 90 seconds. The server may be unresponsive."}
            tlog.error("Soft time limit exceeded during connection test")
            update_task_log(task_id, "failed", result)
            return result
        except Exception as e:
            server.status = "failed"
            db.commit()
            result = {"status": "failed", "error": _friendly_ssh_error(e)}
            tlog.error("SSH connection failed: %s", e)
            update_task_log(task_id, "failed", result)
            return result
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="server.get_system_info",
    autoretry_for=SSH_RETRYABLE,
    retry_backoff=15,
    retry_backoff_max=120,
    retry_kwargs={"max_retries": 2},
)
def get_system_info(self, server_id: int) -> dict:
    """Gather system information from a server via SSH."""
    task_id = self.request.id
    tlog = TaskLogger(task_id, server_id=server_id)
    update_task_log(task_id, "running")

    db = get_sync_db()
    try:
        server = db.query(Server).filter(Server.id == server_id).first()
        if not server:
            result = {"error": "Server not found"}
            tlog.error("Server %d not found", server_id)
            update_task_log(task_id, "failed", result)
            return result

        try:
            tlog.info("Gathering system info from %s", server.host)
            with _get_ssh_service(server) as ssh:
                info = {}

                # OS version
                stdout, _, _ = ssh.execute("cat /etc/os-release | grep PRETTY_NAME | cut -d'=' -f2 | tr -d '\"'")
                info["os_version"] = stdout or "Unknown"

                # CPU
                stdout, _, _ = ssh.execute("nproc")
                info["cpu_cores"] = int(stdout) if stdout.isdigit() else None

                stdout, _, _ = ssh.execute("lscpu | grep 'Model name' | sed 's/Model name:\\s*//'")
                info["cpu_model"] = stdout or None

                # RAM
                stdout, _, _ = ssh.execute("free -b | awk '/^Mem:/ {print $2}'")
                info["ram_total_bytes"] = int(stdout) if stdout.isdigit() else None

                stdout, _, _ = ssh.execute("free -b | awk '/^Mem:/ {print $3}'")
                info["ram_used_bytes"] = int(stdout) if stdout.isdigit() else None

                # Disk
                stdout, _, _ = ssh.execute("df -B1 / | awk 'NR==2 {print $2}'")
                info["disk_total_bytes"] = int(stdout) if stdout.isdigit() else None

                stdout, _, _ = ssh.execute("df -B1 / | awk 'NR==2 {print $3}'")
                info["disk_used_bytes"] = int(stdout) if stdout.isdigit() else None

                # Docker
                stdout, _, exit_code = ssh.execute("docker --version 2>/dev/null")
                if exit_code == 0 and stdout:
                    info["docker_version"] = stdout.split(",")[0].replace("Docker version ", "").strip()
                else:
                    info["docker_version"] = None

                # Uptime
                stdout, _, _ = ssh.execute("uptime -s")
                info["uptime"] = stdout or None

                # Update server cached info
                server.os_version = info.get("os_version")
                server.cpu_cores = info.get("cpu_cores")
                server.ram_total_bytes = info.get("ram_total_bytes")
                server.disk_total_bytes = info.get("disk_total_bytes")
                server.docker_version = info.get("docker_version")
                server.status = "connected"
                server.last_connected_at = datetime.now(UTC)
                db.commit()

                tlog.info("System info collected successfully")
                update_task_log(task_id, "success", info)
                return info

        except Exception as e:
            result = {"error": _friendly_ssh_error(e)}
            tlog.error("Failed to gather system info: %s", e)
            update_task_log(task_id, "failed", result)
            return result
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="server.install_deps",
    autoretry_for=SSH_RETRYABLE,
    retry_backoff=30,
    retry_backoff_max=300,
    retry_kwargs={"max_retries": 3},
)
def install_server_deps(self, server_id: int) -> dict:
    """Install Docker, Nginx, and Certbot on a remote server."""
    task_id = self.request.id
    tlog = TaskLogger(task_id, server_id=server_id)
    update_task_log(task_id, "running")

    db = get_sync_db()
    try:
        server = db.query(Server).filter(Server.id == server_id).first()
        if not server:
            result = {"error": "Server not found"}
            tlog.error("Server %d not found", server_id)
            update_task_log(task_id, "failed", result)
            return result

        try:
            tlog.info("Installing dependencies on %s", server.host)
            with _get_ssh_service(server) as ssh:
                results = {}

                # Install Docker
                tlog.info("Installing Docker")
                _, _, exit_code = ssh.execute(
                    "which docker > /dev/null 2>&1 || (curl -fsSL https://get.docker.com | sh)",
                    timeout=300,
                )
                results["docker_installed"] = exit_code == 0

                # Enable Docker service
                ssh.execute("systemctl enable --now docker", timeout=30)

                # Install Nginx
                tlog.info("Installing Nginx")
                _, _, exit_code = ssh.execute(
                    "which nginx > /dev/null 2>&1 || apt-get install -y nginx",
                    timeout=120,
                )
                results["nginx_installed"] = exit_code == 0

                # Install Certbot
                tlog.info("Installing Certbot")
                _, _, exit_code = ssh.execute(
                    "which certbot > /dev/null 2>&1 || apt-get install -y certbot python3-certbot-nginx",
                    timeout=120,
                )
                results["certbot_installed"] = exit_code == 0

                # Get Docker version after install
                stdout, _, exit_code = ssh.execute("docker --version 2>/dev/null")
                if exit_code == 0:
                    server.docker_version = stdout.split(",")[0].replace("Docker version ", "").strip()
                    db.commit()

                results["status"] = "completed"
                tlog.info("Dependency installation complete: %s", results)
                update_task_log(task_id, "success", results)
                return results

        except Exception as e:
            result = {"error": _friendly_ssh_error(e)}
            tlog.error("Dependency installation failed: %s", e)
            update_task_log(task_id, "failed", result)
            return result
    finally:
        db.close()
