from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongo_uri: str
    mongo_db_name: str = "software_intelligence"

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # respaldo duro del token; la inactividad manda antes

    session_inactivity_minutes: int = 20

    cors_origins: str = "http://localhost:3000"

    rag_api_base_url: str = "https://ragapi-production-acb3.up.railway.app"

    class Config:
        env_file = ".env"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
