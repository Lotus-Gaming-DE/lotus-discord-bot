from .bot import MyBot
import os


def main():
    token = os.getenv("bot_key")
    if not token:
        raise SystemExit("Environment variable 'bot_key' is not set.")
    bot = MyBot()
    bot.run(token)


if __name__ == "__main__":
    main()
