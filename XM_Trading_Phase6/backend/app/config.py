import secrets
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator

class Settings(BaseSettings):
    database_url: str = "sqlite:///./demo.db"
    # Ephemeral random defaults are development conveniences only; production must set both explicitly.
    jwt_secret: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    otp_pepper: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    app_env: str = "development"
    # Explicit opt-in for local development only; never use on a public server.
    allow_dev_otp: bool = False
    otp_ttl_seconds: int = 300
    otp_max_attempts: int = 5
    access_token_minutes: int = 10
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_security(self):
        if self.app_env.lower() in {"production", "prod"}:
            if self.allow_dev_otp:
                raise ValueError("Development OTP must be disabled in production")
            if len(self.jwt_secret.encode()) < 32:
                raise ValueError("JWT_SECRET must contain at least 32 bytes in production")
            if len(self.otp_pepper.encode()) < 32:
                raise ValueError("OTP_PEPPER must contain at least 32 bytes in production")
            if self.database_url.startswith("sqlite"):
                raise ValueError("Production requires PostgreSQL; SQLite is development/test only")
        return self

settings = Settings()
