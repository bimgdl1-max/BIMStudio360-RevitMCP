"""Pruebas estáticas; no se requieren dependencias de Revit ni SDK MCP."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bimstudio360_inventory import MODULES, collect_catalog, extract_tool_names


class CatalogTests(unittest.TestCase):
    def test_extracts_named_constant(self):
        sample = 'GET_TOOL_NAME = "tool_one"\ndef build():\n    return [ToolDefinition(name=GET_TOOL_NAME, description="ok")]\n'
        self.assertEqual(extract_tool_names(sample), ["tool_one"])

    def test_extracts_literal(self):
        sample = 'def build():\n    return [ToolDefinition(name="tool_two")]\n'
        self.assertEqual(extract_tool_names(sample), ["tool_two"])

    def test_rejects_unresolved_expression(self):
        sample = 'def build():\n    return [ToolDefinition(name=dynamic())]\n'
        with self.assertRaises(ValueError):
            extract_tool_names(sample)

    def test_catalog_has_expected_module_structure(self):
        catalog = collect_catalog()
        self.assertEqual(list(catalog["categories"]), list(MODULES))
        all_names = [name for names in catalog["categories"].values() for name in names]
        self.assertEqual(len(all_names), len(set(all_names)))
        self.assertEqual(catalog["total_tools"], len(all_names))


if __name__ == "__main__":
    unittest.main()
