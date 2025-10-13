#!/usr/bin/env python3
"""Admin tool for managing Writing Assistant users."""

import asyncio
import sys
import os
from getpass import getpass
from datetime import datetime


async def list_users():
    """List all users."""
    from writing_assistant.app.database import get_async_session
    from writing_assistant.app.models import User
    from sqlalchemy import select, func

    async for session in get_async_session():
        result = await session.execute(
            select(User).order_by(User.created_at.desc())
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
    from writing_assistant.app.database import get_async_session
    from writing_assistant.app.models import User
    from sqlalchemy import select

    async for session in get_async_session():
        result = await session.execute(
            select(User).where(User.email == email)
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
    from writing_assistant.app.database import get_async_session
    from writing_assistant.app.models import User
    from sqlalchemy import select
    from fastapi_users.password import PasswordHelper

    async for session in get_async_session():
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
    from writing_assistant.app.database import get_async_session
    from writing_assistant.app.models import User
    from sqlalchemy import select

    async for session in get_async_session():
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
    from writing_assistant.app.database import get_async_session
    from writing_assistant.app.models import User
    from sqlalchemy import select

    async for session in get_async_session():
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
    from writing_assistant.app.database import get_async_session
    from writing_assistant.app.models import User
    from sqlalchemy import select

    async for session in get_async_session():
        result = await session.execute(
            select(User).where(User.email == email)
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

Usage: python admin_users.py <command> [arguments]

Commands:
  list                          List all users
  info <email>                  Show detailed user information
  delete <email>                Delete a user and all their data
  reset-password <email>        Reset a user's password
  toggle-active <email>         Toggle user active/inactive status
  make-superuser <email>        Make a user a superuser
  help                          Show this help message

Examples:
  python admin_users.py list
  python admin_users.py info user@example.com
  python admin_users.py delete user@example.com
  python admin_users.py reset-password user@example.com
  python admin_users.py make-superuser admin@example.com

Note: This tool requires direct access to the database.
    """)


async def main():
    """Main entry point."""
    # Set up Python path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

    from writing_assistant.app.database import create_db_and_tables

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
                print("Usage: python admin_users.py info <email>")
                return
            await show_user_info(sys.argv[2])

        elif command == "delete":
            if len(sys.argv) < 3:
                print("Error: Email required")
                print("Usage: python admin_users.py delete <email>")
                return
            await delete_user(sys.argv[2])

        elif command == "reset-password":
            if len(sys.argv) < 3:
                print("Error: Email required")
                print("Usage: python admin_users.py reset-password <email>")
                return
            await reset_password(sys.argv[2])

        elif command == "toggle-active":
            if len(sys.argv) < 3:
                print("Error: Email required")
                print("Usage: python admin_users.py toggle-active <email>")
                return
            await toggle_active(sys.argv[2])

        elif command == "make-superuser":
            if len(sys.argv) < 3:
                print("Error: Email required")
                print("Usage: python admin_users.py make-superuser <email>")
                return
            await make_superuser(sys.argv[2])

        elif command == "help":
            print_help()

        else:
            print(f"Unknown command: {command}")
            print_help()

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
