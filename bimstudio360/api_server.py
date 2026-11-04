"""Run the standalone, loopback-only API, without the legacy chat routes."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))


def main():
    from flask import Flask
    from RevitMCP_ExternalServer.core.runtime_config import load_runtime_config, create_startup_logger
    from RevitMCP_ExternalServer.core.services import create_services
    from RevitMCP_ExternalServer.tools.registry import build_tool_registry
    from api_v1 import create_api_app

    token = os.environ.get('BIMSTUDIO360_API_TOKEN', '')
    if len(token) < 32 or not token.isascii():
        raise SystemExit('Configure BIMSTUDIO360_API_TOKEN with at least 32 ASCII characters.')
    config = load_runtime_config()
    logger = create_startup_logger()
    services = create_services(config, logger, Flask('bimstudio360_services'))
    registry = build_tool_registry()
    services.tool_registry = registry
    app = create_api_app(registry, services, token)
    services.app = app
    services.logger = app.logger
    app.run(host='127.0.0.1', port=8765, debug=False, use_reloader=False, threaded=True)


if __name__ == '__main__':
    main()
