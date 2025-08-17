"""
Login handler for Epic Games accounts
Handles the actual login process, form filling, and navigation
"""
import asyncio
import logging
import random
from typing import Any, Dict, Optional, Tuple

from config.settings import LOGIN_URL, NAVIGATION_TIMEOUT

logger = logging.getLogger(__name__)


class LoginHandler:
    """Handles Epic Games login process"""
    
    def __init__(self, turnstile_handler, auth_handler):
        self.turnstile_handler = turnstile_handler
        self.auth_handler = auth_handler
    
    async def perform_login(self, page: Any, email: str, password: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Perform the complete login process
        """
        try:
            logger.info(f"🔐 {email} - Starting login process...")
            
            # Navigate to login page
            if not await self._navigate_to_login(page, email):
                return False, {'error': 'Failed to navigate to login page'}
            
            # Handle any initial Turnstile challenges
            if not await self.turnstile_handler.handle_turnstile_if_present(page):
                return False, {'error': 'Failed to solve initial Turnstile challenge'}
            
            # Fill login form
            if not await self._fill_login_form(page, email, password):
                return False, {'error': 'Failed to fill login form'}
            
            # Submit form and handle challenges
            if not await self._submit_login_form(page, email):
                return False, {'error': 'Failed to submit login form'}
            
            # Wait for login to complete and detect outcome
            status, result = await self.auth_handler.detect_outcome_and_extract_auth(page, email)
            
            if status.value == "valid":
                logger.info(f"✅ {email} - Login successful")
                return True, result
            else:
                logger.info(f"❌ {email} - Login failed: {status.value}")
                return False, result
                
        except Exception as e:
            logger.info(f"❌ {email} - Login error: {str(e)}")
            return False, {'error': f'Login error: {str(e)}'}
    
    async def _navigate_to_login(self, page: Any, email: str) -> bool:
        """Navigate to Epic Games login page"""
        try:
            logger.info(f"🌐 {email} - Navigating to login page...")
            
            response = await page.goto(LOGIN_URL, wait_until="networkidle", timeout=NAVIGATION_TIMEOUT)
            
            if not response or response.status != 200:
                logger.info(f"❌ {email} - Failed to load login page: {response.status if response else 'No response'}")
                return False
            
            # Wait for page to be ready
            await asyncio.sleep(2)
            
            # Check if we're on the correct page
            current_url = page.url
            if 'login' not in current_url.lower() and 'signin' not in current_url.lower():
                logger.info(f"⚠️ {email} - Unexpected page after navigation: {current_url}")
            
            logger.info(f"✅ {email} - Successfully navigated to login page")
            return True
            
        except Exception as e:
            logger.info(f"❌ {email} - Navigation error: {str(e)}")
            return False
    
    async def _fill_login_form(self, page: Any, email: str, password: str) -> bool:
        """Fill the login form with credentials"""
        try:
            logger.info(f"📝 {email} - Filling login form...")
            
            # Wait for form elements to be available
            await page.wait_for_selector('input[type="email"], input[name="email"], input[id="email"]', timeout=10000)
            
            # Find and fill email field
            email_selectors = [
                'input[type="email"]',
                'input[name="email"]',
                'input[id="email"]',
                'input[placeholder*="email" i]',
                'input[aria-label*="email" i]'
            ]
            
            email_filled = False
            for selector in email_selectors:
                try:
                    email_field = await page.query_selector(selector)
                    if email_field:
                        await email_field.clear()
                        await email_field.type(email, delay=random.randint(50, 150))
                        email_filled = True
                        logger.info(f"✅ {email} - Email field filled")
                        break
                except:
                    continue
            
            if not email_filled:
                logger.info(f"❌ {email} - Could not find email field")
                return False
            
            # Small delay between fields
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Find and fill password field
            password_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                'input[id="password"]',
                'input[placeholder*="password" i]',
                'input[aria-label*="password" i]'
            ]
            
            password_filled = False
            for selector in password_selectors:
                try:
                    password_field = await page.query_selector(selector)
                    if password_field:
                        await password_field.clear()
                        await password_field.type(password, delay=random.randint(50, 150))
                        password_filled = True
                        logger.info(f"✅ {email} - Password field filled")
                        break
                except:
                    continue
            
            if not password_filled:
                logger.info(f"❌ {email} - Could not find password field")
                return False
            
            # Small delay after filling
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            logger.info(f"✅ {email} - Login form filled successfully")
            return True
            
        except Exception as e:
            logger.info(f"❌ {email} - Error filling login form: {str(e)}")
            return False
    
    async def _submit_login_form(self, page: Any, email: str) -> bool:
        """Submit the login form and handle any challenges"""
        try:
            logger.info(f"🚀 {email} - Submitting login form...")
            
            # Handle any Turnstile challenges before submission
            if not await self.turnstile_handler.handle_turnstile_if_present(page):
                logger.info(f"❌ {email} - Failed to solve Turnstile before submission")
                return False
            
            # Find and click submit button
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button[id*="login" i]',
                'button[id*="signin" i]',
                'button:has-text("Sign In")',
                'button:has-text("Log In")',
                'button:has-text("Login")',
                '.login-button',
                '.signin-button'
            ]
            
            submit_clicked = False
            for selector in submit_selectors:
                try:
                    submit_button = await page.query_selector(selector)
                    if submit_button:
                        # Check if button is enabled
                        is_disabled = await submit_button.get_attribute('disabled')
                        if is_disabled:
                            logger.info(f"⚠️ {email} - Submit button is disabled, waiting...")
                            await asyncio.sleep(2)
                            continue
                        
                        await submit_button.click()
                        submit_clicked = True
                        logger.info(f"✅ {email} - Submit button clicked")
                        break
                except:
                    continue
            
            if not submit_clicked:
                # Try pressing Enter as fallback
                try:
                    await page.keyboard.press('Enter')
                    submit_clicked = True
                    logger.info(f"✅ {email} - Form submitted with Enter key")
                except:
                    pass
            
            if not submit_clicked:
                logger.info(f"❌ {email} - Could not submit login form")
                return False
            
            # Wait for form submission to process
            await asyncio.sleep(3)
            
            # Handle any post-submission challenges
            challenge_attempts = 0
            max_challenge_attempts = 3
            
            while challenge_attempts < max_challenge_attempts:
                # Check for Turnstile challenges after submission
                if await self.turnstile_handler.detect_turnstile_challenge(page):
                    logger.info(f"🔐 {email} - Post-submission Turnstile detected (attempt {challenge_attempts + 1})")
                    
                    if await self.turnstile_handler.handle_turnstile_if_present(page):
                        logger.info(f"✅ {email} - Post-submission Turnstile solved")
                        await asyncio.sleep(2)  # Wait for page to process
                    else:
                        logger.info(f"❌ {email} - Failed to solve post-submission Turnstile")
                        return False
                    
                    challenge_attempts += 1
                else:
                    # No more challenges, break out of loop
                    break
            
            # Final wait for login to complete
            await asyncio.sleep(2)
            
            logger.info(f"✅ {email} - Login form submission completed")
            return True
            
        except Exception as e:
            logger.info(f"❌ {email} - Error submitting login form: {str(e)}")
            return False
    
    async def handle_two_factor_auth(self, page: Any, email: str, two_fa_code: Optional[str] = None) -> bool:
        """Handle two-factor authentication if required"""
        try:
            if not two_fa_code:
                logger.info(f"⚠️ {email} - 2FA required but no code provided")
                return False
            
            logger.info(f"🔐 {email} - Handling two-factor authentication...")
            
            # Wait for 2FA form
            await page.wait_for_selector('input[name*="code"], input[id*="code"], input[placeholder*="code" i]', timeout=10000)
            
            # Find and fill 2FA code field
            code_selectors = [
                'input[name*="code"]',
                'input[id*="code"]',
                'input[placeholder*="code" i]',
                'input[aria-label*="code" i]',
                'input[type="text"][maxlength="6"]',
                'input[type="number"][maxlength="6"]'
            ]
            
            code_filled = False
            for selector in code_selectors:
                try:
                    code_field = await page.query_selector(selector)
                    if code_field:
                        await code_field.clear()
                        await code_field.type(two_fa_code, delay=random.randint(100, 200))
                        code_filled = True
                        logger.info(f"✅ {email} - 2FA code entered")
                        break
                except:
                    continue
            
            if not code_filled:
                logger.info(f"❌ {email} - Could not find 2FA code field")
                return False
            
            # Submit 2FA form
            submit_selectors = [
                'button[type="submit"]',
                'button:has-text("Verify")',
                'button:has-text("Continue")',
                'button:has-text("Submit")'
            ]
            
            for selector in submit_selectors:
                try:
                    submit_button = await page.query_selector(selector)
                    if submit_button:
                        await submit_button.click()
                        logger.info(f"✅ {email} - 2FA form submitted")
                        break
                except:
                    continue
            
            # Wait for 2FA to process
            await asyncio.sleep(3)
            
            return True
            
        except Exception as e:
            logger.info(f"❌ {email} - Error handling 2FA: {str(e)}")
            return False