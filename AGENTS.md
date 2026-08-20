# AGENTS.md

This file provides guidance to AI coding agents working with code in this repository.

## Repository state

`ansible-sensorfleet` is an Ansible project for SensorFleet, and is its own git repository (not a submodule of anything). Current state:

- `ansible.cfg` is configured (`roles_path = roles`, `interpreter_python = /usr/bin/python3`).
- `inventories/example/hosts.yml` is a checked-in example inventory (a small fleetmgmt host + a few sensors) intended as a starting point, not a real deployment target.
- `inventories/devel/` holds real local/developer inventory data (hosts, group_vars, cached PKI material, generated credentials) and is excluded from git via `.gitignore` (`/inventories/devel`) — never expect it to be committed or shared.
- `roles/` contains many roles, all named `sensorfleet_<component>` (see `ls roles/` for the current set).
- `playbooks/` contains `sensorfleet.yml` (main provisioning play, `hosts: fleetmgmt:sensors`), `prepare_ubuntu.yml`, and `migrate_legacy_ansible.yml`.
- `tools/migrate/` contains a standalone Python inventory-variable migration tool (see below).
- A local `.venv` (gitignored) provides Ansible and `ansible-lint` for authoring/testing. This is controller-side tooling only — it does not change the version constraint below, which governs what roles/playbooks may target.

## Version constraint

This project targets **Ansible 2.10.8 as the minimum supported version**. Avoid modules, plugins, and syntax features introduced after that release — check module `version_added` in the Ansible docs before using anything that feels new, and prefer constructs compatible with 2.10 over newer idioms.

## Module constraints

Target hosts are assumed to have the full `ansible` community package installed (not just `ansible-core`), so modules from collections it bundles — e.g. `ansible.posix` (`ansible.posix.mount`, etc.) — are fair game. Don't add a `requirements.yml` or pull in collections via `ansible-galaxy collection install` beyond what ships in that bundle.

## Structure and conventions

- `roles/` — every role is named `sensorfleet_<component>` and role variables are always prefixed with the role name (required for `ansible-lint`'s `production` profile). When a role needs different behavior on fleetmgmt hosts vs. sensor hosts, the established pattern is a group-gated include in `tasks/main.yml` (`when: "'fleetmgmt' in group_names"`) that dispatches to separate `fm.yml`/`sensor.yml` task files — see `sensorfleet_internal_certificates` and `sensorfleet_usermgmt` for examples. Simpler group-based branching (e.g. picking a value, not a whole task sequence) is sometimes done inline with the same `'fleetmgmt' in group_names` condition in a template or handler instead.
- `playbooks/` and `roles/` are the locations for playbooks and roles as the project grows.
- `inventories/example/` is the checked-in example inventory; `inventories/devel/` is local-only (see above).
- `tools/migrate/` — migrates an inventory's variables from the legacy SensorFleet naming scheme to this project's current one (`migrate_inventory.py`, `mapping.py`, `special_cases.py`, `yaml_io.py`). It's a standalone script with no dependency on Ansible itself (just `ruamel.yaml`). Full usage, the mapping-table format, and how to extend it are documented in `tools/migrate/README.md` — read that before changing anything there.
- **`ansible-lint` at the `production` profile is the acceptance bar for every change to a role or playbook.** There is no `.ansible-lint` config file, so the profile must be passed explicitly (see Commands below).

## Commands

From within `ansible-sensorfleet/`, with the local virtualenv activated:

```bash
source .venv/bin/activate
```

```bash
ansible-inventory -i inventories/devel/hosts.yml --list                    # validate inventory
ansible-playbook -i inventories/devel/hosts.yml playbooks/<playbook>.yml   # run a playbook
ansible-lint --profile production roles/<role>                            # lint a role (or playbooks/, or the whole repo)
```

`inventories/devel/` is the local inventory to use for testing; `inventories/example/` is a starting-point template, not meant to be run against directly.
