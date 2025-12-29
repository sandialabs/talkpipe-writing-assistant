#!/usr/bin/env python3
"""Admin tool for managing Writing Assistant users."""

import asyncio
import sys
from getpass import getpass


async def list_users():
    """List all users."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from writing_assistant.app.database import get_session_maker
    from writing_assistant.app.models import User

    session_maker = get_session_maker()
    async with session_maker() as session:
        result = await session.execute(
            select(User)
            .options(selectinload(User.documents))
            .order_by(User.created_at.desc())
        )
        users = result.scalars().all()

        if not users:
            print("No users found.")
            return

        print(f"\n{'ID':<38} {'Email':<30} {'Active':<8} {'Super':<8} {'Documents':<10} {'Created'}")
        print("-" * 120)

        for user in users:
            # Count documents
            doc_count = len(user.documents) if user.documents else 0

            print(
                f"{str(user.id):<38} "
                f"{user.email:<30} "
                f"{'Yes' if user.is_active else 'No':<8} "
                f"{'Yes' if user.is_superuser else 'No':<8} "
                f"{doc_count:<10} "
                f"{user.created_at.strftime('%Y-%m-%d %H:%M')}"
            )


async def delete_user(email: str):
    """Delete a user and all their documents."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from writing_assistant.app.database import get_session_maker
    from writing_assistant.app.models import User

    session_maker = get_session_maker()
    async with session_maker() as session:
        result = await session.execute(
            select(User)
            .options(selectinload(User.documents))
            .where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if not user:
            print(f"User with email '{email}' not found.")
            return

        # Count documents
        doc_count = len(user.documents) if user.documents else 0

        print(f"\nUser: {user.email}")
        print(f"ID: {user.id}")
        print(f"Documents: {doc_count}")
        print(f"Created: {user.created_at}")

        confirm = input(f"\nAre you sure you want to delete this user? (yes/no): ").strip().lower()

        if confirm != "yes":
            print("Deletion cancelled.")
            return

        # Delete user (cascade will delete documents and snapshots)
        await session.delete(user)
        await session.commit()

        print(f"✓ User '{email}' and all associated data deleted successfully.")


async def reset_password(email: str):
    """Reset a user's password."""
    from fastapi_users.password import PasswordHelper
    from sqlalchemy import select

    from writing_assistant.app.database import get_session_maker
    from writing_assistant.app.models import User

    session_maker = get_session_maker()
    async with session_maker() as session:
        result = await session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if not user:
            print(f"User with email '{email}' not found.")
            return

        print(f"\nResetting password for: {user.email}")

        password = getpass("New password: ")
        password_confirm = getpass("Confirm password: ")

        if password != password_confirm:
            print("Error: Passwords don't match")
            return

        if len(password) < 8:
            print("Error: Password must be at least 8 characters")
            return

        # Hash and update password
        password_helper = PasswordHelper()
        user.hashed_password = password_helper.hash(password)
        await session.commit()

        print(f"✓ Password reset successfully for {email}")


async def toggle_active(email: str):
    """Toggle user active status."""
    from sqlalchemy import select

    from writing_assistant.app.database import get_session_maker
    from writing_assistant.app.models import User

    session_maker = get_session_maker()
    async with session_maker() as session:
        result = await session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if not user:
            print(f"User with email '{email}' not found.")
            return

        user.is_active = not user.is_active
        await session.commit()

        status = "active" if user.is_active else "inactive"
        print(f"✓ User '{email}' is now {status}")


async def make_superuser(email: str):
    """Make a user a superuser."""
    from sqlalchemy import select

    from writing_assistant.app.database import get_session_maker
    from writing_assistant.app.models import User

    session_maker = get_session_maker()
    async with session_maker() as session:
        result = await session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if not user:
            print(f"User with email '{email}' not found.")
            return

        user.is_superuser = True
        user.is_verified = True
        await session.commit()

        print(f"✓ User '{email}' is now a superuser")


async def show_user_info(email: str):
    """Show detailed user information."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from writing_assistant.app.database import get_session_maker
    from writing_assistant.app.models import User

    session_maker = get_session_maker()
    async with session_maker() as session:
        result = await session.execute(
            select(User)
            .options(selectinload(User.documents))
            .where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if not user:
            print(f"User with email '{email}' not found.")
            return

        print(f"\n{'='*60}")
        print(f"User Information")
        print(f"{'='*60}")
        print(f"ID:          {user.id}")
        print(f"Email:       {user.email}")
        print(f"Active:      {user.is_active}")
        print(f"Superuser:   {user.is_superuser}")
        print(f"Verified:    {user.is_verified}")
        print(f"Created:     {user.created_at}")
        print(f"Documents:   {len(user.documents) if user.documents else 0}")

        if user.documents:
            print(f"\nDocuments:")
            for doc in user.documents[:5]:  # Show first 5
                print(f"  - {doc.filename} (updated: {doc.updated_at.strftime('%Y-%m-%d %H:%M')})")
            if len(user.documents) > 5:
                print(f"  ... and {len(user.documents) - 5} more")


def print_help():
    """Print help message."""
    print("""
Writing Assistant - User Administration Tool

Usage: writing-assistant-admin <command> [arguments]

Commands:
  list                          List all users
  info <email>                  Show detailed user information
  delete <email>                Delete a user and all their data
  reset-password <email>        Reset a user's password
  toggle-active <email>         Toggle user active/inactive status
  make-superuser <email>        Make a user a superuser
  help                          Show this help message

Examples:
  writing-assistant-admin list
  writing-assistant-admin info user@example.com
  writing-assistant-admin delete user@example.com
  writing-assistant-admin reset-password user@example.com
  writing-assistant-admin make-superuser admin@example.com

Note: This tool requires direct access to the database.
    """)


async def async_main():
    """Async main entry point."""
    from writing_assistant.app.database import create_db_and_tables, get_engine

    # Initialize database
    await create_db_and_tables()

    if len(sys.argv) < 2:
        print_help()
        return

    command = sys.argv[1].lower()

    try:
        if command == "list":
            await list_users()

        elif command == "info":
            if len(sys.argv) < 3:
                print("Error: Email required")
                print("Usage: writing-assistant-admin info <email>")
                sys.exit(1)
            await show_user_info(sys.argv[2])

        elif command == "delete":
            if len(sys.argv) < 3:
                print("Error: Email required")
                print("Usage: writing-assistant-admin delete <email>")
                sys.exit(1)
            await delete_user(sys.argv[2])

        elif command == "reset-password":
            if len(sys.argv) < 3:
                print("Error: Email required")
                print("Usage: writing-assistant-admin reset-password <email>")
                sys.exit(1)
            await reset_password(sys.argv[2])

        elif command == "toggle-active":
            if len(sys.argv) < 3:
                print("Error: Email required")
                print("Usage: writing-assistant-admin toggle-active <email>")
                sys.exit(1)
            await toggle_active(sys.argv[2])

        elif command == "make-superuser":
            if len(sys.argv) < 3:
                print("Error: Email required")
                print("Usage: writing-assistant-admin make-superuser <email>")
                sys.exit(1)
            await make_superuser(sys.argv[2])

        elif command == "help":
            print_help()

        else:
            print(f"Unknown command: {command}")
            print_help()
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Dispose of the engine to close all connections
        engine = get_engine()
        await engine.dispose()


def main():
    """Main entry point for the admin command."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
