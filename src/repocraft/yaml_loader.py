"""Safe YAML loading that rejects duplicate mapping keys."""

from __future__ import annotations

from typing import Any

import yaml

from repocraft.errors import RepocraftError


class DuplicateKeyError(RepocraftError):
    """A YAML mapping repeats a key; the key is available on ``.key``."""

    def __init__(self, key: Any) -> None:
        super().__init__(f"duplicate key {key!r}")
        self.key = key


class UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys instead of keeping the last."""


def _construct_mapping(loader: Any, node: Any, deep: bool = False) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise DuplicateKeyError(key)
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)
