from fastapi import HTTPException


class AppException(HTTPException):
    def __init__(self, status_code: int, detail: str = None, error_type: str = None):
        super().__init__(status_code=status_code, detail=detail)
        self.error_type = error_type or self.__class__.__name__


class EntityNotFound(AppException):
    def __init__(self, entity: str = "Resource", identifier: str = ""):
        detail = f"{entity} not found"
        if identifier:
            detail += f": {identifier}"
        super().__init__(status_code=404, detail=detail)


class PermissionDenied(AppException):
    def __init__(self, detail: str = "Permission denied"):
        super().__init__(status_code=403, detail=detail)


class ConflictError(AppException):
    def __init__(self, detail: str = "Resource already exists"):
        super().__init__(status_code=409, detail=detail)


class Unauthorized(AppException):
    def __init__(self, detail: str = "Unauthorized"):
        super().__init__(status_code=401, detail=detail)
