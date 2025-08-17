"""
Enhanced Turnstile challenge handler for Epic Games login
Integrates multiple bypass methods for maximum success rate

Architecture:
- Primary: API service (api_solver.py) - Main solver running as web service
- Fallback 1: Direct async solver (async_solver.py) - Core engine for standalone use  
- Fallback 2: DrissionPage CloudflareBypasser - Alternative bypass method
"""
import asyncio
import logging
import time
import aiohttp
from typing import Dict, Any, Optional
from config.settings import (
    ENABLE_TURNSTILE_SERVICE, 
    TURNSTILE_SERVICE_HOST, 
    TURNSTILE_SERVICE_PORT, 
    TURNSTILE_TIMEOUT,
    DEBUG_ENHANCED_FEATURES
)

logger = logging.getLogger(__name__)

try:
    from turnstile_solver.async_solver import AsyncTurnstileSolver
    ASYNC_SOLVER_AVAILABLE = True
except ImportError:
    ASYNC_SOLVER_AVAILABLE = False
    logger.warning("Async turnstile solver not available")

try:
    from .enhanced_turnstile_handler import enhanced_turnstile_handler
    ENHANCED_HANDLER_AVAILABLE = True
except ImportError:
    ENHANCED_HANDLER_AVAILABLE = False
    logger.warning("Enhanced turnstile handler not available")


class TurnstileHandler:
    """Handles Turnstile challenges during Epic Games login"""
    
    def __init__(self):
        self.solver = None
    
    async def solve_turnstile_challenge(self, page: Any, url: str, sitekey: str) -> Dict[str, Any]:
        """
        Enhanced Turnstile challenge solver with multiple bypass methods
        Uses the enhanced handler with API solver + DrissionPage fallback
        Returns dict with success status and token
        """
        start_time = time.time()
        
        if DEBUG_ENHANCED_FEATURES:
            logger.info(f"🔧 Starting enhanced Turnstile challenge solve for sitekey: {sitekey}")
        
        # Try enhanced handler first (includes API solver + DrissionPage fallback)
        if ENHANCED_HANDLER_AVAILABLE:
            try:
                result = await enhanced_turnstile_handler.solve_turnstile_challenge(page)
                
                if result.get('success'):
                    # If we got a token, inject it into the current page
                    if result.get('token'):
                        await self._inject_turnstile_token(page, result['token'])
                    
                    if DEBUG_ENHANCED_FEATURES:
                        method = result.get('method', 'unknown')
                        logger.info(f"✅ Enhanced handler succeeded using {method}")
                    
                    return result
                else:
                    if DEBUG_ENHANCED_FEATURES:
                        logger.info(f"⚠️ Enhanced handler failed: {result.get('error', 'Unknown error')}")
            except Exception as e:
                if DEBUG_ENHANCED_FEATURES:
                    logger.error(f"❌ Enhanced handler error: {str(e)}")
        
        # Fallback to original API service method
        if ENABLE_TURNSTILE_SERVICE:
            result = await self._solve_with_api_service(url, sitekey)
            if result['success']:
                # Inject the token into the current page
                await self._inject_turnstile_token(page, result['token'])
                return result
            else:
                if DEBUG_ENHANCED_FEATURES:
                    logger.info(f"⚠️ API service failed: {result.get('error', 'Unknown error')}")
        
        # Fallback to direct async solver
        if ASYNC_SOLVER_AVAILABLE:
            result = await self._solve_with_async_solver(page, url, sitekey, start_time)
            if result['success']:
                return result
            else:
                if DEBUG_ENHANCED_FEATURES:
                    logger.info(f"⚠️ Async solver failed: {result.get('error', 'Unknown error')}")
        
        # If all methods fail
        elapsed_time = round(time.time() - start_time, 3)
        return {
            'success': False,
            'error': 'All Turnstile solving methods failed',
            'elapsed_time': elapsed_time
        }
    
    async def _solve_with_api_service(self, url: str, sitekey: str) -> Dict[str, Any]:
        """
        Solve using the Turnstile API service (api_solver.py)
        This is the main solver that runs as a web service with HTTP endpoints
        """
        try:
            api_url = f"http://{TURNSTILE_SERVICE_HOST}:{TURNSTILE_SERVICE_PORT}/turnstile"
            params = {
                'url': url,
                'sitekey': sitekey
            }
            
            if DEBUG_ENHANCED_FEATURES:
                logger.info(f"🌐 Using Turnstile API service: {api_url}")
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=TURNSTILE_TIMEOUT)) as session:
                # Step 1: Submit the task (API expects GET with query params)
                async with session.get(api_url, params=params) as response:
                    if response.status in [200, 202]:  # Accept both 200 OK and 202 Accepted
                        data = await response.json()
                        task_id = data.get('task_id') or data.get('id')  # Handle both formats
                        
                        if task_id:
                            if DEBUG_ENHANCED_FEATURES:
                                logger.info(f"🔄 Turnstile task submitted: {task_id}")
                            
                            # Step 2: Poll for result
                            result_url = f"http://{TURNSTILE_SERVICE_HOST}:{TURNSTILE_SERVICE_PORT}/result"
                            max_attempts = 30  # 30 seconds max
                            
                            for attempt in range(max_attempts):
                                await asyncio.sleep(1)  # Wait 1 second between polls
                                
                                async with session.get(result_url, params={'id': task_id}) as result_response:
                                    if result_response.status == 200:
                                        result_text = await result_response.text()
                                        
                                        # Handle different response formats
                                        if result_text == "CAPTCHA_NOT_READY":
                                            continue  # Keep polling
                                        
                                        try:
                                            result = await result_response.json()
                                            
                                            # Check for success with token
                                            if isinstance(result, dict):
                                                if result.get('status') == 'success' or result.get('value') not in ['CAPTCHA_FAIL', 'CAPTCHA_NOT_READY']:
                                                    token = result.get('token') or result.get('value')
                                                    if token and token not in ['CAPTCHA_FAIL', 'CAPTCHA_NOT_READY']:
                                                        if DEBUG_ENHANCED_FEATURES:
                                                            logger.info(f"✅ API service solved Turnstile successfully")
                                                        return {
                                                            'success': True,
                                                            'token': token,
                                                            'elapsed_time': attempt + 1
                                                        }
                                                
                                                # Check for explicit failure
                                                if result.get('status') == 'failed' or result.get('value') == 'CAPTCHA_FAIL':
                                                    return {
                                                        'success': False,
                                                        'error': result.get('error', 'API service failed to solve challenge'),
                                                        'elapsed_time': attempt + 1
                                                    }
                                        except:
                                            # If not JSON, treat as plain text response
                                            if result_text and result_text not in ['CAPTCHA_FAIL', 'CAPTCHA_NOT_READY']:
                                                if DEBUG_ENHANCED_FEATURES:
                                                    logger.info(f"✅ API service returned token: {result_text}")
                                                return {
                                                    'success': True,
                                                    'token': result_text,
                                                    'elapsed_time': attempt + 1
                                                }
                                            elif result_text == 'CAPTCHA_FAIL':
                                                return {
                                                    'success': False,
                                                    'error': 'API service failed to solve challenge',
                                                    'elapsed_time': attempt + 1
                                                }
                            
                            return {'success': False, 'error': 'API service timeout'}
                        else:
                            return {'success': False, 'error': 'No task ID received from API service'}
                    else:
                        return {'success': False, 'error': f'API service returned status {response.status}'}
                        
        except Exception as e:
            return {'success': False, 'error': f'API service error: {str(e)}'}
    
    async def _solve_with_async_solver(self, page: Any, url: str, sitekey: str, start_time: float) -> Dict[str, Any]:
        """
        Solve using the direct async solver (async_solver.py)
        This is the core engine used as fallback when API service is unavailable
        """
        try:
            # Check if turnstile widget is present
            turnstile_widget = await page.query_selector('.cf-turnstile')
            if not turnstile_widget:
                return {'success': False, 'error': 'No Turnstile widget found on page'}
            
            # Get current user agent from page
            user_agent = await page.evaluate("() => navigator.userAgent")
            
            # Initialize solver with current page settings
            solver = AsyncTurnstileSolver(
                debug=DEBUG_ENHANCED_FEATURES,
                headless=True,
                useragent=user_agent,
                browser_type="chromium"
            )
            
            # Solve the challenge
            result = await solver.solve(
                url=url,
                sitekey=sitekey,
                action=None,
                cdata=None
            )
            
            if result.status == "success" and result.turnstile_value:
                elapsed_time = round(time.time() - start_time, 3)
                if DEBUG_ENHANCED_FEATURES:
                    logger.info(f"✅ Async solver solved Turnstile in {elapsed_time}s")
                
                # Inject the token into the current page
                await self._inject_turnstile_token(page, result.turnstile_value)
                
                return {
                    'success': True,
                    'token': result.turnstile_value,
                    'elapsed_time': elapsed_time
                }
            else:
                elapsed_time = round(time.time() - start_time, 3)
                return {
                    'success': False,
                    'error': result.reason or 'Unknown async solver error',
                    'elapsed_time': elapsed_time
                }
                
        except Exception as e:
            elapsed_time = round(time.time() - start_time, 3)
            return {
                'success': False, 
                'error': f'Async solver error: {str(e)}',
                'elapsed_time': elapsed_time
            }
    
    async def _inject_turnstile_token(self, page: Any, token: str):
        """Inject the solved Turnstile token into the current page"""
        try:
            # Find the turnstile response input field
            response_input = await page.query_selector('input[name="cf-turnstile-response"]')
            if response_input:
                await response_input.fill(token)
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
                logger.info("✅ Turnstile response field created and token injected")
                
        except Exception as e:
            logger.info(f"⚠️ Error injecting Turnstile token: {e}")
    
    async def wait_for_turnstile_completion(self, page: Any, timeout: int = 30) -> bool:
        """Wait for Turnstile challenge to be completed on the page"""
        try:
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
            
            logger.info("✅ Turnstile challenge completed")
            return True
            
        except Exception as e:
            logger.info(f"❌ Turnstile completion timeout or error: {e}")
            return False
    
    async def detect_turnstile_challenge(self, page: Any) -> Optional[Dict[str, str]]:
        """Detect if there's a Turnstile challenge on the current page"""
        try:
            current_url = page.url
            page_content = await page.content()
            page_text = await page.inner_text('body')
            
            # Check for Cloudflare challenge indicators
            cf_indicators = [
                'challenges.cloudflare.com',
                'cf-challenge',
                'cf-turnstile',
                'enable javascript and cookies to continue',
                'checking your browser',
                'cloudflare',
                'ray id'
            ]
            
            cf_detected = False
            for indicator in cf_indicators:
                if indicator.lower() in page_content.lower() or indicator.lower() in page_text.lower():
                    cf_detected = True
                    if DEBUG_ENHANCED_FEATURES:
                        logger.info(f"🔍 Cloudflare indicator found: {indicator}")
                    break
            
            if not cf_detected:
                # Also check for standard Turnstile widget
                turnstile_widget = await page.query_selector('.cf-turnstile')
                if turnstile_widget:
                    sitekey = await turnstile_widget.get_attribute('data-sitekey')
                    if sitekey:
                        logger.info(f"🔍 Standard Turnstile widget detected - Sitekey: {sitekey}")
                        return {
                            'url': current_url,
                            'sitekey': sitekey,
                            'action': await turnstile_widget.get_attribute('data-action'),
                            'cdata': await turnstile_widget.get_attribute('data-cdata')
                        }
                return None
            
            # For managed challenges, we need to extract sitekey from different sources
            sitekey = None
            
            # Method 1: Look for sitekey in script tags
            scripts = await page.query_selector_all('script')
            for script in scripts:
                script_content = await script.inner_text()
                if script_content and 'sitekey' in script_content.lower():
                    # Try to extract sitekey using regex
                    import re
                    sitekey_match = re.search(r'["\']?sitekey["\']?\s*[:=]\s*["\']([^"\']+)["\']', script_content, re.IGNORECASE)
                    if sitekey_match:
                        sitekey = sitekey_match.group(1)
                        break
            
            # Method 2: Look for common Cloudflare sitekeys
            if not sitekey:
                common_sitekeys = [
                    '0x4AAAAAAADnPIDROzbs0Aoj',  # Common Epic Games sitekey
                    '0x4AAAAAAADnPIDROrmt1Wwj',  # Alternative Epic Games sitekey
                    '0x4AAAAAAAC3DHQFLr1GavRN',  # Another common sitekey
                ]
                
                for test_sitekey in common_sitekeys:
                    if test_sitekey in page_content:
                        sitekey = test_sitekey
                        break
            
            # Method 3: Use a default sitekey for Epic Games
            if not sitekey and 'epicgames.com' in current_url:
                sitekey = '0x4AAAAAAADnPIDROzbs0Aoj'  # Known Epic Games sitekey
                logger.info("🔧 Using known Epic Games sitekey for managed challenge")
            
            if sitekey:
                logger.info(f"🔍 Cloudflare managed challenge detected - Sitekey: {sitekey}")
                return {
                    'url': current_url,
                    'sitekey': sitekey,
                    'action': None,
                    'cdata': None,
                    'challenge_type': 'managed'
                }
            else:
                logger.info("⚠️ Cloudflare challenge detected but no sitekey found")
                return None
            
        except Exception as e:
            logger.info(f"❌ Error detecting Turnstile challenge: {e}")
            return None
    
    async def handle_turnstile_if_present(self, page: Any) -> bool:
        """Check for and handle Turnstile challenge if present"""
        try:
            # Detect challenge
            challenge_info = await self.detect_turnstile_challenge(page)
            if not challenge_info:
                return True  # No challenge, continue
            
            challenge_type = challenge_info.get('challenge_type', 'standard')
            
            if challenge_type == 'managed':
                # For managed challenges, we need to handle them differently
                logger.info("🔧 Handling Cloudflare managed challenge...")
                
                # First, try to wait for the challenge to auto-solve
                initial_url = page.url
                await asyncio.sleep(5)  # Wait for potential auto-solve
                
                current_url = page.url
                if current_url != initial_url and 'error' not in current_url.lower():
                    logger.info("✅ Managed challenge auto-solved")
                    return True
                
                # If auto-solve didn't work, try to solve with API
                result = await self.solve_turnstile_challenge(
                    page,
                    challenge_info['url'],
                    challenge_info['sitekey']
                )
                
                if result['success']:
                    # For managed challenges, we might need to wait longer and check for redirect
                    logger.info("⏳ Waiting for managed challenge to complete...")
                    
                    # Wait up to 30 seconds for redirect or page change
                    for attempt in range(30):
                        await asyncio.sleep(1)
                        new_url = page.url
                        
                        # Check if we've been redirected away from the challenge page
                        if new_url != initial_url:
                            if 'error' not in new_url.lower() and 'challenge' not in new_url.lower():
                                logger.info(f"✅ Managed challenge completed - redirected to: {new_url}")
                                return True
                            elif 'error' in new_url.lower():
                                logger.info(f"❌ Redirected to error page: {new_url}")
                                return False
                        
                        # Check if login form elements are now available
                        email_field = await page.query_selector('input[type="email"], input[name="email"]')
                        if email_field:
                            logger.info("✅ Login form now available - challenge completed")
                            return True
                    
                    logger.info("⚠️ Managed challenge timeout - continuing anyway")
                    return True  # Continue even if we're not sure it worked
                else:
                    logger.info(f"❌ Failed to solve managed challenge: {result.get('error', 'Unknown error')}")
                    return False
            else:
                # Standard challenge handling
                result = await self.solve_turnstile_challenge(
                    page,
                    challenge_info['url'],
                    challenge_info['sitekey']
                )
                
                if result['success']:
                    # Wait a moment for the page to process the solution
                    await asyncio.sleep(2)
                    return True
                else:
                    logger.info(f"❌ Failed to solve Turnstile: {result.get('error', 'Unknown error')}")
                    return False
                
        except Exception as e:
            logger.info(f"❌ Error handling Turnstile challenge: {e}")
            return False