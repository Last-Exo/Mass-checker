"""
Turnstile challenge handler for Epic Games login
Integrates with the turnstile solver to handle Cloudflare challenges
Uses both API service and direct async solver approaches
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


class TurnstileHandler:
    """Handles Turnstile challenges during Epic Games login"""
    
    def __init__(self):
        self.solver = None
    
    async def solve_turnstile_challenge(self, page: Any, url: str, sitekey: str) -> Dict[str, Any]:
        """
        Solve Turnstile challenge using the integrated solver system
        First tries API service, then falls back to direct async solver
        Returns dict with success status and token
        """
        start_time = time.time()
        
        if DEBUG_ENHANCED_FEATURES:
            logger.info(f"🔧 Starting advanced Turnstile challenge solve for sitekey: {sitekey}")
        
        # First try using the Turnstile API service if enabled
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
        
        # If both methods fail
        elapsed_time = round(time.time() - start_time, 3)
        return {
            'success': False,
            'error': 'All Turnstile solving methods failed',
            'elapsed_time': elapsed_time
        }
    
    async def _solve_with_api_service(self, url: str, sitekey: str) -> Dict[str, Any]:
        """Solve using the Turnstile API service"""
        try:
            api_url = f"http://{TURNSTILE_SERVICE_HOST}:{TURNSTILE_SERVICE_PORT}/turnstile"
            params = {
                'url': url,
                'sitekey': sitekey
            }
            
            if DEBUG_ENHANCED_FEATURES:
                logger.info(f"🌐 Using Turnstile API service: {api_url}")
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=TURNSTILE_TIMEOUT)) as session:
                # Step 1: Submit the task
                async with session.post(api_url, json=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        task_id = data.get('id')
                        
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
                                        result = await result_response.json()
                                        
                                        if isinstance(result, dict) and result.get('status') == 'success':
                                            token = result.get('token')
                                            if token:
                                                if DEBUG_ENHANCED_FEATURES:
                                                    logger.info(f"✅ API service solved Turnstile successfully")
                                                return {
                                                    'success': True,
                                                    'token': token,
                                                    'elapsed_time': attempt + 1
                                                }
                                        elif result.get('status') == 'failed':
                                            return {
                                                'success': False,
                                                'error': result.get('error', 'API service failed'),
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
        """Solve using the direct async solver"""
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
            # Look for Turnstile widget
            turnstile_widget = await page.query_selector('.cf-turnstile')
            if not turnstile_widget:
                return None
            
            # Extract sitekey
            sitekey = await turnstile_widget.get_attribute('data-sitekey')
            if not sitekey:
                logger.info("⚠️ Turnstile widget found but no sitekey")
                return None
            
            # Get current URL
            current_url = page.url
            
            logger.info(f"🔍 Turnstile challenge detected - Sitekey: {sitekey}")
            
            return {
                'url': current_url,
                'sitekey': sitekey,
                'action': await turnstile_widget.get_attribute('data-action'),
                'cdata': await turnstile_widget.get_attribute('data-cdata')
            }
            
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
            
            # Solve challenge
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