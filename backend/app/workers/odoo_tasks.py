import json
import logging
from datetime import UTC, datetime

from app.core.database_sync import get_sync_db
from app.core.encryption import decrypt_value
from app.models.odoo_instance import OdooInstance
from app.models.server import Server
from app.services.ssh_service import SSHService
from app.workers.celery_app import celery_app
from app.workers.utils import SSH_RETRYABLE, TaskLogger, update_task_log

logger = logging.getLogger(__name__)


def _get_ssh_for_instance(instance_id: int, db):
    """Load instance + server, return (ssh_service, instance, server) or raise."""
    instance = db.query(OdooInstance).filter(OdooInstance.id == instance_id).first()
    if not instance:
        raise ValueError("Instance not found")
    server = db.query(Server).filter(Server.id == instance.server_id).first()
    if not server:
        raise ValueError("Server not found")
    ssh = SSHService(
        host=server.host,
        port=server.port,
        username=server.ssh_user,
        private_key_pem=decrypt_value(server.ssh_key_encrypted),
    )
    return ssh, instance, server


@celery_app.task(
    bind=True,
    name="odoo.deploy",
    autoretry_for=SSH_RETRYABLE,
    retry_backoff=30,
    retry_backoff_max=300,
    retry_kwargs={"max_retries": 3},
)
def deploy_odoo_instance(self, instance_id: int) -> dict:
    """Deploy an Odoo instance (Postgres + Odoo containers) on the target server."""
    task_id = self.request.id
    tlog = TaskLogger(task_id, instance_id=instance_id)
    update_task_log(task_id, "running")

    db = get_sync_db()
    try:
        ssh, instance, server = _get_ssh_for_instance(instance_id, db)

        instance.status = "deploying"
        db.commit()

        try:
            with ssh:
                pg_name = instance.pg_container_name
                odoo_name = instance.container_name
                pg_password = instance.pg_password or "odoo"
                odoo_version = instance.odoo_version
                host_port = instance.host_port
                addons_path = instance.addons_path

                tlog.info("Deploying Odoo %s on %s (port %d)", odoo_version, server.host, host_port)

                # Create directories for persistent data
                ssh.execute(f"mkdir -p /opt/cloudtab/{odoo_name}/data", timeout=10)
                ssh.execute(f"mkdir -p /opt/cloudtab/{odoo_name}/addons", timeout=10)
                ssh.execute(f"mkdir -p /opt/cloudtab/{odoo_name}/config", timeout=10)
                ssh.execute(f"mkdir -p /opt/cloudtab/{odoo_name}/pgdata", timeout=10)

                # Odoo container runs as uid 101 (odoo user) — fix ownership so it
                # can write sessions, filestore, etc.
                # chown only works when the SSH user is root; if it fails (non-root
                # SSH user such as "ubuntu"), fall back to chmod 777 so uid 101 can
                # still write to the volume.  Without this the init step fails with:
                #   PermissionError: [Errno 13] Permission denied: '/var/lib/odoo/filestore'
                _, _, chown_exit = ssh.execute(
                    f"chown -R 101:101 /opt/cloudtab/{odoo_name}/data /opt/cloudtab/{odoo_name}/addons",
                    timeout=10,
                )
                if chown_exit != 0:
                    tlog.warning(
                        "chown to uid 101 failed (SSH user may not be root) — "
                        "falling back to chmod 777 on data/addons directories"
                    )
                    ssh.execute(
                        f"chmod -R 777 /opt/cloudtab/{odoo_name}/data /opt/cloudtab/{odoo_name}/addons",
                        timeout=10,
                    )

                # Fail fast if the requested host port is already bound.
                # Without this check the deploy runs for several minutes (image pull,
                # DB init) and only fails at the very last `docker run -p` step.
                tlog.info("Checking port %d availability", host_port)
                port_check, _, _ = ssh.execute(
                    f"ss -tln 2>/dev/null | awk '{{print $4}}' | grep -q ':{host_port}$'"
                    f" && echo in_use || echo free",
                    timeout=10,
                )
                if (port_check or "").strip() == "in_use":
                    raise RuntimeError(
                        f"Port {host_port} is already in use on the server. "
                        f"Another Odoo instance or service is listening on port {host_port}. "
                        f"Please choose a different port number when creating the instance."
                    )

                # Create Docker network for this instance
                network_name = f"net-{odoo_name}"
                ssh.execute(f"docker network create {network_name} 2>/dev/null || true", timeout=15)

                # Stop and remove existing containers if they exist
                ssh.execute(f"docker stop {odoo_name} 2>/dev/null; docker rm {odoo_name} 2>/dev/null", timeout=30)
                ssh.execute(f"docker stop {pg_name} 2>/dev/null; docker rm {pg_name} 2>/dev/null", timeout=30)

                # Deploy PostgreSQL container
                # POSTGRES_DB=odoo creates the 'odoo' database on first start.
                tlog.info("Starting PostgreSQL container %s", pg_name)
                pg_cmd = (
                    f"docker run -d"
                    f" --name {pg_name}"
                    f" --network {network_name}"
                    f" --restart unless-stopped"
                    f" -e POSTGRES_USER=odoo"
                    f" -e POSTGRES_PASSWORD={pg_password}"
                    f" -e POSTGRES_DB=odoo"
                    f" -v /opt/cloudtab/{odoo_name}/pgdata:/var/lib/postgresql/data"
                    f" postgres:16-alpine"
                )
                stdout, stderr, exit_code = ssh.execute(pg_cmd, timeout=120)
                if exit_code != 0:
                    raise RuntimeError(f"Failed to start PostgreSQL: {stderr}")

                # Wait for PostgreSQL AND the 'odoo' database to be accessible.
                # pg_isready only confirms PG accepts connections; POSTGRES_DB=odoo
                # creates the database slightly after that, so we wait until we can
                # actually SELECT from it to avoid a race condition in the init step.
                tlog.info("Waiting for PostgreSQL and the 'odoo' database to be ready")
                ssh.execute(
                    f"for i in $(seq 1 60); do "
                    f"docker exec {pg_name} psql -U odoo -d odoo -c 'SELECT 1' "
                    f">/dev/null 2>&1 && break; sleep 1; done",
                    timeout=75,
                )

                # Build odoo.conf
                odoo_config_lines = [
                    "[options]",
                    f"db_host = {pg_name}",
                    "db_port = 5432",
                    "db_user = odoo",
                    f"db_password = {pg_password}",
                    "db_name = odoo",
                    f"addons_path = /mnt/extra-addons",
                    "data_dir = /var/lib/odoo",
                ]

                # Apply custom config overrides
                if instance.odoo_config:
                    try:
                        custom = json.loads(instance.odoo_config)
                        for key, value in custom.items():
                            odoo_config_lines.append(f"{key} = {value}")
                    except json.JSONDecodeError:
                        pass

                config_content = "\\n".join(odoo_config_lines)
                ssh.execute(
                    f"printf '{config_content}' > /opt/cloudtab/{odoo_name}/config/odoo.conf",
                    timeout=10,
                )

                odoo_image = f"odoo:{odoo_version}"
                init_name = f"{odoo_name}-init"

                # Pull the image explicitly before starting the init container.
                # Without this, `docker run -d` would pull inline and the 120s SSH
                # timeout fires before the pull completes for large images (odoo:18.0+
                # is several GB on a fresh server).  We give the pull up to 10 minutes.
                tlog.info("Pulling Odoo image %s (may take a few minutes on first deploy)", odoo_image)
                _, pull_stderr, pull_exit = ssh.execute(
                    f"docker pull {odoo_image}", timeout=600
                )
                if pull_exit != 0:
                    # Non-fatal: image might already be present; log the warning and continue
                    tlog.warning("docker pull exited %d: %s", pull_exit, pull_stderr)

                # Initialize the Odoo database using a detached container.
                #
                # We MUST NOT use `docker run --rm` (blocking) here because Odoo's
                # --init=base writes megabytes of log output to stdout/stderr.  If we
                # block on the SSH channel, the pipe buffer fills up, Odoo's process
                # stalls waiting to write more logs, and recv_exit_status() deadlocks.
                #
                # Instead: start detached, use `docker wait` (returns only the exit
                # code — a single integer — so no buffer overflow), then read the last
                # few log lines only if the init failed.
                #
                # --without-demo=all skips demo data loading, which significantly
                # reduces init time (especially on Odoo 17/18) and avoids timeouts.
                tlog.info("Initializing Odoo database (detached, this may take a few minutes)")
                ssh.execute(f"docker rm -f {init_name} 2>/dev/null || true", timeout=15)
                init_start_cmd = (
                    f"docker run -d --name {init_name}"
                    f" --network {network_name}"
                    f" -v /opt/cloudtab/{odoo_name}/data:/var/lib/odoo"
                    f" -v /opt/cloudtab/{odoo_name}/addons:/mnt/extra-addons"
                    f" -v /opt/cloudtab/{odoo_name}/config/odoo.conf:/etc/odoo/odoo.conf"
                    f" {odoo_image}"
                    f" odoo --database=odoo --init=base --without-demo=all --stop-after-init"
                )
                _, stderr, exit_code = ssh.execute(init_start_cmd, timeout=60)
                if exit_code != 0:
                    raise RuntimeError(f"Failed to start Odoo init container: {stderr}")

                # Block until the init container exits; docker wait prints the exit code.
                wait_out, _, _ = ssh.execute(f"docker wait {init_name}", timeout=900)
                init_exit = int(wait_out.strip()) if wait_out.strip().isdigit() else -1
                if init_exit != 0:
                    logs_out, _, _ = ssh.execute(
                        f"docker logs --tail 50 {init_name} 2>&1", timeout=30
                    )
                    ssh.execute(f"docker rm {init_name} 2>/dev/null || true", timeout=15)
                    raise RuntimeError(
                        f"Odoo database initialization failed (exit {init_exit}). "
                        f"Last log lines:\n{logs_out if logs_out else 'none'}"
                    )

                ssh.execute(f"docker rm {init_name} 2>/dev/null || true", timeout=15)
                tlog.info("Database initialization complete")

                # Deploy Odoo container
                tlog.info("Starting Odoo container %s (image odoo:%s)", odoo_name, odoo_version)
                odoo_cmd = (
                    f"docker run -d"
                    f" --name {odoo_name}"
                    f" --network {network_name}"
                    f" --restart unless-stopped"
                    f" -p {host_port}:8069"
                    f" -v /opt/cloudtab/{odoo_name}/data:/var/lib/odoo"
                    f" -v /opt/cloudtab/{odoo_name}/addons:/mnt/extra-addons"
                    f" -v /opt/cloudtab/{odoo_name}/config/odoo.conf:/etc/odoo/odoo.conf"
                    f" {odoo_image}"
                )
                stdout, stderr, exit_code = ssh.execute(odoo_cmd, timeout=60)
                if exit_code != 0:
                    raise RuntimeError(f"Failed to start Odoo: {stderr}")

                # Get container ID
                container_id_out, _, _ = ssh.execute(f"docker inspect --format='{{{{.Id}}}}' {odoo_name}", timeout=10)

                instance.status = "running"
                instance.container_id = container_id_out[:12] if container_id_out else None
                db.commit()

                result = {
                    "status": "running",
                    "container_name": odoo_name,
                    "container_id": instance.container_id,
                    "url": f"http://{server.host}:{host_port}",
                }
                tlog.info("Deploy complete — %s running at port %d", odoo_name, host_port)
                update_task_log(task_id, "success", result)
                return result

        except Exception as e:
            instance.status = "failed"
            db.commit()
            result = {"error": str(e)}
            tlog.error("Deploy failed: %s", e)
            update_task_log(task_id, "failed", result)
            return result
    except Exception as e:
        result = {"error": str(e)}
        tlog.error("Deploy failed (outer): %s", e)
        update_task_log(task_id, "failed", result)
        return result
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="odoo.stop",
    autoretry_for=SSH_RETRYABLE,
    retry_backoff=15,
    retry_backoff_max=120,
    retry_kwargs={"max_retries": 2},
)
def stop_odoo_instance(self, instance_id: int) -> dict:
    """Stop an Odoo instance (both Odoo and Postgres containers)."""
    task_id = self.request.id
    tlog = TaskLogger(task_id, instance_id=instance_id)
    update_task_log(task_id, "running")

    db = get_sync_db()
    try:
        ssh, instance, _ = _get_ssh_for_instance(instance_id, db)

        tlog.info("Stopping instance %s", instance.container_name)
        with ssh:
            ssh.execute(f"docker stop {instance.container_name}", timeout=30)
            ssh.execute(f"docker stop {instance.pg_container_name}", timeout=30)

        instance.status = "stopped"
        db.commit()

        result = {"status": "stopped"}
        tlog.info("Instance stopped")
        update_task_log(task_id, "success", result)
        return result
    except Exception as e:
        result = {"error": str(e)}
        tlog.error("Stop failed: %s", e)
        update_task_log(task_id, "failed", result)
        return result
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="odoo.start",
    autoretry_for=SSH_RETRYABLE,
    retry_backoff=15,
    retry_backoff_max=120,
    retry_kwargs={"max_retries": 2},
)
def start_odoo_instance(self, instance_id: int) -> dict:
    """Start a stopped Odoo instance."""
    task_id = self.request.id
    tlog = TaskLogger(task_id, instance_id=instance_id)
    update_task_log(task_id, "running")

    db = get_sync_db()
    try:
        ssh, instance, _ = _get_ssh_for_instance(instance_id, db)

        tlog.info("Starting instance %s", instance.container_name)
        with ssh:
            ssh.execute(f"docker start {instance.pg_container_name}", timeout=30)
            # Wait for PG
            ssh.execute(
                f"for i in $(seq 1 15); do docker exec {instance.pg_container_name} pg_isready -U odoo && break; sleep 1; done",
                timeout=30,
            )
            ssh.execute(f"docker start {instance.container_name}", timeout=30)

        instance.status = "running"
        db.commit()

        result = {"status": "running"}
        tlog.info("Instance started")
        update_task_log(task_id, "success", result)
        return result
    except Exception as e:
        result = {"error": str(e)}
        tlog.error("Start failed: %s", e)
        update_task_log(task_id, "failed", result)
        return result
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="odoo.restart",
    autoretry_for=SSH_RETRYABLE,
    retry_backoff=15,
    retry_backoff_max=120,
    retry_kwargs={"max_retries": 2},
)
def restart_odoo_instance(self, instance_id: int) -> dict:
    """Restart an Odoo instance."""
    task_id = self.request.id
    tlog = TaskLogger(task_id, instance_id=instance_id)
    update_task_log(task_id, "running")

    db = get_sync_db()
    try:
        ssh, instance, _ = _get_ssh_for_instance(instance_id, db)

        tlog.info("Restarting instance %s", instance.container_name)
        with ssh:
            ssh.execute(f"docker restart {instance.container_name}", timeout=60)

        instance.status = "running"
        db.commit()

        result = {"status": "running"}
        tlog.info("Instance restarted")
        update_task_log(task_id, "success", result)
        return result
    except Exception as e:
        result = {"error": str(e)}
        tlog.error("Restart failed: %s", e)
        update_task_log(task_id, "failed", result)
        return result
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="odoo.destroy",
    autoretry_for=SSH_RETRYABLE,
    retry_backoff=30,
    retry_backoff_max=300,
    retry_kwargs={"max_retries": 2},
)
def destroy_odoo_instance(self, instance_id: int) -> dict:
    """Stop and remove an Odoo instance's containers, network, and data on the server."""
    task_id = self.request.id
    tlog = TaskLogger(task_id, instance_id=instance_id)
    update_task_log(task_id, "running")

    db = get_sync_db()
    try:
        ssh, instance, server = _get_ssh_for_instance(instance_id, db)

        odoo_name = instance.container_name
        pg_name = instance.pg_container_name
        network_name = f"net-{odoo_name}"

        tlog.info("Destroying instance %s on %s", odoo_name, server.host)

        with ssh:
            # Stop and remove Odoo container (and any leftover init container)
            ssh.execute(f"docker stop {odoo_name} 2>/dev/null || true", timeout=60)
            ssh.execute(f"docker rm {odoo_name} 2>/dev/null || true", timeout=30)
            ssh.execute(f"docker rm -f {odoo_name}-init 2>/dev/null || true", timeout=15)

            # Stop and remove PostgreSQL container
            ssh.execute(f"docker stop {pg_name} 2>/dev/null || true", timeout=60)
            ssh.execute(f"docker rm {pg_name} 2>/dev/null || true", timeout=30)

            # Remove the Docker network
            ssh.execute(f"docker network rm {network_name} 2>/dev/null || true", timeout=15)

            # Remove data directories (backups are preserved for safety)
            ssh.execute(f"rm -rf /opt/cloudtab/{odoo_name}/data", timeout=30)
            ssh.execute(f"rm -rf /opt/cloudtab/{odoo_name}/addons", timeout=30)
            ssh.execute(f"rm -rf /opt/cloudtab/{odoo_name}/config", timeout=30)
            ssh.execute(f"rm -rf /opt/cloudtab/{odoo_name}/pgdata", timeout=30)
            ssh.execute(f"rm -rf /opt/cloudtab/{odoo_name}/repo", timeout=30)

        # Delete the instance record from DB (cascades to domains, schedules, etc.)
        db.delete(instance)
        db.commit()

        result = {
            "status": "destroyed",
            "container_name": odoo_name,
            "message": f"Instance {odoo_name} fully removed from server",
        }
        tlog.info("Instance destroyed successfully")
        update_task_log(task_id, "success", result)
        return result

    except Exception as e:
        tlog.error("Failed to destroy instance: %s", e)
        result = {"error": str(e)}
        update_task_log(task_id, "failed", result)
        return result
    finally:
        db.close()


LOCKED_KEYS = {"db_host", "db_port", "db_user", "db_password", "db_name", "addons_path", "data_dir"}


def _parse_odoo_conf(raw: str) -> dict:
    """Parse odoo.conf INI text into a key-value dict."""
    result = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("[") or line.startswith(";") or line.startswith("#"):
            continue
        if " = " in line:
            key, _, value = line.partition(" = ")
            result[key.strip()] = value.strip()
    return result


def _serialize_odoo_conf(config: dict) -> str:
    """Serialize a key-value dict back to odoo.conf INI format."""
    lines = ["[options]"]
    for key, value in config.items():
        lines.append(f"{key} = {value}")
    return "\n".join(lines)


@celery_app.task(
    bind=True,
    name="odoo.read_config",
    autoretry_for=SSH_RETRYABLE,
    retry_backoff=10,
    retry_backoff_max=60,
    retry_kwargs={"max_retries": 2},
)
def read_odoo_config(self, instance_id: int) -> dict:
    """Read the current odoo.conf from the instance and return it as a key-value dict."""
    task_id = self.request.id
    tlog = TaskLogger(task_id, instance_id=instance_id)
    update_task_log(task_id, "running")

    db = get_sync_db()
    try:
        ssh, instance, _ = _get_ssh_for_instance(instance_id, db)

        conf_path = f"/opt/cloudtab/{instance.container_name}/config/odoo.conf"
        tlog.info("Reading config from %s", conf_path)
        with ssh:
            stdout, stderr, exit_code = ssh.execute(f"cat {conf_path}", timeout=15)

        if exit_code != 0:
            raise RuntimeError(f"Failed to read config: {stderr}")

        config = _parse_odoo_conf(stdout)
        result = {"config": config}
        tlog.info("Config read successfully (%d keys)", len(config))
        update_task_log(task_id, "success", result)
        return result
    except Exception as e:
        result = {"error": str(e)}
        tlog.error("Failed to read config: %s", e)
        update_task_log(task_id, "failed", result)
        return result
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="odoo.apply_config",
    autoretry_for=SSH_RETRYABLE,
    retry_backoff=10,
    retry_backoff_max=60,
    retry_kwargs={"max_retries": 2},
)
def apply_odoo_config(self, instance_id: int, updates: dict) -> dict:
    """Write updated config to odoo.conf and restart the Odoo container."""
    task_id = self.request.id
    tlog = TaskLogger(task_id, instance_id=instance_id)
    update_task_log(task_id, "running")

    db = get_sync_db()
    try:
        ssh, instance, _ = _get_ssh_for_instance(instance_id, db)

        conf_path = f"/opt/cloudtab/{instance.container_name}/config/odoo.conf"

        with ssh:
            # Read and parse current config
            tlog.info("Reading current config from %s", conf_path)
            stdout, stderr, exit_code = ssh.execute(f"cat {conf_path}", timeout=15)
            if exit_code != 0:
                raise RuntimeError(f"Failed to read config: {stderr}")

            current = _parse_odoo_conf(stdout)

            # Merge updates (locked keys are preserved from current, user values override the rest)
            merged = {**current}
            for key, value in updates.items():
                if key not in LOCKED_KEYS:
                    merged[key] = value

            # Write back
            conf_content = _serialize_odoo_conf(merged)
            tlog.info("Writing updated config (%d keys)", len(merged))
            # Use printf with escaped content written via SFTP to avoid shell quoting issues
            ssh.write_file(conf_path, conf_content)

            # Restart Odoo container
            tlog.info("Restarting container %s", instance.container_name)
            _, stderr, exit_code = ssh.execute(
                f"docker restart {instance.container_name}", timeout=60
            )
            if exit_code != 0:
                raise RuntimeError(f"Failed to restart container: {stderr}")

        # Persist only non-locked user overrides to DB
        user_overrides = {k: v for k, v in updates.items() if k not in LOCKED_KEYS}
        instance.odoo_config = json.dumps(user_overrides)
        db.commit()

        result = {"status": "applied", "keys_updated": len(user_overrides)}
        tlog.info("Config applied and container restarted")
        update_task_log(task_id, "success", result)
        return result
    except Exception as e:
        result = {"error": str(e)}
        tlog.error("Failed to apply config: %s", e)
        update_task_log(task_id, "failed", result)
        return result
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="odoo.get_logs",
    autoretry_for=SSH_RETRYABLE,
    retry_backoff=10,
    retry_backoff_max=60,
    retry_kwargs={"max_retries": 2},
)
def get_odoo_logs(self, instance_id: int, tail: int = 200) -> dict:
    """Fetch recent logs from an Odoo container."""
    task_id = self.request.id
    tlog = TaskLogger(task_id, instance_id=instance_id)
    update_task_log(task_id, "running")

    db = get_sync_db()
    try:
        ssh, instance, _ = _get_ssh_for_instance(instance_id, db)

        tlog.info("Fetching last %d log lines from %s", tail, instance.container_name)
        with ssh:
            # Check that the container actually exists before fetching logs.
            # If deploy failed before the main container was created, docker logs
            # would return "Error response from daemon: No such container: X" via
            # stderr (captured by 2>&1) which is confusing.  Give a clear message instead.
            _, _, inspect_exit = ssh.execute(
                f"docker inspect {instance.container_name} >/dev/null 2>&1",
                timeout=10,
            )
            if inspect_exit != 0:
                raise RuntimeError(
                    f"Container '{instance.container_name}' does not exist on the server. "
                    f"The instance may not be deployed or the previous deploy may have failed. "
                    f"Try redeploying the instance."
                )

            stdout, stderr, _ = ssh.execute(
                f"docker logs --tail {tail} {instance.container_name} 2>&1",
                timeout=30,
            )

        result = {"logs": stdout or stderr}
        tlog.info("Logs fetched (%d chars)", len(result["logs"]))
        update_task_log(task_id, "success", result)
        return result
    except Exception as e:
        result = {"error": str(e)}
        tlog.error("Failed to fetch logs: %s", e)
        update_task_log(task_id, "failed", result)
        return result
    finally:
        db.close()
