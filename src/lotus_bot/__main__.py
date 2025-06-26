from .bot import MyBot
import os


def main() -> None:
    """Entry point used by ``python -m lotus_bot``."""

    token = os.getenv("bot_key")
    if not token:
        raise SystemExit("Environment variable 'bot_key' is not set.")

    bot = MyBot()
    bot.run(token)


if __name__ == "__main__":  # pragma: no cover
    main()
