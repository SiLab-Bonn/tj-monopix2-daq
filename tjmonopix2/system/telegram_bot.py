import asyncio
import os
import socket
import sys
from contextlib import suppress

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import NetworkError, TimedOut, TelegramError


# --- Config (prefer env vars; fallback keeps your current behavior) ---
BOT_TOKEN = os.getenv("TJMP2_TELEGRAM_BOT_TOKEN")
GROUP_ID = int(os.getenv("TJMP2_TELEGRAM_GROUP_ID"))
if BOT_TOKEN is None:
    raise RuntimeError("Telegram bot token not set (TJMP2_TELEGRAM_BOT_TOKEN)")

THREAD_ID_SCANS = 2
THREAD_ID_ANALYSIS = 4
THREAD_ID_LOG = 48

# Reasonable defaults for flaky lab networks
CONNECT_TIMEOUT_S = float(os.getenv("TJMP2_TELEGRAM_CONNECT_TIMEOUT", "5"))
READ_TIMEOUT_S = float(os.getenv("TJMP2_TELEGRAM_READ_TIMEOUT", "10"))
WRITE_TIMEOUT_S = float(os.getenv("TJMP2_TELEGRAM_WRITE_TIMEOUT", "10"))

# If DNS is broken, don't even try
CHECK_DNS = os.getenv("TJMP2_TELEGRAM_CHECK_DNS", "1") == "1"


def _dns_ok(host: str = "api.telegram.org") -> bool:
    if not CHECK_DNS:
        return True
    try:
        socket.gethostbyname(host)
        return True
    except OSError:
        return False


def send_message_scan(run_config, pdf_path=None):
    msg = f'{run_config["scan_id"]} completed! 🦆'
    send_message_generic(THREAD_ID_SCANS, msg, pdf_path)


def send_message_ana(data=None, pdf_path=None):
    msg = "Analysis completed, but no further info available."
    if data:
        msg = f"Analysis completed: {data}"
    send_message_generic(THREAD_ID_ANALYSIS, msg, pdf_path)


def send_message_log(msg=None, pdf_path=None):
    if not msg:
        msg = "Backup finished!"
    send_message_generic(THREAD_ID_LOG, msg, pdf_path)


async def _send_message_generic(bot: Bot, thread_id: int, msg: str, pdf_path: str | None = None):
    await bot.send_message(
        chat_id=GROUP_ID,
        message_thread_id=thread_id,
        text=msg,
        parse_mode=ParseMode.HTML,
        connect_timeout=CONNECT_TIMEOUT_S,
        read_timeout=READ_TIMEOUT_S,
        write_timeout=WRITE_TIMEOUT_S,
    )

    if pdf_path:
        # ensure file is closed properly
        with open(pdf_path, "rb") as f:
            await bot.send_document(
                chat_id=GROUP_ID,
                message_thread_id=thread_id,
                document=f,
                connect_timeout=CONNECT_TIMEOUT_S,
                read_timeout=READ_TIMEOUT_S,
                write_timeout=WRITE_TIMEOUT_S,
            )


def send_message_generic(thread_id, msg, pdf_path=None):
    # Never let Telegram break the scan
    if not BOT_TOKEN or BOT_TOKEN.strip() == "":
        print("[telegram_bot] WARNING: BOT_TOKEN missing; skipping Telegram message")
        return

    if not _dns_ok():
        print("[telegram_bot] WARNING: DNS resolution failed (api.telegram.org). Skipping Telegram message.")
        return

    bot = Bot(token=BOT_TOKEN)

    try:
        asyncio.run(_send_message_generic(bot, thread_id, msg, pdf_path))
    except (TimedOut, NetworkError) as e:
        print(f"[telegram_bot] WARNING: network error while sending Telegram message: {e}")
    except TelegramError as e:
        print(f"[telegram_bot] WARNING: Telegram API error: {e}")
    except Exception as e:
        print(f"[telegram_bot] WARNING: unexpected error while sending Telegram message: {e}")


def main():
    # Simple CLI helper, keeps your current behavior
    if len(sys.argv) > 1:
        if sys.argv[1] == "analysis":
            # usage: telegram_bot.py analysis "<text>" "<pdf_path>"
            text = sys.argv[2] if len(sys.argv) > 2 else None
            pdf = sys.argv[3] if len(sys.argv) > 3 else None
            send_message_ana(data=text, pdf_path=pdf)
        else:
            send_message_log(sys.argv[1])
    else:
        send_message_log()


if __name__ == "__main__":
    main()