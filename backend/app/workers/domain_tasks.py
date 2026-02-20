import logging
from datetime import UTC, datetime

from app.core.database_sync import get_sync_db
from app.core.encryption import decrypt_value
from app.models.domain import Domain
from app.models.odoo_instance import OdooInstance
from app.models.server import Server
from app.services.ssh_service import SSHService
from app.workers.celery_app import celery_app
from app.workers.utils import SSH_RETRYABLE, TaskLogger, update_task_log

logger = logging.getLogger(__name__)


def _load_domain_context(domain_id: int, db):
    """Load domain, instance, and server records."""
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise ValueError("Domain not found")
    instance = db.query(OdooInstance).filter(OdooInstance.id == domain.instance_id).first()
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
    return ssh, domain, instance, server


@celery_app.task(
    bind=True,
    name="domain.setup_nginx",
    autoretry_for=SSH_RETRYABLE,
    retry_backoff=15,
    retry_backoff_max=120,
    retry_kwargs={"max_retries": 2},
)
def setup_nginx_proxy(self, domain_id: int) -> dict:
    """Configure Nginx reverse proxy for a domain pointing to an Odoo instance."""
    task_id = self.request.id
    tlog = TaskLogger(task_id, domain_id=domain_id)
    update_task_log(task_id, "running")

    db = get_sync_db()
    try:
        ssh, domain, instance, server = _load_domain_context(domain_id, db)

        tlog.info(
            "Setting up Nginx proxy for %s -> %s:%d",
            domain.domain_name, server.host, instance.host_port,
        )

        with ssh:
            domain_name = domain.domain_name
            upstream_port = instance.host_port

            # Ensure Nginx is installed
            ssh.execute("which nginx > /dev/null 2>&1 || apt-get install -y nginx", timeout=120)

            # Write Nginx config
            nginx_config = f"""server {{
    listen 80;
    server_name {domain_name};

    client_max_body_size 200M;
    proxy_read_timeout 720s;
    proxy_connect_timeout 720s;
    proxy_send_timeout 720s;

    location / {{
        proxy_pass http://127.0.0.1:{upstream_port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }}

    location /longpolling {{
        proxy_pass http://127.0.0.1:{upstream_port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}

    location ~* /web/static/ {{
        proxy_pass http://127.0.0.1:{upstream_port};
        proxy_cache_valid 200 90m;
        proxy_buffering on;
        expires 864000;
    }}
}}"""
            # Write config file using heredoc to avoid escaping issues
            ssh.execute(
                f"cat > /etc/nginx/sites-available/{domain_name}.conf << 'NGINX_EOF'\n{nginx_config}\nNGINX_EOF",
                timeout=10,
            )

            # Enable site
            ssh.execute(
                f"ln -sf /etc/nginx/sites-available/{domain_name}.conf /etc/nginx/sites-enabled/{domain_name}.conf",
                timeout=5,
            )

            # Test and reload Nginx
            tlog.info("Testing Nginx configuration")
            stdout, stderr, exit_code = ssh.execute("nginx -t", timeout=10)
            if exit_code != 0:
                raise RuntimeError(f"Nginx config test failed: {stderr}")

            ssh.execute("systemctl reload nginx", timeout=10)

            domain.status = "active"
            db.commit()

            result = {"status": "active", "domain": domain_name}
            tlog.info("Nginx proxy configured successfully for %s", domain_name)
            update_task_log(task_id, "success", result)
            return result

    except Exception as e:
        try:
            domain_obj = db.query(Domain).filter(Domain.id == domain_id).first()
            if domain_obj:
                domain_obj.status = "failed"
                db.commit()
        except Exception:
            pass
        result = {"error": str(e)}
        tlog.error("Nginx setup failed: %s", e)
        update_task_log(task_id, "failed", result)
        return result
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="domain.issue_ssl",
    autoretry_for=SSH_RETRYABLE,
    retry_backoff=30,
    retry_backoff_max=300,
    retry_kwargs={"max_retries": 3},
)
def issue_ssl_cert(self, domain_id: int) -> dict:
    """Issue a Let's Encrypt SSL certificate for a domain via Certbot."""
    task_id = self.request.id
    tlog = TaskLogger(task_id, domain_id=domain_id)
    update_task_log(task_id, "running")

    db = get_sync_db()
    try:
        ssh, domain, instance, server = _load_domain_context(domain_id, db)

        domain.ssl_status = "pending"
        db.commit()

        tlog.info("Issuing SSL certificate for %s", domain.domain_name)

        with ssh:
            domain_name = domain.domain_name

            # Ensure Certbot is installed
            ssh.execute(
                "which certbot > /dev/null 2>&1 || apt-get install -y certbot python3-certbot-nginx",
                timeout=120,
            )

            # Issue certificate
            tlog.info("Running Certbot for %s", domain_name)
            stdout, stderr, exit_code = ssh.execute(
                f"certbot --nginx -d {domain_name} --non-interactive --agree-tos --register-unsafely-without-email",
                timeout=120,
            )

            if exit_code != 0:
                domain.ssl_status = "failed"
                db.commit()
                result = {"error": f"Certbot failed: {stderr}"}
                tlog.error("Certbot failed for %s: %s", domain_name, stderr)
                update_task_log(task_id, "failed", result)
                return result

            # Get certificate expiry date
            expiry_out, _, _ = ssh.execute(
                f"openssl x509 -enddate -noout -in /etc/letsencrypt/live/{domain_name}/cert.pem 2>/dev/null | cut -d= -f2",
                timeout=10,
            )

            domain.ssl_status = "active"
            if expiry_out:
                try:
                    domain.ssl_expires_at = datetime.strptime(
                        expiry_out.strip(), "%b %d %H:%M:%S %Y %Z"
                    ).replace(tzinfo=UTC)
                except ValueError:
                    pass
            db.commit()

            result = {"status": "active", "ssl_expires_at": str(domain.ssl_expires_at)}
            tlog.info("SSL certificate issued for %s (expires %s)", domain_name, domain.ssl_expires_at)
            update_task_log(task_id, "success", result)
            return result

    except Exception as e:
        result = {"error": str(e)}
        tlog.error("SSL issuance failed: %s", e)
        update_task_log(task_id, "failed", result)
        return result
    finally:
        db.close()
