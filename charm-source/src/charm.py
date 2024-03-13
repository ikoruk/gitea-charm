#!/usr/bin/env python3
# Copyright 2023 Ubuntu
# See LICENSE file for licensing details.

"""Charm for the Canonical Kernel Team's Gitea configuration."""

import logging
import os
import shutil
import subprocess

import ops
from charms.data_platform_libs.v0.data_interfaces import (DatabaseCreatedEvent,
                                                          DatabaseRequires)
from charms.operator_libs_linux.v0 import apt, passwd, systemd
from config import GiteaConfig
from jinja2 import Template

logger = logging.getLogger(__name__)


class KernelTeamGiteaCharm(ops.CharmBase):
    """Charm for the Canonical Kernel Team's Gitea configuration."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)

        # Object for write-only Gitea configuration
        self._gitea_config = GiteaConfig('/etc/gitea/app.ini')

        # Requires PostgreSQL DB
        self.database = DatabaseRequires(self, relation_name="database", database_name="giteadb")
        self.framework.observe(self.database.on.database_created, self._on_database_created)

    def _start_gitea(self):
        """Start Gitea service"""
        logger.info("Starting Gitea service...")
        status = systemd.service_start("kteam-gitea")

        if status:
            logger.info("Gitea service started.")
        else:
            logger.info("Failed to start Gitea service.")

        return status

    def _stop_gitea(self):
        """Stop Gitea service"""
        logger.info("Stopping Gitea service...")
        status = systemd.service_stop("kteam-gitea")

        if status:
            logger.info("Gitea service stopped.")
        else:
            logger.info("Failed to stop Gitea service.")

        return status

    def _gitea_running(self):
        return systemd.service_running("kteam-gitea")

    def _on_start(self, event: ops.StartEvent):
        """Handle start event."""

        self.unit.status = ops.WaitingStatus("awaiting postgresql db")

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
    
    def _on_database_created(self, event: DatabaseCreatedEvent):
        """Handle database create event."""

        # Install generated app.ini config
        if not event.username or not event.password or not event.endpoints:
            self.unit.status = ops.BlockedStatus("Failed to configure database")
            return

        if self._gitea_running():
            self._stop_gitea()

        self._gitea_config.load()
        self._gitea_config.set_db_config(event.username, event.password,
                                         event.endpoints)
        self._gitea_config.save()

        # Start Gitea with new DB configuration
        if not self._start_gitea():
            ops.BlockedStatus("Failed to start Gitea after database config change")
        else:
            self.unit.status = ops.ActiveStatus()
    
    def _on_config_changed(self, event: ops.ConfigChangedEvent):
        if self._gitea_running():
            self._stop_gitea()

        # Load, apply changes, and save config.
        self._gitea_config.load()
        try:
            self._gitea_config.apply(self.config)
        except ValueError as e:
            msg = " ".join(e.args)
            logger.error(msg)
            self.unit.status = ops.BlockedStatus(msg)
            return
        self._gitea_config.save()

        # Open TCP port for Gitea web access
        self.unit.set_ports(self.config['gitea-server-http-port'])

        # Restart Gitea with new config
        if not self._start_gitea():
            self.unit.status = ops.BlockedStatus("Failed to start Gitea after config change")
        else:
            self.unit.status = ops.ActiveStatus()

    def _on_install(self, event: ops.InstallEvent):
        """Handle install event."""
        self.unit.status = ops.MaintenanceStatus("Begin install")

        # Fetch and verify Gitea
        BIN_URL = "https://dl.gitea.com/gitea/1.20.2/gitea-1.20.2-linux-amd64"
        BIN_NAME = os.path.basename(BIN_URL)
        self.unit.status = ops.MaintenanceStatus("Fetch and verify Gitea binary")
        subprocess.run(["wget", BIN_URL], check=True)
        subprocess.run(["wget", f"{BIN_URL}.asc"], check=True)
        subprocess.run(["gpg", "--keyserver", "keyserver.ubuntu.com",
                        "--recv", "7C9E68152594688862D62AF62D9AE806EC1592E2"],
                       check=True)
        subprocess.run(["gpg", "--verify", f"{BIN_NAME}.asc", BIN_NAME],
                       check=True)
        os.chmod(BIN_NAME, 0o775)

        # Ensure Git is installed
        self.unit.status = ops.MaintenanceStatus("Install Git")
        apt.update()
        apt.add_package("git")

        # Add 'git' user
        self.unit.status = ops.MaintenanceStatus("Configure system")
        passwd.add_user("git", None, system_user=True,
                        home_dir="/home/git", create_home=True)
        
        # Create required directories
        subprocess.run(["mkdir", "-p",
                        "/var/lib/gitea/custom",
                        "/var/lib/gitea/data",
                        "/var/lib/gitea/log",
                        "/data/gitea-storage"], check=True)
        subprocess.run(["chown", "-R", "git:git",
                        "/var/lib/gitea",
                        "/data/gitea-storage"], check=True)
        subprocess.run(["chmod", "-R", "750",
                        "/var/lib/gitea",
                        "/data/gitea-storage"], check=True)
        os.mkdir("/etc/gitea")
        shutil.chown("/etc/gitea", "root", "git")
        os.chmod("/etc/gitea", 0o770)
        
        # Install 'gitea' executable
        shutil.copy(BIN_NAME, "/usr/local/bin/gitea")

        # Configuration is installed in _on_database_created
        self._install_template("app.ini.j2", "/etc/gitea/app.ini", 0o660, "root:git")

        # Create systemd service, disabled until database available.
        self._install_template("kteam-gitea.service.j2", 
                               "/etc/systemd/system/kteam-gitea.service",
                               0o644, "root:root")
        if not systemd.daemon_reload():
            raise RuntimeError("Systemd daemon reload failed")
        if not systemd.service_resume("kteam-gitea"):
            raise RuntimeError("Failed to enable kteam-gitea service")

        self.unit.status = ops.ActiveStatus()


if __name__ == "__main__":  # pragma: nocover
    ops.main(KernelTeamGiteaCharm)  # type: ignore
