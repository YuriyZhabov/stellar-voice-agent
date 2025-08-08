"""Security middleware for HTTP requests and responses."""

import logging
import time
from typing import Dict, Set, Optional, Callable, Any
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from src.security import get_security_headers


@dataclass
class RateLimitInfo:
    """Rate limiting information for an IP address."""
    requests: deque = field(default_factory=deque)
    blocked_until: Optional[datetime] = None
    total_requests: int = 0
    blocked_requests: int = 0


class SecurityMiddleware:
    """
    Security middleware for HTTP applications.
    
    Provides:
    - Security headers
    - Rate limiting
    - Request validation
    - Security logging
    """
    
    def __init__(
        self,
        rate_limit_per_minute: int = 60,
        rate_limit_burst: int = 10,
        block_duration_minutes: int = 15,
        enable_security_headers: bool = True,
        enable_rate_limiting: bool = True,
        trusted_proxies: Optional[Set[str]] = None
    ):
        """
        Initialize security middleware.
        
        Args:
            rate_limit_per_minute: Maximum requests per minute per IP
            rate_limit_burst: Maximum burst requests allowed
            block_duration_minutes: How long to block IPs that exceed limits
            enable_security_headers: Whether to add security headers
            enable_rate_limiting: Whether to enable rate limiting
            trusted_proxies: Set of trusted proxy IP addresses
        """
        self.rate_limit_per_minute = rate_limit_per_minute
        self.rate_limit_burst = rate_limit_burst
        self.block_duration = timedelta(minutes=block_duration_minutes)
        self.enable_security_headers = enable_security_headers
        self.enable_rate_limiting = enable_rate_limiting
        self.trusted_proxies = trusted_proxies or set()
        
        # Rate limiting storage
        self.rate_limits: Dict[str, RateLimitInfo] = defaultdict(RateLimitInfo)
        
        # Security headers
        self.security_headers = get_security_headers()
        
        # Logger
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(
            "Security middleware initialized",
            extra={
                "rate_limit_per_minute": rate_limit_per_minute,
                "rate_limit_burst": rate_limit_burst,
                "block_duration_minutes": block_duration_minutes,
                "security_headers_enabled": enable_security_headers,
                "rate_limiting_enabled": enable_rate_limiting
            }
        )
    
    def get_client_ip(self, request: Any) -> str:
        """
        Extract client IP address from request.
        
        Args:
            request: HTTP request object
            
        Returns:
            str: Client IP address
        """
        # Try to get real IP from headers (for proxied requests)
        forwarded_for = getattr(request, 'headers', {}).get('X-Forwarded-For')
        if forwarded_for:
            # Take the first IP in the chain
            client_ip = forwarded_for.split(',')[0].strip()
            return client_ip
        
        real_ip = getattr(request, 'headers', {}).get('X-Real-IP')
        if real_ip:
            return real_ip.strip()
        
        # Fallback to direct connection IP
        client_ip = getattr(request, 'client', {}).get('host', '127.0.0.1')
        return client_ip
    
    def is_rate_limited(self, client_ip: str) -> bool:
        """
        Check if client IP is rate limited.
        
        Args:
            client_ip: Client IP address
            
        Returns:
            bool: True if rate limited
        """
        if not self.enable_rate_limiting:
            return False
        
        now = datetime.now()
        rate_info = self.rate_limits[client_ip]
        
        # Check if still blocked
        if rate_info.blocked_until and now < rate_info.blocked_until:
            rate_info.blocked_requests += 1
            return True
        
        # Clear old requests (older than 1 minute)
        minute_ago = now - timedelta(minutes=1)
        while rate_info.requests and rate_info.requests[0] < minute_ago:
            rate_info.requests.popleft()
        
        # Check rate limits
        current_requests = len(rate_info.requests)
        
        # Check burst limit
        if current_requests >= self.rate_limit_burst:
            # Check if we're over the per-minute limit
            if current_requests >= self.rate_limit_per_minute:
                # Block the IP
                rate_info.blocked_until = now + self.block_duration
                rate_info.blocked_requests += 1
                
                self.logger.warning(
                    f"IP {client_ip} blocked for rate limit violation",
                    extra={
                        "client_ip": client_ip,
                        "requests_in_minute": current_requests,
                        "rate_limit": self.rate_limit_per_minute,
                        "blocked_until": rate_info.blocked_until.isoformat()
                    }
                )
                return True
        
        # Add current request
        rate_info.requests.append(now)
        rate_info.total_requests += 1
        
        return False
    
    def add_security_headers(self, response: Any) -> None:
        """
        Add security headers to response.
        
        Args:
            response: HTTP response object
        """
        if not self.enable_security_headers:
            return
        
        if hasattr(response, 'headers'):
            for header_name, header_value in self.security_headers.items():
                response.headers[header_name] = header_value
    
    def validate_request(self, request: Any) -> Optional[str]:
        """
        Validate incoming request for security issues.
        
        Args:
            request: HTTP request object
            
        Returns:
            Optional[str]: Error message if validation fails, None if valid
        """
        # Check request size
        content_length = getattr(request, 'headers', {}).get('Content-Length')
        if content_length:
            try:
                size = int(content_length)
                if size > 100 * 1024 * 1024:  # 100MB limit
                    return "Request too large"
            except ValueError:
                return "Invalid Content-Length header"
        
        # Check for suspicious headers
        headers = getattr(request, 'headers', {})
        suspicious_headers = [
            'X-Forwarded-Host',
            'X-Originating-IP',
            'X-Remote-IP',
            'X-Remote-Addr'
        ]
        
        for header in suspicious_headers:
            if header in headers:
                value = headers[header]
                # Log suspicious header but don't block
                self.logger.warning(
                    f"Suspicious header detected: {header}",
                    extra={
                        "header": header,
                        "value": value[:100],  # Limit logged value length
                        "client_ip": self.get_client_ip(request)
                    }
                )
        
        return None
    
    def log_request(self, request: Any, response: Any, duration: float) -> None:
        """
        Log request for security monitoring.
        
        Args:
            request: HTTP request object
            response: HTTP response object
            duration: Request duration in seconds
        """
        client_ip = self.get_client_ip(request)
        method = getattr(request, 'method', 'UNKNOWN')
        path = getattr(request, 'url', {}).get('path', '/')
        status_code = getattr(response, 'status_code', 0)
        user_agent = getattr(request, 'headers', {}).get('User-Agent', '')
        
        # Log level based on status code
        if status_code >= 500:
            log_level = logging.ERROR
        elif status_code >= 400:
            log_level = logging.WARNING
        else:
            log_level = logging.INFO
        
        self.logger.log(
            log_level,
            f"{method} {path} - {status_code}",
            extra={
                "client_ip": client_ip,
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration": duration,
                "user_agent": user_agent[:200],  # Limit user agent length
                "request_size": getattr(request, 'headers', {}).get('Content-Length', '0')
            }
        )
    
    def get_rate_limit_stats(self) -> Dict[str, Any]:
        """
        Get rate limiting statistics.
        
        Returns:
            Dict[str, Any]: Rate limiting statistics
        """
        now = datetime.now()
        active_ips = 0
        blocked_ips = 0
        total_requests = 0
        total_blocked = 0
        
        for ip, rate_info in self.rate_limits.items():
            total_requests += rate_info.total_requests
            total_blocked += rate_info.blocked_requests
            
            # Clean old requests
            minute_ago = now - timedelta(minutes=1)
            while rate_info.requests and rate_info.requests[0] < minute_ago:
                rate_info.requests.popleft()
            
            if rate_info.requests:
                active_ips += 1
            
            if rate_info.blocked_until and now < rate_info.blocked_until:
                blocked_ips += 1
        
        return {
            "active_ips": active_ips,
            "blocked_ips": blocked_ips,
            "total_requests": total_requests,
            "total_blocked": total_blocked,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "rate_limit_burst": self.rate_limit_burst
        }
    
    def cleanup_old_entries(self) -> None:
        """Clean up old rate limiting entries to prevent memory leaks."""
        now = datetime.now()
        cleanup_threshold = now - timedelta(hours=1)
        
        ips_to_remove = []
        for ip, rate_info in self.rate_limits.items():
            # Remove old requests
            minute_ago = now - timedelta(minutes=1)
            while rate_info.requests and rate_info.requests[0] < minute_ago:
                rate_info.requests.popleft()
            
            # Remove IPs with no recent activity and not blocked
            if (not rate_info.requests and 
                (not rate_info.blocked_until or rate_info.blocked_until < cleanup_threshold)):
                ips_to_remove.append(ip)
        
        for ip in ips_to_remove:
            del self.rate_limits[ip]
        
        if ips_to_remove:
            self.logger.debug(
                f"Cleaned up {len(ips_to_remove)} old rate limit entries"
            )


# FastAPI middleware wrapper
class FastAPISecurityMiddleware:
    """FastAPI-compatible security middleware wrapper."""
    
    def __init__(self, security_middleware: SecurityMiddleware):
        self.security_middleware = security_middleware
    
    async def __call__(self, request, call_next):
        """Process request through security middleware."""
        client_ip = self.security_middleware.get_client_ip(request)
        start_time = time.time()
        
        # Check rate limiting
        if self.security_middleware.is_rate_limited(client_ip):
            from fastapi import HTTPException
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later."
            )
        
        # Validate request
        validation_error = self.security_middleware.validate_request(request)
        if validation_error:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400,
                detail=validation_error
            )
        
        # Process request
        response = await call_next(request)
        
        # Add security headers
        self.security_middleware.add_security_headers(response)
        
        # Log request
        duration = time.time() - start_time
        self.security_middleware.log_request(request, response, duration)
        
        return response


# Utility function to create security middleware
def create_security_middleware(
    rate_limit_per_minute: int = 60,
    enable_security_headers: bool = True,
    enable_rate_limiting: bool = True
) -> SecurityMiddleware:
    """
    Create and configure security middleware.
    
    Args:
        rate_limit_per_minute: Requests per minute limit
        enable_security_headers: Enable security headers
        enable_rate_limiting: Enable rate limiting
        
    Returns:
        SecurityMiddleware: Configured security middleware
    """
    return SecurityMiddleware(
        rate_limit_per_minute=rate_limit_per_minute,
        enable_security_headers=enable_security_headers,
        enable_rate_limiting=enable_rate_limiting
    )