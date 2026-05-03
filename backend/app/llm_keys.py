"""
Utilities for handling custom LLM API keys passed from frontend via headers.
Allows users to provide their own API keys instead of using server-side keys.
"""

from typing import Optional
from fastapi import Request
from app.config import settings


def get_llm_api_key_from_request(request: Request) -> Optional[str]:
    """
    Extract custom LLM API key from request headers.
    Header format:
      X-LLM-API-Key: <key>
      X-LLM-Provider: anthropic|openai
    """
    api_key = request.headers.get("X-LLM-API-Key")
    provider = request.headers.get("X-LLM-Provider", "").lower()
    
    if not api_key or not provider:
        return None
    
    # Validate it looks like an API key (basic check)
    if len(api_key) < 20:
        return None
    
    return api_key


def get_llm_provider_from_request(request: Request) -> Optional[str]:
    """
    Extract LLM provider from request headers.
    """
    provider = request.headers.get("X-LLM-Provider", "").lower()
    if provider in ("anthropic", "openai"):
        return provider
    return None


def get_anthropic_api_key(request: Optional[Request] = None) -> str:
    """
    Get Anthropic API key from request headers first, then fall back to settings.
    """
    if request:
        provider = get_llm_provider_from_request(request)
        if provider == "anthropic":
            custom_key = get_llm_api_key_from_request(request)
            if custom_key:
                return custom_key
    
    return settings.anthropic_api_key


def get_openai_api_key(request: Optional[Request] = None) -> str:
    """
    Get OpenAI API key from request headers first, then fall back to settings.
    """
    if request:
        provider = get_llm_provider_from_request(request)
        if provider == "openai":
            custom_key = get_llm_api_key_from_request(request)
            if custom_key:
                return custom_key
    
    return settings.openai_api_key


def should_use_custom_key(request: Optional[Request] = None) -> bool:
    """
    Check if request provides a custom API key.
    """
    if not request:
        return False
    
    return (
        get_llm_api_key_from_request(request) is not None
        and get_llm_provider_from_request(request) is not None
    )
