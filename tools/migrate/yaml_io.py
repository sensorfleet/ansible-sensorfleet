"""YAML load/dump/rename mechanics for the inventory migration tool.

Uses ruamel.yaml in round-trip mode so comments, key order, quoting style, and other
hand-edited formatting in the source inventory files are preserved as much as possible.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap


def make_yaml() -> YAML:
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.width = 4096  # avoid unwanted line-wrapping of long values
    yaml.explicit_start = True  # preserve the leading '---' document marker
    yaml.indent(mapping=2, sequence=4, offset=2)  # match this repo's existing style
    return yaml


def load_yaml_file(path: Path) -> Any:
    """Load a YAML file. Returns None for a genuinely empty file, matching
    ruamel's own behavior for 0-byte input (e.g. inventories/example/hosts.yml).
    """
    yaml = make_yaml()
    with path.open("r", encoding="utf-8") as f:
        return yaml.load(f)


def dump_yaml_file(doc: Any, path: Path) -> None:
    """Write a YAML document back out. An empty (None) document is written as an
    empty file rather than a synthesized '---' marker, so an empty input stays
    byte-equivalent empty output instead of being "fixed".
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if doc is None:
        path.write_text("", encoding="utf-8")
        return
    yaml = make_yaml()
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(doc, f)


def rename_key_in_place(mapping: CommentedMap, old_key: str, new_key: str) -> None:
    """Rename a key in a CommentedMap in place, preserving both key order and any
    comment attached to the old key.

    A naive `mapping[new_key] = mapping.pop(old_key)` would move the key to the end
    of the mapping's insertion order, causing every renamed variable to visibly jump
    to the bottom of its vars block on every migrated file.
    """
    items = list(mapping.items())
    comment = mapping.ca.items.pop(old_key, None)
    mapping.clear()
    for key, value in items:
        mapping[new_key if key == old_key else key] = value
    if comment is not None:
        mapping.ca.items[new_key] = comment
