"""Analyze Python imports in a subprocess to isolate importlib's global state."""

import dis
import importlib.machinery
import importlib.util
import json
import pathlib
import sys
import traceback
from collections.abc import Callable, Iterator
from types import CodeType, ModuleType, SimpleNamespace
from typing import Protocol, cast

from modulegraph2 import BaseNode, ModuleGraph, Package


def _instructions(code: CodeType) -> Iterator[dis.Instruction]:
    for instruction in dis.get_instructions(code):
        if instruction.opname == "LOAD_COMMON_CONSTANT" and instruction.argval is None:
            # The analysis-only code object has an extra None constant at the end.
            yield instruction._replace(opname="LOAD_CONST", arg=len(code.co_consts) - 1)
        elif instruction.opname == "IMPORT_NAME":
            # Python 3.15 packs lazy/eager flags into the import operand.
            yield instruction._replace(arg=code.co_names.index(instruction.argval))
        else:
            yield instruction


def _patch_modulegraph() -> None:
    """Adapt old bytecode scanners without changing the interpreter's dis module."""
    if sys.version_info < (3, 15):
        return

    tools = importlib.import_module("modulegraph2._bytecode_tools")
    extract_bytecode_info = cast(
        "Callable[[CodeType], object]",
        tools.extract_bytecode_info,
    )
    try:
        # Leave versions with native support (and already patched workers) alone.
        extract_bytecode_info(compile("import os", "<modulegraph-probe>", "exec"))
    except AssertionError as error:
        if str(error) != "LOAD_COMMON_CONSTANT":
            raise
    else:
        return

    def compatible_extract_bytecode_info(code: CodeType) -> object:
        # Collect nested code iteratively, as modulegraph2's scanner does.
        code_objects = [code]
        for current in code_objects:
            code_objects.extend(
                value for value in current.co_consts if isinstance(value, CodeType)
            )

        # Build analysis-only copies from children to parents. Constant indices
        # and instruction offsets stay intact; each copy gains a None constant.
        copies: dict[CodeType, CodeType] = {}
        for current in reversed(code_objects):
            constants = tuple(
                copies[value] if isinstance(value, CodeType) else value
                for value in current.co_consts
            )
            copies[current] = current.replace(co_consts=(*constants, None))
        return extract_bytecode_info(copies[code])

    # Only modulegraph2's scanner sees this adapter. The process-wide dis module
    # and the code objects used for execution are unchanged.
    tools.dis = SimpleNamespace(get_instructions=_instructions)
    tools.extract_bytecode_info = compatible_extract_bytecode_info
    graphbuilder = importlib.import_module("modulegraph2._graphbuilder")
    graphbuilder.extract_bytecode_info = compatible_extract_bytecode_info


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


def _serve() -> None:
    original_path = sys.path.copy()
    original_find_spec = importlib.util.find_spec
    original_modules = sys.modules.copy()
    for request in sys.stdin:
        try:
            path, basedir = (
                pathlib.Path(value).resolve() for value in json.loads(request)
            )
            response: dict[str, list[str] | str] = {
                "dependencies": [
                    str(dependency) for dependency in _list_dependencies(path, basedir)
                ]
            }
        except (ImportError, OSError, RuntimeError, SyntaxError, ValueError):
            response = {"error": traceback.format_exc()}
        finally:
            # Every request starts with the worker's original import state.
            sys.path[:] = original_path
            importlib.util.find_spec = original_find_spec
            for name in sys.modules.keys() - original_modules.keys():
                del sys.modules[name]
            sys.modules.update(original_modules)
        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    _patch_modulegraph()
    if len(sys.argv) == 1:
        _serve()
    else:
        dependencies = _list_dependencies(
            pathlib.Path(sys.argv[1]).resolve(), pathlib.Path(sys.argv[2]).resolve()
        )
        print(json.dumps([str(path) for path in dependencies]))
