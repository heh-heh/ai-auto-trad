from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    toss_client_id: str = ""
    toss_client_secret: str = ""
    toss_account_seq: str = ""
    trading_mode: str = "paper"
    allowed_origins: str = "http://localhost:8080,https://heh-heh.github.io"
    max_order_krw: int = 100_000
    max_daily_loss_krw: int = 50_000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
