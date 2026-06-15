import datetime

import bcrypt
from sqlalchemy import select

from src.infra.database.models import Auth, Feature, Role, RoleFeature, User
from src.shared.config.constants import FEATURES_DATA, ROLES_DATA
from src.shared.config.settings import settings


async def seed_features(session):
    for key, data in FEATURES_DATA.items():
        feature = await session.get(Feature, key)
        if not feature:
            feature = Feature(id=key, name=data["name"], description=data["description"])
            session.add(feature)
        else:
            feature.name = data["name"]
            feature.description = data["description"]


async def seed_roles(session):
    for key, data in ROLES_DATA.items():
        role = await session.get(Role, key)
        if not role:
            role = Role(id=key, name=data["name"], description=data["description"])
            session.add(role)
        else:
            role.name = data["name"]
            role.description = data["description"]

        await session.flush()

        for f_data in data["features"]:
            rf = await session.get(RoleFeature, (key, f_data["key"]))
            if not rf:
                rf = RoleFeature(
                    id_role=key,
                    id_feature=f_data["key"],
                    create=f_data["create"],
                    view=f_data["view"],
                    delete=f_data["delete"],
                    activate=f_data["activate"],
                )
                session.add(rf)
            else:
                rf.create = f_data["create"]
                rf.view = f_data["view"]
                rf.delete = f_data["delete"]
                rf.activate = f_data["activate"]


async def seed_admin(session):
    email = settings.first_user
    password = settings.first_password

    if not email or not password:
        return

    user_stmt = select(User).where(User.email == email)
    user_result = await session.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if not user:
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        auth = Auth(password=hashed, password_algo="bcrypt", password_updated_at=datetime.datetime.now())
        session.add(auth)
        await session.flush()

        user = User(email=email, name="Admin", id_auth=auth.id, id_role="administrator")
        session.add(user)
    else:
        user.id_role = "administrator"
        session.add(user)
