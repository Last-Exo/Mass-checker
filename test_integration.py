#!/usr/bin/env python3
"""
Integration test script for the unified turnstile solver system
Tests all components without requiring actual Epic Games login
"""

import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_imports():
    """Test all critical imports"""
    print("🧪 Testing imports...")
    
    try:
        from utils.unified_turnstile_handler import UnifiedTurnstileHandler, create_turnstile_handler
        print("✅ Unified turnstile handler")
        
        from utils.dropbox_uploader import DropboxUploader
        print("✅ Dropbox uploader")
        
        from utils.login_handler import LoginHandler
        from utils.auth_handler import AuthHandler
        print("✅ Login and auth handlers")
        
        from utils.browser_manager import BrowserManager
        print("✅ Browser manager")
        
        from utils.account_checker import AccountChecker
        print("✅ Account checker")
        
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

async def test_solver_availability():
    """Test solver availability"""
    print("\n🔍 Testing solver availability...")
    
    try:
        from solvers.turnstile_solver import ASYNC_SOLVER_AVAILABLE
        from solvers.cloudflare_botsforge import BOTSFORGE_AVAILABLE  
        from solvers.cloudflare_bypass import DRISSION_AVAILABLE
        
        print(f"  - Turnstile Solver (Primary): {'✅' if ASYNC_SOLVER_AVAILABLE else '❌'}")
        print(f"  - BotsForge (Fallback 1): {'✅' if BOTSFORGE_AVAILABLE else '❌'}")
        print(f"  - DrissionPage (Fallback 2): {'✅' if DRISSION_AVAILABLE else '❌'}")
        
        available_count = sum([ASYNC_SOLVER_AVAILABLE, BOTSFORGE_AVAILABLE, DRISSION_AVAILABLE])
        print(f"  - Total available: {available_count}/3")
        
        return available_count > 0
    except Exception as e:
        print(f"❌ Solver availability check failed: {e}")
        return False

async def test_handler_creation():
    """Test creating handlers with different configurations"""
    print("\n🏗️ Testing handler creation...")
    
    try:
        from utils.unified_turnstile_handler import create_turnstile_handler
        from utils.login_handler import LoginHandler
        from utils.auth_handler import AuthHandler
        from utils.dropbox_uploader import DropboxUploader
        
        # Test turnstile handler creation
        handler = create_turnstile_handler(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
            proxy="127.0.0.1:8080"
        )
        print("✅ Turnstile handler created")
        
        # Test login handler creation
        auth_handler = AuthHandler()
        login_handler = LoginHandler(
            auth_handler, 
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
            proxy="127.0.0.1:8080"
        )
        print("✅ Login handler created")
        
        # Test dropbox uploader creation
        uploader = DropboxUploader()
        print("✅ Dropbox uploader created")
        
        return True
    except Exception as e:
        print(f"❌ Handler creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_account_checker():
    """Test account checker initialization"""
    print("\n🔧 Testing account checker...")
    
    try:
        from utils.account_checker import AccountChecker
        
        # Test with no proxies
        checker = AccountChecker()
        print("✅ Account checker created (no proxies)")
        
        # Test with proxy list
        checker_with_proxies = AccountChecker(proxies=["127.0.0.1:8080", "127.0.0.1:8081"])
        print("✅ Account checker created (with proxies)")
        
        return True
    except Exception as e:
        print(f"❌ Account checker test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all tests"""
    print("🚀 Starting integration tests...\n")
    
    tests = [
        ("Imports", test_imports),
        ("Solver Availability", test_solver_availability),
        ("Handler Creation", test_handler_creation),
        ("Account Checker", test_account_checker),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n📊 Test Results:")
    print("=" * 50)
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:20} {status}")
        if result:
            passed += 1
    
    print("=" * 50)
    print(f"Total: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 All tests passed! Integration is ready.")
        return True
    else:
        print(f"\n⚠️ {len(results) - passed} tests failed. Check the errors above.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)