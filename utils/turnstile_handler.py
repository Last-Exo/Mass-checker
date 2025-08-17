"""
Turnstile challenge handler for Epic Games login
Integrates with the turnstile solver to handle Cloudflare challenges
"""
import asyncio
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

try:
    from turnstile_solver.async_solver import AsyncTurnstileSolver
    TURNSTILE_SOLVER_AVAILABLE = True
except ImportError:
    TURNSTILE_SOLVER_AVAILABLE = False
    logger.warning("Turnstile solver not available - challenges may not be handled")


class TurnstileHandler:
    """Handles Turnstile challenges during Epic Games login"""
    
    def __init__(self):
        self.solver = None
    
    async def solve_turnstile_challenge(self, page: Any, url: str, sitekey: str) -> Dict[str, Any]:
        """
        Solve Turnstile challenge using the integrated solver
        Returns dict with success status and token
        """
        try:
            logger.info(f"🔐 Solving Turnstile challenge for {url}")
            
            if not TURNSTILE_SOLVER_AVAILABLE:
                logger.info("❌ Turnstile solver not available")
                return {'success': False, 'error': 'Turnstile solver not available'}
            
            # Check if turnstile widget is present
            turnstile_widget = await page.query_selector('.cf-turnstile')
            if not turnstile_widget:
                logger.info("❌ No Turnstile widget found on page")
                return {'success': False, 'error': 'No Turnstile widget found'}
            
            # Get current user agent from page
            user_agent = await page.evaluate("() => navigator.userAgent")
            
            # Initialize solver with current page settings
            solver = AsyncTurnstileSolver(
                debug=True,
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
                logger.info(f"✅ Turnstile solved successfully in {result.elapsed_time_seconds}s")
                
                # Inject the token into the current page
                await self._inject_turnstile_token(page, result.turnstile_value)
                
                return {
                    'success': True,
                    'token': result.turnstile_value,
                    'elapsed_time': result.elapsed_time_seconds
                }
            else:
                logger.info(f"❌ Turnstile solve failed: {result.reason}")
                return {
                    'success': False,
                    'error': result.reason or 'Unknown error',
                    'elapsed_time': result.elapsed_time_seconds
                }
                
        except Exception as e:
            logger.info(f"❌ Error solving Turnstile challenge: {str(e)}")
            return {'success': False, 'error': f'Solver error: {str(e)}'}
    
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