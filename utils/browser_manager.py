"""
Browser management module for Epic Games account checking
Handles browser initialization, context management, and proxy configuration
"""
import asyncio
import logging
import random
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse

from config.settings import (
    HEADLESS, 
    NAVIGATION_TIMEOUT, 
    MAX_CONCURRENT_CHECKS,
    BLOCK_RESOURCE_TYPES,
    BROWSER_SLOWMO,
    USE_ENHANCED_BROWSER,
    PREFERRED_BROWSER_TYPE,
    DEBUG_ENHANCED_FEATURES,
    MAX_CONTEXTS_PER_BROWSER,
    CONTEXT_REUSE_COUNT,
    CLEANUP_INTERVAL
)

logger = logging.getLogger(__name__)

try:
    from patchright.async_api import async_playwright as patchright_async
    PATCHRIGHT_AVAILABLE = True
except ImportError:
    PATCHRIGHT_AVAILABLE = False
    logger.error("Patchright not available - enhanced browser required!")

try:
    from camoufox.async_api import AsyncCamoufox
    CAMOUFOX_AVAILABLE = True
except ImportError:
    CAMOUFOX_AVAILABLE = False
    logger.warning("Camoufox not available, using Chromium-based browsers only")


class BrowserManager:
    """Manages browser instances, contexts, and proxy configurations"""
    
    def __init__(self, proxies: List[str] = None):
        self.proxies = proxies or []
        self.playwright = None
        self.browser_pool: Dict[str, Any] = {}
        self.context_pool: Dict[str, List[Any]] = {}
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHECKS)
        
        # Performance optimization settings
        self.max_contexts_per_browser = MAX_CONTEXTS_PER_BROWSER
        self.context_reuse_count = CONTEXT_REUSE_COUNT
        self.context_usage_counter: Dict[str, int] = {}
        self.cleanup_interval = CLEANUP_INTERVAL
        self.checks_performed = 0
        
        # Single proxy handling
        self.single_proxy_mode = len(self.proxies) == 1
        self.current_proxy_index = 0
        
        # User agent management
        try:
            import simple_useragent as sua
            self._sua = sua
        except Exception:
            self._sua = None
        self._ua_toggle = True
    
    async def __aenter__(self):
        """Initialize enhanced browser automation"""
        if DEBUG_ENHANCED_FEATURES:
            logger.info("🚀 Initializing enhanced browser automation")
        
        if PATCHRIGHT_AVAILABLE:
            self.playwright = await patchright_async().start()
            if DEBUG_ENHANCED_FEATURES:
                logger.info("✅ Using Patchright for enhanced stealth")
        else:
            # Fallback to regular playwright if available
            try:
                from playwright.async_api import async_playwright
                self.playwright = await async_playwright().start()
                logger.info("⚠️ Using regular Playwright (Patchright not available)")
            except ImportError:
                raise RuntimeError("Neither Patchright nor Playwright is available!")
        
        return self
    
    async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
        """Clean up browsers and Playwright"""
        for browser in self.browser_pool.values():
            try:
                await browser.close()
            except Exception:
                pass
        
        if self.playwright:
            await self.playwright.stop()
    
    def get_next_user_agent(self) -> str:
        """Get next user agent string, rotating between Android and iPhone mobiles"""
        if self._sua is not None:
            try:
                uas = self._sua.get(mobile=True, shuffle=True)
                if isinstance(uas, list) and uas:
                    if self._ua_toggle:
                        android = [ua for ua in uas if ('Android' in getattr(ua, 'string', str(ua)) or 'Android' in str(ua))]
                        if android:
                            ua_obj = android[0]
                        else:
                            ua_obj = uas[0]
                    else:
                        ios = [ua for ua in uas if ('iPhone' in getattr(ua, 'string', str(ua)) or 'iPad' in str(ua) or 'iOS' in str(ua))]
                        if ios:
                            ua_obj = ios[0]
                        else:
                            ua_obj = uas[0]

                    self._ua_toggle = not self._ua_toggle

                    try:
                        return ua_obj.string
                    except Exception:
                        return str(ua_obj)
            except Exception:
                pass

        # Fallback mobile user-agents
        fallback_mobile = [
            "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 13; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        ]
        ua = fallback_mobile[0] if self._ua_toggle else fallback_mobile[1]
        self._ua_toggle = not self._ua_toggle
        return ua
    
    def get_proxy_for_check(self) -> Optional[str]:
        """Get proxy for account check with optimized single proxy handling"""
        if not self.proxies:
            return None
        
        if self.single_proxy_mode:
            return self.proxies[0]
        else:
            proxy = self.proxies[self.current_proxy_index]
            self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
            return proxy
    
    def parse_proxy_for_playwright(self, proxy_line: str) -> Optional[Dict[str, str]]:
        """Parse proxy string into Playwright proxy format"""
        if not proxy_line:
            return None
        
        try:
            if '://' not in proxy_line:
                proxy_line = f"http://{proxy_line}"
            
            parsed = urlparse(proxy_line)
            scheme = parsed.scheme.lower()
            
            # Handle SOCKS5 with authentication issue
            if scheme == 'socks5' and parsed.username and parsed.password:
                logger.info(f"⚠️ SOCKS5 with auth not supported by Chromium, converting to HTTP")
                scheme = "http"
            elif scheme not in ['http', 'https', 'socks5']:
                logger.info(f"⚠️ Unsupported proxy scheme '{scheme}', defaulting to http")
                scheme = "http"
            
            proxy_dict = {
                "server": f"{scheme}://{parsed.hostname}:{parsed.port}"
            }
            
            if parsed.username and parsed.password:
                if scheme in ['http', 'https']:
                    proxy_dict["username"] = parsed.username
                    proxy_dict["password"] = parsed.password
                elif scheme == 'socks5':
                    logger.info(f"⚠️ SOCKS5 authentication not supported, proxy may not work")
            
            logger.info(f"🔧 Parsed proxy: {scheme}://{parsed.hostname}:{parsed.port} (auth: {'yes' if parsed.username and scheme != 'socks5' else 'no'})")
            return proxy_dict
            
        except Exception as e:
            logger.info(f"❌ Error parsing proxy {proxy_line}: {e}")
            return None
    
    async def get_or_launch_browser(self, proxy_line: Optional[str]) -> Any:
        """Get or launch browser with enhanced capabilities"""
        proxy_key = f"{proxy_line or '__noproxy__'}_{PREFERRED_BROWSER_TYPE}"
        
        if proxy_key in self.browser_pool:
            return self.browser_pool[proxy_key]
        
        proxy_dict = None
        if proxy_line:
            proxy_dict = self.parse_proxy_for_playwright(proxy_line)
        
        # Enhanced browser launch arguments
        browser_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-features=VizDisplayCompositor",
            "--disable-default-apps",
            "--disable-extensions",
            "--disable-component-extensions-with-background-pages",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-field-trial-config",
            "--disable-back-forward-cache",
            "--disable-background-networking",
            "--enable-features=NetworkService,NetworkServiceInProcess",
            "--disable-background-media-suspend",
            "--disable-low-res-tiling",
            "--disable-new-content-rendering-timeout",
            "--disable-threaded-animation",
            "--disable-threaded-scrolling",
            "--disable-in-process-stack-traces",
            "--disable-histogram-customizer",
            "--disable-translate",
            "--disable-ipc-flooding-protection",
            "--no-default-browser-check",
            "--no-first-run",
            "--no-pings",
            "--no-service-autorun",
            "--media-cache-size=0",
            "--disk-cache-size=0",
            "--aggressive-cache-discard",
            "--disable-hang-monitor",
            "--disable-prompt-on-repost",
            "--disable-client-side-phishing-detection",
            "--disable-component-update",
            "--disable-domain-reliability",
            "--disable-features=TranslateUI,BlinkGenPropertyTrees",
            "--disable-sync",
            "--disable-web-security",
            "--allow-running-insecure-content",
            "--disable-webgl",
            "--disable-webgl2",
            "--disable-3d-apis",
            "--disable-webrtc",
            "--disable-speech-api",
            "--disable-file-system",
            "--disable-presentation-api",
            "--disable-permissions-api",
            "--disable-notification-api",
            "--disable-sensor-api",
            "--disable-wake-lock-api",
            "--disable-webaudio",
            "--autoplay-policy=no-user-gesture-required",
            "--disable-shared-workers",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-accelerated-2d-canvas",
            "--disable-accelerated-jpeg-decoding",
            "--disable-accelerated-mjpeg-decode",
            "--disable-accelerated-video-decode",
            "--disable-gpu-sandbox",
            "--disable-software-rasterizer",
            "--disable-zygote"
        ]
        
        # Launch browser based on preference
        if PREFERRED_BROWSER_TYPE == "camoufox" and CAMOUFOX_AVAILABLE:
            try:
                browser = await AsyncCamoufox(
                    headless=HEADLESS,
                    proxy=proxy_dict,
                    addons=[],
                    os="windows",
                    screen="1920x1080",
                    humanize=True
                ).start()
                
                if DEBUG_ENHANCED_FEATURES:
                    logger.info(f"🦊 Launched Camoufox browser with proxy: {proxy_line or 'None'}")
                
            except Exception as e:
                logger.info(f"❌ Failed to launch Camoufox: {e}, falling back to Chromium")
                browser = await self.playwright.chromium.launch(
                    headless=HEADLESS,
                    proxy=proxy_dict,
                    args=browser_args,
                    slow_mo=BROWSER_SLOWMO
                )
        else:
            browser = await self.playwright.chromium.launch(
                headless=HEADLESS,
                proxy=proxy_dict,
                args=browser_args,
                slow_mo=BROWSER_SLOWMO
            )
            
            if DEBUG_ENHANCED_FEATURES:
                logger.info(f"🌐 Launched Chromium browser with proxy: {proxy_line or 'None'}")
        
        self.browser_pool[proxy_key] = browser
        return browser
    
    async def new_context(self, browser: Any) -> Any:
        """Create new browser context with stealth settings"""
        user_agent = self.get_next_user_agent()
        
        context = await browser.new_context(
            user_agent=user_agent,
            viewport={"width": random.randint(1024, 1920), "height": random.randint(768, 1080)},
            locale="en-US",
            timezone_id="America/New_York",
            permissions=["geolocation", "notifications"],
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        
        # Enhanced stealth JavaScript
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            
            const originalQuery = window.navigator.permissions.query;
            return window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            Object.defineProperty(navigator, 'serviceWorker', {
                get: () => ({
                    register: () => Promise.resolve(),
                    getRegistrations: () => Promise.resolve([]),
                    ready: Promise.resolve({
                        unregister: () => Promise.resolve(true),
                        update: () => Promise.resolve(),
                        pushManager: {
                            subscribe: () => Promise.resolve(),
                            getSubscription: () => Promise.resolve(null)
                        },
                        sync: {
                            register: () => Promise.resolve()
                        },
                        active: {
                            postMessage: () => {},
                            terminate: () => {}
                        },
                        installing: null,
                        waiting: null,
                        onupdatefound: null,
                        oncontrollerchange: null,
                        onmessage: null
                    }),
                    controller: null,
                    oncontrollerchange: null,
                    onmessage: null
                })
            });
        """)
        
        # Block unnecessary resources for performance
        if BLOCK_RESOURCE_TYPES:
            await context.route("**/*", lambda route: (
                route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"] 
                else route.continue_()
            ))
        
        return context
    
    async def get_optimized_context(self, browser: Any, proxy_key: str) -> Any:
        """Get a completely fresh browser context for maximum isolation"""
        if self.context_reuse_count <= 1:
            context = await self.new_context(browser)
            if DEBUG_ENHANCED_FEATURES:
                logger.info(f"🆕 Created fresh isolated context for {proxy_key}")
            return context
        
        # Legacy reuse logic (only if CONTEXT_REUSE_COUNT > 1)
        if proxy_key not in self.context_pool:
            self.context_pool[proxy_key] = []
        
        contexts = self.context_pool[proxy_key]
        for i, context in enumerate(contexts):
            context_key = f"{proxy_key}_{i}"
            usage_count = self.context_usage_counter.get(context_key, 0)
            
            if usage_count < self.context_reuse_count:
                await self.clear_context_session(context)
                self.context_usage_counter[context_key] = usage_count + 1
                if DEBUG_ENHANCED_FEATURES:
                    logger.info(f"🔄 Reusing context {context_key} (usage: {usage_count + 1}/{self.context_reuse_count}) - Session cleared")
                return context
        
        if len(contexts) < self.max_contexts_per_browser:
            context = await self.new_context(browser)
            contexts.append(context)
            context_key = f"{proxy_key}_{len(contexts) - 1}"
            self.context_usage_counter[context_key] = 1
            
            if DEBUG_ENHANCED_FEATURES:
                logger.info(f"🆕 Created new context {context_key}")
            return context
        
        # Replace oldest context if at max capacity
        old_context = contexts[0]
        try:
            await old_context.close()
        except:
            pass
        
        new_context = await self.new_context(browser)
        contexts[0] = new_context
        context_key = f"{proxy_key}_0"
        self.context_usage_counter[context_key] = 1
        
        if DEBUG_ENHANCED_FEATURES:
            logger.info(f"🔄 Replaced oldest context {context_key}")
        return new_context
    
    async def clear_context_session(self, context: Any):
        """Clear all session data from context to ensure clean state"""
        try:
            await context.clear_cookies()
            
            for page in context.pages:
                try:
                    await page.evaluate("() => { localStorage.clear(); }")
                    await page.evaluate("() => { sessionStorage.clear(); }")
                    await page.evaluate("() => { if (window.caches) { caches.keys().then(names => names.forEach(name => caches.delete(name))); } }")
                except:
                    pass
            
            if DEBUG_ENHANCED_FEATURES:
                logger.info("🧹 Context session cleared - cookies, localStorage, sessionStorage")
                
        except Exception as e:
            if DEBUG_ENHANCED_FEATURES:
                logger.info(f"⚠️ Error clearing context session: {e}")
            pass
    
    async def cleanup_old_contexts(self, force: bool = False):
        """Clean up old browser contexts to free memory"""
        if not force and self.checks_performed % self.cleanup_interval != 0:
            return
        
        if DEBUG_ENHANCED_FEATURES:
            logger.info(f"🧹 Performing memory cleanup (checks performed: {self.checks_performed})")
        
        contexts_cleaned = 0
        for proxy_key, contexts in list(self.context_pool.items()):
            if len(contexts) > self.max_contexts_per_browser:
                old_contexts = contexts[:-self.max_contexts_per_browser]
                self.context_pool[proxy_key] = contexts[-self.max_contexts_per_browser:]
                
                for context in old_contexts:
                    try:
                        await context.close()
                        contexts_cleaned += 1
                    except:
                        pass
        
        # Clean up usage counters for removed contexts
        for key in list(self.context_usage_counter.keys()):
            if key not in [f"{pk}_{i}" for pk in self.context_pool.keys() for i in range(len(self.context_pool[pk]))]:
                del self.context_usage_counter[key]
        
        if DEBUG_ENHANCED_FEATURES and contexts_cleaned > 0:
            logger.info(f"🧹 Cleaned up {contexts_cleaned} old browser contexts")