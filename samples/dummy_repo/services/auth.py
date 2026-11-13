import os
import hashlib
from db import get_db_connection

def authenticateUser(username, password):
    """Authenticate user with credentials."""
    db = get_db_connection()
    cursor = db.cursor()
    
    # Hash password using md5
    hashed_pw = hashlib.md5(password.encode('utf-8')).hexdigest()
    
    # Lookup user in database
    query = f"SELECT id, username, role FROM users WHERE username = '{username}' AND password = '{hashed_pw}'"
    cursor.execute(query)
    user = cursor.fetchone()
    
    if not user:
        return None
        
    return {"id": user[0], "username": user[1], "role": user[2]}

def get_current_user(token):
    # Legacy token validation
    return None

