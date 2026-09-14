# ansible-sensorfleet

Ansible project for provisioning and configuring SensorFleet hosts: **fleet management (`fleetmgmt`)** servers and **sensor (`sensors`)** hosts. It is a standalone repository (not a submodule of anything else).

Licensed under the MIT License — see [`LICENSE.md`](LICENSE.md) (Copyright (c) 2026 SensorFleet Oy).

## Prerequisites

- **Ansible 2.10.8 or newer** as the supported minimum. This is a floor, not a target — see [`AGENTS.md`](AGENTS.md) for the full version-constraint rationale (avoid relying on anything introduced after 2.10.8).
- The full `ansible` community package on the control node (not bare `ansible-core`). Roles use modules from bundled collections such as `ansible.posix`, and there is deliberately no `requirements.yml` — the assumption is that the full package already provides what's needed.
- Python 3 on target hosts (`interpreter_python = /usr/bin/python3`, set in [`ansible.cfg`](ansible.cfg)).
- A local `.venv` (gitignored) is the supported way to get a pinned Ansible + `ansible-lint`. Activate it before running any command below:

  ```bash
  source .venv/bin/activate
  ```

## Repository layout

```
ansible.cfg           # roles_path, interpreter_python
playbooks/             # top-level playbooks (flat directory)
roles/                 # sensorfleet_<component> roles
inventories/
  example/              # checked-in example inventory (starting-point template)
  devel/                # local/gitignored real dev inventory (never committed)
docs/
  VARIABLES.md           # reference for every role's configurable variables
tools/migrate/          # standalone inventory-variable migration tool (own README)
AGENTS.md / CLAUDE.md   # conventions and guidance for AI coding agents
LICENSE.md              # MIT license
```

## Inventory setup

Every inventory has exactly two groups:

- **`fleetmgmt`** — normally a single host, the fleet management server.
- **`sensors`** — one or more sensor hosts managed by that fleet management server.

[`inventories/example/hosts.yml`](inventories/example/hosts.yml) is the checked-in starting-point template — copy it as the basis for a new environment (it is not meant to be run against directly):

```yaml
all:
  vars:
    sensorfleet_openvpn_server_connect_ip: 192.168.0.10   # address sensors dial to reach the FM's OpenVPN server
    ansible_user: root
  children:
    fleetmgmt:
      hosts:
        fleetmanagement:
          ansible_host: 192.168.0.10
          sensorfleet_openvpn_client_ip: 169.254.255.255   # this host's address inside the OpenVPN tunnel
    sensors:
      hosts:
        sensor001:
          ansible_host: 192.168.1.101
          sensorfleet_openvpn_client_ip: 169.254.1.1
```

`inventories/devel/` is the local, gitignored inventory used for real development/test targets (hosts, `group_vars`, cached PKI material, generated credentials). It is never committed — see `.gitignore`. Role-specific configuration on top of the defaults documented in [`docs/VARIABLES.md`](docs/VARIABLES.md) is set the same way: inventory `hosts.yml` vars, or `group_vars`/`host_vars` files alongside it.

Migrating an inventory that already uses the legacy SensorFleet variable naming scheme? Use the standalone tool in [`tools/migrate/`](tools/migrate/README.md) instead of hand-writing a new one.

## Usage — running playbooks

Validate an inventory before running anything against it:

```bash
ansible-inventory -i inventories/devel/hosts.yml --list
```

### `playbooks/sensorfleet.yml` — main provisioning playbook

The main, recurring provisioning play. Targets `fleetmgmt:sensors` and runs every role in sequence.

```bash
ansible-playbook -i inventories/devel/hosts.yml playbooks/sensorfleet.yml
```

`sensorfleet_globals` and `sensorfleet_sanity_checks` always run (tagged `always`); every other role is tagged with its own short name (`mounts`, `internal_certificates`, `openvpn`, `system_cacerts`, `repos`, `services_ntp`, `kernel`, `sysctl`, `system`, `logging`, `ssh`, `nginx`, `fleetgram`, `firewall`, `config`, `usermgmt`, `license`, `instruments`), so a subset can be applied with `--tags`/`--skip-tags`, e.g.:

```bash
ansible-playbook -i inventories/devel/hosts.yml playbooks/sensorfleet.yml --tags firewall,ssh
```

### `playbooks/prepare_ubuntu.yml` — bootstrap a fresh Ubuntu 22.04 host

Run once, before the first `sensorfleet.yml` run, on a fresh Ubuntu install: upgrades/purges packages, sets up base mounts and certificates/VPN, and installs the role-specific package. It's guarded to skip hosts that are already bootstrapped, unless explicitly forced.

When creating a new sensor network using the prepare ubuntu playbooks it is required to create and fully provision the Fleet Management VM first. Proper ordering is:

1. Create Fleet Management VM with Ubuntu 22.04 installed on it (FM-VM)
2. Run sensorfleet_prepare_ubuntu playbook on the FM-VM
3. Run sensorfleet playbook on the FM-VM
4. Create sensor(s) VM(s) if desired with Ubuntu 22.04 on them (S-VMs)
5. Run sensorfleet_prepare_ubuntu playbook on the S-VMs
6. Run sensorfleet playbook on S-VMs (or without any limit)

```bash
ansible-playbook -i inventories/devel/hosts.yml playbooks/prepare_ubuntu.yml
```

### `playbooks/migrate_legacy_ansible.yml` — migrate off the legacy Ansible setup

Transition path for a host previously managed by the legacy Ansible project. Two phases: migrate legacy files forward (default), then remove them once the new setup is verified working (`sensorfleet_ansible_migrate_cleanup` is tagged `[cleanup, never]`, so it only runs when explicitly requested). See [`tools/migrate/README.md`](tools/migrate/README.md)'s "Migration notes" section for the full runbook (order of operations, verification steps, reboot).

```bash
ansible-playbook -i inventories/devel/hosts.yml playbooks/migrate_legacy_ansible.yml
ansible-playbook -i inventories/devel/hosts.yml playbooks/sensorfleet.yml
ansible-playbook -i inventories/devel/hosts.yml playbooks/migrate_legacy_ansible.yml --tags cleanup
```

### `playbooks/reboot.yml` — reboot hosts

Trivial helper: a single `ansible.builtin.reboot` task against `fleetmgmt:sensors`.

```bash
ansible-playbook -i inventories/devel/hosts.yml playbooks/reboot.yml
```

## Roles overview

Provisioning roles, in the order `sensorfleet.yml` runs them. See [`docs/VARIABLES.md`](docs/VARIABLES.md) for every variable each role accepts.

| Role | Purpose | Variables |
|---|---|---|
| `sensorfleet_globals` | Shared defaults consumed by other roles (retry counts/delays, grsec kernel flag, FM repo service flag); defines no tasks of its own. | [→](docs/VARIABLES.md#sensorfleet_globals) |
| `sensorfleet_sanity_checks` | Asserts system hostname matches the inventory hostname, checks clock skew against the controller, and waits out any apt lock before proceeding. | [→](docs/VARIABLES.md#sensorfleet_sanity_checks) |
| `sensorfleet_mounts` | Sets up `/mnt/transient-data` (tmpfs) and `/mnt/persistent-data`. | — (no configurable variables) |
| `sensorfleet_internal_certificates` | Manages internal TLS material and CSRs under `/etc/sensorfleet/tls/internal` and `/etc/sensorfleet/csr`. | [→](docs/VARIABLES.md#sensorfleet_internal_certificates) |
| `sensorfleet_openvpn` | Configures OpenVPN client/server material under `/etc/sensorfleet/openvpn` and `/etc/openvpn`. | [→](docs/VARIABLES.md#sensorfleet_openvpn) |
| `sensorfleet_system_cacerts` | Manages `ca-certificates` debconf settings and custom CA certificates. | [→](docs/VARIABLES.md#sensorfleet_system_cacerts) |
| `sensorfleet_repos` | Installs the SensorFleet apt GPG key; configures FM-relayed or direct apt repository access. | [→](docs/VARIABLES.md#sensorfleet_repos) |
| `sensorfleet_services_ntp` | Configures time sync: chrony on `fleetmgmt`, systemd-timesyncd on `sensors`. | [→](docs/VARIABLES.md#sensorfleet_services_ntp) |
| `sensorfleet_kernel` | Installs `linux-fleet`/`linux-fleet-grsec` kernel packages and disables selected kernel modules. | [→](docs/VARIABLES.md#sensorfleet_kernel) |
| `sensorfleet_sysctl` | Applies merged sysctl defaults, optional grsec overrides, and user overrides. | [→](docs/VARIABLES.md#sensorfleet_sysctl) |
| `sensorfleet_system` | General system hardening: package installation, root password, auth-import lockdown, journald/shell/sudo/lxd configuration. | [→](docs/VARIABLES.md#sensorfleet_system) |
| `sensorfleet_logging` | Configures remote loghost forwarding over TCP/UDP/TLS via syslog-ng. | [→](docs/VARIABLES.md#sensorfleet_logging) |
| `sensorfleet_ssh` | Installs `sshd_config` (validated with `sshd -t`) and the SSH login banner. | [→](docs/VARIABLES.md#sensorfleet_ssh) |
| `sensorfleet_nginx` | Installs the nginx vhost SSL certificate/key for the sensor UI. | [→](docs/VARIABLES.md#sensorfleet_nginx) |
| `sensorfleet_fleetgram` | Manages the fleetgram index config and initial sensor config sync via the `fleet config` CLI. | [→](docs/VARIABLES.md#sensorfleet_fleetgram) |
| `sensorfleet_firewall` | Manages `ferm` firewall rules under `/etc/ferm/ferm.d`. | [→](docs/VARIABLES.md#sensorfleet_firewall) |
| `sensorfleet_config` | Reads, merges/replaces, and writes back `fleet config` via the `fleet` CLI. | [→](docs/VARIABLES.md#sensorfleet_config) |
| `sensorfleet_usermgmt` | Creates the initial admin account on `fleetmgmt` hosts via the `fleet` CLI. | [→](docs/VARIABLES.md#sensorfleet_usermgmt) |
| `sensorfleet_license` | Installs a base64-decoded license file to `/etc/sensorfleet/license.json`. | [→](docs/VARIABLES.md#sensorfleet_license) |
| `sensorfleet_instruments` | Manages instrument configuration (e.g. netflow) via `fleet config`. | [→](docs/VARIABLES.md#sensorfleet_instruments) |

Bootstrap and migration roles, used only by `prepare_ubuntu.yml` and `migrate_legacy_ansible.yml`:

| Role | Purpose | Variables |
|---|---|---|
| `sensorfleet_prepare_ubuntu` | One-time bootstrap of a fresh Ubuntu install: upgrades packages, installs the required base package set, purges unneeded ones, reboots if needed. Skips already-bootstrapped hosts unless forced. | [→](docs/VARIABLES.md#sensorfleet_prepare_ubuntu) |
| `sensorfleet_prepare_role` | Installs the role-specific package (`sensorfleet-fm` on `fleetmgmt`, `sensorfleet-sensor` on `sensors`). | — (no configurable variables) |
| `sensorfleet_ansible_migrate` | Copies/adapts files left over from the legacy Ansible setup (e.g. `ta.key`) forward to their new locations. | — (no configurable variables) |
| `sensorfleet_ansible_migrate_cleanup` | Removes the legacy files once the migration is verified. Only runs with `--tags cleanup`. | — (no configurable variables) |

## Conventions & contributing

Full contributor/agent-facing conventions live in [`AGENTS.md`](AGENTS.md) — read it before making changes. In short:

- Every role is named `sensorfleet_<component>`, and every role variable is prefixed with its role's name (`sensorfleet_<component>_*`).
- Roles that behave differently on `fleetmgmt` vs. `sensors` hosts dispatch to separate `fm.yml`/`sensor.yml` task files, gated on `when: "'fleetmgmt' in group_names"`.
- **`ansible-lint --profile production` is the acceptance bar for every change** to a role or playbook:

  ```bash
  ansible-lint --profile production roles/<role>
  ```

## License

MIT — Copyright (c) 2026 SensorFleet Oy. See [`LICENSE.md`](LICENSE.md).
