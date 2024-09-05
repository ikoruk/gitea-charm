<!--
Avoid using this README file for information that is maintained or published elsewhere, e.g.:

* metadata.yaml > published on Charmhub
* documentation > published on (or linked to from) Charmhub
* detailed contribution guide > documentation or CONTRIBUTING.md

Use links instead.
-->

# Gitea for Canonical Kernel Team

Charmhub package name: operator-template
More information: https://charmhub.io/gitea-charm

Deploys Gitea for the Canonical Kernel Team.

So far this charm:
- Installs Gitea 1.20.2 binary from dl.gitea.com
- Installs required directories and systemd service.
- Installs the configuration from KERNTT-691 with database values set as required to work with the postgresql charm.

## Building and deploying

1. Clone charm repo
Private URL: git clone https://kernel.ubuntu.com/gitea/tnt/gitea-charm.git
Public URL: git clone https://kernel.ubuntu.com/gitea/tnt-public/gitea-charm.git
```shell
git clone $URL $REPO_DIR
```

2. Build main charm
```shell
cd $REPO_DIR/charm-source
charmcraft pack
```

3. Build runner
```shell
cd $REPO_DIR/runner-charm-source
charmcraft pack
```

4. Obtain Gitea binary
This can be done by building it yourself or downloading it elsewhere.
The binary should be placed with the path `$REPO_DIR/gitea`.

5. Create model
```shell
juju add-model default
```

6. Deploy charms

    a. Deploy charm
    ```shell
    juju deploy $REPO_DIR/charm-source/kteam-gitea_ubuntu-22.04-amd64.charm --resource gitea-binary=$REPO_DIR/gitea
    ```

    b. Deploy runner
    ```shell
    juju deploy $REPO_DIR/runner-charm-source/kteam-gitea-runner_ubuntu-22.04-amd64.charm
    ```

    c. Integrate postgresql
    ```shell
    juju deploy postgresql
    juju integrate postgresql kteam-gitea
    ```

## Other resources

<!-- If your charm is documented somewhere else other than Charmhub, provide a link separately. -->

- [Read more](https://example.com)

- [Contributing](CONTRIBUTING.md) <!-- or link to other contribution documentation -->

- See the [Juju SDK documentation](https://juju.is/docs/sdk) for more information about developing and improving charms.
