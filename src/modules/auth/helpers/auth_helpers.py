def format_permissions(user: dict) -> list:

    role_data = user.get("role", {})
    permissions = []

    if role_data:
        for rf in role_data.get("role_features", []):
            permissions.append(
                {
                    "feature": rf.get("id_feature"),
                    "create": rf.get("create", False),
                    "view": rf.get("view", False),
                    "delete": rf.get("delete", False),
                    "activate": rf.get("activate", False),
                }
            )
    return permissions


def format_user_auth_response(user: dict, permissions: list) -> dict:

    role_data = user.get("role", {})

    return {
        "id": user.get("id"),
        "name": user.get("name"),
        "email": user.get("email"),
        "role": {
            "id": role_data.get("id", user.get("id_role")),
            "name": role_data.get("name", "User"),
            "description": role_data.get("description", ""),
            "permissions": permissions,
        },
    }
