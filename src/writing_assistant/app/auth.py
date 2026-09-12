"""Authentication setup with FastAPI Users."""

import logging
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

logger = logging.getLogger(__name__)

DEFAULT_SECRET = "CHANGE_THIS_IN_PRODUCTION_PLEASE"  # nosec B105 - placeholder, not a credential
"""Fallback JWT secret.

It is a fixed placeholder, not a generated value: every install that leaves
``WRITING_ASSISTANT_SECRET`` unset signs tokens with this same string, so
anyone can forge one. ``server.main`` warns about it when the server is
reachable from other machines.
"""

SECRET = os.getenv("WRITING_ASSISTANT_SECRET", DEFAULT_SECRET)


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
        """Called after a user requests password reset.

        There is no mail delivery, so the token can only go to the server's
        log — which makes that log as good as the account's password. It is
        logged as a warning (rather than printed) so a deployment can route or
        silence it, and the documented way to reset a password is
        ``writing-assistant-admin reset-password <email>``.
        """
        logger.warning(
            "Password reset requested for %s (%s). No email is configured, so "
            "the reset token is only available here — treat this log as "
            "sensitive, or reset the password with "
            "`writing-assistant-admin reset-password %s` instead. Token: %s",
            user.email,
            user.id,
            user.email,
            token,
        )

    async def on_after_request_verify(
        self, user: User, token: str, request: Request | None = None
    ) -> None:
        """Called after a user requests email verification.

        Same caveat as password reset: with no mail delivery the token ends up
        in the server's log.
        """
        logger.warning(
            "Email verification requested for %s (%s). No email is configured, "
            "so the token is only available here — treat this log as "
            "sensitive. Token: %s",
            user.email,
            user.id,
            token,
        )


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
