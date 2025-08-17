"""
Turnstile Solver Package
Provides both API service and direct async solving capabilities for Cloudflare Turnstile challenges

Architecture:
- api_solver.py: Main solver that runs as a web service with HTTP endpoints
- async_solver.py: Core engine for direct async solving (standalone)
"""

from .async_solver import AsyncTurnstileSolver, TurnstileResult

__all__ = ['AsyncTurnstileSolver', 'TurnstileResult']