from telebotapi import TelegramBot
from main import CommandStore
from threading import Thread
from time import sleep


def add_command(m, t: TelegramBot, commands: CommandStore):
    def run(msg, tbot, cmds):
        tbot.sendMessage(msg.from_, f"Type of command?\n"
                                    f"- Trap (T)\n"
                                    f"- Command (C)")
        sleep(10)
        tbot.sendMessage(msg.from_, "Timeout reached")

    Thread(target=run, args=(m, t, commands), daemon=True).start()

