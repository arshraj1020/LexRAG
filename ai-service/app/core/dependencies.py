"""
Shared FastAPI dependencies — authentication, DB session, service singletons.
"""

from fastapi import Header, HTTPException, status
from .settings import get_settings

settings = get_settings()


async def verify_internal_api_key(x_internal_api_key: str = Header(...)):
    """
    All internal endpoints are protected by a shared secret between
    the Spring Boot backend and the AI service. Never expose these
    endpoints publicly.
    """
    if x_internal_api_key != settings.internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid internal API key",
        )
