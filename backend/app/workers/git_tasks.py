import logging
from datetime import UTC, datetime

from app.core.database_sync import get_sync_db
from app.core.encryption import decrypt_value
from app.models.git_repo import GitRepo
from app.models.odoo_instance import OdooInstance
from app.models.server import Server
from app.services.ssh_service import SSHService
from app.workers.celery_app import celery_app
from app.workers.utils import SSH_RETRYABLE, TaskLogger, update_task_log

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="git.deploy_modules",
    autoretry_for=SSH_RETRYABLE,
    retry_backoff=30,
    retry_backoff_max=300,
    retry_kwargs={"max_retries": 3},
)
def deploy_git_modules(self, repo_id: int) -> dict:
    """Pull a git repo and deploy Odoo addons to the instance."""
    task_id = self.request.id
    tlog = TaskLogger(task_id, repo_id=repo_id)
    update_task_log(task_id, "running")

    db = get_sync_db()
    try:
        repo = db.query(GitRepo).filter(GitRepo.id == repo_id).first()
        if not repo:
            result = {"error": "Git repo not found"}
            tlog.error("Git repo %d not found", repo_id)
            update_task_log(task_id, "failed", result)
            return result

        instance = db.query(OdooInstance).filter(OdooInstance.id == repo.instance_id).first()
        if not instance:
            result = {"error": "Instance not found"}
            tlog.error("Instance not found for repo %d", repo_id)
            update_task_log(task_id, "failed", result)
            return result

        # Enrich tlog with instance context
        tlog = TaskLogger(task_id, repo_id=repo_id, instance_id=instance.id)

        server = db.query(Server).filter(Server.id == instance.server_id).first()
        if not server:
            result = {"error": "Server not found"}
            tlog.error("Server not found for instance %d", instance.id)
            update_task_log(task_id, "failed", result)
            return result

        ssh = SSHService(
            host=server.host,
            port=server.port,
            username=server.ssh_user,
            private_key_pem=decrypt_value(server.ssh_key_encrypted),
        )

        tlog.info(
            "Deploying git modules from %s (branch %s) to %s",
            repo.repo_url, repo.branch, instance.container_name,
        )

        with ssh:
            odoo_name = instance.container_name
            addons_dir = f"/opt/cloudtab/{odoo_name}/addons"
            repo_dir = f"/opt/cloudtab/{odoo_name}/repo"

            # Install git if not present
            ssh.execute("which git > /dev/null 2>&1 || apt-get install -y git", timeout=60)

            # If deploy key exists, set up SSH key for git
            if repo.deploy_key_encrypted:
                deploy_key = decrypt_value(repo.deploy_key_encrypted)
                ssh.execute(f"mkdir -p /root/.ssh && chmod 700 /root/.ssh", timeout=5)
                # Write deploy key using heredoc
                ssh.execute(
                    f"cat > /root/.ssh/cloudtab_deploy_key << 'KEY_EOF'\n{deploy_key}\nKEY_EOF",
                    timeout=5,
                )
                ssh.execute("chmod 600 /root/.ssh/cloudtab_deploy_key", timeout=5)
                git_ssh_cmd = "GIT_SSH_COMMAND='ssh -i /root/.ssh/cloudtab_deploy_key -o StrictHostKeyChecking=no'"
            else:
                git_ssh_cmd = "GIT_SSH_COMMAND='ssh -o StrictHostKeyChecking=no'"

            # Clone or pull the repository
            _, _, exit_code = ssh.execute(f"test -d {repo_dir}/.git", timeout=5)
            if exit_code == 0:
                # Repo already cloned — pull latest
                tlog.info("Pulling latest changes from origin/%s", repo.branch)
                stdout, stderr, exit_code = ssh.execute(
                    f"cd {repo_dir} && {git_ssh_cmd} git fetch origin && git checkout {repo.branch} && {git_ssh_cmd} git pull origin {repo.branch}",
                    timeout=120,
                )
            else:
                # Fresh clone
                tlog.info("Cloning repository: %s", repo.repo_url)
                ssh.execute(f"mkdir -p {repo_dir}", timeout=5)
                stdout, stderr, exit_code = ssh.execute(
                    f"{git_ssh_cmd} git clone -b {repo.branch} {repo.repo_url} {repo_dir}",
                    timeout=180,
                )

            if exit_code != 0:
                result = {"error": f"Git operation failed: {stderr}"}
                tlog.error("Git operation failed: %s", stderr)
                update_task_log(task_id, "failed", result)
                return result

            # Get latest commit SHA
            commit_sha, _, _ = ssh.execute(f"cd {repo_dir} && git rev-parse HEAD", timeout=5)

            # Copy addons to the instance addons directory
            # Find directories that contain __manifest__.py (Odoo modules)
            ssh.execute(f"mkdir -p {addons_dir}", timeout=5)
            module_dirs, _, _ = ssh.execute(
                f"find {repo_dir} -name '__manifest__.py' -exec dirname {{}} \\;",
                timeout=30,
            )

            if module_dirs:
                for module_dir in module_dirs.strip().split("\n"):
                    module_name = module_dir.rstrip("/").split("/")[-1]
                    ssh.execute(
                        f"rm -rf {addons_dir}/{module_name} && cp -r {module_dir} {addons_dir}/{module_name}",
                        timeout=30,
                    )

            # Restart Odoo to pick up new modules
            tlog.info("Restarting Odoo container %s to load new modules", odoo_name)
            ssh.execute(f"docker restart {odoo_name}", timeout=60)

            # Update repo record
            repo.last_deployed_at = datetime.now(UTC)
            repo.last_commit_sha = commit_sha.strip()[:40] if commit_sha else None
            db.commit()

            deployed_modules = [d.rstrip("/").split("/")[-1] for d in module_dirs.strip().split("\n")] if module_dirs else []
            result = {
                "status": "deployed",
                "commit": repo.last_commit_sha,
                "modules": deployed_modules,
            }
            tlog.info(
                "Deploy complete — commit %s, %d modules deployed",
                repo.last_commit_sha, len(deployed_modules),
            )
            update_task_log(task_id, "success", result)
            return result

    except Exception as e:
        result = {"error": str(e)}
        tlog.error("Git deploy failed: %s", e)
        update_task_log(task_id, "failed", result)
        return result
    finally:
        db.close()
