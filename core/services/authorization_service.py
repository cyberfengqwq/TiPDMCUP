# core/sercices/authorization_service.py


class AuthorizationService:
    ROLE_PERMISSIONS: dict[str, set[str]] = {
        "owner": {
            "company:read",
            "company:write",
            "user:manage",
            "report:read",
            "report:write",
        },
        "admin": {
            "company:read",
            "user:manage",
            "report:read",
        },
        "member": {
            "company:read",
            "report:read",
        },
    }

    def has_permission(self, roles: list[str], permission: str) -> bool:
        for role in roles:
            if permission in self.ROLE_PERMISSIONS.get(role, set()):
                return True
        return False

    def reuqire_permission(self, roles: list[str], permission: str) -> None:
        if not self.has_permission(roles, permission):
            raise PermissionError(f"Permission denied: {permission}")
