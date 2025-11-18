"""Request deduplication middleware to prevent rapid-fire duplicate requests."""
import asyncio
import hashlib
import time
from typing import Dict, Tuple
from fastapi import Request, Response
import logging

logger = logging.getLogger(__name__)


class CachedResponse:
    """Container for cached response data that can be used to create fresh Response objects."""

    def __init__(self, content: bytes, status_code: int, headers: dict, media_type: str = None):
        self.content = content
        self.status_code = status_code
        self.headers = headers
        self.media_type = media_type

    def create_fresh_response(self) -> Response:
        """Create a new Response object with the cached data."""
        if self.media_type:
            response = Response(
                content=self.content,
                status_code=self.status_code,
                headers=self.headers,
                media_type=self.media_type
            )
        else:
            response = Response(
                content=self.content,
                status_code=self.status_code,
                headers=self.headers
            )
        return response


class RequestDeduplicator:
    """
    Middleware to deduplicate identical requests happening within a short time window.
    
    This prevents the frontend from overwhelming the backend with rapid-fire requests
    for the same endpoint, which was causing database performance issues.
    """

    def __init__(self, window_seconds: float = 2.0):
        self.window_seconds = window_seconds
        self._pending_requests: Dict[str, Tuple[asyncio.Task, float]] = {}
        self._cleanup_interval = 30.0  # Clean up old entries every 30 seconds
        self._last_cleanup = time.time()

    def _get_request_key(self, request: Request) -> str:
        """Generate a unique key for the request based on method, path, and user."""
        # Include user ID if available from authorization header
        user_part = ""
        if auth_header := request.headers.get("authorization"):
            # Just use a hash of the auth header to identify the user
            user_hash = hashlib.sha256(auth_header.encode()).hexdigest()[:8]
            user_part = f":{user_hash}"

        # Create key from method, path, and user
        key_data = f"{request.method}:{request.url.path}{user_part}"
        return hashlib.sha256(key_data.encode()).hexdigest()

    async def _cache_response(self, response: Response) -> CachedResponse:
        """Convert a Response object to a CachedResponse for reuse."""
        # Read the response body
        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        # Extract headers (excluding hop-by-hop headers)
        headers = dict(response.headers)
        # Remove headers that shouldn't be duplicated
        hop_by_hop_headers = {
            "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
            "te", "trailers", "transfer-encoding", "upgrade"
        }
        headers = {k: v for k, v in headers.items() if k.lower() not in hop_by_hop_headers}

        return CachedResponse(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=getattr(response, 'media_type', None)
        )

    def _cleanup_old_entries(self):
        """Remove expired entries from the pending requests cache."""
        current_time = time.time()
        if current_time - self._last_cleanup < self._cleanup_interval:
            return

        expired_keys = []
        for key, (task, timestamp) in self._pending_requests.items():
            if current_time - timestamp > self.window_seconds:
                if not task.done():
                    # Task is still running but outside our dedup window
                    pass
                else:
                    expired_keys.append(key)

        for key in expired_keys:
            self._pending_requests.pop(key, None)

        self._last_cleanup = current_time

    async def deduplicate_request(self, request: Request, call_next) -> Response:
        """
        Deduplicate identical requests within the time window.
        
        If an identical request is already in progress, wait for its result.
        Otherwise, process the request normally.
        """
        # Only deduplicate GET requests to dashboard-related endpoints
        if request.method != "GET":
            return await call_next(request)

        if not any(path in str(request.url.path) for path in ["/dashboard", "/balance", "/tutorial/status"]):
            return await call_next(request)

        request_key = self._get_request_key(request)
        current_time = time.time()

        # Clean up old entries periodically
        self._cleanup_old_entries()

        # Check if we have a pending request for this key
        if request_key in self._pending_requests:
            existing_task, timestamp = self._pending_requests[request_key]

            # If the existing request is within our dedup window and still valid
            if current_time - timestamp < self.window_seconds and not existing_task.done():
                logger.debug(f"Deduplicating request to {request.url.path}")
                try:
                    # Wait for the existing request to complete and get cached response
                    cached_response = await existing_task
                    # Create a fresh Response object from the cached data
                    return cached_response.create_fresh_response()
                except Exception as e:
                    logger.warning(f"Deduplicated request failed: {e}")
                    # Fall through to make a new request

        # Create a new task for this request
        async def make_request():
            try:
                response = await call_next(request)
                # Cache the response data for potential reuse
                cached_response = await self._cache_response(response)
                return cached_response
            finally:
                # Clean up our entry when done
                self._pending_requests.pop(request_key, None)

        task = asyncio.create_task(make_request())
        self._pending_requests[request_key] = (task, current_time)

        # Wait for our task and create a fresh response
        cached_response = await task
        return cached_response.create_fresh_response()


# Global instance
request_deduplicator = RequestDeduplicator()


async def deduplication_middleware(request: Request, call_next):
    """FastAPI middleware function for request deduplication."""
    return await request_deduplicator.deduplicate_request(request, call_next)
