#!/usr/bin/env python3
"""
Test script to verify Turnstile solver functionality with actual Epic Games challenges
"""

import asyncio
import logging
import sys
import os
from patchright.async_api import async_playwright
from config.settings import LOGIN_URL, NAVIGATION_TIMEOUT

# Add turnstile solver to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'turnstile_solver'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_turnstile_with_epic():
    """Test Turnstile solver with Epic Games login page"""
    
    async with async_playwright() as p:
        # Launch browser with enhanced settings
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-dev-shm-usage',
                '--no-first-run',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-images',
                '--disable-javascript',  # Temporarily disable to see raw HTML
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        page = await context.new_page()
        
        try:
            logger.info("🌐 Navigating to Epic Games login page...")
            response = await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT)
            
            if not response:
                logger.error("Failed to get response from login page")
                return
            
            logger.info(f"📊 Response status: {response.status}")
            logger.info(f"📍 Final URL: {page.url}")
            
            # Wait for page to load
            await asyncio.sleep(3)
            
            # Check for Cloudflare challenge indicators
            cf_indicators = [
                'challenges.cloudflare.com',
                'cf-challenge',
                'cf-turnstile',
                'cloudflare',
                'ray id',
                'enable javascript and cookies to continue'
            ]
            
            page_content = await page.content()
            page_text = await page.inner_text('body')
            
            cf_detected = False
            for indicator in cf_indicators:
                if indicator.lower() in page_content.lower() or indicator.lower() in page_text.lower():
                    logger.info(f"🔍 Cloudflare indicator found: {indicator}")
                    cf_detected = True
            
            if cf_detected:
                logger.info("🛡️ Cloudflare challenge detected!")
                
                # Look for challenge iframe
                iframes = await page.query_selector_all('iframe')
                logger.info(f"📋 Found {len(iframes)} iframes")
                
                for i, iframe in enumerate(iframes):
                    src = await iframe.get_attribute('src')
                    if src:
                        logger.info(f"   Iframe {i+1}: {src}")
                        if 'challenges.cloudflare.com' in src:
                            logger.info("   ✅ This is a Cloudflare challenge iframe!")
                
                # Look for turnstile widgets
                turnstile_widgets = await page.query_selector_all('.cf-turnstile, [data-sitekey]')
                logger.info(f"🔐 Found {len(turnstile_widgets)} Turnstile widgets")
                
                for i, widget in enumerate(turnstile_widgets):
                    sitekey = await widget.get_attribute('data-sitekey')
                    if sitekey:
                        logger.info(f"   Widget {i+1} sitekey: {sitekey}")
                
                # Check for challenge form
                forms = await page.query_selector_all('form')
                logger.info(f"📝 Found {len(forms)} forms")
                
                for i, form in enumerate(forms):
                    action = await form.get_attribute('action')
                    method = await form.get_attribute('method')
                    logger.info(f"   Form {i+1}: action={action}, method={method}")
                
                # Look for challenge script
                scripts = await page.query_selector_all('script')
                challenge_script_found = False
                for script in scripts:
                    src = await script.get_attribute('src')
                    if src and 'challenge-platform' in src:
                        logger.info(f"🔧 Challenge script found: {src}")
                        challenge_script_found = True
                
                if challenge_script_found:
                    logger.info("✅ This appears to be a Cloudflare managed challenge")
                    
                    # Try to wait for the challenge to auto-solve or present interactive elements
                    logger.info("⏳ Waiting for challenge to load...")
                    await asyncio.sleep(10)
                    
                    # Check if page changed
                    new_url = page.url
                    if new_url != LOGIN_URL:
                        logger.info(f"📍 Page redirected to: {new_url}")
                        
                        # Check if we're now on the actual login page
                        if 'login' in new_url.lower() and 'error' not in new_url.lower():
                            logger.info("🎉 Successfully bypassed Cloudflare challenge!")
                            
                            # Now look for actual login form elements
                            await asyncio.sleep(3)
                            
                            # Look for email field
                            email_selectors = [
                                'input[type="email"]',
                                'input[name="email"]',
                                'input[id="email"]',
                                'input[placeholder*="email" i]'
                            ]
                            
                            for selector in email_selectors:
                                element = await page.query_selector(selector)
                                if element:
                                    logger.info(f"✅ Found email field: {selector}")
                                    break
                            else:
                                logger.info("❌ No email field found on login page")
                        else:
                            logger.info("❌ Still on challenge/error page")
                    else:
                        logger.info("❌ Page did not redirect, challenge may have failed")
                
            else:
                logger.info("✅ No Cloudflare challenge detected - checking for login form")
                
                # Look for login form elements
                email_field = await page.query_selector('input[type="email"], input[name="email"]')
                password_field = await page.query_selector('input[type="password"], input[name="password"]')
                
                if email_field and password_field:
                    logger.info("✅ Login form found - no challenge needed")
                else:
                    logger.info("❌ No login form found")
            
            # Save debug files
            await page.screenshot(path='turnstile_test_debug.png')
            with open('turnstile_test_debug.html', 'w', encoding='utf-8') as f:
                f.write(await page.content())
            
            logger.info("📄 Debug files saved: turnstile_test_debug.png, turnstile_test_debug.html")
            
        except Exception as e:
            logger.error(f"❌ Error during test: {str(e)}")
        
        finally:
            await browser.close()

async def test_turnstile_api_service():
    """Test the Turnstile API service directly"""
    import aiohttp
    
    try:
        logger.info("🧪 Testing Turnstile API service...")
        
        # Test service health
        async with aiohttp.ClientSession() as session:
            async with session.get('http://127.0.0.1:5000/') as response:
                if response.status == 200:
                    logger.info("✅ Turnstile API service is running")
                else:
                    logger.error(f"❌ Turnstile API service returned status {response.status}")
                    return
        
        # Test with a sample challenge (this will likely fail but shows the API works)
        test_params = {
            'url': 'https://www.epicgames.com/id/login',
            'sitekey': '0x4AAAAAAADnPIDROzbs0Aoj'  # Common Cloudflare sitekey
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post('http://127.0.0.1:5000/turnstile', json=test_params) as response:
                if response.status == 200:
                    data = await response.json()
                    task_id = data.get('id')
                    logger.info(f"✅ Turnstile task submitted: {task_id}")
                    
                    # Poll for result
                    for attempt in range(10):
                        await asyncio.sleep(2)
                        async with session.get(f'http://127.0.0.1:5000/result?id={task_id}') as result_response:
                            if result_response.status == 200:
                                result = await result_response.json()
                                logger.info(f"📊 Attempt {attempt + 1}: {result}")
                                
                                if result.get('status') in ['success', 'failed']:
                                    break
                    
                else:
                    logger.error(f"❌ Failed to submit task: {response.status}")
                    
    except Exception as e:
        logger.error(f"❌ Error testing API service: {str(e)}")

if __name__ == '__main__':
    async def main():
        await test_turnstile_api_service()
        await test_turnstile_with_epic()
    
    asyncio.run(main())