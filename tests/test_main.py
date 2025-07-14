# from fastapi.testclient import TestClient
# from adtivity.main import app
# from adtivity.database import SessionLocal, engine
# import pytest

# client = TestClient(app)

# @pytest.fixture(scope="module")
# def test_db():
#     # Setup test database
#     models.Base.metadata.create_all(bind=engine)
#     db = SessionLocal()
#     yield db
#     db.close()
#     # Teardown
#     models.Base.metadata.drop_all(bind=engine)

# def test_health_check():
#     response = client.get("/health")
#     assert response.status_code == 200
#     assert response.json()["status"] == "healthy"

# def test_user_creation():
#     test_user = {
#         "email": "testuser@example.com",
#         "password": "testpass123",
#         "wallet_address": "0x71C7656EC7ab88b098defB751B7401B5f6d8976F"
#     }
#     response = client.post("/users/", json=test_user)
#     assert response.status_code == 201
#     assert response.json()["email"] == test_user["email"]