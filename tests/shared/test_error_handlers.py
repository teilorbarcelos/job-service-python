from src.shared.middlewares.error_handlers import _problem_detail


def test_problem_detail_with_string_detail():
    result = _problem_detail(status=400, title="Bad Request", detail="invalid email")
    assert result["detail"] == "invalid email"


def test_problem_detail_with_non_string_detail():
    result = _problem_detail(status=422, title="Validation Error", detail=["field is required"])
    assert result["detail"] == "['field is required']"


def test_problem_detail_with_none_detail():
    result = _problem_detail(status=500, title="Internal Server Error", detail=None)
    assert result["detail"] == "Internal Server Error"


def test_problem_detail_with_custom_type():
    result = _problem_detail(status=400, title="Bad Request", detail="error", type_="custom/error")
    assert result["type"] == "custom/error"
