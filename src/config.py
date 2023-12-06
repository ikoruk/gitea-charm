import configparser
import ops

class GiteaConfig():
    def __init__(self, path):
        self._path = path

    def load(self):
        self._config = configparser.ConfigParser(allow_no_value=True)

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
        self._config.optionxform = lambda option: option

        self._config.read(self._path)

    def apply(self, config: ops.model.ConfigData):
        # Ensure all Juju-managed properties are set correctly
        self._gitea_server_port(config)
        self._gitea_oauth2_jwt_secret(config)
        self._gitea_proxy_url(config)
        self._gitea_proxy_hosts(config)
        self._gitea_storage_dir(config)
        self._gitea_metrics_token(config)

    def save(self):
        with open(self._path, "w+") as file:
            self._config.write(file)

    def _gitea_server_port(self, config: ops.model.ConfigData):
        self._config.set('server', 'HTTP_PORT', str(config['gitea-server-port']))

    def _gitea_oauth2_jwt_secret(self, config: ops.model.ConfigData):
        key = 'gitea-oauth2-jwt-secret'
        if key in config:
            self._config.set('oauth2', 'ENABLE', 'true')
            self._config.set('oauth2', 'JWT_SECRET', config[key])
        else:
            self._config.set('oauth2', 'ENABLE', 'false')

    def _gitea_proxy_url(self, config: ops.model.ConfigData):
        self._config.set('proxy', 'PROXY_URL', config['gitea-proxy-url'])

    def _gitea_proxy_hosts(self, config: ops.model.ConfigData):
        self._config.set('proxy', 'PROXY_HOSTS', config['gitea-proxy-hosts'])

    def _gitea_storage_dir(self, config: ops.model.ConfigData):
        dir = config['gitea-storage-dir']
        self._config.set('repository', 'ROOT', f"{dir}/repos")
        self._config.set('picture', 'AVATAR_UPLOAD_PATH', f"{dir}/avatars")
        self._config.set('picture', 'REPOSITORY_AVATAR_UPLOAD_PATH', f"{dir}/repo-avatars")
        self._config.set('attachment', 'PATH', f"{dir}/attachments")
        self._config.set('packages', 'PATH', f"{dir}/packages")
        self._config.set('storage', 'PATH', f"{dir}/repo-archive")
        self._config.set('storage.packages', 'PATH', f"{dir}/packages")
        self._config.set('storage.actions_log', 'PATH', f"{dir}/actions_log")
        self._config.set('storage.actions_artifacts', 'PATH', f"{dir}/actions_artifacts")

    def _gitea_metrics_token(self, config: ops.model.ConfigData):
        key = 'gitea-metrics-token'
        if key in config:
            self._config.set('metrics', 'ENABLED', 'true')
            self._config.set('metrics', 'TOKEN', config[key])
        else:
            self._config.set('metrics', 'ENABLED', 'false')

    def set_db_config(self, username: str, password: str, host: str):
        self._config.set('database', 'NAME', "giteadb")
        self._config.set('database', 'USER', username)
        self._config.set('database', 'PASSWD', password)
        self._config.set('database', 'HOST', host)


class GiteaConfigError(RuntimeError):
    pass