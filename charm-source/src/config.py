"""Configuration management for Gitea charm"""

import configparser
import grp
import os
import pwd
import re

import ops


class GiteaConfig():
    """Used to manipulate Gitea's app.ini configuration"""

    _GITEA_LOG_LEVELS = ('Trace', 'Debug', 'Info', 'Warn', 'Error', 'Critical', 'Fatal', 'None',)
    _GITEA_PW_HASH_ALGOS = ('argon2', 'pbkdf2', 'pbkdf2_v1', 'pbkdf2_hi', 'scrypt', 'bcrypt',)
    _GITEA_REPO_UNITS = ('repo.code', 'repo.releases', 'repo.issues', 'repo.ext_issues', 'repo.pulls', 'repo.wiki', 'repo.ext_wiki', 'repo.projects', 'repo.packages', 'repo.actions',)
    _GITEA_STORAGE_TYPES = ('local', 'minio',)

    def __init__(self, path):
        self._path = path

        # Not yet loaded
        self._ini = None

        self._options = [
            # [DEFAULT]

            # [server]
            DirectOption(self, 'gitea-server-http-port',
                         'server', 'HTTP_PORT',
                         DirectOption.apply_non_empty_or_remove),
            DirectOption(self, 'gitea-server-protocol',
                         'server', 'PROTOCOL',
                         DirectOption.apply_allowed,
                         ['http', 'https', 'http+unix', 'fcgi', 'fcgi+unix']),
            DirectOption(self, 'gitea-server-domain',
                         'server', 'DOMAIN',
                         DirectOption.apply_non_empty_or_remove),
            DirectOption(self, 'gitea-server-root-url',
                         'server', 'ROOT_URL',
                        DirectOption.apply_non_empty_or_remove),
            DirectOption(self, 'gitea-server-static-url-prefix',
                         'server', 'STATIC_URL_PREFIX',
                         DirectOption.apply_non_empty_or_remove),
            DirectOption(self, 'gitea-server-ssh-domain',
                         'server', 'SSH_DOMAIN',
                         DirectOption.apply_non_empty_or_remove),

            # [database]

            # [security]

            # [oauth2]

            # [log]
            DirectOption(self, 'gitea-log-level',
                         'log', 'LEVEL',
                         DirectOption.apply_allowed,
                         GiteaConfig._GITEA_LOG_LEVELS,
                         allow_empty=False),

            # [git.timeout]

            # [service]

            # [repository]
            DirectOption(self, 'gitea-repository-max-creation-limit',
                         'repository', 'MAX_CREATION_LIMIT',
                         DirectOption.apply_non_empty_or_remove),

            # [repository.upload]

            # [repository.pull-request]

            # [repository.signing]

            # [ui]

            # [admin]

            # [openid]

            # [webhook]

            # [mailer]
            DirectOption(self, 'gitea-mailer-user',
                         'mailer', 'USER',
                         DirectOption.apply_non_empty_or_remove),
            DirectOption(self, 'gitea-mailer-passwd',
                         'mailer', 'PASSWD',
                         DirectOption.apply_non_empty_or_remove),
            DirectOption(self, 'gitea-mailer-from',
                         'mailer', 'FROM',
                         DirectOption.apply_non_empty_or_remove),
            DirectOption(self, 'gitea-mailer-smtp-addr',
                         'mailer', 'SMTP_ADDR',
                         DirectOption.apply_non_empty_or_remove),
            DirectOption(self, 'gitea-mailer-smtp-port',
                         'mailer', 'SMTP_PORT',
                         DirectOption.apply_non_empty_or_remove),
            DirectOption(self, 'gitea-mailer-protocol',
                         'mailer', 'PROTOCOL',
                         DirectOption.apply_non_empty_or_remove),

            # [session]
            DirectOption(self, 'gitea-session-provider',
                         'session', 'PROVIDER',
                         DirectOption.apply_non_empty_or_remove),

            # [picture]

            # [attachment]

            # [cron.repo_health_check]

            # [cron.update_checker]

            # [metrics]
            DirectOption(self, 'gitea-metrics-token',
                         'metrics', 'TOKEN',
                         DirectOption.apply_non_empty_or_remove),

            # [packages]

            # [storage]

            # [storage.repo-archive]

            # [storage.packages]

            # [proxy]
            DirectOption(self, 'gitea-proxy-proxy-enabled',
                         'proxy', 'PROXY_ENABLED',
                         DirectOption.apply_non_empty_or_remove),
            DirectOption(self, 'gitea-proxy-proxy-url',
                         'proxy', 'PROXY_URL',
                         DirectOption.apply_non_empty_or_remove),
            DirectOption(self, 'gitea-proxy-proxy-hosts',
                         'proxy', 'PROXY_HOSTS',
                         DirectOption.apply_non_empty_or_remove),

            # [actions]

            # [storage.actions_log]

            # [storage.actions_artifacts]

        ]

    def load(self):
        """Load config from .ini file"""

        self._ini = configparser.ConfigParser(allow_no_value=True)

        # Hack to add an initial [DEFAULT] that ConfigParser expects
        # Gitea likes to remove this.
        # TODO: replace this with something more elegant
        lines = []
        with open(self._path, "r") as readfile:
            lines.extend(readfile)
        if not lines or lines[0] != "[DEFAULT]\n":
            lines.insert(0, "[DEFAULT]\n")
        with open(self._path, "w") as writefile:
            writefile.writelines(lines)

        # do not transform keys to lower-case
        self._ini.optionxform = lambda option: option

        self._ini.read(self._path)

    def apply(self, config: ops.model.ConfigData):
        """Set Juju-managed Gitea parameters from Juju config"""
        # Ensure all Juju-managed properties are set correctly
        for opt in self._options:
            opt.apply(config)

    def save(self):
        """Write app.ini file"""
        with open(self._path, "w+") as file:
            self._ini.write(file)

    def ensure_section(self, section: str):
        """Ensure section exists in Gitea config"""
        if not self._ini.has_section(section):
            self._ini.add_section(section)

    def set(self, ini_sect: str, ini_key: str, val: str):
        """Set Gitea config, allow 'default' to be used for DEFAULT section"""
        if ini_sect.lower() == "default":
            ini_sect = self._ini.default_section

        self._ini.set(ini_sect, ini_key, val)

    def remove(self, ini_sect: str, ini_key: str):
        return self._ini.remove_option(ini_sect, ini_key)

    def set_db_config(self, username: str, password: str, host: str):
        """Set database-related Gitea options"""
        self.set('database', 'DB_TYPE', 'postgres')
        self.set('database', 'SCHEMA', '')
        self.set('database', 'NAME', "giteadb")
        self.set('database', 'USER', username)
        self.set('database', 'PASSWD', password)
        self.set('database', 'HOST', host)

class Option:
    """Base Option class"""

    def __init__(self, gitea_conf: GiteaConfig):
        self._gitea_conf = gitea_conf

    def apply(self, config: ops.model.ConfigData):
        pass

class DirectOption(Option):
    """An option that directly maps a Juju param to a Gitea param"""

    def __init__(self, gitea_conf: GiteaConfig, juju_key, ini_sect, ini_key, apply, *args, **kwargs):
        """Used to declare a Juju configuration parameter that directly maps to
           a Gitea config parameter.

           Arguments:
           gitea_conf -- The GiteaConfig object this Option is used in.
           juju_key -- The key string for the Juju config option.
           ini_sect -- The section string for the Gitea config option.
           ini_key -- The key string for the Gitea config option.
           apply -- An apply_* function from this class to handle setting and validation.
           *args -- Additional arguments to pass to the selected apply_* function.
           **kwargs -- Additional keyword arguments to pass to the selected apply_* function.
        """
        super().__init__(gitea_conf)

        self._juju_key = juju_key
        self._ini_sect = ini_sect
        self._ini_key = ini_key
        self._apply = apply
        self._args = args
        self._kwargs = kwargs

    def apply(self, config: ops.model.ConfigData):
        try:
            self._apply(self, config, *self._args, **self._kwargs)
        except Exception as err:
            raise ValueError(f"Value for config '{self._juju_key}' is invalid") from err

    def _get(self, config: ops.model.ConfigData, allow_empty=False):
        if self._juju_key not in config or not config[self._juju_key]:
            if allow_empty:
                return ""
            raise ValueError("Option is unset, but must be set.")

        return str(config[self._juju_key])

    def _set(self, value, remove_if_empty=True):
        self._gitea_conf.ensure_section(self._ini_sect)

        if not value and remove_if_empty:
            self._gitea_conf.remove(self._ini_sect, self._ini_key)
        else:
            self._gitea_conf.set(self._ini_sect, self._ini_key, value)

    def _matches_any(self, patterns, string):
        for pattern in patterns:
            if re.fullmatch(pattern, string):
                return True
        return False

    def apply_allowed(self, config: ops.model.ConfigData, allowed,
                      allow_empty=True, remove_if_empty=True):
        """Raise an error if supplied value is not in allowlist"""
        value = self._get(config, allow_empty)
        if not self._matches_any(allowed, value):
            raise ValueError(f"'{value}' not in {allowed}.")

        self._set(value, remove_if_empty)

    def apply_multi_allowed(self, config: ops.model.ConfigData, allowed,
                            allow_empty=True, remove_if_empty=True):
        """
        Raise an error if the supplied value is not a comma separated list of
        options from 'allowed'.
        """
        value = self._get(config, allow_empty)

        if value:
            for opt in value.split(','):
                opt = opt.strip()
                if not self._matches_any(allowed, opt):
                    raise ValueError(f"'{opt} not in {allowed}")

        self._set(value, remove_if_empty)

    def apply_any(self, config: ops.model.ConfigData):
        """Accept any supplied string, including an empty string"""
        self.apply_allowed(config, [r".*"], allow_empty=True,
                           remove_if_empty=False)

    def apply_non_empty(self, config: ops.model.ConfigData):
        """Raise an error if the provided value is an empty string"""
        self.apply_allowed(config, [r".*"], allow_empty=False,
                           remove_if_empty=False)

    def apply_non_empty_or_remove(self, config: ops.model.ConfigData):
        """Set the value if it is non-empty, else remove it from the ini"""
        self.apply_allowed(config, [r".*"], allow_empty=True,
                           remove_if_empty=True)

class PathOption(DirectOption):
    """A DirectOption option that specifies a path"""

    def __init__(self, gitea_conf: GiteaConfig, juju_key, ini_sect, ini_key,
                 mode=0o750, owner="git:git"):
        """Used to declare a Juju configuration parameter that directly maps to
            a Gitea config parameter.

            Arguments:
            gitea_conf -- The GiteaConfig object this Option is used in.
            juju_key -- The key string for the Juju config option.
            ini_sect -- The section string for the Gitea config option.
            ini_key -- The key string for the Gitea config option.
            mode -- Mode of the created directory.
            owner -- Owner of the created directory.
        """
        super().__init__(gitea_conf, juju_key, ini_sect, ini_key, None)

        self._mode = mode

        usr_grp = owner.split(":")
        self._unam = usr_grp[0]
        self._gnam = usr_grp[1]

    def apply(self, config: ops.model.ConfigData):
        self.apply_non_empty_or_remove(config)

        # Ensure directory exists
        path = self._get(config, allow_empty=True)
        if path:
            os.makedirs(path, self._mode, exist_ok=True)
            uid = pwd.getpwnam(self._unam).pw_uid
            gid = grp.getgrnam(self._gnam).gr_gid
            os.chown(path, uid, gid)
