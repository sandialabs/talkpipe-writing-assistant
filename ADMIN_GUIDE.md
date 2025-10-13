# User Administration Guide

This guide explains how to administer users in the Writing Assistant application.

## Quick Start

### 1. Create a Superuser (First Time Setup)

```bash
python create_superuser.py
```

This creates an admin account that can manage other users via the API.

### 2. Use the Admin CLI Tool

```bash
# List all users
python admin_users.py list

# Show detailed user info
python admin_users.py info user@example.com

# Delete a user (and all their documents)
python admin_users.py delete user@example.com

# Reset a user's password
python admin_users.py reset-password user@example.com

# Deactivate/activate a user
python admin_users.py toggle-active user@example.com

# Make a user a superuser
python admin_users.py make-superuser user@example.com

# Show help
python admin_users.py help
```

## Administration Methods

### Method 1: Command-Line Admin Tool (Recommended)

The `admin_users.py` script provides a simple interface for common tasks:

**List all users:**
```bash
$ python admin_users.py list

ID                                     Email                          Active   Super    Documents  Created
-------------------------------------------------------------------------------------------------------------------------
a1b2c3d4-e5f6-7890-abcd-ef1234567890  admin@example.com              Yes      Yes      5          2025-10-12 14:30
b2c3d4e5-f6a7-8901-bcde-f12345678901  user@example.com               Yes      No       12         2025-10-12 15:45
```

**Delete a user:**
```bash
$ python admin_users.py delete user@example.com

User: user@example.com
ID: b2c3d4e5-f6a7-8901-bcde-f12345678901
Documents: 12
Created: 2025-10-12 15:45:23

Are you sure you want to delete this user? (yes/no): yes
✓ User 'user@example.com' and all associated data deleted successfully.
```

**Reset password:**
```bash
$ python admin_users.py reset-password user@example.com

Resetting password for: user@example.com
New password: ********
Confirm password: ********
✓ Password reset successfully for user@example.com
```

### Method 2: REST API (Requires Superuser Token)

First, login as a superuser to get a token:

```bash
# Login
curl -X POST http://localhost:8001/auth/jwt/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=yourpassword"

# Response: {"access_token": "eyJ...", "token_type": "bearer"}
```

Then use the token for admin operations:

**List users (via /users/me for self, need to query each user ID for others):**
```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8001/users/me
```

**Update a user (deactivate, change email, etc.):**
```bash
curl -X PATCH \
  -H "Authorization: Bearer <superuser_token>" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}' \
  http://localhost:8001/users/{user_id}
```

**Delete a user:**
```bash
curl -X DELETE \
  -H "Authorization: Bearer <superuser_token>" \
  http://localhost:8001/users/{user_id}
```

### Method 3: Direct Database Access

For advanced operations, you can access the SQLite database directly:

```bash
# Open the database
sqlite3 ~/.writing_assistant/writing_assistant.db

# List all users
SELECT id, email, is_active, is_superuser, created_at FROM users;

# Deactivate a user
UPDATE users SET is_active = 0 WHERE email = 'user@example.com';

# Delete a user (will cascade to documents and snapshots)
DELETE FROM users WHERE email = 'user@example.com';

# Count documents per user
SELECT u.email, COUNT(d.id) as doc_count
FROM users u
LEFT JOIN documents d ON u.id = d.user_id
GROUP BY u.id;

# Exit
.quit
```

**Database Schema:**
```sql
-- Users table
users (
    id UUID PRIMARY KEY,
    email VARCHAR(320) UNIQUE NOT NULL,
    hashed_password VARCHAR(1024) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP,
    preferences TEXT
)

-- Documents table (foreign key to users)
documents (
    id INTEGER PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    title VARCHAR(500),
    content TEXT NOT NULL,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)

-- Snapshots table (foreign key to documents)
document_snapshots (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    snapshot_name VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP
)
```

## Common Tasks

### Creating the First Admin User

```bash
python create_superuser.py
```

Follow the prompts to enter email and password.

### Resetting a Forgotten Password

```bash
python admin_users.py reset-password user@example.com
```

### Deactivating a User (Soft Delete)

```bash
# Deactivate (user can't login but data is preserved)
python admin_users.py toggle-active user@example.com

# Reactivate later
python admin_users.py toggle-active user@example.com
```

### Permanently Deleting a User and All Their Data

```bash
python admin_users.py delete user@example.com
```

**Warning:** This deletes:
- The user account
- All their documents
- All their document snapshots
- Their preferences

This action cannot be undone!

### Promoting a User to Administrator

```bash
python admin_users.py make-superuser user@example.com
```

Superusers can:
- Access all API endpoints
- Manage other users via the API
- View and modify any user's data

### Viewing User Statistics

```bash
python admin_users.py list
```

Shows:
- User ID
- Email
- Active status
- Superuser status
- Number of documents
- Account creation date

### Getting Detailed User Information

```bash
python admin_users.py info user@example.com
```

Shows:
- All user fields
- List of their documents
- Document metadata

## Security Best Practices

1. **Protect Superuser Credentials**: Superusers have full access to all data
2. **Use Strong Passwords**: Minimum 8 characters (enforced)
3. **Deactivate Instead of Delete**: When possible, deactivate users rather than deleting them
4. **Regular Backups**: Copy `~/.writing_assistant/writing_assistant.db` regularly
5. **Set JWT Secret**: In production, set `WRITING_ASSISTANT_SECRET` environment variable to a strong random value
6. **Database Permissions**: Ensure only authorized users can access the database file

## Troubleshooting

**"User not found"**
- Check spelling of email address
- Use `admin_users.py list` to see all users

**"Permission denied" when accessing database**
- Check file permissions: `ls -la ~/.writing_assistant/writing_assistant.db`
- Ensure you have read/write access

**Scripts won't run**
- Make sure you're in the project directory
- Check Python path: `python admin_users.py help`

**Database is locked**
- Stop the server before running admin commands
- SQLite doesn't handle concurrent writes well

## API Documentation

For full API documentation, visit:
```
http://localhost:8001/docs
```

This shows all available endpoints including user management routes.

## Custom Database Location

If using a custom database location:

```bash
# Set the database path
export WRITING_ASSISTANT_DB_PATH=/path/to/database.db

# Or specify in the admin command
WRITING_ASSISTANT_DB_PATH=/path/to/database.db python admin_users.py list
```

## Backup and Restore

**Backup:**
```bash
# Copy the entire database
cp ~/.writing_assistant/writing_assistant.db ~/backups/db-$(date +%Y%m%d).db

# Or export specific user data
sqlite3 ~/.writing_assistant/writing_assistant.db ".dump users documents" > backup.sql
```

**Restore:**
```bash
# Restore from backup
cp ~/backups/db-20251012.db ~/.writing_assistant/writing_assistant.db

# Or import SQL dump
sqlite3 ~/.writing_assistant/writing_assistant.db < backup.sql
```
