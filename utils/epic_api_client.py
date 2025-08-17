"""
Epic Games API Client for fetching account details
Uses auth codes extracted from browser login to access Epic Games APIs
"""
import aiohttp
import asyncio
import json
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class EpicAPIClient:
    """Client for Epic Games API to fetch account details"""
    
    def __init__(self):
        self.session = None
        
        # Epic Games API endpoints
        self.base_url = "https://fortnite-public-service-prod11.ol.epicgames.com"
        self.account_url = "https://account-public-service-prod.ol.epicgames.com"
        
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
    
    async def get_account_details(self, auth_token: str, email: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Fetch detailed account information using auth token
        Returns (success, details_dict)
        """
        try:
            logger.info(f"🔍 {email} - Fetching account details with auth token...")
            
            # Get account info
            account_info = await self._get_account_info(auth_token)
            if not account_info:
                return False, {'error': 'Failed to get account info'}
            
            account_id = account_info.get('id')
            if not account_id:
                return False, {'error': 'No account ID found'}
            
            logger.info(f"🆔 {email} - Account ID: {account_id}")
            
            # Basic account details only
            details = {
                'account_id': account_id,
                'display_name': account_info.get('displayName', ''),
                'email': account_info.get('email', email),
                'country': account_info.get('country', ''),
                'created_at': account_info.get('dateOfBirth', ''),
                'updated_at': account_info.get('lastLogin', ''),
                'language': account_info.get('preferredLanguage', '')
            }
            
            logger.info(f"✅ {email} - Account details retrieved successfully")
            return True, details
            
        except Exception as e:
            logger.info(f"❌ {email} - Error fetching account details: {str(e)}")
            return False, {'error': f'API error: {str(e)}'}
    
    async def _get_account_info(self, auth_token: str) -> Optional[Dict[str, Any]]:
        """Get basic account information"""
        try:
            headers = {
                'Authorization': f'Bearer {auth_token}',
                'Content-Type': 'application/json'
            }
            
            # Try multiple endpoints for account info
            endpoints = [
                f"{self.account_url}/account/api/public/account",
                f"{self.account_url}/account/api/oauth/verify",
                "https://account-public-service-prod03.ol.epicgames.com/account/api/public/account"
            ]
            
            for endpoint in endpoints:
                try:
                    async with self.session.get(endpoint, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            if isinstance(data, list) and len(data) > 0:
                                return data[0]
                            elif isinstance(data, dict):
                                return data
                except:
                    continue
            
            return None
            
        except Exception as e:
            logger.info(f"Error getting account info: {e}")
            return None
    

    


# Alternative method using different auth approach
class EpicWebAPIClient:
    """Alternative Epic API client using web-based authentication"""
    
    def __init__(self):
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
    
    async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_account_details_from_cookies(self, cookies: Dict[str, str], email: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Alternative method: Extract account details using session cookies
        This might work better with browser-extracted auth data
        """
        try:
            logger.info(f"🔍 {email} - Fetching account details using session cookies...")
            
            # Convert cookies to proper format
            cookie_header = '; '.join([f"{name}={value}" for name, value in cookies.items()])
            
            headers = {
                'Cookie': cookie_header,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.epicgames.com/',
                'Accept': 'application/json, text/plain, */*'
            }
            
            # Try to access Epic Games account page
            account_endpoints = [
                'https://www.epicgames.com/account/v2/api/public/account',
                'https://www.epicgames.com/id/api/account',
                'https://account-public-service-prod.ol.epicgames.com/account/api/public/account'
            ]
            
            for endpoint in account_endpoints:
                try:
                    async with self.session.get(endpoint, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            logger.info(f"✅ {email} - Account data retrieved from {endpoint}")
                            return True, {
                                'account_id': data.get('id', ''),
                                'display_name': data.get('displayName', ''),
                                'email': data.get('email', email),
                                'created_at': data.get('dateOfBirth', ''),
                                'message': 'Account details retrieved via web API'
                            }
                except Exception as e:
                    logger.info(f"Failed endpoint {endpoint}: {e}")
                    continue
            
            # If direct API fails, try to extract from Epic Games web pages
            return await self._extract_from_web_pages(headers, email)
            
        except Exception as e:
            logger.info(f"❌ {email} - Error with cookie-based auth: {str(e)}")
            return False, {'error': f'Cookie auth error: {str(e)}'}
    
    async def _extract_from_web_pages(self, headers: Dict[str, str], email: str) -> Tuple[bool, Dict[str, Any]]:
        """Extract account info from Epic Games web pages"""
        try:
            # Try Epic Games account page
            async with self.session.get('https://www.epicgames.com/account/personal', headers=headers) as response:
                if response.status == 200:
                    html_content = await response.text()
                    
                    # Basic extraction from HTML (this is a fallback method)
                    details = {
                        'message': 'Account accessible via web interface',
                        'login_successful': True,
                        'account_page_accessible': True
                    }
                    
                    # Try to extract basic info from HTML
                    if 'displayName' in html_content:
                        import re
                        display_name_match = re.search(r'"displayName":"([^"]+)"', html_content)
                        if display_name_match:
                            details['display_name'] = display_name_match.group(1)
                    
                    logger.info(f"✅ {email} - Account page accessible, basic info extracted")
                    return True, details
            
            return False, {'error': 'Could not access account pages'}
            
        except Exception as e:
            logger.info(f"Error extracting from web pages: {e}")
            return False, {'error': f'Web extraction error: {str(e)}'}