from dataclasses import dataclass
from paramiko import SSHClient, AutoAddPolicy
from threading import Thread
from queue import Queue


class Server:
    def __init__(self, ip, username="smnair"):
        self.ip = ip
        self.username = username
        self.ssh = SSHClient()
        self.ssh.set_missing_host_key_policy(AutoAddPolicy())
        self.ssh.connect(self.ip, username=self.username)
        self.queue = Queue()
        self.gpu_data = []
        self.start_worker()

    def start_worker(self):
        def worker():
            while True:
                command, callback = self.queue.get()
                stdin, stdout, stderr = self.ssh.exec_command(command)
                output = stdout.read().decode()
                callback(output)
                self.queue.task_done()

        Thread(target=worker, daemon=True).start()

    def exec_command(self, command, callback):
        self.queue.put((command, callback))


SERVERS_LIST = [
    "banana",
    "chai",
    "cheetah",
    "citrus",
    "davincci",
    # "frappe",
    "guacamole",
    "kiwi",
    "latte",
    "lavazza",
    "lilac",
    "lox",
    "macchiato",
    "matcha",
    "platypus",
]
SERVERS = {key: Server(f"{key}.uwaterloo.ca") for key in SERVERS_LIST}
