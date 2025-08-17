"""
Enhanced Turnstile Handler with Multiple Bypass Methods
Combines the original Turnstile solver with CloudflareBypassForScraping as fallback
"""

import asyncio
import logging
import time
import requests
import json
from typing import Optional, Dict, Any
from playwright.async_api import Page

# Import the CloudflareBypasser as fallback
try:
    from DrissionPage import ChromiumPage, ChromiumOptions
    from .CloudflareBypasser import CloudflareBypasser
    DRISSION_AVAILABLE = True
except ImportError:
    DRISSION_AVAILABLE = False
    logging.warning("DrissionPage not available. CloudflareBypasser fallback disabled.")

logger = logging.getLogger(__name__)

class EnhancedTurnstileHandler:
    """Enhanced Turnstile handler with multiple bypass methods"""
    
    def __init__(self, api_url: str = "http://127.0.0.1:5000"):
        self.api_url = api_url
        self.timeout = 30
        
        # Known Epic Games sitekeys for better detection
        self.epic_sitekeys = [
            "0x4AAAAAAADnPIDROzLVaoAo",
            "0x4AAAAAAADnPIDROzLVaoAp", 
            "0x4AAAAAAADnPIDROzLVaoAq",
            "0x4AAAAAAADnPIDROzLVaoAr"
        ]
    
    async def detect_turnstile_challenge(self, page: Page) -> Dict[str, Any]:
        """
        Enhanced detection for Turnstile challenges
        Returns challenge info or None if no challenge detected
        """
        try:
            # Wait a moment for page to load
            await asyncio.sleep(2)
            
            # Check for multiple Cloudflare indicators
            indicators = [
                "Just a moment",
                "Checking your browser",
                "Please wait while we check your browser",
                "Cloudflare",
                "cf-turnstile",
                "turnstile",
                "challenge-form"
            ]
            
            page_content = await page.content()
            page_title = await page.title()
            
            # Check title and content for indicators
            challenge_detected = False
            for indicator in indicators:
                if indicator.lower() in page_title.lower() or indicator.lower() in page_content.lower():
                    challenge_detected = True
                    break
            
            if not challenge_detected:
                return {"detected": False}
            
            logger.info("🔍 Turnstile challenge detected")
            
            # Try to find Turnstile widget
            turnstile_elements = await page.query_selector_all('[data-sitekey]')
            
            challenge_info = {
                "detected": True,
                "url": page.url,
                "sitekey": None,
                "action": None,
                "cdata": None,
                "method": "api_solver"  # Default method
            }
            
            # Extract sitekey from Turnstile widget
            if turnstile_elements:
                element = turnstile_elements[0]
                sitekey = await element.get_attribute('data-sitekey')
                action = await element.get_attribute('data-action')
                cdata = await element.get_attribute('data-cdata')
                
                challenge_info.update({
                    "sitekey": sitekey,
                    "action": action,
                    "cdata": cdata
                })
                
                logger.info(f"🎯 Found Turnstile widget with sitekey: {sitekey}")
            else:
                # Try to find sitekey in page source for managed challenges
                for sitekey in self.epic_sitekeys:
                    if sitekey in page_content:
                        challenge_info["sitekey"] = sitekey
                        logger.info(f"🎯 Found Epic Games sitekey in page: {sitekey}")
                        break
                
                # If no specific sitekey found, try fallback method
                if not challenge_info["sitekey"]:
                    challenge_info["method"] = "drission_fallback"
                    logger.info("🔄 No sitekey found, will use DrissionPage fallback")
            
            return challenge_info
            
        except Exception as e:
            logger.error(f"❌ Error detecting Turnstile challenge: {str(e)}")
            return {"detected": False, "error": str(e)}
    
    async def solve_with_api(self, challenge_info: Dict[str, Any]) -> Dict[str, Any]:
        """Solve using the original Turnstile API solver"""
        try:
            if not challenge_info.get("sitekey"):
                return {"success": False, "error": "No sitekey available for API solver"}
            
            # Make request to Turnstile API
            params = {
                "url": challenge_info["url"],
                "sitekey": challenge_info["sitekey"]
            }
            
            if challenge_info.get("action"):
                params["action"] = challenge_info["action"]
            if challenge_info.get("cdata"):
                params["cdata"] = challenge_info["cdata"]
            
            logger.info(f"🚀 Requesting Turnstile solve via API: {params}")
            
            # Request challenge solving
            response = requests.get(f"{self.api_url}/turnstile", params=params, timeout=10)
            
            if response.status_code == 202:
                # Get task ID
                task_data = response.json()
                task_id = task_data.get("task_id")
                
                if not task_id:
                    return {"success": False, "error": "No task ID received"}
                
                logger.info(f"📋 Task created: {task_id}")
                
                # Poll for result
                start_time = time.time()
                while time.time() - start_time < self.timeout:
                    try:
                        result_response = requests.get(
                            f"{self.api_url}/result", 
                            params={"id": task_id}, 
                            timeout=5
                        )
                        
                        if result_response.status_code == 200:
                            result_data = result_response.json()
                            
                            if isinstance(result_data, dict) and "value" in result_data:
                                token = result_data["value"]
                                if token and token != "CAPTCHA_FAIL" and token != "CAPTCHA_NOT_READY":
                                    logger.info(f"✅ API solver successful: {token[:20]}...")
                                    return {
                                        "success": True, 
                                        "token": token,
                                        "method": "api_solver",
                                        "elapsed_time": result_data.get("elapsed_time", 0)
                                    }
                                elif token == "CAPTCHA_FAIL":
                                    logger.warning("❌ API solver failed")
                                    return {"success": False, "error": "API solver failed"}
                        
                        elif result_response.status_code == 422:
                            logger.warning("❌ API solver failed with 422")
                            return {"success": False, "error": "Challenge failed"}
                        
                        # Still processing, wait and retry
                        await asyncio.sleep(2)
                        
                    except requests.RequestException as e:
                        logger.warning(f"⚠️ Error polling result: {str(e)}")
                        await asyncio.sleep(2)
                
                return {"success": False, "error": "API solver timeout"}
            
            else:
                logger.error(f"❌ API request failed: {response.status_code}")
                return {"success": False, "error": f"API request failed: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"❌ API solver error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def solve_with_drission(self, challenge_info: Dict[str, Any]) -> Dict[str, Any]:
        """Solve using DrissionPage CloudflareBypasser as fallback"""
        if not DRISSION_AVAILABLE:
            return {"success": False, "error": "DrissionPage not available"}
        
        try:
            logger.info("🔄 Attempting DrissionPage fallback method")
            
            # Setup ChromiumOptions
            options = ChromiumOptions().auto_port()
            options.headless(True)  # Run headless
            options.set_argument("--no-sandbox")
            options.set_argument("--disable-gpu")
            options.set_argument("--disable-dev-shm-usage")
            
            # Create driver
            driver = ChromiumPage(addr_or_opts=options)
            
            try:
                # Navigate to the URL
                driver.get(challenge_info["url"])
                
                # Use CloudflareBypasser
                cf_bypasser = CloudflareBypasser(driver, max_retries=5, log=True)
                cf_bypasser.bypass()
                
                # Check if bypass was successful
                if cf_bypasser.is_bypassed():
                    # Try to extract Turnstile token if available
                    token = None
                    try:
                        # Look for cf-turnstile-response input
                        turnstile_inputs = driver.eles("tag:input")
                        for input_elem in turnstile_inputs:
                            if "name" in input_elem.attrs and "cf-turnstile-response" in input_elem.attrs["name"]:
                                token = input_elem.attrs.get("value", "")
                                if token:
                                    break
                    except:
                        pass
                    
                    logger.info("✅ DrissionPage bypass successful")
                    return {
                        "success": True,
                        "method": "drission_fallback",
                        "token": token,
                        "cookies": {cookie.get("name", ""): cookie.get("value", "") for cookie in driver.cookies()},
                        "user_agent": driver.user_agent
                    }
                else:
                    logger.warning("❌ DrissionPage bypass failed")
                    return {"success": False, "error": "DrissionPage bypass failed"}
                    
            finally:
                driver.quit()
                
        except Exception as e:
            logger.error(f"❌ DrissionPage error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def solve_turnstile_challenge(self, page: Page) -> Dict[str, Any]:
        """
        Main method to solve Turnstile challenges using multiple methods
        """
        try:
            # First detect the challenge
            challenge_info = await self.detect_turnstile_challenge(page)
            
            if not challenge_info.get("detected"):
                return {"success": True, "status": "no_challenge"}
            
            logger.info("🎯 Attempting to solve Turnstile challenge...")
            
            # Method 1: Try API solver first (if sitekey available)
            if challenge_info.get("sitekey") and challenge_info.get("method") == "api_solver":
                result = await self.solve_with_api(challenge_info)
                if result.get("success"):
                    return result
                
                logger.warning("⚠️ API solver failed, trying fallback method...")
            
            # Method 2: Try DrissionPage fallback
            if DRISSION_AVAILABLE:
                result = self.solve_with_drission(challenge_info)
                if result.get("success"):
                    return result
            
            # All methods failed
            logger.error("❌ All Turnstile solving methods failed")
            return {
                "success": False, 
                "status": "captcha",
                "error": "All solving methods failed"
            }
            
        except Exception as e:
            logger.error(f"❌ Error solving Turnstile challenge: {str(e)}")
            return {
                "success": False,
                "status": "error", 
                "error": str(e)
            }

# Global instance
enhanced_turnstile_handler = EnhancedTurnstileHandler()