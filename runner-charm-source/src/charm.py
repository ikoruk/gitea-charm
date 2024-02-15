#!/usr/bin/env python3
# Copyright 2024 Ubuntu
# See LICENSE file for licensing details.

"""Charm the application."""

import logging
import os
import subprocess

from jinja2 import Template
import ops

from charms.operator_libs_linux.v0 import (
    apt,
    passwd,
    systemd,
)

logger = logging.getLogger(__name__)

class GiteaRunnerCharm(ops.CharmBase):
    """Charm the application."""

    _stored = ops.StoredState()

    def __init__(self, *args):
        super().__init__(*args)

        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.update_status, self._on_update_status)

    def _start_runner(self):
        """Start runner service."""
        logger.info("Starting Gitea Runner service...")
        success = systemd.service_start("kteam-gitea-runner")
        logger.info("Gitea Runner service started.")

        return success

    def _stop_runner(self):
        """Stop runner service."""
        logger.info("Stopping Gitea Runner service...")
        success = systemd.service_stop("kteam-gitea-runner")
        logger.info("Stopped Gitea Runner service.")

        return success

    def _is_running(self):
        return systemd.service_running("kteam-gitea-runner")

    def _on_start(self, event: ops.StartEvent):
        """Handle start event."""
        self.unit.set_ports(8088)

    def _on_config_changed(self, event: ops.ConfigChangedEvent):
        self._stop_runner()

        # update any configs here

        self._start_runner()
        self.unit.status = ops.ActiveStatus()

    def _on_update_status(self, event: ops.UpdateStatusEvent):
        if self._is_running():
            self.unit.status = ops.ActiveStatus()
        else:
            self._error("Failed to start runner service. Has a runner token been registered?")

    def _on_install(self, event: ops.InstallEvent):
        self.unit.status = ops.MaintenanceStatus("Begin install")

        # Fetch and verify the Gitea runner
        ZIP_URL = "https://gitea.com/gitea/act_runner/releases/download/v0.2.6/act_runner-0.2.6-linux-amd64.xz"
        ZIP_NAME = os.path.basename(ZIP_URL)
        BIN_NAME = ZIP_NAME[:-len(".xz")]
        self.unit.status = ops.MaintenanceStatus("Fetch and verify Gitea runner")
        subprocess.run(["wget", ZIP_URL], check=True)
        subprocess.run(["wget", f"{ZIP_URL}.sha256"], check=True)
        subprocess.run(["sha256sum", "-c", f"{ZIP_NAME}.sha256"], check=True)
        subprocess.run(["xz", "-d", ZIP_NAME], check=True)
        subprocess.run(["chmod", "+x", BIN_NAME], check=True)

        # Ensure Docker is installed and running
        self.unit.status = ops.MaintenanceStatus("Install Docker")
        apt.update()
        apt.add_package("docker.io")
        systemd.service_start("docker")

        # Create user
        passwd.add_user("act_runner", None, system_user=True, create_home=True,
                        home_dir="/home/act_runner", secondary_groups=["docker"])

        # Create directories
        subprocess.run(["mkdir", "-p",
                        "/var/lib/act_runner",
                        "/etc/act_runner"], check=True)
        subprocess.run(["chown", "-R", "act_runner:act_runner",
                        "/var/lib/act_runner",
                        "/etc/act_runner"], check=True)

        # Install Gitea executable
        self.unit.status = ops.MaintenanceStatus("Configuring system")
        subprocess.run(["cp", BIN_NAME, "/usr/local/bin/act_runner"], check=True)

        # Generate config.yaml
        subprocess.run("/usr/local/bin/act_runner generate-config > /etc/act_runner/config.yaml",
                       check=True, shell=True)

        # Create systemd service
        self._install_template("kteam-gitea-runner.service.j2",
                               "/etc/systemd/system/kteam-gitea-runner.service",
                               0o644, "root:root")
        subprocess.run(["systemctl", "daemon-reload"], check=True)

        self.unit.status = ops.ActiveStatus()

    def _install_template(self, name: str, install_path: str, mode: int,
                          owner: str = "root:git", **kwargs):
        # Read and render template.
        with open(f"templates/{name}", "r") as file:
            template = Template(file.read())
        rendered = template.render(**kwargs)

        # Write filled-in template to file.
        with open(install_path, "w+") as file:
            file.write(rendered)
        os.chmod(install_path, mode)
        subprocess.run(["chown", owner, install_path], check=True)

    def _error(self, msg):
        logger.error(msg)
        self.unit.status = ops.BlockedStatus(msg)

if __name__ == "__main__":  # pragma: nocover
    ops.main(GiteaRunnerCharm)  # type: ignore
