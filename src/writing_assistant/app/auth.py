"""Authentication setup with FastAPI Users."""

import os
import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from fastapi_users import (
    BaseUserManager,
    FastAPIUsers,
    InvalidPasswordException,
    UUIDIDMixin,
    schemas,
)
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)

from .database import UserDatabase, get_user_db
from .models import User

# Secret key for JWT - should be set via environment variable in production
SECRET = os.getenv("WRITING_ASSISTANT_SECRET", "CHANGE_THIS_IN_PRODUCTION_PLEASE")


# The type-var ignores below share one cause: mypy compares User's class-level
# Mapped[...] columns against fastapi-users' UserProtocol without applying the
# descriptor, so it rejects a model that satisfies the protocol at runtime
# (see database.UserDatabase).
class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):  # type: ignore[type-var]
    """User manager for handling user lifecycle events."""

    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def validate_password(self, password: str, user: schemas.UC | User) -> None:
        """Enforce the same minimum password length as the registration page."""
        if len(password) < 8:
            raise InvalidPasswordException(
                reason="Password must be at least 8 characters long"
            )

    async def on_after_register(
        self, user: User, request: Request | None = None
    ) -> None:
        """Called after a user successfully registers."""
        print(f"User {user.id} has registered with email {user.email}")

    async def on_after_forgot_password(
        self, user: User, token: str, request: Request | None = None
    ) -> None:
        """Called after a user requests password reset."""
        print(f"User {user.id} has requested password reset. Token: {token}")

    async def on_after_request_verify(
        self, user: User, token: str, request: Request | None = None
    ) -> None:
        """Called after a user requests email verification."""
        print(f"Verification requested for user {user.id}. Token: {token}")


async def get_user_manager(
    user_db: UserDatabase = Depends(get_user_db),
) -> AsyncGenerator[UserManager, None]:
    """Dependency to get user manager."""
    yield UserManager(user_db)


# Bearer token transport
bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    """Get JWT strategy."""
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600 * 24 * 7)  # 7 days


# Authentication backend
auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# FastAPI Users instance
fastapi_users = FastAPIUsers[User, uuid.UUID](  # type: ignore[type-var]
    get_user_manager,
    [auth_backend],
)

# Dependencies for getting current user
current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)
