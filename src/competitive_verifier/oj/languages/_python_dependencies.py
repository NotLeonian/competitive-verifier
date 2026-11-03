"""Analyze Python imports in a subprocess to isolate importlib's global state."""

import importlib.machinery
import importlib.util
import json
import pathlib
import sys
from types import ModuleType
from typing import Protocol, cast

from modulegraph2 import BaseNode, ModuleGraph, Package


class _ScriptGraph(Protocol):
    # modulegraph2's PathLike annotation omits its generic argument.
    def add_script(self, script_path: pathlib.Path) -> BaseNode: ...


def _find_spec(
    name: str, package: str | None = None
) -> importlib.machinery.ModuleSpec | None:
    """Find local module specs without executing parent package initializers."""
    if name.startswith("."):
        name = importlib.util.resolve_name(name, package)
    parent, _, _ = name.rpartition(".")
    search_path = sys.path
    if parent:
        parent_spec = _find_spec(parent)
        if parent_spec is None or parent_spec.submodule_search_locations is None:
            return None
        search_path = list(parent_spec.submodule_search_locations)

    spec = importlib.machinery.PathFinder.find_spec(name, search_path)
    if spec is not None and spec.submodule_search_locations is not None:
        # Namespace package lookup needs its parent to exist in sys.modules.
        module = ModuleType(name)
        module.__spec__ = spec
        module.__path__ = list(spec.submodule_search_locations)
        sys.modules[name] = module
    return spec


def _list_dependencies(path: pathlib.Path, basedir: pathlib.Path) -> list[pathlib.Path]:
    # modulegraph2 uses find_spec, whose default behavior imports parent packages.
    # This worker has its own import state, so these changes stay in the subprocess.
    sys.path[:] = [str(basedir)]
    importlib.util.find_spec = _find_spec
    graph = ModuleGraph(use_stdlib_implies=False, use_builtin_hooks=False)

    module_name = ""
    if path.parent != basedir and path.is_relative_to(basedir):
        parts = path.relative_to(basedir).with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if all(part.isidentifier() for part in parts):
            module_name = ".".join(parts)
    spec = _find_spec(module_name) if module_name else None
    if (
        spec is not None
        and spec.origin is not None
        and pathlib.Path(spec.origin) == path
    ):
        # Keep the package context when the entrypoint uses relative imports.
        compile(path.read_bytes(), str(path), "exec")
        graph.add_module(module_name)
    else:
        cast("_ScriptGraph", graph).add_script(path)

    dependencies = {path}
    for node in graph.nodes():
        if not isinstance(node, BaseNode):
            continue
        filename = (
            node.init_module.filename if isinstance(node, Package) else node.filename
        )
        if filename is None:
            continue
        dependency = filename.resolve()
        if dependency.suffix == ".py" and dependency.is_relative_to(basedir):
            dependencies.add(dependency)
    return sorted(dependencies)


if __name__ == "__main__":
    dependencies = _list_dependencies(
        pathlib.Path(sys.argv[1]).resolve(), pathlib.Path(sys.argv[2]).resolve()
    )
    print(json.dumps([str(path) for path in dependencies]))
