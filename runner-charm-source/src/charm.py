#!/usr/bin/env python3
# Copyright 2024 Ubuntu
# See LICENSE file for licensing details.

"""Charm the application."""

import logging
import os
import subprocess
import shutil

from jinja2 import Template
import ops

from charms.operator_libs_linux.v0 import (
    apt,
    passwd,
    systemd,
)

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

class GiteaRunnerCharm(ops.CharmBase):
    """Charm the application."""

    _stored = ops.StoredState()

    def __init__(self, *args):
        super().__init__(*args)

        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.update_status, self._on_update_status)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)
        self.framework.observe(self.on.register_action, self._on_register_action)

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

        # Check for act_runner resource
        if not self._runner_resource():
            self.unit.status = ops.BlockedStatus(
                "Something went wrong when claiming resource 'act-runner'; "
                "run `juju debug-log` for more info"
            )
            return

        self._start_runner()
        self.unit.status = ops.ActiveStatus()

    def _on_update_status(self, event: ops.UpdateStatusEvent):
        if self._is_running():
            self.unit.status = ops.ActiveStatus()
        else:
            self._error("Failed to start runner service. Has a runner token been registered?")

    def _on_upgrade_charm(self, event: ops.UpgradeCharmEvent):
        # First Stop runner
        if self._is_running():
            self._stop_runner()

        # Call the runner resource, check to see if it exists, install it.
        # If not, We want to HARD STOP here.
        if not self._runner_resource():
            raise MissingResourceError("Failure to Locate Resource")

        if not self._runner_install_resource():
            raise InstallResourceError("Failure to Install Resource")

        # Start runner
        if not self._start_runner():
            self.unit.status = ops.BlockedStatus("Failed to start runner after upgrade")
        else:
            self.unit.status = ops.ActiveStatus("Runner Running")

    def _runner_resource(self):
        '''
        Ensure to provide the act runner resource
        juju deploy ./kteam-gitea-runner --resource runner-binary=/path_to_act_runner_binary
        This method should only check if the act runner resource is present.
        '''
        try:
            resource_path = self.model.resources.fetch("runner-binary")
        except ops.ModelError as e:
            logger.error(e)
            return
        except NameError as e:
            logger.error(e)
            return
        return resource_path

    def _runner_install_resource(self):
        '''
        # Install 'act_runner' executable
        '''
        resource_path = self.model.resources.fetch("runner-binary")

        try:
            os.chmod(resource_path, 0o775)
            shutil.copy(resource_path, "/usr/local/bin/act_runner")
        # This should not trigger an exception, but anything can happen.
        # If it does, that's really bad
        except Exception as e:
            raise

        return True

    def _on_install(self, event: ops.InstallEvent):
        self.unit.status = ops.MaintenanceStatus("Begin install")

        # Call the runner resource, check to see if it exists, install it.
        # If not, We want to HARD STOP here.
        if not self._runner_resource():
            raise MissingResourceError("Failure to Locate Resource")

        if not self._runner_install_resource():
            raise InstallResourceError("Failure to Install Resource")

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

        # Generate config.yaml
        self.unit.status = ops.MaintenanceStatus("Configuring system")
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

    def _on_register_action(self, event: ops.ActionEvent):
        """Handle register action."""

        # First Stop runner
        if self._is_running():
            self._stop_runner()

        self.unit.status = ops.MaintenanceStatus("Registering runner")

        os.chdir("/var/lib/act_runner")
        try:
            # run as act_runner
            subprocess.run(
                [
                    "sudo",
                    "-u",
                    "act_runner",
                    "/usr/local/bin/act_runner",
                    "--config",
                    "/etc/act_runner/config.yaml",
                    "register",
                    "--no-interactive",
                    "--instance",
                    event.params["gitea-instance-url"],
                    "--token",
                    event.params["gitea-instance-token"],
                    "--name",
                    event.params["gitea-runner-name"],
                    "--labels",
                    event.params["gitea-runner-labels"],
                ],
                check=True,
                capture_output=True,
            )
            event.set_results({"result": "success"})
        except subprocess.CalledProcessError as e:
            event.fail(
                f"Failed to register runner. Output was:\n{e.stderr}"
            )

        # Start Runner
        if not self._start_runner():
            self.unit.status = ops.BlockedStatus("Failed to start runner after upgrade")
        else:
            self.unit.status = ops.ActiveStatus("Runner Running")

if __name__ == "__main__":  # pragma: nocover
    ops.main(GiteaRunnerCharm)  # type: ignore
