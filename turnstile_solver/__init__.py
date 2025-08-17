"""
Turnstile Solver Package
Provides both API service and direct async solving capabilities for Cloudflare Turnstile challenges
"""

from .async_solver import AsyncTurnstileSolver, TurnstileResult

__all__ = ['AsyncTurnstileSolver', 'TurnstileResult']