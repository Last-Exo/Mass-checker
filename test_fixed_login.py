#!/usr/bin/env python3
"""
Test script to verify the fixed login process with Turnstile handling
"""

import asyncio
import logging
import sys
import os
from utils.account_checker import AccountChecker

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_account_login():
    """Test the account login process with a sample account"""
    
    # Test credentials (these will likely fail but should show the process working)
    test_email = "test@example.com"
    test_password = "testpassword123"
    
    logger.info("🧪 Testing Epic Games account login process...")
    
    try:
        # Initialize account checker without proxies for testing
        async with AccountChecker(proxies=None) as checker:
            logger.info("✅ Account checker initialized")
            
            # Test the login process
            status, result = await checker.check_account(test_email, test_password)
            
            logger.info(f"📊 Login test result:")
            logger.info(f"   Status: {status.value}")
            logger.info(f"   Result: {result}")
            
            if status.value == "error":
                error_msg = result.get('error', 'Unknown error')
                if 'turnstile' in error_msg.lower() or 'challenge' in error_msg.lower():
                    logger.info("🔍 Turnstile/Challenge related error - this is expected for test credentials")
                elif 'invalid' in error_msg.lower() or 'credentials' in error_msg.lower():
                    logger.info("🔍 Invalid credentials error - this is expected for test credentials")
                elif 'navigation' in error_msg.lower() or 'timeout' in error_msg.lower():
                    logger.error("❌ Navigation/timeout error - this indicates a problem with the login process")
                else:
                    logger.info(f"🔍 Other error: {error_msg}")
            
            return status.value != "error" or "invalid" in result.get('error', '').lower()
            
    except Exception as e:
        logger.error(f"❌ Test failed with exception: {str(e)}")
        return False

async def test_turnstile_detection():
    """Test Turnstile detection on Epic Games login page"""
    
    logger.info("🔍 Testing Turnstile detection...")
    
    try:
        from utils.turnstile_handler import TurnstileHandler
        from utils.browser_manager import BrowserManager
        
        # Initialize components
        browser_manager = BrowserManager(proxies=None)
        turnstile_handler = TurnstileHandler()
        
        async with browser_manager:
            # Get browser and create page
            browser = await browser_manager.get_or_launch_browser(None)
            context = await browser_manager.get_optimized_context(browser, "__noproxy__")
            page = await context.new_page()
            
            try:
                # Navigate to Epic Games login
                logger.info("🌐 Navigating to Epic Games login page...")
                await page.goto("https://www.epicgames.com/id/login", wait_until="networkidle", timeout=30000)
                
                # Test challenge detection
                challenge_info = await turnstile_handler.detect_turnstile_challenge(page)
                
                if challenge_info:
                    logger.info("✅ Turnstile challenge detected!")
                    logger.info(f"   URL: {challenge_info['url']}")
                    logger.info(f"   Sitekey: {challenge_info['sitekey']}")
                    logger.info(f"   Type: {challenge_info.get('challenge_type', 'standard')}")
                    
                    # Test challenge handling
                    logger.info("🔧 Testing challenge handling...")
                    success = await turnstile_handler.handle_turnstile_if_present(page)
                    
                    if success:
                        logger.info("✅ Challenge handling completed successfully")
                        
                        # Check if we can now access login form
                        await asyncio.sleep(3)
                        email_field = await page.query_selector('input[type="email"], input[name="email"]')
                        if email_field:
                            logger.info("✅ Login form is now accessible")
                            return True
                        else:
                            logger.info("⚠️ Login form not yet accessible, but challenge handling succeeded")
                            return True
                    else:
                        logger.error("❌ Challenge handling failed")
                        return False
                else:
                    logger.info("ℹ️ No Turnstile challenge detected")
                    
                    # Check if login form is directly available
                    email_field = await page.query_selector('input[type="email"], input[name="email"]')
                    if email_field:
                        logger.info("✅ Login form is directly accessible")
                        return True
                    else:
                        logger.info("❌ No login form found and no challenge detected")
                        return False
                
            finally:
                await page.close()
                
    except Exception as e:
        logger.error(f"❌ Turnstile detection test failed: {str(e)}")
        return False

async def test_api_service():
    """Test the Turnstile API service"""
    
    logger.info("🧪 Testing Turnstile API service...")
    
    try:
        import aiohttp
        
        # Test service health
        async with aiohttp.ClientSession() as session:
            async with session.get('http://127.0.0.1:5000/') as response:
                if response.status == 200:
                    logger.info("✅ Turnstile API service is accessible")
                    return True
                else:
                    logger.error(f"❌ API service returned status {response.status}")
                    return False
                    
    except Exception as e:
        logger.error(f"❌ API service test failed: {str(e)}")
        return False

async def main():
    """Run all tests"""
    
    logger.info("🚀 Starting comprehensive login system tests...")
    logger.info("=" * 60)
    
    tests = [
        ("API Service", test_api_service),
        ("Turnstile Detection", test_turnstile_detection),
        ("Account Login Process", test_account_login),
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\n📋 Running test: {test_name}")
        logger.info("-" * 40)
        
        try:
            result = await test_func()
            results.append((test_name, result))
            
            if result:
                logger.info(f"✅ {test_name}: PASSED")
            else:
                logger.error(f"❌ {test_name}: FAILED")
                
        except Exception as e:
            logger.error(f"❌ {test_name}: EXCEPTION - {str(e)}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 Test Results Summary:")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"   {test_name}: {status}")
    
    logger.info(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! The login system is working correctly.")
    elif passed > 0:
        logger.info("⚠️ Some tests passed. The system is partially working.")
    else:
        logger.error("❌ All tests failed. The system needs attention.")
    
    return passed == total

if __name__ == '__main__':
    success = asyncio.run(main())
    sys.exit(0 if success else 1)