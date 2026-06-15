from fastapi import Depends, HTTPException

from src.shared.middlewares.auth_middleware import check_auth


def check_permission(feature: str, action: str):
    async def permission_dependency(payload: dict = Depends(check_auth)):

        if payload.get("roleId") == "administrator":
            return payload

        permissions = payload.get("permissions", [])

        for p in permissions:
            if p.get("feature") == feature and p.get(action):
                return payload

        raise HTTPException(status_code=403, detail=f"Permission denied: You do not have '{action}' access to '{feature}'")

    return permission_dependency
