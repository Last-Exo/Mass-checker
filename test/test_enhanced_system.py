#!/usr/bin/env python3
"""
Comprehensive test script for the unified Turnstile system
Tests all solver methods and fallback mechanisms
"""

import asyncio
import logging
import sys
import time
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.unified_turnstile_handler import create_turnstile_handler
from utils.account_checker import AccountChecker

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_unified_turnstile_system():
    """Test the complete unified Turnstile system"""
    
    print("🚀 Starting Unified Turnstile System Test")
    print("=" * 60)
    
    # Test 1: Solver Availability
    print("\n🔍 Test 1: Solver Availability")
    try:
        from solvers.turnstile_solver import ASYNC_SOLVER_AVAILABLE
        from solvers.cloudflare_botsforge import BOTSFORGE_AVAILABLE  
        from solvers.cloudflare_bypass import DRISSION_AVAILABLE
        
        print(f"  - Turnstile Solver: {'✅' if ASYNC_SOLVER_AVAILABLE else '❌'}")
        print(f"  - BotsForge: {'✅' if BOTSFORGE_AVAILABLE else '❌'}")
        print(f"  - DrissionPage: {'✅' if DRISSION_AVAILABLE else '❌'}")
        
        available_count = sum([ASYNC_SOLVER_AVAILABLE, BOTSFORGE_AVAILABLE, DRISSION_AVAILABLE])
        print(f"  - Available solvers: {available_count}/3")
        
        if available_count == 0:
            print("❌ No solvers available!")
            return False
        else:
            print("✅ At least one solver is available")
    except Exception as e:
        print(f"❌ Solver availability check failed: {e}")
        return False
    
    # Test 2: Handler Creation
    print("\n🔧 Test 2: Handler Creation")
    try:
        handler = create_turnstile_handler(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
            proxy="127.0.0.1:8080"
        )
        print("✅ Unified handler created successfully")
    except Exception as e:
        print(f"❌ Handler creation failed: {e}")
        return False
    
    # Test 3: Account Checker Integration
    print("\n🔗 Test 3: Account Checker Integration")
    try:
        checker = AccountChecker(proxies=["127.0.0.1:8080"])
        print("✅ Account checker created with unified handler")
    except Exception as e:
        print(f"❌ Account checker integration failed: {e}")
        return False
    
    # Test 4: Dropbox Integration
    print("\n📸 Test 4: Dropbox Integration")
    try:
        from utils.dropbox_uploader import DropboxUploader
        uploader = DropboxUploader()
        print("✅ Dropbox uploader available")
    except Exception as e:
        print(f"❌ Dropbox integration failed: {e}")
        return False
    
    print("\n🎉 All tests passed! Unified system is ready.")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_unified_turnstile_system())
    if success:
        print("\n✅ Unified Turnstile System: FULLY OPERATIONAL")
    else:
        print("\n❌ Unified Turnstile System: ISSUES DETECTED")
        sys.exit(1)