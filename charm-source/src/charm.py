#!/usr/bin/env python3
# Copyright 2023 Ubuntu
# See LICENSE file for licensing details.

"""Charm for the Canonical Kernel Team's Gitea configuration."""

import sys
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

class ResourceBaseException(ops.ModelError):
    status_type = ops.BlockedStatus
    status_message = "Resource error"

    def __init__(self, msg):
        self.msg = msg
        self.status = self.status_type(
            "{}: {}".format(self.status_message, self.msg)
        )

class MissingResourceError(ResourceBaseException):
    pass

class InstallResourceError(ResourceBaseException):
    pass

class KernelTeamGiteaCharm(ops.CharmBase):
    """Charm for the Canonical Kernel Team's Gitea configuration."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)

        # Object for write-only Gitea configuration
        self._gitea_config = GiteaConfig('/etc/gitea/conf/app.ini')

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

    def _gitea_resource(self):
        '''
         Ensure to provide the gitea binary resource
         juju deploy ./kteam-gitea --resource gitea-binary=/path_to_gitea_binary
         This method should only check if the gitea resource is present.
         '''
        try:
            resource_path = self.model.resources.fetch("gitea-binary")
        except ops.ModelError as e:
            logger.error(e)
            return
        except NameError as e:
            logger.error(e)
            return
        return resource_path

    def _gitea_install_resource(self):
        '''
        # Install 'gitea' executable
        '''
        resource_path = self.model.resources.fetch("gitea-binary")

        try:
            os.chmod(resource_path, 0o775)
            shutil.copy(resource_path, "/usr/local/bin/gitea")
        # This should not trigger an exception, but anything can happen.
        # If it does, that's really bad
        except Exception as e:
            raise

        return True

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
            self.unit.status = ops.BlockedStatus("Failed to start Gitea after database config change")
        else:
            self.unit.status = ops.ActiveStatus("Gitea Running")
    
    def _on_config_changed(self, event: ops.ConfigChangedEvent):
        """ Do these things on a model config changes"""
        # Regardless of what is done, gitea should be stopped.
        if self._gitea_running():
            self._stop_gitea()

        # Check the loaded gitea binary resource, update it.
        # This should probably only update if the hash sums differ
        if not self._gitea_resource():
            self.unit.status = ops.BlockedStatus(
                "Something went wrong when claiming resource 'gitea-binary; "
                "run `juju debug-log` for more info'"
            )
            return


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
            self.unit.status = ops.ActiveStatus("Gitea Running")

    def _gitea_required_directories(self) -> bool:
        """ These are the required directories for Gitea to install correctly
        """
        # Create required directories
        try:
            subprocess.run(["mkdir", "-p",
                            "/var/lib/gitea/custom",
                            "/var/lib/gitea/data",
                            "/var/lib/gitea/log",
                            "/data/gitea-storage",
                            "/etc/gitea/conf"], check=True)

            subprocess.run(["chown", "-R", "git:git",
                            "/var/lib/gitea/custom",
                            "/var/lib/gitea/data",
                            "/var/lib/gitea/log",
                            "/data/gitea-storage"], check=True)

            subprocess.run(["chmod", "-R", "750",
                            "/var/lib/gitea/custom",
                            "/var/lib/gitea/data",
                            "/var/lib/gitea/log",
                            "/data/gitea-storage"], check=True)

            subprocess.run(["chown", "-R", "root:git",
                            "/etc/gitea/conf"], check=True)

            subprocess.run(["chmod", "-R", "770",
                            "/etc/gitea/conf"], check=True)

        except CalledProcessError as e:
            logger.error(e)
            return
        return True

    def _on_upgrade_charm(self, event: ops.UpgradeCharmEvent):
        """Handle upgrade event.
           An Upgrade Event simply upgrades the resource
        """

        self.unit.status = ops.MaintenanceStatus("Upgrading Charm")

        # First Stop Gitea
        if self._gitea_running():
            self._stop_gitea()

        # Call the gitea resource, check to see if it exists, install it.
        # If not, We want to HARD STOP here.
        if not self._gitea_resource():
            raise MissingResourceError("Failure to Locate Resource")

        if not self._gitea_install_resource():
            raise InstallResourceError("Failure to Install Resource")

        # Start Gitea
        if not self._start_gitea():
            self.unit.status = ops.BlockedStatus("Failed to start Gitea after upgrade")
        else:
            self.unit.status = ops.ActiveStatus("Gitea Running")

    def _on_install(self, event: ops.InstallEvent):
        """Handle install event."""
        self.unit.status = ops.MaintenanceStatus("Begin install")

        # These need to be broken into separate private methods so that, if a
        # failure occurs, it will pause juju correctly.

        # Call the gitea resource, check to see if it exists, install it.
        # If not, We want to HARD STOP here.
        if not self._gitea_resource():
            raise MissingResourceError("Failure to Locate Resource")

        if not self._gitea_install_resource():
            raise InstallResourceError("Failure to Install Resource")

        # Ensure Git is installed
        self.unit.status = ops.MaintenanceStatus("Install Git")
        apt.update()
        apt.add_package("git")

        # Add 'git' user
        self.unit.status = ops.MaintenanceStatus("Configure system")
        passwd.add_user("git", None, system_user=True,
                        home_dir="/home/git", create_home=True)
        
        if not self._gitea_required_directories():
            self.unit.status = ops.BlockedStatus("Error Creating Required Charm Directories")
            raise RuntimeError("Systemd daemon reload failed")

        #################################################################
        # IMPORTANT
        # These remaining steps need to be wrapped in try/excepts
        # and set ops.BlockedStatus if they fail
        #################################################################
        # Configuration is installed in _on_database_created
        self._install_template("app.ini.j2", "/etc/gitea/conf/app.ini", 0o660, "root:git")

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
