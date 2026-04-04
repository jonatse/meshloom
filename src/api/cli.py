"""CLI interface for Meshloom API."""

import argparse
import json
import sys
from typing import Any, Dict

from .client import APIClient


def format_output(data: Any, as_json: bool = False) -> None:
    """Format and print output."""
    if as_json:
        print(json.dumps(data, indent=2))
    else:
        if isinstance(data, dict):
            if "error" in data and data["error"]:
                print(f"Error: {data['error']}", file=sys.stderr)
            if data.get("data"):
                print(json.dumps(data["data"], indent=2))
        else:
            print(data)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Meshloom API CLI")
    parser.add_argument(
        "--socket", "-s",
        default=None,
        help="Unix socket path (default: ~/.local/run/meshloom/api.sock)"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output raw JSON"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    subparsers.add_parser("peers", help="List discovered peers")
    subparsers.add_parser("status", help="Get system status")

    exec_parser = subparsers.add_parser("execute", help="Execute command in container")
    exec_parser.add_argument("command", help="Command to execute")

    subparsers.add_parser("apps", help="List installed apps")

    app_start_parser = subparsers.add_parser("app-start", help="Start an app")
    app_start_parser.add_argument("app_id", help="App ID to start")

    app_stop_parser = subparsers.add_parser("app-stop", help="Stop an app")
    app_stop_parser.add_argument("app_id", help="App ID to stop")

    config_get_parser = subparsers.add_parser("config-get", help="Get config value")
    config_get_parser.add_argument("key", help="Config key")

    config_set_parser = subparsers.add_parser("config-set", help="Set config value")
    config_set_parser.add_argument("key", help="Config key")
    config_set_parser.add_argument("value", help="Config value")

    subparsers.add_parser("sync", help="Trigger sync")
    subparsers.add_parser("bridges", help="List bridge connections")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    client = APIClient(args.socket)

    try:
        if args.command == "peers":
            result = client.peers()
        elif args.command == "status":
            result = client.status()
        elif args.command == "execute":
            result = client.execute(args.command)
        elif args.command == "apps":
            result = client.apps()
        elif args.command == "app-start":
            result = client.app_start(args.app_id)
        elif args.command == "app-stop":
            result = client.app_stop(args.app_id)
        elif args.command == "config-get":
            result = client.config_get(args.key)
        elif args.command == "config-set":
            result = client.config_set(args.key, args.value)
        elif args.command == "sync":
            result = client.sync()
        elif args.command == "bridges":
            result = client.bridges()
        else:
            print(f"Unknown command: {args.command}", file=sys.stderr)
            sys.exit(1)

        format_output(result, args.json)

        if not result.get("success", False):
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
