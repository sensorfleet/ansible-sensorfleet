"""Migration logic that can't be expressed as a single legacy-name -> new-name
VarMigration table entry, either because it needs to combine multiple legacy
variables into one, or because it needs to add a variable that has no legacy
source at all.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ruamel.yaml.comments import CommentedMap

FLEETMGMT_OPENVPN_CLIENT_IP = "169.254.255.255"
USE_FM_REPO_SERVICE_VAR = "sensorfleet_globals_use_fm_repo_service"
ENFORCE_EGRESS_POLICY_VAR = "sensorfleet_firewall_enforce_egress_policy"

# New-side variable names produced directly by the functions below (not sourced from
# LEGACY_TO_NEW_VARS) -- callers should treat these as already-migrated names too,
# not flag them as unmapped when the generic renamer encounters them afterward.
SPECIAL_CASE_NEW_NAMES = {"sensorfleet_repos_repository_fleet"}


def inject_fleetmgmt_openvpn_client_ip(hosts_doc: Any) -> None:
    """Legacy inventories never gave the fleetmgmt host a VPN client IP (only
    sensors had one) -- the new scheme needs sensorfleet_openvpn_client_ip set on
    every host in the fleetmgmt group. Walks the hosts tree looking for any group
    named "fleetmgmt" at any nesting depth, and sets the IP on each of its hosts
    only if not already present.
    """
    if not hasattr(hosts_doc, "items"):
        return

    for group_name, group_node in hosts_doc.items():
        _walk_for_fleetmgmt(group_name, group_node)


def _walk_for_fleetmgmt(group_name: str, node: Any) -> None:
    if not hasattr(node, "get"):
        return

    if group_name == "fleetmgmt":
        hosts_block = node.get("hosts")
        if hosts_block:
            for host_name in list(hosts_block.keys()):
                host_vars = hosts_block[host_name]
                if host_vars is None:
                    host_vars = {}
                    hosts_block[host_name] = host_vars
                if "sensorfleet_openvpn_client_ip" not in host_vars:
                    host_vars["sensorfleet_openvpn_client_ip"] = FLEETMGMT_OPENVPN_CLIENT_IP

    children_block = node.get("children")
    if children_block:
        for child_name, child_node in children_block.items():
            _walk_for_fleetmgmt(child_name, child_node)


def merge_apt_repository_url(mapping: Any, *, file: Any, location: str, report: Any) -> None:
    """Legacy splits the fleet repo URL across sensorfleet_apt_scheme (e.g. "https")
    and sensorfleet_apt_repository (e.g. "repository.sensorfleet.com", no path) --
    the new scheme wants one variable, sensorfleet_repos_repository_fleet, a full
    URL with a "/fleet" path suffix. If both legacy keys are present, combine them
    and remove both. If only one is present, leave both alone -- they'll surface in
    the unmapped-variable report rather than being silently guessed at.
    """
    if not hasattr(mapping, "get"):
        return

    if "sensorfleet_apt_scheme" in mapping and "sensorfleet_apt_repository" in mapping:
        scheme = mapping.pop("sensorfleet_apt_scheme")
        repository = mapping.pop("sensorfleet_apt_repository")
        mapping["sensorfleet_repos_repository_fleet"] = f"{scheme}://{repository}/fleet"
        report.add_renamed(
            file,
            location,
            "sensorfleet_apt_scheme + sensorfleet_apt_repository",
            "sensorfleet_repos_repository_fleet",
            True,
        )


def default_use_fm_repo_service(
    to_write: list[tuple[Path, Any]], *, root: Path, report: Any
) -> list[tuple[Path, Any]]:
    """Legacy inventories could leave use_fm_repo_service/use_fm_repo_connection
    unset entirely (its effective default lived outside any single variable) -- the
    new scheme has no implicit fallback for sensorfleet_globals_use_fm_repo_service,
    so if the migrated inventory doesn't define it anywhere, default it to False.
    See inject_default_if_absent for the shared mechanics.
    """
    return inject_default_if_absent(to_write, USE_FM_REPO_SERVICE_VAR, False, root=root, report=report)


def default_disable_egress_policy_enforcement(
    to_write: list[tuple[Path, Any]], *, root: Path, report: Any
) -> list[tuple[Path, Any]]:
    """sensorfleet_firewall_enforce_egress_policy is a brand-new feature with no
    legacy equivalent at all -- a legacy inventory has no way to already define it,
    so every migrated inventory would otherwise silently pick up the role's default
    of True (egress enforced) even though the legacy setup it came from never
    enforced any egress policy. Explicitly default it to False on migration so
    migrated hosts keep their pre-migration (non-enforcing) firewall behavior
    instead of picking up new, potentially-breaking enforcement unannounced.
    See inject_default_if_absent for the shared mechanics.
    """
    return inject_default_if_absent(to_write, ENFORCE_EGRESS_POLICY_VAR, False, root=root, report=report)


def inject_default_if_absent(
    to_write: list[tuple[Path, Any]], key: str, value: Any, *, root: Path, report: Any
) -> list[tuple[Path, Any]]:
    """If `key` isn't defined anywhere in the migrated inventory (hosts.yml vars at
    any nesting depth, or any group_vars/host_vars file's top level), set it
    explicitly to `value` so behavior stays well-defined instead of silently
    depending on whatever the new role's own default happens to be. Prefers an
    "all.yml" already among the files being written (wherever it lives in the
    input's own group_vars layout); creates a fresh group_vars/all.yml only if none
    exists.

    Returns the (possibly appended-to) to_write list.
    """
    if _key_present_anywhere(to_write, key):
        return to_write

    for path, doc in to_write:
        if path.name == "all.yml" and "group_vars" in path.parts and hasattr(doc, "__setitem__"):
            doc[key] = value
            report.add_injected(path, "<top-level>", key, value)
            return to_write

    new_doc = CommentedMap()
    new_doc[key] = value
    new_path = root / "group_vars" / "all.yml"
    report.add_injected(new_path, "<top-level>", key, value)
    return [*to_write, (new_path, new_doc)]


def _key_present_anywhere(to_write: list[tuple[Path, Any]], key: str) -> bool:
    for path, doc in to_write:
        if doc is None:
            continue
        if path.name == "hosts.yml":
            if _key_present_in_hosts_tree(doc, key):
                return True
        elif hasattr(doc, "__contains__") and key in doc:
            return True
    return False


def _key_present_in_hosts_tree(doc: Any, key: str) -> bool:
    if not hasattr(doc, "items"):
        return False
    return any(_key_present_in_group_node(group_node, key) for group_node in doc.values())


def _key_present_in_group_node(node: Any, key: str) -> bool:
    if not hasattr(node, "get"):
        return False

    vars_block = node.get("vars")
    if vars_block and key in vars_block:
        return True

    hosts_block = node.get("hosts")
    if hosts_block and any(host_vars and key in host_vars for host_vars in hosts_block.values()):
        return True

    children_block = node.get("children")
    if children_block:
        return any(_key_present_in_group_node(child_node, key) for child_node in children_block.values())

    return False
