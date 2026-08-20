# Inventory variable migration tool

Migrates an Ansible inventory's variables from the legacy SensorFleet naming scheme
to this project's current one. It reads `hosts.yml`, `group_vars/*`, and
`host_vars/*` under an inventory root, renames any variable listed in
`mapping.py`'s `LEGACY_TO_NEW_VARS` table (optionally applying a value transform),
and writes the migrated inventory to an output path, mirroring the input's directory
structure.

## Prerequisites

Python 3.9+ and the `ruamel.yaml` package. This is a standalone script with no
dependency on Ansible itself, so it works whether you're using a project virtualenv
or a system-provided Ansible install — just make sure `ruamel.yaml` is available to
whichever `python3` you invoke it with:

```bash
python3 -c "import ruamel.yaml" || pip install --user ruamel.yaml
```

## Usage

Run from the `ansible-sensorfleet` project root:

```bash
python3 tools/migrate/migrate_inventory.py \
  --inventory-root /path/to/legacy/inventory \
  --output /path/to/migrated/inventory
```

Short flags: `-i`/`-o`. Add `--dry-run` to run the full migration and print the
report without writing any output files.

The tool always prints a report after running:

- **Renamed** — every variable occurrence it renamed (and whether a value transform
  was applied), with the file and location it was found in.
- **Injected** — default values added because the migrated inventory didn't define
  them anywhere, with the file and location the value was written to. Examples:
  `sensorfleet_globals_use_fm_repo_service` defaulting to `False` when
  `use_fm_repo_service`/`use_fm_repo_connection` was never set, and
  `sensorfleet_firewall_enforce_egress_policy` defaulting to `False` since it's a
  brand-new feature with no legacy equivalent at all — without this, a migrated
  inventory would silently pick up the role's own default of `True` (egress
  enforced) even though the legacy setup it came from never enforced one.
- **Skipped files** — empty or unexpectedly-structured files it left untouched.
- **Unmapped** — variable names it encountered with no entry in `LEGACY_TO_NEW_VARS`.
  This list is the main thing to review after a run: it's exactly what's needed to
  grow the mapping table, and it's also where genuinely-dropped legacy variables
  (features no longer configurable in the new scheme) will show up as expected, not
  an error. Variables listed in `mapping.py`'s `IGNORED_VARS`/`IGNORED_VAR_PREFIXES`
  (e.g. `is_sensor`, Ansible's own builtin vars like `ansible_host`/`ansible_user`)
  are carried through untouched and don't appear in this list at all — see
  "Ignoring variables entirely" below.

### Example run

```
root@sfpfm:~/ansible-new/ansible-sensor/tools/migrate# python3 -m venv env
root@sfpfm:~/ansible-new/ansible-sensor/tools/migrate# ./env/bin/pip install ruamel.yaml
Collecting ruamel.yaml
  Using cached ruamel_yaml-0.19.1-py3-none-any.whl (118 kB)
Installing collected packages: ruamel.yaml
Successfully installed ruamel.yaml-0.19.1
root@sfpfm:~/ansible-new/ansible-sensor/tools/migrate# ./env/bin/python migrate_inventory.py -i ~/ansible-sensor -o ~/ansible-new/ansible-sensor/inventories/sfpfm
Renamed 11 variable occurrence(s):
  /root/ansible-sensor/hosts.yml [all.vars]: vpn_server_host -> sensorfleet_openvpn_server_host
  /root/ansible-sensor/hosts.yml [all.vars]: vpn_server_connect_ip -> sensorfleet_openvpn_server_connect_ip
  /root/ansible-sensor/group_vars/all.yml [<top-level>]: sensorfleet_apt_scheme + sensorfleet_apt_repository -> sensorfleet_repos_repository_fleet (value transformed)
  /root/ansible-sensor/group_vars/all.yml [<top-level>]: use_fm_repo_connection -> sensorfleet_globals_use_fm_repo_service
  /root/ansible-sensor/group_vars/all.yml [<top-level>]: sensorfleet_apt_release -> sensorfleet_repos_apt_release
  /root/ansible-sensor/group_vars/all.yml [<top-level>]: sensorfleet_apt_auth_user -> sensorfleet_repos_repository_login
  /root/ansible-sensor/group_vars/all.yml [<top-level>]: sensorfleet_apt_auth_pass -> sensorfleet_repos_repository_password
  /root/ansible-sensor/group_vars/all.yml [<top-level>]: system_repository_source -> sensorfleet_repos_repository_os
  /root/ansible-sensor/group_vars/all.yml [<top-level>]: apt_extra_packages -> sensorfleet_system_extra_packages
  /root/ansible-sensor/group_vars/fleetmgmt.yml [<top-level>]: sensorfleet_ferm_rules -> sensorfleet_firewall_ferm_rules (value transformed)
  /root/ansible-sensor/group_vars/fleetmgmt.yml [<top-level>]: sysctl -> sensorfleet_sysctl_defaults (value transformed)

Skipped 1 file(s):
  /root/ansible-sensor/group_vars/sensors.yml: empty file

0 unmapped variable name(s) encountered:
root@sfpfm:~/ansible-new/ansible-sensor/tools/migrate#
```

## What it touches

Only `hosts.yml`, `group_vars/**/*.yml` (both the single-file and directory-of-files
forms), and `host_vars/**/*.yml` under the given root. Anything else in the
inventory root (e.g. cached PKI material, downloaded packages) is left alone.

## Extending the mapping

Add entries to `LEGACY_TO_NEW_VARS` in `mapping.py`:

```python
"old_var": VarMigration(new_name="new_var"),                      # pure rename
"old_var": VarMigration(new_name="new_var", transform=some_fn),   # rename + reshape value
```

A few reusable transforms already exist in `mapping.py` (`list_to_dict_by_key`,
`list_to_dict_by_key_value`, `null_to_empty_list`, `truthy_string_to_bool`) — check
there before writing a new one.

If a migration needs to combine multiple legacy variables into one, or add a
variable that has no legacy source at all (things a single old-name -> new-name
table entry can't express), add a function to `special_cases.py` instead and wire
it into `migrate_inventory.py`'s `process_vars_file`/`walk_hosts_tree` — see
`merge_apt_repository_url` and `inject_fleetmgmt_openvpn_client_ip` for examples of
each. For a variable that should get an explicit default only when it's missing
from the *entire* migrated inventory (not just one file), use
`inject_default_if_absent` (see `default_use_fm_repo_service` and
`default_disable_egress_policy_enforcement` for examples), wired into `main()`
after all files are processed — it prefers an existing `group_vars/*/all.yml`
among the files being written and only creates a fresh `group_vars/all.yml` if
none exists.

### Ignoring variables entirely

For legacy variables that have no new-side equivalent at all and don't need a
mapping decision (e.g. a dropped play-targeting flag, or Ansible's own builtin
vars), add them to `IGNORED_VARS` (exact name) or `IGNORED_VAR_PREFIXES` (prefix
match) in `mapping.py` instead of `LEGACY_TO_NEW_VARS`. These are carried through
untouched and don't show up in the unmapped-variable report at all, since they're
known no-ops rather than gaps to fill in.

## Known limitations

- Jinja2 template strings that reference a variable *by name* (e.g. `"{{ old_var }}"`)
  aren't rewritten when that variable's key is renamed elsewhere.
- Ansible Vault-encrypted values (the `!vault` YAML tag) aren't supported — ruamel's
  round-trip loader will error on that custom tag without a registered constructor.

## Migration notes

Once a playbook is migrated it is required to run the `migrate_legacy_ansible.yml` playbook for the sensor network in order to modernize some items on the sensors. After an old Ansible inventory is migrated to new ansible the following process MUST be done:

- Run `migrate_legacy_ansible.yml` playbook without any extra tags for all hosts
  - This will not cause any breaking changes yet, it will just copy some files
  - Cleanup task later will clean the old files out
- Run `playbooks/sensorfleet.yml` with `--diff` and `--check`
  - Firewall policy ordering and layout is changed so expect many changes there
  - Migrated playbooks will NOT have egress firewalling in enforcing mode by default
    - Egress firewall policy violations are only logged when enforcing is not done
    - Toggle this by setting `sensorfleet_firewall_enforce_egress_policy`
- Run `migrate_legacy_ansible.yml` playbook with `--tags cleanup`
- It is recommended to reboot the sensors and FM to ensure everything works normally
- After reboot, ensure everything is OK with `fleet sensor health`