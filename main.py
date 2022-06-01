import bot_commands
import re
from bot_key import key
from utils import Filter, Condition, wait_for, Forks
from telebotapi import TelegramBot, File as TBotFile
from json import load, dump
from os.path import exists
from typing import Union


ADMINS = [TelegramBot.User.by_id(461073396)]
CHATS = [TelegramBot.Chat.by_id(-1001625660193)]

t = TelegramBot(key, safe_mode=True)


def admin_command_dispatcher(msg):
    # check stuff
    if isinstance(msg, TelegramBot.Update.Text):
        for i in admin_commands.commands:
            if i == msg:
                i.fire(t, msg)

    # else send to normal user command
    command_dispatcher(msg)


def command_dispatcher(msg):
    if isinstance(msg, TelegramBot.Update.Text):
        for i in commands.commands:
            if i == msg:
                i.fire(t, msg)


class CommandStore:
    class Response:
        def fire(self, tbot, to, msg, data=None):
            pass

        def dump(self):
            pass

        @staticmethod
        def detect(data: dict):
            if data["type"] == "function":
                return CommandStore.Function(data["call"], data["additional_arguments"])
            elif data["type"] == "photo":
                return CommandStore.Photo(data["photo"])
            elif data["type"] == "text":
                return CommandStore.Text(data["text"])
            elif data["type"] == "sticker":
                return CommandStore.Sticker(data["sticker"])
            elif data["type"] == "audio":
                return CommandStore.Audio(data["audio"])
            else:
                raise TypeError(data)

    class Function(Response):
        def __init__(self, call: callable, additional_arguments=None):
            self.call = call
            self.additional_arguments = additional_arguments

        def fire(self, tbot, to, msg, data=None):
            self.call(msg, tbot, **(self.additional_arguments if self.additional_arguments else {}))

        def dump(self):
            raise TypeError("Commands of type BotCommand cannot be dumped, they can only be defined at runtime")

        def __eq__(self, other):
            if isinstance(other, self.__class__):
                return self.call == other.call

    class Photo(Response):
        def __init__(self, photo: TelegramBot.Photo):
            if isinstance(photo, dict):
                self.photo = TelegramBot.Update.Photo(photo)
            elif isinstance(photo, TelegramBot.Update.Photo):
                self.photo = photo
            else:
                raise TypeError(photo)

        def fire(self, tbot, to, msg, data=None):
            tbot.sendPhoto(to, self.photo, reply_to_message=msg)

        def dump(self):
            return {"type": "photo", "photo": self.photo.raw}

        def __eq__(self, other):
            if isinstance(other, self.__class__):
                return self.photo == other.photo

    class Text(Response):
        MATCH = {
            "%everything%": lambda l: l.text
        }

        def __init__(self, text: str):
            if not isinstance(text, str):
                raise TypeError(text)
            self.text = text

        def match(self, msg, data=None):
            out = self.text
            for m, f in self.MATCH.items():
                out = out.replace(m, f(msg))
            if data:
                for n, d in enumerate(data, start=1):
                    out = out.replace(f"${n}", d)
            return out

        def fire(self, tbot, to, msg, data=None):
            tbot.sendMessage(to, self.match(msg, data) if data else self.match(msg), reply_to_message=msg)

        def dump(self):
            return {"type": "text", "text": self.text}

        def __eq__(self, other):
            if isinstance(other, self.__class__):
                return self.text == other.text

    class Sticker(Response):
        def __init__(self, sticker: TelegramBot.Update.Sticker):
            if isinstance(sticker, dict):
                self.sticker = TelegramBot.Update.Sticker(sticker)
            elif isinstance(sticker, TelegramBot.Update.Sticker):
                self.sticker = sticker
            else:
                raise TypeError(sticker)

        def fire(self, tbot, to, msg, data=None):
            tbot.sendSticker(to, self.sticker, reply_to_message=msg)

        def dump(self):
            return {"type": "sticker", "sticker": self.sticker.raw}

        def __eq__(self, other):
            if isinstance(other, self.__class__):
                return self.sticker == other.sticker

    class Audio(Response):
        def __init__(self, audio: TelegramBot.Update.Audio):
            if isinstance(audio, dict):
                self.audio = TelegramBot.Update.Audio(audio)
            elif isinstance(audio, TelegramBot.Update.Audio):
                self.audio = audio
            else:
                raise TypeError(audio)

        def fire(self, tbot, to, msg, data=None):
            tbot.sendDocument(to, self.audio, reply_to_message=msg)

        def dump(self):
            return {"type": "audio", "audio": self.audio.raw}

        def __eq__(self, other):
            if isinstance(other, self.__class__):
                return self.audio == other.audio

    class Command:
        def __init__(self, response):
            if not isinstance(response, CommandStore.Response):
                raise TypeError(response)
            self.response = response

        @staticmethod
        def detect(data: dict):
            response = CommandStore.Response.detect(data["response"])

            if data["type"] == "trap":
                return CommandStore.Trap(response, data["regex"])
            elif data["type"] == "bot_command":
                return CommandStore.BotCommand(response, data["regex"])

        def dump_all(self, type_, **other):
            if type_ is None:
                raise TypeError()
            return {
                "type": type_,
                "response": self.response.dump(),
                **other
            }

        def fire(self, tbot: TelegramBot, msg, data=None):
            self.response.fire(tbot, msg.chat, msg, data)

        def __eq__(self, other):
            if isinstance(other, self.__class__):
                return self.response == other.response

    class Trap(Command):
        def __init__(self, response, regex):
            super().__init__(response)
            self.regex = regex

        def dump(self):
            return super().dump_all("trap", regex=self.regex)

        def fire(self, tbot: TelegramBot, msg, data=None):
            super().fire(tbot, msg, data=re.findall(self.regex, msg.text, re.IGNORECASE))

        def __eq__(self, other):
            if isinstance(other, self.__class__):
                return super().__eq__(other) and self.regex == other.regex
            elif isinstance(other, TelegramBot.Update.Message):
                return re.findall(self.regex, other.text, re.IGNORECASE)

    class BotCommand(Command):
        def __init__(self, response, command: str):
            super().__init__(response)
            self.command = command

        def __eq__(self, other):
            if isinstance(other, self.__class__):
                return super().__eq__(other) and self.command == other.command
            elif isinstance(other, TelegramBot.Update.Message):
                return self.command in other.text

        def dump(self):
            return super().dump_all("bot_command", command=self.command)

    def __init__(self, data=None):
        self.commands = []
        if data:
            for d in data:
                self.add(d)

    def dump(self):
        return [
            d.dump()
            for d in self.commands
            if not isinstance(d.response, CommandStore.Function)
        ]

    def add(self, data):
        if isinstance(data, CommandStore.Command):
            self.commands.append(data)
        elif isinstance(data, dict):
            response = CommandStore.Response.detect(data["response"])

            if data["type"] == "trap":
                self.commands.append(CommandStore.Trap(response, data["regex"]))
            elif data["type"] == "bot_command":
                self.commands.append(CommandStore.BotCommand(response, data["regex"]))


def dump_to_json(file=None):
    if not file:
        file = "data.json"
    dump({"normal": commands.dump(), "admin": admin_commands.dump()}, open(file, "w+"), indent=4)


if __name__ == "__main__":
    forks = Forks()

    if exists("data.json"):
        raw_data = load(open("data.json"))
        commands = CommandStore(raw_data["normal"])
        admin_commands = CommandStore(raw_data["admin"])
    else:
        commands = CommandStore()
        admin_commands = CommandStore()
        dump_to_json()

    admin_commands.commands.append(CommandStore.BotCommand(
        CommandStore.Function(bot_commands.add_command, {"commands": commands, "forks": forks, "dump_to_json": dump_to_json}),
        "/add_command")
    )

    """commands.commands.append(CommandStore.Trap(
        CommandStore.Text("Chiaramente intendevi dire \"$1 sei un coglione\", non \"%everything%\""),
        r".*(patta|bodo|lorenzo|degra).*"
    ))

    commands.commands.append(CommandStore.Trap(
        CommandStore.Sticker(
            TelegramBot.Update.Sticker.from_id(
                "CAACAgQAAx0CYOWbIQADFmKUkeerJpymCT9Fl5zA4Tx0i4wbAALQAAOeQjse6LIcHW6-2gYkBA")),
        r".*calma\sfrank.*"
    ))"""

    t.bootstrap()

    conditions = [
        Condition(
            Filter(lambda l: l.chat in ADMINS),
            callback=admin_command_dispatcher
        ),
        Condition(
            Filter(lambda l: l.chat in CHATS),
            callback=command_dispatcher
        ),
        # Condition(
        #     Filter(lambda l: isinstance(l, TelegramBot.Update.Sticker)),
        #     callback=lambda l: print(l.file.raw)
        # )
    ]

    wait_for(t, *conditions, forks=forks, timeout=0)

