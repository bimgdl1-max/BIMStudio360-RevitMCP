"""Authenticated local HTTP surface over the existing tool registry."""
import copy
import hmac
import threading
import uuid

from flask import Flask, jsonify, request
from jsonschema import Draft7Validator

# All unknown/future tools require explicit confirmation by default.
READ_TOOLS = frozenset('''get_revit_project_info list_family_types
get_revit_schema_context resolve_revit_targets get_revit_memory_context
analyze_model_statistics get_active_view_info get_active_view_elements
list_views analyze_view_naming_patterns suggest_view_name_corrections
list_schedules get_schedule_info list_schedule_available_fields get_schedule_rows
compare_schedules get_active_selection get_revit_diagnostics
get_elements_by_category list_stored_elements filter_elements
filter_stored_elements_by_parameter get_element_properties get_element_relationships
get_element_locations get_related_element_properties'''.split())


def requires_confirmation(name):
    return name not in READ_TOOLS


def argument_schema(definition):
    schema = copy.deepcopy(definition.json_schema)
    schema['additionalProperties'] = False
    return schema


def create_api_app(registry, services, token):
    if not isinstance(token, str) or len(token) < 32 or not token.isascii():
        raise ValueError('BIMSTUDIO360_API_TOKEN must contain at least 32 ASCII characters')
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024
    gate = threading.Lock()

    @app.before_request
    def authenticate():
        if request.remote_addr not in ('127.0.0.1', '::1'):
            return jsonify(error='local_only'), 403
        supplied = request.headers.get('Authorization', '')
        if not hmac.compare_digest(supplied.encode('utf-8'), ('Bearer ' + token).encode('ascii')):
            return jsonify(error='unauthorized'), 401

    @app.after_request
    def prevent_caching(response):
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/api/v1/health')
    def health():
        return jsonify(status='ready', tool_count=len(registry.list_definitions()),
                       revit_status='not_checked')

    @app.get('/api/v1/tools')
    def catalog():
        return jsonify(tools=[dict(name=d.name, description=d.description,
                                   input_schema=argument_schema(d),
                                   requires_confirmation=requires_confirmation(d.name))
                              for d in registry.list_definitions()])

    @app.get('/api/v1/openapi.json')
    def specification():
        paths = {}
        for d in registry.list_definitions():
            envelope = {'type': 'object', 'additionalProperties': False,
                        'required': ['arguments'], 'properties': {
                            'arguments': argument_schema(d),
                            'confirm': {'type': 'boolean', 'default': False}}}
            if requires_confirmation(d.name):
                envelope['required'].append('confirm')
                envelope['properties']['confirm']['const'] = True
            paths['/api/v1/tools/' + d.name + '/execute'] = {'post': {
                'operationId': d.name, 'description': d.description,
                'requestBody': {'required': True, 'content': {'application/json': {'schema': envelope}}},
                'responses': {str(code): {'description': desc} for code, desc in (
                    (200, 'Tool result'), (400, 'Invalid arguments'), (401, 'Unauthorized'),
                    (403, 'Confirmation required or nonlocal'), (404, 'Unknown tool'),
                    (409, 'Operation in progress'), (422, 'Tool reported an error'))}}}
        return jsonify(openapi='3.1.0', info={'title': 'BIM Studio 360 Local API', 'version': '0.1.0'},
                       paths=paths, security=[{'bearerAuth': []}],
                       components={'securitySchemes': {'bearerAuth': {'type': 'http', 'scheme': 'bearer'}}})

    @app.post('/api/v1/tools/<name>/execute')
    def execute(name):
        definition = registry.get(name)
        if definition is None:
            return jsonify(error='unknown_tool'), 404
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or set(body) - {'arguments', 'confirm'}:
            return jsonify(error='expected_arguments_and_optional_confirm'), 400
        args = body.get('arguments')
        if not isinstance(args, dict) or ('confirm' in body and not isinstance(body['confirm'], bool)):
            return jsonify(error='invalid_envelope'), 400
        errors = list(Draft7Validator(argument_schema(definition)).iter_errors(args))
        if errors:
            return jsonify(error='invalid_arguments', details=[e.message for e in errors]), 400
        if requires_confirmation(name) and body.get('confirm') is not True:
            return jsonify(error='confirmation_required'), 403
        if not gate.acquire(blocking=False):
            return jsonify(error='operation_in_progress', message='Do not retry a write blindly.'), 409
        operation_id = str(uuid.uuid4())
        try:
            result = registry.dispatch(services, name, args)
            failed = isinstance(result, dict) and result.get('status') == 'error'
            app.logger.info('operation=%s tool=%s outcome=%s', operation_id, name, 'error' if failed else 'completed')
            return jsonify(operation_id=operation_id, result=result), 422 if failed else 200
        finally:
            gate.release()

    return app
