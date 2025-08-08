import os
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv


load_dotenv()


def _get_admin_ids(env_value: str | None) -> List[int]:
    if not env_value:
        return []
    result: List[int] = []
    for part in env_value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            result.append(int(part))
        except ValueError:
            continue
    return result


@dataclass
class Settings:
    bot_token: str
    admin_ids: List[int]
    timezone: str
    database_path: str


def load_settings() -> Settings:
    bot_token = os.getenv("BOT_TOKEN", "")
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is not set. Put it in .env or environment.")

    admin_ids = _get_admin_ids(os.getenv("ADMIN_IDS"))
    timezone = os.getenv("TZ", os.getenv("TIMEZONE", "Europe/Moscow"))
    database_path = os.getenv("DATABASE_PATH", os.path.abspath("bot.db"))

    return Settings(
        bot_token=bot_token,
        admin_ids=admin_ids,
        timezone=timezone,
        database_path=database_path,
    )