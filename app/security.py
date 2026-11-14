"""Cabeceras HTTP de seguridad y Content-Security-Policy con nonce.

Scripts: solo propios, jsDelivr (con SRI) o en línea con el nonce de la petición.
Estilos en línea permitidos (atributos style=). Iframes: YouTube, Drive y Power BI.
HSTS solo bajo HTTPS (Render termina TLS en su proxy; ProxyFix recupera el esquema).
"""
from __future__ import annotations

import secrets

from flask import Flask, g, request
from werkzeug.middleware.proxy_fix import ProxyFix

CDN = "https://cdn.jsdelivr.net"
FRAME_SOURCES = (
    "https://www.youtube.com",
    "https://www.youtube-nocookie.com",
    "https://drive.google.com",
    "https://app.powerbi.com",
)


def csp_nonce() -> str:
    """Nonce aleatorio por petición."""
    if "csp_nonce" not in g:
        g.csp_nonce = secrets.token_urlsafe(16)
    return g.csp_nonce


def _policy(nonce: str, https: bool) -> str:
    directives = {
        "default-src": "'self'",
        "script-src": f"'self' 'nonce-{nonce}' {CDN}",
        "style-src": f"'self' 'unsafe-inline' {CDN} https://fonts.googleapis.com",
        "font-src": f"'self' data: {CDN} https://fonts.gstatic.com",
        "img-src": "'self' data: blob:",
        "connect-src": f"'self' {CDN}",
        "frame-src": " ".join(FRAME_SOURCES),
        "media-src": "'self'",
        "object-src": "'none'",
        "base-uri": "'self'",
        "form-action": "'self'",
        "frame-ancestors": "'self'",
    }
    policy = "; ".join(f"{k} {v}" for k, v in directives.items())
    return policy + ("; upgrade-insecure-requests" if https else "")


def init_security(app: Flask) -> None:
    # Detrás del proxy de Render.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)  # type: ignore[method-assign]
    app.jinja_env.globals["csp_nonce"] = csp_nonce

    @app.after_request
    def set_security_headers(response):
        h = response.headers
        h.setdefault("Content-Security-Policy", _policy(csp_nonce(), request.is_secure))
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "SAMEORIGIN")
        # YouTube exige un Referer para reproducir videos embebidos.
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()")
        h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if request.is_secure:
            h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response
