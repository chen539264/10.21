"""Local password verifier. Accounts must be provisioned outside source control."""
import hashlib
import hmac
import json
import secrets
from pathlib import Path

def make_user(password):
    salt=secrets.token_hex(16)
    return {'salt':salt,'iterations':600000,'hash':hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),600000).hex()}

def verify(users, username, password):
    user=users.get(username)
    if not user:return False
    try:
        value=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(user['salt']),int(user['iterations'])).hex()
        return hmac.compare_digest(value,user['hash'])
    except (KeyError,ValueError,TypeError):return False
