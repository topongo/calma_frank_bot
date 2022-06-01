from telebotapi import TelegramBot
from main import CommandStore
from threading import Thread
from time import sleep
from utils import Forks, Fork, Condition, Filter


def add_command(m, t: TelegramBot, commands: CommandStore, forks: Forks, dump_to_json):
    def run(msg, tbot, cmds):
        def type_clb(msg_):
            txt = msg_.text.lower()
            if txt == "t" or txt == "trap":
                new_command["type"] = "trap"
            elif txt == "c" or txt == "command":
                new_command["type"] = "bot_command"
            else:
                tbot.sendMessage(msg.from_, f"Unrecognized type")

        tbot.sendMessage(msg.from_, f"Type of command?\n"
                                    f"- Trap (T)\n"
                                    f"- Command (C)")
        new_command = {}
        id_ = forks.attach(
            Condition(
                Filter(lambda l: l.from_ == msg.from_),
                callback=type_clb),
            Condition(
                Filter(lambda l: "type" in new_command),
                stop_return=True
            )
        )

        forks.get(id_).join()
        forks.detach(id_)

        tbot.sendMessage(msg.from_, f"Type: \"{new_command['type']}\", ok")

        if new_command["type"] == "trap":
            def regex_clb(msg_):
                if isinstance(msg_, TelegramBot.Update.Text):
                    new_command["regex"] = msg_.text
                else:
                    tbot.sendMessage(msg_.from_, "Invalid data sent.")

            tbot.sendMessage(msg.from_, f"Now send me the matching regex")
            id_ = forks.attach(
                Condition(
                    Filter(lambda l: l.from_ == msg.from_),
                    callback=regex_clb),
                Condition(
                    Filter(lambda l: "regex" in new_command),
                    stop_return=True)
            )
        elif new_command["type"] == "bot_command":
            def bot_command_clb(msg_):
                if isinstance(msg_, TelegramBot.Update.Text):
                    new_command["bot_command"] = msg_.text
                else:
                    tbot.sendMessage(msg_.from_, "Invalid data sent.")

            tbot.sendMessage(msg.from_, "Now send me the command.")
            id_ = forks.attach(
                Condition(
                    Filter(lambda l: l.from_ == msg.from_),
                    callback=bot_command_clb),
                Condition(
                    Filter(lambda l: "bot_command" in new_command),
                    stop_return=True)
            )

        forks.get(id_).join()
        forks.detach(id_)

        tbot.sendMessage(msg.from_, "Send me whatever you want me to send back. (text, audio, sticker, photo")

        def response_clb(msg_):
            if isinstance(msg_, TelegramBot.Update.Text):
                new_command["response"] = CommandStore.Text(msg_.text).dump()
            elif isinstance(msg_, TelegramBot.Update.Sticker):
                new_command["response"] = CommandStore.Sticker(msg_).dump()
            elif isinstance(msg_, TelegramBot.Update.Photo):
                new_command["response"] = CommandStore.Photo(msg_).dump()
            elif isinstance(msg_, TelegramBot.Update.Audio):
                new_command["response"] = CommandStore.Audio(msg_).dump()
            else:
                tbot.sendMessage(msg_.from_, "Sorry, this type of content isn't yet recognized.")

        id_ = forks.attach(
            Condition(
                Filter(lambda l: l.from_ == msg.from_),
                callback=response_clb),
            Condition(
                Filter(lambda l: "response" in new_command),
                stop_return=True
            )
        )

        forks.get(id_).join()
        forks.detach(id_)
        print(f"About to add this command: {new_command}")
        commands.add(new_command)
        dump_to_json()

    Thread(target=run, args=(m, t, commands), daemon=True).start()

