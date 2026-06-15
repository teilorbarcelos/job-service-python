from src.shared.exceptions import AppException, EntityNotFound, PermissionDenied, ConflictError, Unauthorized


def test_app_exception_default_error_type():
    exc = AppException(status_code=400, detail="Bad request")
    assert exc.error_type == "AppException"
    assert exc.detail == "Bad request"


def test_entity_not_found_default():
    exc = EntityNotFound()
    assert exc.status_code == 404
    assert exc.detail == "Resource not found"


def test_entity_not_found_with_identifier():
    exc = EntityNotFound(entity="User", identifier="123")
    assert exc.status_code == 404
    assert exc.detail == "User not found: 123"


def test_permission_denied():
    exc = PermissionDenied()
    assert exc.status_code == 403
    assert exc.detail == "Permission denied"


def test_conflict_error():
    exc = ConflictError()
    assert exc.status_code == 409
    assert exc.detail == "Resource already exists"


def test_unauthorized():
    exc = Unauthorized()
    assert exc.status_code == 401
    assert exc.detail == "Unauthorized"
