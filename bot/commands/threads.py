# -*- coding: utf-8  -*-

import threading
import re

from classes import BaseCommand, Data, KwargParseException
import tasks
import config

class Command(BaseCommand):
    """Manage wiki tasks from IRC, and check on thread status."""
    name = "threads"

    def check(self, data):
        commands = ["tasks", "task", "threads", "tasklist"]
        if data.is_command and data.command in commands:
            return True
        return False

    def process(self, data):
        self.data = data
        if data.host not in config.irc["permissions"]["owners"]:
            msg = "you must be a bot owner to use this command."
            self.connection.reply(data, msg)
            return

        if not data.args:
            if data.command == "tasklist":
                self.do_list()
            else:
                msg = "no arguments provided. Maybe you wanted '!{0} list', '!{0} start', or '!{0} listall'?"
                self.connection.reply(data, msg.format(data.command))
            return

        if data.args[0] == "list":
            self.do_list()

        elif data.args[0] == "start":
            self.do_start()

        elif data.args[0] in ["listall", "all"]:
            self.do_listall()

        else:  # They asked us to do something we don't know
            msg = "unknown argument: \x0303{0}\x0301.".format(data.args[0])
            self.connection.reply(data, msg)

    def do_list(self):
        """With !tasks list (or abbreviation !tasklist), list all running
        threads. This includes the main threads, like the irc frontend and the
        watcher, and task threads."""
        threads = threading.enumerate()

        normal_threads = []
        task_threads = []

        for thread in threads:
            tname = thread.name
            if tname == "MainThread":
                tname = self.get_main_thread_name()
                t = "\x0302{0}\x0301 (as main thread, id {1})"
                normal_threads.append(t.format(tname, thread.ident))
            elif tname in ["irc-frontend", "irc-watcher", "wiki-scheduler"]:
                t = "\x0302{0}\x0301 (id {1})"
                normal_threads.append(t.format(tname, thread.ident))
            elif tname.startswith("reminder"):
                tname = tname.replace("reminder ", "")
                t = "\x0302reminder\x0301 (until {0})"
                normal_threads.append(t.format(tname))
            else:
                tname, start_time = re.findall("^(.*?) \((.*?)\)$", tname)[0]
                t = "\x0302{0}\x0301 (id {1}, since {2})"
                task_threads.append(t.format(tname, thread.ident, start_time))

        if task_threads:
            msg = "\x02{0}\x0F threads active: {1}, and \x02{2}\x0F task threads: {3}."
            msg = msg.format(len(threads), ', '.join(normal_threads),
                             len(task_threads), ', '.join(task_threads))
        else:
            msg = "\x02{0}\x0F threads active: {1}, and \x020\x0F task threads."
            msg = msg.format(len(threads), ', '.join(normal_threads))

        self.connection.reply(self.data, msg)

    def do_listall(self):
        """With !tasks listall or !tasks all, list all loaded tasks, and report
        whether they are currently running or idle."""
        all_tasks = tasks.get_all().keys()
        threads = threading.enumerate()
        tasklist = []

        all_tasks.sort()

        for task in all_tasks:
            threadlist = [t for t in threads if t.name.startswith(task)]
            ids = [str(t.ident) for t in threadlist]
            if not ids:
                tasklist.append("\x0302{0}\x0301 (idle)".format(task))
            elif len(ids) == 1:
                t = "\x0302{0}\x0301 (\x02active\x0F as id {1})"
                tasklist.append(t.format(task, ids[0]))
            else:
                t = "\x0302{0}\x0301 (\x02active\x0F as ids {1})"
                tasklist.append(t.format(task, ', '.join(ids)))

        tasklist = ", ".join(tasklist)

        msg = "{0} tasks loaded: {1}.".format(len(all_tasks), tasklist)
        self.connection.reply(self.data, msg)

    def do_start(self):
        """With !tasks start, start any loaded task by name with or without
        kwargs."""
        data = self.data

        try:
            task_name = data.args[1]
        except IndexError:  # No task name given
            self.connection.reply(data, "what task do you want me to start?")
            return

        try:
            data.parse_kwargs()
        except KwargParseException, arg:
            msg = "error parsing argument: \x0303{0}\x0301.".format(arg)
            self.connection.reply(data, msg)
            return

        if task_name not in tasks.get_all().keys():
            # This task does not exist or hasn't been loaded:
            msg = "task could not be found; either bot/tasks/{0}.py doesn't exist, or it wasn't loaded correctly."
            self.connection.reply(data, msg.format(task_name))
            return

        tasks.start(task_name, **data.kwargs)
        msg = "task \x0302{0}\x0301 started.".format(task_name)
        self.connection.reply(data, msg)

    def get_main_thread_name(self):
        """Return the "proper" name of the MainThread."""
        if "irc_frontend" in config.components:
            return "irc-frontend"
        elif "wiki_schedule" in config.components:
            return "wiki-scheduler"
        else:
            return "irc-watcher"
