"""
Environment-specific configuration for different deployment targets.
"""

import os
from enum import Enum


class Environment(Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


def get_environment() -> Environment:
    """
    Determine environment from ENV variable or VERCEL/RAILWAY flags.
    """
    env = os.getenv("ENV", "development").lower()
    
    # Vercel sets VERCEL_ENV
    if os.getenv("VERCEL_ENV") == "production":
        return Environment.PRODUCTION
    
    # Railway sets RAILWAY_ENVIRONMENT
    if os.getenv("RAILWAY_ENVIRONMENT") == "production":
        return Environment.PRODUCTION
    
    if env == "production":
        return Environment.PRODUCTION
    elif env == "staging":
        return Environment.STAGING
    
    return Environment.DEVELOPMENT


def get_api_base_url() -> str:
    """
    Get the API base URL for the current environment.
    """
    env = get_environment()
    
    if env == Environment.PRODUCTION:
        # Set in Vercel/Railway environment variables
        return os.getenv("API_BASE_URL", "")
    elif env == Environment.STAGING:
        return os.getenv("API_BASE_URL", "http://localhost:8000")
    
    # Development
    return os.getenv("API_BASE_URL", "http://localhost:8000")


def should_require_auth() -> bool:
    """
    Whether authentication is required in this environment.
    """
    return get_environment() != Environment.DEVELOPMENT
