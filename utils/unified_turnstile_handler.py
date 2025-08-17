"""
Unified Turnstile Handler - Integrates all three solver methods
1. Primary: Turnstile Solver (Theyka/Turnstile-Solver)
2. Fallback 1: CloudFlare BotsForge (BotsForge/CloudFlare)
3. Fallback 2: CloudFlare Bypass (sarperavci/CloudflareBypassForScraping)

Features:
- Uses user-uploaded proxies from Telegram menus
- Uses user agents from simple_useragent package (no hardcoded UAs)
- Maintains session cookies and user agents across URL navigations
- Takes screenshots on successful login and uploads to Dropbox
- Proper fallback chain with error handling
"""

import asyncio
import logging
import time
import aiohttp
import base64
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
from playwright.async_api import Page

# Import our solvers
try:
    from solvers.turnstile_solver import AsyncTurnstileSolver, TurnstileResult
    TURNSTILE_SOLVER_AVAILABLE = True
except ImportError as e:
    TURNSTILE_SOLVER_AVAILABLE = False
    logging.warning(f"Turnstile solver not available: {e}")

try:
    from solvers.cloudflare_botsforge.browser import Browser as CloudflareBrowser
    from solvers.cloudflare_botsforge.models import CaptchaTask
    BOTSFORGE_AVAILABLE = True
except ImportError as e:
    BOTSFORGE_AVAILABLE = False
    logging.warning(f"BotsForge CloudFlare solver not available: {e}")

try:
    from DrissionPage import ChromiumPage, ChromiumOptions
    from solvers.cloudflare_bypass import CloudflareBypasser
    DRISSION_AVAILABLE = True
except ImportError as e:
    DRISSION_AVAILABLE = False
    logging.warning(f"DrissionPage CloudFlare bypasser not available: {e}")

# Import utilities
from utils.dropbox_uploader import DropboxUploader
from config.settings import (
    ENABLE_TURNSTILE_SERVICE,
    TURNSTILE_SERVICE_HOST,
    TURNSTILE_SERVICE_PORT,
    TURNSTILE_TIMEOUT,
    DEBUG_ENHANCED_FEATURES,
    DROPBOX_ENABLED
)

logger = logging.getLogger(__name__)


class UnifiedTurnstileHandler:
    """Unified handler for all Turnstile/Cloudflare bypass methods"""
    
    def __init__(self, user_agent: str = None, proxy: str = None):
        self.user_agent = user_agent
        self.proxy = proxy
        self.dropbox_uploader = DropboxUploader() if DROPBOX_ENABLED else None
        
        # Known Epic Games sitekeys
        self.epic_sitekeys = [
            "0x4AAAAAAADnPIDROzLVaoAo",
            "0x4AAAAAAADnPIDROzLVaoAp", 
            "0x4AAAAAAADnPIDROzLVaoAq",
            "0x4AAAAAAADnPIDROzLVaoAr"
        ]
    
    async def detect_turnstile_challenge(self, page: Page) -> Dict[str, Any]:
        """
        Enhanced detection for Turnstile/Cloudflare challenges
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
                "challenge-form",
                "ray id",
                "enable javascript and cookies to continue"
            ]
            
            page_content = await page.content()
            page_title = await page.title()
            current_url = page.url
            
            # Check title and content for indicators
            challenge_detected = False
            detected_indicator = None
            for indicator in indicators:
                if indicator.lower() in page_title.lower() or indicator.lower() in page_content.lower():
                    challenge_detected = True
                    detected_indicator = indicator
                    break
            
            if not challenge_detected:
                return {"detected": False}
            
            if DEBUG_ENHANCED_FEATURES:
                logger.info(f"🔍 Turnstile/Cloudflare challenge detected: {detected_indicator}")
            
            # Try to find Turnstile widget
            turnstile_elements = await page.query_selector_all('[data-sitekey]')
            
            challenge_info = {
                "detected": True,
                "url": current_url,
                "sitekey": None,
                "action": None,
                "cdata": None,
                "method": "turnstile_solver",  # Default to primary method
                "indicator": detected_indicator
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
                
                if DEBUG_ENHANCED_FEATURES:
                    logger.info(f"🎯 Found Turnstile widget with sitekey: {sitekey}")
            else:
                # Try to find sitekey in page source for managed challenges
                for sitekey in self.epic_sitekeys:
                    if sitekey in page_content:
                        challenge_info["sitekey"] = sitekey
                        if DEBUG_ENHANCED_FEATURES:
                            logger.info(f"🎯 Found Epic Games sitekey in page: {sitekey}")
                        break
                
                # If no specific sitekey found, will try fallback methods
                if not challenge_info["sitekey"]:
                    if DEBUG_ENHANCED_FEATURES:
                        logger.info("🔄 No sitekey found, will use fallback methods")
            
            return challenge_info
            
        except Exception as e:
            logger.error(f"❌ Error detecting Turnstile challenge: {str(e)}")
            return {"detected": False, "error": str(e)}
    
    async def solve_with_turnstile_solver(self, challenge_info: Dict[str, Any]) -> Dict[str, Any]:
        """Method 1: Solve using the primary Turnstile solver"""
        if not TURNSTILE_SOLVER_AVAILABLE:
            return {"success": False, "error": "Turnstile solver not available"}
        
        if not challenge_info.get("sitekey"):
            return {"success": False, "error": "No sitekey available for Turnstile solver"}
        
        try:
            if DEBUG_ENHANCED_FEATURES:
                logger.info("🚀 Attempting primary Turnstile solver...")
            
            # Initialize solver with our user agent and proxy settings
            solver = AsyncTurnstileSolver(
                debug=DEBUG_ENHANCED_FEATURES,
                headless=True,
                useragent=self.user_agent,
                browser_type="chromium"
            )
            
            # Solve the challenge
            result = await solver.solve(
                url=challenge_info["url"],
                sitekey=challenge_info["sitekey"],
                action=challenge_info.get("action"),
                cdata=challenge_info.get("cdata")
            )
            
            if result.status == "success" and result.turnstile_value:
                if DEBUG_ENHANCED_FEATURES:
                    logger.info(f"✅ Primary Turnstile solver successful in {result.elapsed_time_seconds}s")
                
                return {
                    "success": True,
                    "token": result.turnstile_value,
                    "method": "turnstile_solver",
                    "elapsed_time": result.elapsed_time_seconds
                }
            else:
                return {
                    "success": False,
                    "error": result.reason or "Turnstile solver failed",
                    "elapsed_time": result.elapsed_time_seconds
                }
                
        except Exception as e:
            logger.error(f"❌ Turnstile solver error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def solve_with_botsforge(self, challenge_info: Dict[str, Any]) -> Dict[str, Any]:
        """Method 2: Solve using BotsForge CloudFlare solver"""
        if not BOTSFORGE_AVAILABLE:
            return {"success": False, "error": "BotsForge solver not available"}
        
        try:
            if DEBUG_ENHANCED_FEATURES:
                logger.info("🔄 Attempting BotsForge CloudFlare solver...")
            
            # Create captcha task
            task = CaptchaTask(
                websiteURL=challenge_info["url"],
                websiteKey=challenge_info.get("sitekey", ""),
                type="TurnstileTaskProxyless"
            )
            
            # Initialize browser with our settings
            browser = CloudflareBrowser()
            
            # Solve the captcha
            result = await browser.solve_captcha(task)
            
            if result and hasattr(result, 'solution') and result.solution:
                if DEBUG_ENHANCED_FEATURES:
                    logger.info("✅ BotsForge solver successful")
                
                return {
                    "success": True,
                    "token": result.solution.get('token', ''),
                    "method": "botsforge",
                    "elapsed_time": getattr(result, 'elapsed_time', 0)
                }
            else:
                return {
                    "success": False,
                    "error": "BotsForge solver failed to get solution"
                }
                
        except Exception as e:
            logger.error(f"❌ BotsForge solver error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def solve_with_drission_bypass(self, challenge_info: Dict[str, Any]) -> Dict[str, Any]:
        """Method 3: Solve using DrissionPage CloudFlare bypasser"""
        if not DRISSION_AVAILABLE:
            return {"success": False, "error": "DrissionPage bypasser not available"}
        
        try:
            if DEBUG_ENHANCED_FEATURES:
                logger.info("🔄 Attempting DrissionPage CloudFlare bypasser...")
            
            # Setup ChromiumOptions with our settings
            options = ChromiumOptions().auto_port()
            options.headless(True)
            options.set_argument("--no-sandbox")
            options.set_argument("--disable-gpu")
            options.set_argument("--disable-dev-shm-usage")
            
            # Set user agent if available
            if self.user_agent:
                options.set_user_agent(self.user_agent)
            
            # Set proxy if available
            if self.proxy:
                # Parse proxy format: username:password@host:port
                if '@' in self.proxy:
                    auth_part, host_part = self.proxy.split('@')
                    if ':' in auth_part:
                        username, password = auth_part.split(':', 1)
                        options.set_proxy(f"http://{host_part}")
                        options.set_argument(f"--proxy-auth={username}:{password}")
                    else:
                        options.set_proxy(f"http://{self.proxy}")
                else:
                    options.set_proxy(f"http://{self.proxy}")
            
            # Create driver
            driver = ChromiumPage(addr_or_opts=options)
            
            try:
                # Navigate to the URL
                driver.get(challenge_info["url"])
                
                # Use CloudflareBypasser
                cf_bypasser = CloudflareBypasser(driver, max_retries=5, log=DEBUG_ENHANCED_FEATURES)
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
                    
                    if DEBUG_ENHANCED_FEATURES:
                        logger.info("✅ DrissionPage bypass successful")
                    
                    return {
                        "success": True,
                        "method": "drission_bypass",
                        "token": token,
                        "cookies": {cookie.get("name", ""): cookie.get("value", "") for cookie in driver.cookies()},
                        "user_agent": driver.user_agent
                    }
                else:
                    return {"success": False, "error": "DrissionPage bypass failed"}
                    
            finally:
                driver.quit()
                
        except Exception as e:
            logger.error(f"❌ DrissionPage bypasser error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def take_screenshot_and_upload(self, page: Page, account_info: str = "") -> Optional[str]:
        """Take screenshot on successful login and upload to Dropbox"""
        if not self.dropbox_uploader:
            return None
        
        try:
            # Take screenshot
            screenshot_bytes = await page.screenshot(full_page=True)
            
            # Generate filename with timestamp
            timestamp = int(time.time())
            filename = f"successful_login_{timestamp}_{account_info.replace(':', '_').replace('@', '_at_')}.png"
            
            # Upload to Dropbox
            dropbox_path = await self.dropbox_uploader.upload_screenshot(screenshot_bytes, filename)
            
            if DEBUG_ENHANCED_FEATURES:
                logger.info(f"📸 Screenshot uploaded to Dropbox: {dropbox_path}")
            
            return dropbox_path
            
        except Exception as e:
            logger.error(f"❌ Error taking screenshot or uploading: {str(e)}")
            return None
    
    async def inject_turnstile_token(self, page: Page, token: str):
        """Inject the solved Turnstile token into the current page"""
        try:
            # Find the turnstile response input field
            response_input = await page.query_selector('input[name="cf-turnstile-response"]')
            if response_input:
                await response_input.fill(token)
                if DEBUG_ENHANCED_FEATURES:
                    logger.info("✅ Turnstile token injected into response field")
            else:
                # Create the response field if it doesn't exist
                await page.evaluate(f"""
                    () => {{
                        const input = document.createElement('input');
                        input.type = 'hidden';
                        input.name = 'cf-turnstile-response';
                        input.value = '{token}';
                        document.body.appendChild(input);
                    }}
                """)
                if DEBUG_ENHANCED_FEATURES:
                    logger.info("✅ Turnstile response field created and token injected")
                
        except Exception as e:
            logger.warning(f"⚠️ Error injecting Turnstile token: {e}")
    
    async def solve_turnstile_challenge(self, page: Page) -> Dict[str, Any]:
        """
        Main method to solve Turnstile challenges using all available methods
        Implements proper fallback chain: Primary -> Fallback1 -> Fallback2
        """
        try:
            start_time = time.time()
            
            # First detect the challenge
            challenge_info = await self.detect_turnstile_challenge(page)
            
            if not challenge_info.get("detected"):
                return {"success": True, "status": "no_challenge"}
            
            if DEBUG_ENHANCED_FEATURES:
                logger.info("🎯 Attempting to solve Turnstile/Cloudflare challenge...")
            
            # Method 1: Try primary Turnstile solver first
            if TURNSTILE_SOLVER_AVAILABLE and challenge_info.get("sitekey"):
                result = await self.solve_with_turnstile_solver(challenge_info)
                if result.get("success"):
                    # Inject token into page
                    if result.get("token"):
                        await self.inject_turnstile_token(page, result["token"])
                    return result
                
                if DEBUG_ENHANCED_FEATURES:
                    logger.warning("⚠️ Primary Turnstile solver failed, trying fallback 1...")
            
            # Method 2: Try BotsForge CloudFlare solver
            if BOTSFORGE_AVAILABLE:
                result = await self.solve_with_botsforge(challenge_info)
                if result.get("success"):
                    # Inject token into page if available
                    if result.get("token"):
                        await self.inject_turnstile_token(page, result["token"])
                    return result
                
                if DEBUG_ENHANCED_FEATURES:
                    logger.warning("⚠️ BotsForge solver failed, trying fallback 2...")
            
            # Method 3: Try DrissionPage bypasser as last resort
            if DRISSION_AVAILABLE:
                result = self.solve_with_drission_bypass(challenge_info)
                if result.get("success"):
                    # Apply cookies and user agent to current page if available
                    if result.get("cookies"):
                        try:
                            await page.context.add_cookies([
                                {"name": name, "value": value, "domain": urlparse(challenge_info["url"]).netloc}
                                for name, value in result["cookies"].items()
                                if name and value
                            ])
                        except Exception as e:
                            logger.warning(f"⚠️ Error applying cookies: {e}")
                    
                    return result
            
            # All methods failed
            elapsed_time = round(time.time() - start_time, 3)
            logger.error("❌ All Turnstile solving methods failed")
            return {
                "success": False, 
                "status": "captcha",
                "error": "All solving methods failed",
                "elapsed_time": elapsed_time
            }
            
        except Exception as e:
            elapsed_time = round(time.time() - start_time, 3)
            logger.error(f"❌ Error solving Turnstile challenge: {str(e)}")
            return {
                "success": False,
                "status": "error", 
                "error": str(e),
                "elapsed_time": elapsed_time
            }
    
    async def wait_for_turnstile_completion(self, page: Page, timeout: int = 30) -> bool:
        """Wait for Turnstile challenge to be completed on the page"""
        try:
            if DEBUG_ENHANCED_FEATURES:
                logger.info("⏳ Waiting for Turnstile completion...")
            
            # Wait for the turnstile response field to have a value
            await page.wait_for_function(
                """
                () => {
                    const responseField = document.querySelector('input[name="cf-turnstile-response"]');
                    return responseField && responseField.value && responseField.value.length > 0;
                }
                """,
                timeout=timeout * 1000
            )
            
            if DEBUG_ENHANCED_FEATURES:
                logger.info("✅ Turnstile challenge completed")
            return True
            
        except Exception as e:
            logger.warning(f"❌ Turnstile completion timeout or error: {e}")
            return False


# Global instance factory
def create_turnstile_handler(user_agent: str = None, proxy: str = None) -> UnifiedTurnstileHandler:
    """Create a new UnifiedTurnstileHandler instance with the given settings"""
    return UnifiedTurnstileHandler(user_agent=user_agent, proxy=proxy)