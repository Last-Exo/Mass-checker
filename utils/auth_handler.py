"""
Authentication handler for Epic Games accounts
Handles login flow, auth code extraction, and account information retrieval
"""
import asyncio
import logging
import aiohttp
import json
from typing import Dict, Any, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class AccountStatus(Enum):
    VALID = "valid"
    INVALID = "invalid"
    CAPTCHA = "captcha"
    TWO_FA = "2fa"
    ERROR = "error"


class AuthHandler:
    """Handles Epic Games authentication flow"""
    
    def __init__(self):
        self.session = None
    
    async def __aenter__(self):
        """Initialize aiohttp session"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        )
        return self
    
    async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
    
    async def detect_outcome_and_extract_auth(self, page: Any, email: str) -> Tuple[AccountStatus, Dict[str, Any]]:
        """
        Detect login outcome and extract authentication data
        """
        try:
            logger.info(f"🔍 {email} - Detecting login outcome...")
            
            # Wait for page to stabilize
            await asyncio.sleep(3)
            
            current_url = page.url
            logger.info(f"📍 {email} - Current URL: {current_url}")
            
            # Check for successful login indicators
            if any(indicator in current_url for indicator in [
                'epicgames.com/account',
                'epicgames.com/id/account',
                'fortnite.com/account'
            ]):
                logger.info(f"✅ {email} - Login successful, extracting auth data...")
                
                # Extract auth code
                auth_code = await self.extract_auth_code(page, email)
                if auth_code:
                    # Get account information
                    account_info = await self.get_account_info_from_page(page, email)
                    
                    return AccountStatus.VALID, {
                        'auth_code': auth_code,
                        'account_info': account_info,
                        'login_url': current_url
                    }
                else:
                    # Try to get account info directly from the page
                    account_info = await self.get_account_info_from_page(page, email)
                    if account_info.get('isLoggedIn'):
                        return AccountStatus.VALID, {
                            'account_info': account_info,
                            'login_url': current_url
                        }
            
            # Check for 2FA requirement
            if any(indicator in current_url.lower() for indicator in [
                'mfa', '2fa', 'two-factor', 'verify'
            ]):
                logger.info(f"🔐 {email} - Two-factor authentication required")
                return AccountStatus.TWO_FA, {'message': 'Two-factor authentication required'}
            
            # Check for captcha/challenge
            if any(indicator in current_url.lower() for indicator in [
                'captcha', 'challenge', 'verify-human'
            ]):
                logger.info(f"🤖 {email} - Captcha challenge detected")
                return AccountStatus.CAPTCHA, {'message': 'Captcha challenge required'}
            
            # Check page content for error indicators
            page_content = await page.content()
            
            # Check for invalid credentials
            if any(error in page_content.lower() for error in [
                'invalid credentials', 'incorrect password', 'wrong password',
                'invalid email', 'account not found', 'login failed'
            ]):
                logger.info(f"❌ {email} - Invalid credentials detected")
                return AccountStatus.INVALID, {'message': 'Invalid credentials'}
            
            # If we're still on login page, credentials are likely invalid
            if 'login' in current_url.lower() or 'signin' in current_url.lower():
                logger.info(f"❌ {email} - Still on login page, likely invalid credentials")
                return AccountStatus.INVALID, {'message': 'Login failed - still on login page'}
            
            # Default to error if we can't determine the outcome
            logger.info(f"⚠️ {email} - Unable to determine login outcome")
            return AccountStatus.ERROR, {'message': 'Unable to determine login outcome', 'url': current_url}
            
        except Exception as e:
            logger.info(f"❌ {email} - Error detecting login outcome: {str(e)}")
            return AccountStatus.ERROR, {'error': f'Detection error: {str(e)}'}
    
    async def extract_auth_code(self, page: Any, email: str) -> Optional[str]:
        """
        Extract authorization code from Epic Games redirect
        """
        try:
            logger.info(f"🔑 {email} - Extracting authorization code...")
            
            # Navigate to the redirect endpoint to get auth code
            redirect_url = "https://www.epicgames.com/id/api/redirect?clientId=007c0bfe154c4f5396648f013c641dcf&responseType=code"
            
            try:
                response = await page.goto(redirect_url, wait_until="networkidle", timeout=15000)
                if response and response.status == 200:
                    content = await page.content()
                    
                    # Try to parse JSON response
                    try:
                        # Look for JSON in the page content
                        if 'redirectUrl' in content and 'authorizationCode' in content:
                            import re
                            auth_code_match = re.search(r'"authorizationCode":"([^"]+)"', content)
                            if auth_code_match:
                                auth_code = auth_code_match.group(1)
                                logger.info(f"✅ {email} - Authorization code extracted: {auth_code[:20]}...")
                                return auth_code
                    except:
                        pass
                    
                    # Check if we got redirected with code in URL
                    current_url = page.url
                    if 'code=' in current_url:
                        import re
                        code_match = re.search(r'code=([^&]+)', current_url)
                        if code_match:
                            auth_code = code_match.group(1)
                            logger.info(f"✅ {email} - Authorization code from URL: {auth_code[:20]}...")
                            return auth_code
                            
            except Exception as e:
                logger.info(f"⚠️ {email} - Error accessing redirect endpoint: {e}")
            
            # Alternative: try to extract from current page
            current_content = await page.content()
            if 'authorizationCode' in current_content:
                import re
                auth_code_match = re.search(r'"authorizationCode":"([^"]+)"', current_content)
                if auth_code_match:
                    auth_code = auth_code_match.group(1)
                    logger.info(f"✅ {email} - Authorization code from page: {auth_code[:20]}...")
                    return auth_code
            
            logger.info(f"⚠️ {email} - No authorization code found")
            return None
            
        except Exception as e:
            logger.info(f"❌ {email} - Error extracting auth code: {str(e)}")
            return None
    
    async def get_account_info_from_page(self, page: Any, email: str) -> Dict[str, Any]:
        """
        Get account information from the current page or API
        """
        try:
            logger.info(f"📋 {email} - Getting account information...")
            
            # Try to get account info from the correct API endpoint
            try:
                # Use the correct Fortnite API endpoint with locale
                api_url = "https://www.fortnite.com/en/api/accountInfo"
                response = await page.goto(api_url, wait_until="networkidle", timeout=10000)
                
                if response and response.status == 200:
                    content = await page.content()
                    
                    # Try to parse JSON response
                    try:
                        # Look for JSON in the page content
                        import re
                        # More specific regex to match the account info structure
                        json_match = re.search(r'\{[^{}]*"isLoggedIn"[^{}]*\}', content)
                        if not json_match:
                            # Try broader match
                            json_match = re.search(r'\{.*?"accountInfo".*?\}', content, re.DOTALL)
                        
                        if json_match:
                            account_data = json.loads(json_match.group(0))
                            
                            if account_data.get('isLoggedIn'):
                                logger.info(f"✅ {email} - Account info retrieved from API")
                                # Extract the accountInfo if it's nested
                                if 'accountInfo' in account_data:
                                    return {
                                        'isLoggedIn': account_data['isLoggedIn'],
                                        **account_data['accountInfo']
                                    }
                                return account_data
                    except json.JSONDecodeError as e:
                        logger.info(f"⚠️ {email} - JSON parse error: {e}")
                        
                    # If JSON parsing fails, try to extract specific fields
                    import re
                    display_name_match = re.search(r'"displayName"\s*:\s*"([^"]+)"', content)
                    account_id_match = re.search(r'"id"\s*:\s*"([^"]+)"', content)
                    country_match = re.search(r'"country"\s*:\s*"([^"]+)"', content)
                    
                    if display_name_match or account_id_match:
                        result = {'isLoggedIn': True}
                        if display_name_match:
                            result['displayName'] = display_name_match.group(1)
                        if account_id_match:
                            result['id'] = account_id_match.group(1)
                        if country_match:
                            result['country'] = country_match.group(1)
                        
                        logger.info(f"✅ {email} - Account info extracted from API response")
                        return result
                        
            except Exception as e:
                logger.info(f"⚠️ {email} - Error accessing account API: {e}")
            
            # Fallback: try to extract from current page
            try:
                # Look for account data in page scripts or content
                account_info = await page.evaluate("""
                    () => {
                        // Try to find account data in window objects
                        if (window.accountInfo) return window.accountInfo;
                        if (window.user) return window.user;
                        if (window.profile) return window.profile;
                        
                        // Try to find in script tags
                        const scripts = document.querySelectorAll('script');
                        for (let script of scripts) {
                            const content = script.textContent || script.innerHTML;
                            if (content.includes('displayName') || content.includes('accountInfo')) {
                                try {
                                    // Look for various patterns
                                    let match = content.match(/accountInfo["\']?\\s*:\\s*({[^}]+})/);
                                    if (!match) {
                                        match = content.match(/"isLoggedIn"\\s*:\\s*true[^}]*}/);
                                    }
                                    if (match) {
                                        return JSON.parse(match[1] || match[0]);
                                    }
                                } catch (e) {}
                            }
                        }
                        
                        return null;
                    }
                """)
                
                if account_info:
                    logger.info(f"✅ {email} - Account info extracted from page")
                    return account_info
                    
            except Exception as e:
                logger.info(f"⚠️ {email} - Error extracting from page: {e}")
            
            # Return basic info if we can't get detailed data
            return {
                'isLoggedIn': True,
                'email': email,
                'message': 'Login successful but limited account info available'
            }
            
        except Exception as e:
            logger.info(f"❌ {email} - Error getting account info: {str(e)}")
            return {'error': f'Account info error: {str(e)}'}
    
    async def fetch_account_details_with_auth(self, auth_code: str, email: str) -> Dict[str, Any]:
        """
        Fetch detailed account information using authorization code
        """
        try:
            logger.info(f"🔍 {email} - Fetching account details with auth code...")
            
            if not self.session:
                raise Exception("HTTP session not initialized")
            
            # Exchange auth code for access token
            token_data = await self._exchange_auth_code_for_token(auth_code)
            if not token_data:
                return {'error': 'Failed to exchange auth code for token'}
            
            access_token = token_data.get('access_token')
            if not access_token:
                return {'error': 'No access token received'}
            
            # Use the access token to get account details
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Try multiple Epic Games API endpoints
            endpoints = [
                'https://account-public-service-prod.ol.epicgames.com/account/api/public/account',
                'https://www.epicgames.com/account/v2/api/public/account',
                'https://fortnite-public-service-prod11.ol.epicgames.com/fortnite/api/game/v2/profile'
            ]
            
            for endpoint in endpoints:
                try:
                    async with self.session.get(endpoint, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            logger.info(f"✅ {email} - Account details retrieved from {endpoint}")
                            
                            # Format the response
                            if isinstance(data, list) and len(data) > 0:
                                account_data = data[0]
                            else:
                                account_data = data
                            
                            return {
                                'account_id': account_data.get('id', ''),
                                'display_name': account_data.get('displayName', ''),
                                'email': account_data.get('email', email),
                                'country': account_data.get('country', ''),
                                'created_at': account_data.get('dateOfBirth', ''),
                                'last_login': account_data.get('lastLogin', ''),
                                'auth_method': 'api_token'
                            }
                            
                except Exception as e:
                    logger.info(f"⚠️ {email} - Failed endpoint {endpoint}: {e}")
                    continue
            
            return {'error': 'All API endpoints failed'}
            
        except Exception as e:
            logger.info(f"❌ {email} - Error fetching account details: {str(e)}")
            return {'error': f'Fetch error: {str(e)}'}
    
    async def _exchange_auth_code_for_token(self, auth_code: str) -> Optional[Dict[str, Any]]:
        """Exchange authorization code for access token"""
        try:
            token_url = "https://account-public-service-prod.ol.epicgames.com/account/api/oauth/token"
            
            data = {
                'grant_type': 'authorization_code',
                'code': auth_code,
                'client_id': '007c0bfe154c4f5396648f013c641dcf'
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            async with self.session.post(token_url, data=data, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.info(f"❌ Token exchange failed: {response.status}")
                    return None
                    
        except Exception as e:
            logger.info(f"❌ Error exchanging auth code: {e}")
            return None