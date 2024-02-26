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

1. Build charm
Private URL: git clone https://kernel.ubuntu.com/gitea/tnt/gitea-charm.git
Public URL: git clone https://kernel.ubuntu.com/gitea/tnt-public/gitea-charm.git
```shell
git clone $URL
cd gitea-charm/charm-source
charmcraft pack
```

2. Deploy charm
```shell
juju add-model default
juju deploy ./kteam-gitea_ubuntu-22.04-amd64.charm
```

3. Integrate postgresql
```shell
juju deploy postgresql
juju integrate postgresql kteam-gitea
```

## Other resources

<!-- If your charm is documented somewhere else other than Charmhub, provide a link separately. -->

- [Read more](https://example.com)

- [Contributing](CONTRIBUTING.md) <!-- or link to other contribution documentation -->

- See the [Juju SDK documentation](https://juju.is/docs/sdk) for more information about developing and improving charms.
