import io
import logging

import paramiko

logger = logging.getLogger(__name__)


class SSHService:
    """Wrapper around paramiko.SSHClient for executing commands on remote servers."""

    def __init__(self, host: str, port: int, username: str, private_key_pem: str):
        self.host = host
        self.port = port
        self.username = username
        self.private_key_pem = private_key_pem
        self._client: paramiko.SSHClient | None = None

    def connect(self) -> None:
        """Establish SSH connection using the provided private key."""
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Try RSA first, then Ed25519, then ECDSA
        pkey = self._parse_private_key(self.private_key_pem)

        self._client.connect(
            hostname=self.host,
            port=self.port,
            username=self.username,
            pkey=pkey,
            timeout=15,
            allow_agent=False,
            look_for_keys=False,
        )

    @staticmethod
    def _parse_private_key(pem: str) -> paramiko.PKey:
        """Parse a PEM-encoded private key, trying multiple key types."""
        key_file = io.StringIO(pem)
        key_classes = [
            paramiko.RSAKey,
            paramiko.Ed25519Key,
            paramiko.ECDSAKey,
        ]
        last_error = None
        for key_class in key_classes:
            try:
                key_file.seek(0)
                return key_class.from_private_key(key_file)
            except (paramiko.SSHException, ValueError) as e:
                last_error = e
                continue
        raise paramiko.SSHException(f"Unable to parse private key: {last_error}")

    def execute(self, command: str, timeout: int = 30) -> tuple[str, str, int]:
        """Execute a command on the remote server.

        Returns:
            Tuple of (stdout, stderr, exit_code)
        """
        if self._client is None:
            raise RuntimeError("SSH client is not connected. Call connect() first.")

        _, stdout, stderr = self._client.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        return (
            stdout.read().decode("utf-8", errors="replace").strip(),
            stderr.read().decode("utf-8", errors="replace").strip(),
            exit_code,
        )

    def download_file(self, remote_path: str, local_path: str) -> None:
        """Download a file from the remote server via SFTP.

        Args:
            remote_path: Absolute path on the remote server.
            local_path: Local file path to write to.
        """
        if self._client is None:
            raise RuntimeError("SSH client is not connected. Call connect() first.")
        sftp = self._client.open_sftp()
        try:
            logger.info("SFTP download: %s -> %s", remote_path, local_path)
            sftp.get(remote_path, local_path)
        finally:
            sftp.close()

    def upload_file(self, local_path: str, remote_path: str) -> None:
        """Upload a local file to the remote server via SFTP.

        Args:
            local_path: Local file path to read from.
            remote_path: Absolute path on the remote server.
        """
        if self._client is None:
            raise RuntimeError("SSH client is not connected. Call connect() first.")
        sftp = self._client.open_sftp()
        try:
            logger.info("SFTP upload: %s -> %s", local_path, remote_path)
            sftp.put(local_path, remote_path)
        finally:
            sftp.close()

    def write_file(self, remote_path: str, content: str) -> None:
        """Write string content directly to a file on the remote server via SFTP.

        Args:
            remote_path: Absolute path on the remote server.
            content: String content to write.
        """
        if self._client is None:
            raise RuntimeError("SSH client is not connected. Call connect() first.")
        sftp = self._client.open_sftp()
        try:
            logger.info("SFTP write: %s (%d bytes)", remote_path, len(content))
            with sftp.open(remote_path, "w") as f:
                f.write(content)
        finally:
            sftp.close()

    def close(self) -> None:
        """Close the SSH connection."""
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self) -> "SSHService":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
