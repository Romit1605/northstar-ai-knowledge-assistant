import pytest
from fastapi.testclient import TestClient
# pyrefly: ignore [missing-import]
from sqlalchemy import create_engine
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db

# Use an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_auth.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def cleanup_db():
    # Run before each test
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    # Run after each test
    pass

def test_successful_registration():
    response = client.post(
        "/api/auth/register",
        json={"full_name": "Test User", "email": "test@example.com", "password": "SecurePassword123!"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["full_name"] == "Test User"
    assert "id" in data
    assert "hashed_password" not in data
    assert "password" not in data

def test_duplicate_email_rejection():
    # First registration
    client.post(
        "/api/auth/register",
        json={"full_name": "Test User", "email": "duplicate@example.com", "password": "SecurePassword123!"}
    )
    # Second registration
    response = client.post(
        "/api/auth/register",
        json={"full_name": "Another User", "email": "duplicate@example.com", "password": "DifferentPassword123!"}
    )
    assert response.status_code == 400
    assert "Email already registered" in response.json()["detail"]

def test_successful_login():
    # Register first
    client.post(
        "/api/auth/register",
        json={"full_name": "Login User", "email": "login@example.com", "password": "SecurePassword123!"}
    )
    # Login
    response = client.post(
        "/api/auth/login",
        json={"email": "login@example.com", "password": "SecurePassword123!"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_wrong_password_rejection():
    # Register first
    client.post(
        "/api/auth/register",
        json={"full_name": "Wrong Pass User", "email": "wrongpass@example.com", "password": "SecurePassword123!"}
    )
    # Login with wrong password
    response = client.post(
        "/api/auth/login",
        json={"email": "wrongpass@example.com", "password": "WrongPassword456!"}
    )
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]

def test_protected_route_without_token():
    response = client.get("/api/auth/me")
    assert response.status_code == 401

def test_protected_route_with_valid_token():
    # Register and Login
    client.post(
        "/api/auth/register",
        json={"full_name": "Protected User", "email": "protected@example.com", "password": "SecurePassword123!"}
    )
    login_response = client.post(
        "/api/auth/login",
        json={"email": "protected@example.com", "password": "SecurePassword123!"}
    )
    token = login_response.json()["access_token"]
    
    # Access protected route
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "protected@example.com"
    assert data["full_name"] == "Protected User"

def test_password_stored_as_hash():
    # Register
    client.post(
        "/api/auth/register",
        json={"full_name": "Hash User", "email": "hash@example.com", "password": "MySecretPassword!"}
    )
    # Check DB manually
    db = TestingSessionLocal()
    from app.models.user import User
    user = db.query(User).filter(User.email == "hash@example.com").first()
    db.close()
    
    assert user is not None
    assert user.hashed_password != "MySecretPassword!"
    assert user.hashed_password.startswith("$2b$") # bcrypt prefix
