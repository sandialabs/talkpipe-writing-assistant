#!/usr/bin/env python3
"""Create a superuser for the Writing Assistant application."""

import asyncio
import sys
import os
from getpass import getpass


async def create_superuser():
    """Create a superuser account."""
    # Set up Python path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

    from writing_assistant.app.database import get_async_session, create_db_and_tables
    from writing_assistant.app.models import User
    from sqlalchemy import select
    from fastapi_users.password import PasswordHelper

    # Initialize database
    print("Initializing database...")
    await create_db_and_tables()

    # Get user input
    print("\n=== Create Superuser ===")
    email = input("Email: ").strip()

    if not email:
        print("Error: Email is required")
        return

    password = getpass("Password: ")
    password_confirm = getpass("Password (again): ")

    if password != password_confirm:
        print("Error: Passwords don't match")
        return

    if len(password) < 8:
        print("Error: Password must be at least 8 characters")
        return

    # Create user
    async for session in get_async_session():
        # Check if user already exists
        result = await session.execute(
            select(User).where(User.email == email)
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            print(f"\nUser with email {email} already exists.")
            update = input("Make this user a superuser? (y/n): ").strip().lower()
            if update == 'y':
                existing_user.is_superuser = True
                existing_user.is_active = True
                existing_user.is_verified = True
                await session.commit()
                print(f"✓ User {email} is now a superuser")
            return

        # Hash password
        password_helper = PasswordHelper()
        hashed_password = password_helper.hash(password)

        # Create new superuser
        import uuid
        new_user = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password=hashed_password,
            is_active=True,
            is_superuser=True,
            is_verified=True,
        )

        session.add(new_user)
        await session.commit()

        print(f"\n✓ Superuser created successfully!")
        print(f"  Email: {email}")
        print(f"  ID: {new_user.id}")
        print(f"\nYou can now login at: http://localhost:8001/login")


if __name__ == "__main__":
    asyncio.run(create_superuser())
