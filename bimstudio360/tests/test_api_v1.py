import copy
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from RevitMCP_ExternalServer.tools.registry import build_tool_registry, ToolDefinition, ToolRegistry
from api_v1 import create_api_app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.registry = build_tool_registry()
        self.registry.dispatch = Mock(return_value={'status': 'success', 'value': 42})
        self.token = 't' * 40
        self.app = create_api_app(self.registry, None, self.token)
        self.client = self.app.test_client()
        self.headers = {'Authorization': 'Bearer ' + self.token}

    def call(self, name='get_revit_project_info', arguments=None, **kwargs):
        body = {'arguments': {} if arguments is None else arguments}
        body.update(kwargs)
        return self.client.post('/api/v1/tools/' + name + '/execute', json=body, headers=self.headers)

    def test_catalog_contains_all_real_tools(self):
        tools = self.client.get('/api/v1/tools', headers=self.headers).json['tools']
        self.assertEqual(len(tools), 49)
        self.assertEqual({t['name'] for t in tools}, {d.name for d in self.registry.list_definitions()})
        self.assertIn('tag_rooms', {t['name'] for t in tools})

    def test_authentication_all_surfaces(self):
        for path in ('health', 'tools', 'openapi.json', 'tools/get_revit_project_info/execute'):
            self.assertEqual(self.client.get('/api/v1/' + path).status_code, 401)
        self.assertEqual(self.client.get('/api/v1/tools', headers={'Authorization': 'Bearer wrong'}).status_code, 401)
        self.registry.dispatch.assert_not_called()

    def test_nonlocal_denied(self):
        self.assertEqual(self.client.get('/api/v1/tools', headers=self.headers,
                         environ_overrides={'REMOTE_ADDR': '192.168.1.2'}).status_code, 403)

    def test_short_token_rejected(self):
        with self.assertRaises(ValueError):
            create_api_app(self.registry, None, 'short')

    def test_exact_dispatch_and_result(self):
        response = self.call()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['result']['value'], 42)
        self.registry.dispatch.assert_called_once_with(None, 'get_revit_project_info', {})
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_unknown_tool(self):
        self.assertEqual(self.call('does_not_exist').status_code, 404)
        self.registry.dispatch.assert_not_called()

    def test_invalid_arguments_do_not_execute(self):
        self.assertEqual(self.call(arguments={'invented': True}).status_code, 400)
        self.assertEqual(self.call(arguments=[]).status_code, 400)
        self.assertEqual(self.call(confirm='true').status_code, 400)
        self.assertEqual(self.call(invented=True).status_code, 400)
        self.assertEqual(self.call('get_elements_by_category').status_code, 400)
        self.registry.dispatch.assert_not_called()

    def test_confirmation_and_existing_tool_safeguards(self):
        self.assertEqual(self.call('clear_temporary_isolate').status_code, 403)
        self.registry.dispatch.assert_not_called()
        self.assertEqual(self.call('clear_temporary_isolate', confirm=True).status_code, 200)
        self.registry.dispatch.assert_called_once_with(None, 'clear_temporary_isolate', {})

    def test_tool_errors_are_not_successes(self):
        self.registry.dispatch.return_value = {'status': 'error', 'message': 'Revit unavailable'}
        self.assertEqual(self.call().status_code, 422)

    def test_openapi_covers_registry_without_mutating_schemas(self):
        before = [copy.deepcopy(d.json_schema) for d in self.registry.list_definitions()]
        spec = self.client.get('/api/v1/openapi.json', headers=self.headers).json
        self.assertEqual(len(spec['paths']), 49)
        self.assertEqual(spec['openapi'], '3.1.0')
        self.assertEqual(before, [d.json_schema for d in self.registry.list_definitions()])

    def test_busy_rejects_second_call_and_releases_after_completion(self):
        entered, release = threading.Event(), threading.Event()
        def slow(*args):
            entered.set()
            release.wait(5)
            return {'status': 'success'}
        self.registry.dispatch.side_effect = slow
        thread = threading.Thread(target=lambda: self.app.test_client().post(
            '/api/v1/tools/get_revit_project_info/execute', headers=self.headers, json={'arguments': {}}))
        thread.start()
        try:
            self.assertTrue(entered.wait(3))
            self.assertEqual(self.call().status_code, 409)
        finally:
            release.set()
            thread.join(5)
        self.registry.dispatch.side_effect = None
        self.assertEqual(self.call().status_code, 200)

    def test_future_tools_require_confirmation(self):
        registry = ToolRegistry([ToolDefinition('new_tool', 'New', {'type': 'object'}, lambda *_: {})])
        registry.dispatch = Mock(return_value={})
        client = create_api_app(registry, None, self.token).test_client()
        response = client.post('/api/v1/tools/new_tool/execute', headers=self.headers, json={'arguments': {}})
        self.assertEqual(response.status_code, 403)
        registry.dispatch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
