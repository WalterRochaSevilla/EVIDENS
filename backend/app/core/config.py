from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "EVIDENS"
    environment: str = "development"
    secret_key: str
    database_url: str

    @property
    def async_database_url(self) -> str:
        """Transforma la URL estándar de Neon al formato requerido por asyncpg."""
        url_con_driver = self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        url_con_ssl = url_con_driver.replace("sslmode=require", "ssl=require")
        return url_con_ssl.replace("&channel_binding=require", "")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()