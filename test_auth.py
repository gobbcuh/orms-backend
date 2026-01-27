from utils.auth import *

# password hashing test
password = "test123"
hashed = hash_password(password)
print(f"Original: {password}")
print(f"Hashed: {hashed}")
print(f"Verified: {verify_password(password, hashed)}")
print()

# JWT token generation
user_data = {
    'user_id': 1,
    'username': 'receptionist',
    'role': 'receptionist'
}

token = generate_token(user_data)
print(f"Generated Token: {token[:50]}...")
print()

# token decoding
decoded = decode_token(token)
print(f"Decoded Token:")
print(f"  User ID: {decoded['user_id']}")
print(f"  Username: {decoded['username']}")
print(f"  Role: {decoded['role']}")
print()

# invalid token test
invalid_decoded = decode_token("invalid.token.here")
print(f"Invalid Token Result: {invalid_decoded}")
print()

print("- All auth utilities working.")