<!--
Avoid using this README file for information that is maintained or published elsewhere, e.g.:

* metadata.yaml > published on Charmhub
* documentation > published on (or linked to from) Charmhub
* detailed contribution guide > documentation or CONTRIBUTING.md

Use links instead.
-->

# Gitea Runner for Canonical Kernel Team

Charmhub package name: operator-template
More information: https://charmhub.io/runner-charm-source

Deploys Gitea act_runner for the Canonical Kernel Team.

## Buildling and deploying

1. Build charm
Private URL: git clone https://kernel.ubuntu.com/gitea/tnt/gitea-charm.git
Public URL: git clone https://kernel.ubuntu.com/gitea/tnt-public/gitea-charm.git
```shell
git clone $URL
cd gitea-charm/runner-charm-source
charmcraft pack
```

2. Deploy charm
```shell
juju deploy ./kteam-gitea-runner_ubuntu-22.04-amd64.charm --resource runner-binary=<path_to_act_runner_binary>
```

3. Generate runner token via Gitea Web UI

4. Register the act_runner token:
```shell
juju run $MACHINE register gitea-instance-url=$INSTANCE_URL gitea-instance-token=$INSTANCE_TOKEN gitea-runner-name=$RUNNER_NAME gitea-runner-labels=$RUNNER_LABELS
```

## Other resources

<!-- If your charm is documented somewhere else other than Charmhub, provide a link separately. -->

- [Read more](https://example.com)

- [Contributing](CONTRIBUTING.md) <!-- or link to other contribution documentation -->

- See the [Juju SDK documentation](https://juju.is/docs/sdk) for more information about developing and improving charms.
