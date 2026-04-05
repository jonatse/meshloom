"""
Startup self-check for Meshloom.

Verifies that all required components can be imported and initialized
before attempting to run the full system.
"""

import sys
import os

vendor_dir = os.path.join(os.path.dirname(__file__), '..', 'vendor', 'python')
if os.path.exists(vendor_dir) and vendor_dir not in sys.path:
    sys.path.insert(0, vendor_dir)

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


def check_imports():
    """Verify all required imports work."""
    print("Checking imports...")
    
    required_imports = [
        ("src.core.config", "Config"),
        ("src.core.diagnostics", "Diagnostics"),
        ("src.core.events", "EventBus"),
        ("src.core.version", "VERSION"),
        ("src.services.network", "NetworkService"),
        ("src.services.sync.engine", "SyncEngine"),
        ("src.services.container.manager", "ContainerManager"),
        ("src.apps.registry", "AppRegistry"),
        ("src.bridges.manager", "BridgeManager"),
        ("src.api.server", "APIServer"),
        ("src.api.commands", "CommandHandler"),
    ]
    
    errors = []
    
    for module_name, class_name in required_imports:
        try:
            module = __import__(module_name, fromlist=[class_name])
            cls = getattr(module, class_name)
            print(f"  OK: {module_name}.{class_name}")
        except Exception as e:
            errors.append(f"  FAIL: {module_name}.{class_name}: {e}")
            print(f"  FAIL: {module_name}.{class_name}: {e}")
    
    return len(errors) == 0


def check_config():
    """Verify config can be created."""
    print("\nChecking config...")
    
    try:
        from src.core.config import Config
        config = Config()
        
        required_keys = ["app.version", "sync.sync_dir", "reticulum.identity_path"]
        for key in required_keys:
            value = config.get(key)
            print(f"  OK: {key} = {value}")
        
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def check_diagnostics():
    """Verify diagnostics can be created."""
    print("\nChecking diagnostics...")
    
    try:
        from src.core.config import Config
        from src.core.diagnostics import Diagnostics
        
        config = Config()
        diag = Diagnostics(config)
        
        diag.info("verify", "Diagnostics operational")
        print("  OK: Diagnostics working")
        
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def check_event_bus():
    """Verify event bus can be created."""
    print("\nChecking event bus...")
    
    try:
        from src.core.events import EventBus
        
        bus = EventBus()
        
        received = []
        def handler(event):
            received.append(event)
        
        bus.subscribe("test.event", handler)
        bus.publish_type("test.event", {"value": 123}, "verify")
        
        if received and received[0].data.get("value") == 123:
            print("  OK: Event bus working")
            return True
        else:
            print("  FAIL: Event not received")
            return False
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def check_services():
    """Verify service classes can be instantiated."""
    print("\nChecking services...")
    
    try:
        from src.core.config import Config
        from src.core.diagnostics import Diagnostics
        
        config = Config()
        diag = Diagnostics(config)
        
        from src.services.network import NetworkService
        network = NetworkService(config, diag)
        print("  OK: NetworkService")
        
        from src.bridges.manager import BridgeManager
        bridge_mgr = BridgeManager()
        print("  OK: BridgeManager")
        
        from src.api.server import APIServer
        api_server = APIServer()
        print("  OK: APIServer")
        
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def check_rns():
    """Check if RNS is available (optional)."""
    print("\nChecking RNS (optional)...")
    
    try:
        import RNS
        print("  OK: RNS available")
        return True
    except ImportError:
        print("  SKIP: RNS not installed (optional)")
        return True


def verify():
    """Run all verification checks."""
    print("=" * 50)
    print("Meshloom Startup Verification")
    print("=" * 50)
    
    results = []
    
    results.append(("Imports", check_imports()))
    results.append(("Config", check_config()))
    results.append(("Diagnostics", check_diagnostics()))
    results.append(("Event Bus", check_event_bus()))
    results.append(("Services", check_services()))
    results.append(("RNS", check_rns()))
    
    print("\n" + "=" * 50)
    print("Results:")
    print("=" * 50)
    
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("All checks passed! Meshloom is ready to start.")
        return 0
    else:
        print("Some checks failed. Please fix the errors before running.")
        return 1


if __name__ == "__main__":
    sys.exit(verify())
