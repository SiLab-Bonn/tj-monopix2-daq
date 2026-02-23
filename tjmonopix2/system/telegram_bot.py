import asyncio
from telegram import Bot
from telegram.constants import ParseMode
import sys

# just call api directly:

# https://api.telegram.org/bot8410051827:AAEhUWIkj6qWeJeN_ZSBLP5Wa-AXWPTerZM/getUpdates


# Your bot token
BOT_TOKEN = "8410051827:AAEhUWIkj6qWeJeN_ZSBLP5Wa-AXWPTerZM"

# Replace with your group chat IDs (negative numbers for groups)
GROUP_ID = -1002894820936

THREAD_ID_SCANS = 2
THREAD_ID_ANALYSIS = 4
THREAD_ID_LOG = 48


def send_message_scan(run_config, pdf_path=None):
    msg = f'{run_config["scan_id"]} completed! 🦆'

    send_message_generic(THREAD_ID_SCANS, msg, pdf_path)


def send_message_ana(data=None, pdf_path=None):
    msg = f'Ananlysis completed, but no further info available.'
    if data:
        msg = f'Analysis completed: {data}'

    send_message_generic(THREAD_ID_ANALYSIS, msg, pdf_path)


def send_message_log(msg=None, pdf_path=None):
    if not msg:
        msg = 'Backup finished!'   # default message

    send_message_generic(THREAD_ID_LOG, msg)



def main():
    bot = Bot(token=BOT_TOKEN)

    rc = {'scan_id': 'Test'}

    # send_message_scan(rc)
    # send_message_log('Custom logger message! Isn\'t that cool?')
    # send_message_ana()
    # send_message_ana('very good fit!')

    if len(sys.argv) > 1:
        if sys.argv[1] == 'analysis':
            send_message_ana(data=sys.argv[2], pdf_path=sys.argv[3])
        else:
            send_message_log(sys.argv[1])
    else:
        send_message_log()





async def _send_message_generic(bot, thread_id, msg, pdf_path=None):
    # Send to Group 1, in its thread
    await bot.send_message(
        chat_id=GROUP_ID,
        message_thread_id=thread_id,
        text=msg,
        parse_mode=ParseMode.HTML
    )

    if pdf_path:
        await bot.send_document(
            chat_id=GROUP_ID,
            message_thread_id=thread_id,
            document=open(pdf_path, "rb")
        )


def send_message_generic(thread_id, msg, pdf_path=None):
    bot = Bot(token=BOT_TOKEN)

    # Send to Group 1, in its thread
    asyncio.run(_send_message_generic(bot, thread_id, msg, pdf_path))


if __name__ == "__main__":
    main()
