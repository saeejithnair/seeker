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


SERVERS = {
    "guacamole": Server("129.97.251.225"),
    "banana": Server("129.97.1.49"),
    "lavazza": Server("129.97.250.2"),
    "matcha": Server("129.97.250.15"),
    "latte": Server("129.97.251.209"),
    "chai": Server("129.97.250.21"),
    "lox": Server("129.97.250.179"),
    "cheetah": Server("129.97.1.47", username="saeejith"),
    "kiwi": Server("129.97.1.45", username="saeejith"),
    "macchiato": Server("129.97.251.198"),
}
