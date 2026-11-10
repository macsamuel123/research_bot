"""The only module that reads X-Forwarded-For."""

from __future__ import annotations

import ipaddress

from fastapi import Request

from app.config import Settings


def client_ip(request: Request, settings: Settings) -> str:
    peer = request.client.host if request.client else ""
    try:
        peer_addr = ipaddress.ip_address(peer)
    except ValueError:
        return peer
    if any(peer_addr in net for net in settings.trusted_networks):
        forwarded = request.headers.get("x-forwarded-for", "")
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            return parts[-1]
    return peer
