"""
CloudFlare Solver - BotsForge implementation
Based on BotsForge/CloudFlare repository
"""

try:
    from .browser import CloudflareBrowser
    from .models import CaptchaTask
    BOTSFORGE_AVAILABLE = True
except ImportError as e:
    BOTSFORGE_AVAILABLE = False
    CloudflareBrowser = None
    CaptchaTask = None

__all__ = ['CloudflareBrowser', 'CaptchaTask', 'BOTSFORGE_AVAILABLE']