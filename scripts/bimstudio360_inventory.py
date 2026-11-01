#!/usr/bin/env python3
"""Inventario estático de las herramientas MCP (no inicia Revit ni ejecuta módulos)."""
from __future__ import annotations

import argparse
import ast
import difflib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "lib" / "RevitMCP_ExternalServer" / "tools"
BASELINE = ROOT / "docs" / "bimstudio360" / "tool-baseline.json"

MODULES = (
    "context_tools", "memory_tools", "model_tools", "view_tools",
    "schedule_tools", "element_tools", "element_operation_tools",
    "planning_tools", "tag_tools",
)


def extract_tool_names(source: str, filename: str = "<source>") -> list[str]:
    """Analiza sintaxis sin importar ni ejecutar el código del proyecto."""
    tree = ast.parse(source, filename=filename)
    constants: dict[str, str] = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = node.value.value
    names: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "ToolDefinition"):
            continue
        fields = {field.arg: field.value for field in node.keywords if field.arg}
        expression = fields.get("name")
        if isinstance(expression, ast.Name):
            name = constants.get(expression.id)
        elif isinstance(expression, ast.Constant) and isinstance(expression.value, str):
            name = expression.value
        else:
            name = None
        if not name:
            raise ValueError(f"{filename}:{node.lineno}: nombre de herramienta no resoluble")
        names.append(name)
    return names


def collect_catalog() -> dict:
    categories: dict[str, list[str]] = {}
    seen: set[str] = set()
    for module in MODULES:
        path = TOOLS / f"{module}.py"
        names = extract_tool_names(path.read_text(encoding="utf-8"), str(path))
        if not names:
            raise ValueError(f"Sin herramientas en {path}")
        repeated = seen.intersection(names)
        if repeated or len(names) != len(set(names)):
            raise ValueError(f"Herramientas duplicadas en {module}: {sorted(repeated)}")
        seen.update(names)
        categories[module] = names
    return {
        "schema_version": 1,
        "source": "oakplank/RevitMCP",
        "source_branch": "main",
        "total_tools": len(seen),
        "categories": categories,
    }


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="Contrasta con baseline; error si cambian herramientas")
    group.add_argument("--write", action="store_true", help="Actualiza baseline intencionadamente")
    group.add_argument("--markdown", action="store_true", help="Imprime catálogo en Markdown")
    args = parser.parse_args(argv)
    try:
        actual = collect_catalog()
        if args.write:
            BASELINE.parent.mkdir(parents=True, exist_ok=True)
            BASELINE.write_text(json.dumps(actual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"Baseline actualizado: {BASELINE} ({actual['total_tools']} herramientas)")
            return 0
        if args.check:
            expected = json.loads(BASELINE.read_text(encoding="utf-8"))
            if expected != actual:
                left = json.dumps(expected, ensure_ascii=False, indent=2, sort_keys=True).splitlines()
                right = json.dumps(actual, ensure_ascii=False, indent=2, sort_keys=True).splitlines()
                print("\n".join(difflib.unified_diff(left, right, fromfile="baseline", tofile="código", lineterm="")))
                print("Cambio detectado. Revísalo antes de regenerar el baseline.", file=sys.stderr)
                return 1
            print(f"OK: {actual['total_tools']} herramientas en {len(MODULES)} módulos, sin cambios respecto al baseline.")
            return 0
        if args.markdown:
            print(f"# Catálogo MCP: {actual['total_tools']} herramientas")
            for module, names in actual["categories"].items():
                print(f"\n## {module} ({len(names)})")
                for name in names:
                    print(f"- `{name}`")
            return 0
        print(json.dumps(actual, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, SyntaxError, json.JSONDecodeError) as exc:
        print(f"Error de auditoría: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(run())
