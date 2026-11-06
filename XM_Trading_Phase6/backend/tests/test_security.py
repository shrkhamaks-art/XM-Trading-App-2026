from app.security import hash_password, verify_password, make_access_token, read_access_token

def test_password_hashing():
    hashed = hash_password("Long-demo-password-123!")
    assert hashed != "Long-demo-password-123!"
    assert verify_password("Long-demo-password-123!", hashed)
    assert not verify_password("wrong", hashed)

def test_jwt_claims():
    token = make_access_token("user@example.test", "investor")
    claims = read_access_token(token)
    assert claims["sub"] == "user@example.test"
    assert claims["role"] == "investor"
