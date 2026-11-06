import pytest
from pydantic import ValidationError
from app.config import Settings

def test_dev_otp_disabled_by_default():
    assert Settings(_env_file=None).allow_dev_otp is False

def test_prod_rejects_demo_otp():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="production", allow_dev_otp=True,
                 database_url="postgresql+psycopg://u:p@localhost/db",
                 jwt_secret="x" * 48, otp_pepper="y" * 48)

def test_prod_rejects_sqlite():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="production", allow_dev_otp=False,
                 database_url="sqlite:///demo.db",
                 jwt_secret="x" * 48, otp_pepper="y" * 48)
