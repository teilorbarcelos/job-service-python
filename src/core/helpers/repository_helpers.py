from sqlalchemy import asc, desc, or_
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import class_mapper, selectinload


def model_to_dict(obj, max_depth=1, current_depth=0):
    if obj is None:
        return None

    mapper = class_mapper(obj.__class__)
    d = {c.key: getattr(obj, c.key) for c in mapper.columns}

    if current_depth >= max_depth:
        return d

    insp = inspect(obj)
    for rel in mapper.relationships:
        if rel.key not in insp.unloaded:
            rel_obj = getattr(obj, rel.key)
            if rel_obj is None:
                d[rel.key] = None
            elif isinstance(rel_obj, list):
                d[rel.key] = [model_to_dict(item, max_depth, current_depth + 1) for item in rel_obj]
            else:
                d[rel.key] = model_to_dict(rel_obj, max_depth, current_depth + 1)
    return d


def get_attribute_and_join(model, stmt, key, joined_models):
    if "." not in key:
        if hasattr(model, key):
            return getattr(model, key), stmt
        return None, stmt

    parts = key.split(".")
    current_model = model
    current_stmt = stmt

    for i, part in enumerate(parts[:-1]):
        if hasattr(current_model, part):
            rel = getattr(current_model, part)

            target_model = rel.property.mapper.class_
            if target_model not in joined_models:
                current_stmt = current_stmt.outerjoin(rel)
                joined_models.add(target_model)
            current_model = target_model
        else:
            return None, current_stmt

    final_key = parts[-1]
    if hasattr(current_model, final_key):
        return getattr(current_model, final_key), current_stmt
    return None, current_stmt


def _build_leaf_condition(attr, qt, value):
    if isinstance(value, str) and qt == "contains":
        return attr.ilike(f"%{value}%")
    elif qt == "gte":
        return attr >= value
    elif qt == "lte":
        return attr <= value
    elif qt == "gt":
        return attr > value
    elif qt == "lt":
        return attr < value
    else:
        return attr == value


def build_nested_any_has_condition(model, parts, qt, value):
    if len(parts) == 1:
        attr = getattr(model, parts[0], None)
        if attr is None:
            return None
        return _build_leaf_condition(attr, qt, value)

    part = parts[0]
    if hasattr(model, part):
        rel = getattr(model, part)
        if hasattr(rel, "property") and hasattr(rel.property, "mapper"):
            target_model = rel.property.mapper.class_
            inner_cond = build_nested_any_has_condition(target_model, parts[1:], qt, value)
            if inner_cond is not None:
                if rel.property.uselist:
                    return rel.any(inner_cond)
                else:
                    return rel.has(inner_cond)
    return None


def _process_and_rules(model, stmt, and_rules, joined_models):
    for rule in and_rules:
        key = rule.get("key")
        value = rule.get("search")
        qt = rule.get("qt", "equals")

        parts = key.split(".")
        if len(parts) > 2:
            condition = build_nested_any_has_condition(model, parts, qt, value)
            if condition is not None:
                stmt = stmt.where(condition)
        else:
            attr, stmt = get_attribute_and_join(model, stmt, key, joined_models)
            if attr is not None:
                stmt = stmt.where(_build_leaf_condition(attr, qt, value))
    return stmt


def _process_or_rules(model, stmt, or_rules, joined_models):
    or_conditions = []
    for rule in or_rules:
        key = rule.get("key")
        value = rule.get("search")
        qt = rule.get("qt", "contains")

        parts = key.split(".")
        if len(parts) > 2:
            condition = build_nested_any_has_condition(model, parts, qt, value)
            if condition is not None:
                or_conditions.append(condition)
        else:
            attr, stmt = get_attribute_and_join(model, stmt, key, joined_models)
            if attr is not None:
                or_conditions.append(_build_leaf_condition(attr, qt, value))

    if or_conditions:
        stmt = stmt.where(or_(*or_conditions))
    return stmt


def apply_filters(model, stmt, filters, joined_models=None):
    if joined_models is None:
        joined_models = set()

    include_deleted = filters.get("includeDeleted", False) if filters else False
    if hasattr(model, "is_deleted") and not include_deleted:
        stmt = stmt.where(model.is_deleted == False)

    if not filters:
        if hasattr(model, "active"):
            stmt = stmt.where(model.active == True)
        return stmt

    ignore_default = filters.get("ignoreDefaultFilters", False)

    if not ignore_default:
        if hasattr(model, "active") and "active" not in [r.get("key") for r in filters.get("andRules", [])]:
            stmt = stmt.where(model.active == True)

    and_rules = filters.get("andRules", [])
    if and_rules:
        stmt = _process_and_rules(model, stmt, and_rules, joined_models)

    or_rules = filters.get("orRules", [])
    if or_rules:
        stmt = _process_or_rules(model, stmt, or_rules, joined_models)

    return stmt


def apply_ordering(model, stmt, ordering, joined_models=None):
    if joined_models is None:
        joined_models = set()

    if not ordering or not ordering.get("orderBy"):
        if hasattr(model, "created_at"):
            return stmt.order_by(desc(model.created_at))
        return stmt

    order_by = ordering.get("orderBy")
    direction = ordering.get("orderDirection", "asc").lower()

    if order_by:
        attr, stmt = get_attribute_and_join(model, stmt, order_by, joined_models)
        if attr is not None:
            if direction == "desc":
                stmt = stmt.order_by(desc(attr))
            else:
                stmt = stmt.order_by(asc(attr))
    return stmt


def apply_includes(model, stmt, include):
    if not include:
        return stmt

    for key, value in include.items():
        if value and hasattr(model, key):
            stmt = stmt.options(selectinload(getattr(model, key)))
    return stmt
