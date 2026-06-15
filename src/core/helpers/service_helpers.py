import re
from datetime import datetime

from fastapi import HTTPException

CAMEL_TO_SNAKE_PATTERN = r"(?<!^)(?=[A-Z])"


def convert_value(value):
    if isinstance(value, str):
        val_lower = value.lower()
        if val_lower == "true":
            return True
        if val_lower == "false":
            return False
        if re.match(r"^-?\d+$", value):
            return int(value)
        if re.match(r"^-?\d+\.\d+$", value):
            return float(value)
    return value


def parse_date_value(value, qt):
    if not isinstance(value, str):
        return value
    is_range = qt in ["gte", "lte", "gt", "lt"]
    if len(value) == 10:
        try:
            dt = datetime.strptime(value, "%Y-%m-%d")
            if qt == "lte":
                dt = dt.replace(hour=23, minute=59, second=59)
            return dt
        except ValueError:
            if is_range:
                raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD.")
            return value
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        if is_range:
            raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD or ISO 8601.")
        return value


def process_search_word(search_word, search_fields, allowed_search: dict):
    if not search_fields or not isinstance(search_fields, str) or not search_fields.strip():
        raise HTTPException(status_code=400, detail='O parâmetro "searchFields" é obrigatório quando "searchWord" é fornecido.')

    or_rules = []
    requested_fields = [f.strip() for f in search_fields.split(",")]
    for field_key in requested_fields:
        config = allowed_search.get(field_key) or allowed_search.get(field_key.lower())

        if not config:
            snake_k = re.sub(CAMEL_TO_SNAKE_PATTERN, "_", field_key).lower()
            config = allowed_search.get(snake_k)

        if not config:
            raise HTTPException(status_code=400, detail=f"O campo '{field_key}' não está disponível para pesquisa global.")

        or_rules.append({"key": config["key"], "search": search_word, "qt": "contains"})
    return or_rules


def validate_order_by(order_by, allowed_filters: dict, allowed_search: dict):
    if not order_by:
        return
    normalized_order_by = re.sub(CAMEL_TO_SNAKE_PATTERN, "_", order_by).lower()
    valid_keys = {"id"}
    for k in allowed_filters.keys():
        valid_keys.add(k.lower())
        valid_keys.add(re.sub(CAMEL_TO_SNAKE_PATTERN, "_", k).lower())
    for k in allowed_search.keys():
        valid_keys.add(k.lower())
        valid_keys.add(re.sub(CAMEL_TO_SNAKE_PATTERN, "_", k).lower())

    if normalized_order_by not in valid_keys and order_by.lower() not in valid_keys:
        raise HTTPException(status_code=400, detail=f"Sort field '{order_by}' is not allowed.")


def _get_key_and_qt(k: str) -> tuple[str, str]:
    qt = "equals"
    if k.lower().endswith("_start"):
        k, qt = k[:-6], "gte"
    elif k.lower().endswith("start"):
        k, qt = k[:-5], "gte"
    elif k.lower().endswith("_end"):
        k, qt = k[:-4], "lte"
    elif k.lower().endswith("end"):
        k, qt = k[:-3], "lte"
    return k, qt


def process_filters(filters: dict, allowed_filters: dict) -> list:
    and_rules = []
    for original_key, v in list(filters.items()):
        if original_key in ["ignoreDefaultFilters", "includeDeleted"]:
            continue

        k, qt = _get_key_and_qt(original_key)

        config = allowed_filters.get(k) or allowed_filters.get(k.lower())
        if not config:
            snake_k = re.sub(CAMEL_TO_SNAKE_PATTERN, "_", k).lower()
            config = allowed_filters.get(snake_k)

        if not config:
            raise HTTPException(status_code=400, detail=f"Filtro '{original_key}' não é permitido")

        processed_value = convert_value(v)
        if qt in ["gte", "lte", "gt", "lt"]:
            processed_value = parse_date_value(processed_value, qt)

        and_rules.append(
            {"key": config.get("targetKey", config["key"]), "search": processed_value, "qt": config.get("qt", qt) if qt == "equals" else qt}
        )
    return and_rules


def build_filter_and_order(filters: dict, allowed_filters: dict, allowed_search: dict):
    filters = dict(filters)

    page = int(filters.pop("page", 0))
    size = int(filters.pop("size", 10))

    if size > 100:
        raise HTTPException(status_code=400, detail="Page size cannot exceed 100")

    search_word = filters.pop("searchWord", None)
    search_fields = filters.pop("searchFields", None)
    order_by = filters.pop("orderBy", None)
    order_direction = filters.pop("orderDirection", "asc")

    validate_order_by(order_by, allowed_filters, allowed_search)

    and_rules = process_filters(filters, allowed_filters)

    or_rules = process_search_word(search_word, search_fields, allowed_search) if search_word else []

    return {
        "pageable": {"page": page, "size": size},
        "rules": {"andRules": and_rules, "orRules": or_rules},
        "ordering": {"orderBy": order_by, "orderDirection": order_direction},
    }
