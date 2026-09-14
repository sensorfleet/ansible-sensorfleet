#!/usr/bin/env python3
"""Migrate an Ansible inventory's variables from a legacy naming scheme to the new one.

Reads hosts.yml, group_vars/*, and host_vars/* under an inventory root, renames any
variable that has an entry in the LEGACY_TO_NEW_VARS mapping table (see mapping.py),
and writes the migrated inventory to an output path, mirroring the input's directory
structure. Variables with no mapping entry are left untouched and reported at the end
so the mapping table can be grown incrementally. Variables listed in mapping.py's
IGNORED_VARS/IGNORED_VAR_PREFIXES (e.g. is_sensor, ansible_*) are carried through
untouched and silently left out of that report entirely.

Known limitations (not handled, intentionally, for this first pass):
  - Jinja2 template strings that reference a variable *by name* (e.g. "{{ old_var }}")
    are not rewritten when old_var's key is renamed elsewhere.
  - Ansible Vault-encrypted values (the !vault YAML tag) are not supported; ruamel's
    round-trip loader will error on that custom tag without a registered constructor.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from mapping import IGNORED_VAR_PREFIXES, IGNORED_VARS, LEGACY_TO_NEW_VARS, VarMigration
from special_cases import (
    SPECIAL_CASE_NEW_NAMES,
    default_disable_egress_policy_enforcement,
    default_use_fm_repo_service,
    inject_fleetmgmt_openvpn_client_ip,
    merge_apt_repository_url,
    merge_sysctl_overrides,
)
from yaml_io import dump_yaml_file, load_yaml_file, rename_key_in_place

# Valid new-side target names -- used so a key already produced by a special-case
# function (e.g. merge_apt_repository_url) isn't flagged as "unmapped" when the
# generic renamer encounters it afterward.
_NEW_NAMES = {migration.new_name for migration in LEGACY_TO_NEW_VARS.values()} | SPECIAL_CASE_NEW_NAMES


@dataclass
class InventoryFiles:
    hosts_file: Optional[Path]
    group_vars_files: list[Path]
    host_vars_files: list[Path]


@dataclass
class RenameRecord:
    file: Path
    location: str
    old_name: str
    new_name: str
    transformed: bool


@dataclass
class InjectedRecord:
    file: Path
    location: str
    name: str
    value: Any


@dataclass
class MigrationReport:
    renamed: list[RenameRecord] = field(default_factory=list)
    injected: list[InjectedRecord] = field(default_factory=list)
    unmapped: set[str] = field(default_factory=set)
    skipped_files: list[tuple[Path, str]] = field(default_factory=list)

    def add_renamed(
        self, file: Path, location: str, old_name: str, new_name: str, transformed: bool
    ) -> None:
        self.renamed.append(RenameRecord(file, location, old_name, new_name, transformed))

    def add_injected(self, file: Path, location: str, name: str, value: Any) -> None:
        self.injected.append(InjectedRecord(file, location, name, value))

    def add_unmapped(self, name: str) -> None:
        self.unmapped.add(name)

    def add_skipped(self, file: Path, reason: str) -> None:
        self.skipped_files.append((file, reason))


def discover_inventory_files(root: Path) -> InventoryFiles:
    hosts_file = root / "hosts.yml"
    if not hosts_file.is_file():
        hosts_file = None

    group_vars_dir = root / "group_vars"
    group_vars_files = sorted(group_vars_dir.rglob("*.yml")) if group_vars_dir.is_dir() else []

    host_vars_dir = root / "host_vars"
    host_vars_files = sorted(host_vars_dir.rglob("*.yml")) if host_vars_dir.is_dir() else []

    return InventoryFiles(hosts_file, group_vars_files, host_vars_files)


def rename_keys_in_mapping(
    mapping: Any,
    mapping_table: dict[str, VarMigration],
    *,
    file: Path,
    location: str,
    report: MigrationReport,
) -> None:
    """Rename any top-level key of `mapping` that has an entry in `mapping_table`.

    This is the one invariant the whole tool depends on: it only ever looks at the
    top-level keys of a vars-bearing scope (a group_vars/host_vars file's top level,
    a hosts.yml `vars:` block, or a host's inline vars dict). It never recurses into
    a variable's own value looking for more "variables" to rename — nested structure
    inside a value is that variable's own schema, not other separate Ansible
    variables. A migration's `transform` (if set) is the only sanctioned way a
    variable's value shape changes, and it operates on that one variable's whole
    value, not on keys discovered by recursion.
    """
    if not hasattr(mapping, "keys"):
        return

    for key in list(mapping.keys()):
        if key in IGNORED_VARS or key.startswith(IGNORED_VAR_PREFIXES):
            continue

        migration = mapping_table.get(key)
        if migration is None:
            # A key that already equals a valid new-side target name isn't
            # "unmapped" -- most likely a special-case function (e.g.
            # merge_apt_repository_url) already produced it earlier in this same
            # pass, so it should neither be renamed again nor flagged as unknown.
            if key not in _NEW_NAMES:
                report.add_unmapped(key)
            continue

        transform = migration.transform
        transformed = transform is not None
        new_value = transform(mapping[key]) if transform is not None else None

        rename_key_in_place(mapping, key, migration.new_name)
        if transformed:
            mapping[migration.new_name] = new_value

        report.add_renamed(file, location, key, migration.new_name, transformed)


def walk_hosts_tree(
    node: Any,
    mapping_table: dict[str, VarMigration],
    report: MigrationReport,
    *,
    file: Path,
    path: str,
) -> None:
    """Recursively walk a hosts.yml group node (`vars:`/`hosts:`/`children:`),
    renaming variables at every level. No depth limit is assumed for `children:`
    nesting, matching Ansible's own YAML inventory format.
    """
    if not hasattr(node, "get"):
        return

    vars_block = node.get("vars")
    if vars_block:
        merge_apt_repository_url(vars_block, file=file, location=f"{path}.vars", report=report)
        merge_sysctl_overrides(vars_block, file=file, location=f"{path}.vars", report=report)
        rename_keys_in_mapping(vars_block, mapping_table, file=file, location=f"{path}.vars", report=report)

    hosts_block = node.get("hosts")
    if hosts_block:
        for host_name, host_vars in hosts_block.items():
            if host_vars:
                merge_apt_repository_url(
                    host_vars, file=file, location=f"{path}.hosts.{host_name}", report=report
                )
                merge_sysctl_overrides(
                    host_vars, file=file, location=f"{path}.hosts.{host_name}", report=report
                )
                rename_keys_in_mapping(
                    host_vars,
                    mapping_table,
                    file=file,
                    location=f"{path}.hosts.{host_name}",
                    report=report,
                )

    children_block = node.get("children")
    if children_block:
        for child_name, child_node in children_block.items():
            walk_hosts_tree(
                child_node, mapping_table, report, file=file, path=f"{path}.children.{child_name}"
            )


def process_hosts_file(path: Path, mapping_table: dict[str, VarMigration], report: MigrationReport) -> Any:
    doc = load_yaml_file(path)
    if doc is None:
        report.add_skipped(path, "empty file")
        return doc
    if not hasattr(doc, "items"):
        report.add_skipped(path, "unexpected top-level structure")
        return doc

    for group_name, group_node in doc.items():
        walk_hosts_tree(group_node, mapping_table, report, file=path, path=group_name)

    inject_fleetmgmt_openvpn_client_ip(doc)

    return doc


def process_vars_file(path: Path, mapping_table: dict[str, VarMigration], report: MigrationReport) -> Any:
    """Process a flat group_vars/host_vars file, where the whole top-level mapping
    IS the vars scope (unlike hosts.yml, there's no `vars:` key to unwrap).
    """
    doc = load_yaml_file(path)
    if doc is None:
        report.add_skipped(path, "empty file")
        return doc
    if not hasattr(doc, "items"):
        report.add_skipped(path, "unexpected top-level structure")
        return doc

    merge_apt_repository_url(doc, file=path, location="<top-level>", report=report)
    merge_sysctl_overrides(doc, file=path, location="<top-level>", report=report)
    rename_keys_in_mapping(doc, mapping_table, file=path, location="<top-level>", report=report)
    return doc


def print_report(report: MigrationReport, stream=sys.stdout) -> None:
    print(f"Renamed {len(report.renamed)} variable occurrence(s):", file=stream)
    for record in report.renamed:
        transform_note = " (value transformed)" if record.transformed else ""
        print(
            f"  {record.file} [{record.location}]: {record.old_name} -> {record.new_name}{transform_note}",
            file=stream,
        )

    if report.injected:
        print(f"\nInjected {len(report.injected)} default value(s):", file=stream)
        for record in report.injected:
            print(f"  {record.file} [{record.location}]: {record.name} = {record.value!r}", file=stream)

    if report.skipped_files:
        print(f"\nSkipped {len(report.skipped_files)} file(s):", file=stream)
        for skipped_path, reason in report.skipped_files:
            print(f"  {skipped_path}: {reason}", file=stream)

    print(f"\n{len(report.unmapped)} unmapped variable name(s) encountered:", file=stream)
    for name in sorted(report.unmapped):
        print(f"  {name}", file=stream)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-i", "--inventory-root", required=True, type=Path, help="Path to the inventory root to migrate"
    )
    parser.add_argument(
        "-o", "--output", required=True, type=Path, help="Path to write the migrated inventory to"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the full migration and print the report, but don't write any output files",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    root: Path = args.inventory_root
    output: Path = args.output

    if not root.is_dir():
        print(f"error: inventory root does not exist or is not a directory: {root}", file=sys.stderr)
        return 1

    report = MigrationReport()
    files = discover_inventory_files(root)

    to_write: list[tuple[Path, Any]] = []

    if files.hosts_file is not None:
        doc = process_hosts_file(files.hosts_file, LEGACY_TO_NEW_VARS, report)
        to_write.append((files.hosts_file, doc))

    for vars_file in [*files.group_vars_files, *files.host_vars_files]:
        doc = process_vars_file(vars_file, LEGACY_TO_NEW_VARS, report)
        to_write.append((vars_file, doc))

    to_write = default_use_fm_repo_service(to_write, root=root, report=report)
    to_write = default_disable_egress_policy_enforcement(to_write, root=root, report=report)

    if not args.dry_run:
        for src_path, doc in to_write:
            dump_yaml_file(doc, output / src_path.relative_to(root))

    print_report(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
