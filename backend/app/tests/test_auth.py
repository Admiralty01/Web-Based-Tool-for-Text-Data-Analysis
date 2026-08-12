import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.user import User


def test_signup_user(client: TestClient):
    """Test user registration endpoint."""
    signup_data = {
        "email": "testuser@example.com",
        "password": "strongpassword123",
        "role": "viewer"
    }
    response = client.post("/api/v1/auth/signup", json=signup_data)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == "testuser@example.com"
    # Because it is the first user registered in the db, it gets elevated to admin
    assert data["role"] == "admin"
    assert data["is_active"] is True
    assert "id" in data


def test_signup_duplicate_email(client: TestClient):
    """Test registering a duplicate email returns an error."""
    user_data = {
        "email": "duplicate@example.com",
        "password": "password123"
    }
    # Upload first time
    response = client.post("/api/v1/auth/signup", json=user_data)
    assert response.status_code == status.HTTP_201_CREATED
    
    # Upload duplicate
    response = client.post("/api/v1/auth/signup", json=user_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "already exists" in response.json()["detail"]


def test_login_user(client: TestClient):
    """Test user authentication and token issuance."""
    # Register user
    signup_data = {
        "email": "loginuser@example.com",
        "password": "secretpassword",
        "role": "analyst"
    }
    client.post("/api/v1/auth/signup", json=signup_data)

    # Login
    login_payload = {
        "username": "loginuser@example.com",
        "password": "secretpassword"
    }
    response = client.post("/api/v1/auth/login", data=login_payload)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_credentials(client: TestClient):
    """Test login fails with incorrect password."""
    signup_data = {
        "email": "fail@example.com",
        "password": "correct_password"
    }
    client.post("/api/v1/auth/signup", json=signup_data)

    login_payload = {
        "username": "fail@example.com",
        "password": "wrong_password"
    }
    response = client.post("/api/v1/auth/login", data=login_payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Incorrect email or password" in response.json()["detail"]


def test_get_me_profile(client: TestClient):
    """Test fetching details of current active session user using JWT authentication."""
    email = "profile@example.com"
    password = "profilepassword"
    # Register
    client.post("/api/v1/auth/signup", json={"email": email, "password": password})
    
    # Login to get token
    login_res = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    token = login_res.json()["access_token"]
    
    # Access profile
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["email"] == email
