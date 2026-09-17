from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_does_not_store_plaintext() -> None:
    hashed = hash_password("mypassword123")

    assert hashed != "mypassword123"
    assert verify_password("mypassword123", hashed) is True


def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password("mypassword123")

    assert verify_password("wrongpassword", hashed) is False


def test_create_and_decode_access_token_roundtrip() -> None:
    token = create_access_token(subject="user-123", role="ADMIN")

    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["role"] == "ADMIN"


def test_decode_access_token_rejects_garbage_token() -> None:
    assert decode_access_token("this-is-not-a-jwt") is None
