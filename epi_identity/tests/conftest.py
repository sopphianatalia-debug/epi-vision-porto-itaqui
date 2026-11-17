import os
import tempfile

# Configura ambiente ANTES de importar a aplicação.
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.environ["EPI_DATABASE_URL"] = f"sqlite+aiosqlite:///{_db_path}"
os.environ["EPI_ENVIRONMENT"] = "test"
os.environ["EPI_FACE_PROVIDER"] = "mock"
# Chave Fernet fixa para determinismo nos testes.
from cryptography.fernet import Fernet  # noqa: E402

os.environ["EPI_BIOMETRIC_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.enums import Role  # noqa: E402
from app.main import app  # noqa: E402
from app.security.auth import create_access_token  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def _reset_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def auth_header(role: Role = Role.SECURITY_MANAGER, subject: str = "tester") -> dict:
    token = create_access_token(subject=subject, role=role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sm_header():
    return auth_header(Role.SECURITY_MANAGER)


@pytest.fixture
def viewer_header():
    return auth_header(Role.VIEWER)
