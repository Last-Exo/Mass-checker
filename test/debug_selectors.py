#!/usr/bin/env python3
"""
Debug script to test Epic Games login page selectors
"""

import asyncio
import logging
from patchright.async_api import async_playwright
from config.settings import LOGIN_URL, NAVIGATION_TIMEOUT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_epic_login_page():
    """Debug Epic Games login page to find correct selectors"""
    
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(
            headless=True,  # Must be True in server environment
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        page = await context.new_page()
        
        try:
            logger.info("🌐 Navigating to Epic Games login page...")
            response = await page.goto(LOGIN_URL, wait_until="networkidle", timeout=NAVIGATION_TIMEOUT)
            
            if not response or response.status != 200:
                logger.error(f"Failed to load login page: {response.status if response else 'No response'}")
                return
            
            logger.info(f"✅ Successfully loaded page: {page.url}")
            
            # Wait for page to fully load
            await asyncio.sleep(5)
            
            # Take a screenshot for debugging
            await page.screenshot(path='epic_login_debug.png')
            logger.info("📸 Screenshot saved as epic_login_debug.png")
            
            # Get page title
            title = await page.title()
            logger.info(f"📄 Page title: {title}")
            
            # Check for common form elements
            logger.info("🔍 Searching for form elements...")
            
            # Email field selectors to test
            email_selectors = [
                'input[type="email"]',
                'input[name="email"]',
                'input[id="email"]',
                'input[placeholder*="email" i]',
                'input[aria-label*="email" i]',
                'input[data-testid*="email"]',
                'input[autocomplete="email"]',
                '#email',
                '.email-input',
                '[data-cy="email"]'
            ]
            
            email_found = False
            for selector in email_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        placeholder = await element.get_attribute('placeholder')
                        name = await element.get_attribute('name')
                        id_attr = await element.get_attribute('id')
                        logger.info(f"✅ Found email field with selector: {selector}")
                        logger.info(f"   - placeholder: {placeholder}")
                        logger.info(f"   - name: {name}")
                        logger.info(f"   - id: {id_attr}")
                        email_found = True
                        break
                except:
                    continue
            
            if not email_found:
                logger.warning("❌ No email field found with standard selectors")
                # Try to find all input elements
                all_inputs = await page.query_selector_all('input')
                logger.info(f"📋 Found {len(all_inputs)} input elements:")
                for i, input_elem in enumerate(all_inputs[:10]):  # Limit to first 10
                    try:
                        input_type = await input_elem.get_attribute('type')
                        name = await input_elem.get_attribute('name')
                        id_attr = await input_elem.get_attribute('id')
                        placeholder = await input_elem.get_attribute('placeholder')
                        logger.info(f"   Input {i+1}: type={input_type}, name={name}, id={id_attr}, placeholder={placeholder}")
                    except:
                        continue
            
            # Password field selectors to test
            password_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                'input[id="password"]',
                'input[placeholder*="password" i]',
                'input[aria-label*="password" i]',
                'input[data-testid*="password"]',
                'input[autocomplete="current-password"]',
                '#password',
                '.password-input',
                '[data-cy="password"]'
            ]
            
            password_found = False
            for selector in password_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        placeholder = await element.get_attribute('placeholder')
                        name = await element.get_attribute('name')
                        id_attr = await element.get_attribute('id')
                        logger.info(f"✅ Found password field with selector: {selector}")
                        logger.info(f"   - placeholder: {placeholder}")
                        logger.info(f"   - name: {name}")
                        logger.info(f"   - id: {id_attr}")
                        password_found = True
                        break
                except:
                    continue
            
            if not password_found:
                logger.warning("❌ No password field found with standard selectors")
            
            # Submit button selectors to test
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button[id*="login" i]',
                'button[id*="signin" i]',
                'button:has-text("Sign In")',
                'button:has-text("Log In")',
                'button:has-text("Login")',
                'button[data-testid*="login"]',
                'button[data-testid*="signin"]',
                '.login-button',
                '.signin-button',
                '[data-cy="login"]',
                '[data-cy="signin"]'
            ]
            
            submit_found = False
            for selector in submit_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        text = await element.inner_text()
                        id_attr = await element.get_attribute('id')
                        class_attr = await element.get_attribute('class')
                        logger.info(f"✅ Found submit button with selector: {selector}")
                        logger.info(f"   - text: {text}")
                        logger.info(f"   - id: {id_attr}")
                        logger.info(f"   - class: {class_attr}")
                        submit_found = True
                        break
                except:
                    continue
            
            if not submit_found:
                logger.warning("❌ No submit button found with standard selectors")
                # Try to find all buttons
                all_buttons = await page.query_selector_all('button')
                logger.info(f"📋 Found {len(all_buttons)} button elements:")
                for i, button in enumerate(all_buttons[:10]):  # Limit to first 10
                    try:
                        text = await button.inner_text()
                        id_attr = await button.get_attribute('id')
                        class_attr = await button.get_attribute('class')
                        type_attr = await button.get_attribute('type')
                        logger.info(f"   Button {i+1}: text='{text}', type={type_attr}, id={id_attr}, class={class_attr}")
                    except:
                        continue
            
            # Check for any Turnstile/Cloudflare challenges
            turnstile_selectors = [
                'iframe[src*="challenges.cloudflare.com"]',
                '.cf-turnstile',
                '[data-sitekey]',
                'iframe[title*="cloudflare"]'
            ]
            
            for selector in turnstile_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        logger.info(f"🔐 Found Turnstile challenge with selector: {selector}")
                        src = await element.get_attribute('src')
                        if src:
                            logger.info(f"   - src: {src}")
                except:
                    continue
            
            # Get page HTML for further analysis
            html_content = await page.content()
            with open('epic_login_debug.html', 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.info("📄 Page HTML saved as epic_login_debug.html")
            
            # No need to wait in headless mode
            logger.info("✅ Debug analysis completed")
            
        except Exception as e:
            logger.error(f"❌ Error during debugging: {str(e)}")
        
        finally:
            await browser.close()

if __name__ == '__main__':
    asyncio.run(debug_epic_login_page())