import time
from flask import Flask
from flask_socketio import SocketIO, emit
from paramiko import SSHClient, AutoAddPolicy
from dataclasses import dataclass, field
import re
from typing import Dict
from threading import Thread
from flask import send_from_directory

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")


@dataclass
class Server:
    ip: str
    username: str = "smnair"
    ssh: SSHClient = field(default_factory=SSHClient)

    def connect(self):
        self.ssh = SSHClient()
        self.ssh.set_missing_host_key_policy(AutoAddPolicy())
        self.ssh.connect(self.ip, username=self.username)
        transport = self.ssh.get_transport()
        if transport is not None:
            transport.set_keepalive(30)  # send a keep-alive packet every 60 seconds

    def __post_init__(self):
        self.connect()


SERVERS: Dict[str, Server] = {
    "guacamole": Server(ip="129.97.251.225"),
    "lavazza": Server(ip="129.97.250.2"),
}


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@socketio.on("connect")
def connect():
    def gather_and_emit_data(server):
        while True:
            try:
                stdin, stdout, stderr = server.ssh.exec_command("nvidia-smi")
                output = stdout.read().decode()
                gpu_data = parse_nvidia_smi_output(output)
                socketio.emit("gpu_data", {"server": hostname, "data": gpu_data})
            except Exception as e:
                print(f"Error gathering data from {server.ip}: {str(e)}")
                print("Attempting to re-establish connection...")
                try:
                    server.ssh.close()
                    server.ssh.connect(server.ip, username=server.username)
                    print("Connection re-established")
                except Exception as e:
                    print(f"Failed to re-establish connection: {str(e)}")
                    server.connect()

            time.sleep(1)  # reduce delay to 1 second

    for hostname, server in SERVERS.items():
        Thread(target=gather_and_emit_data, args=(server,)).start()


def parse_nvidia_smi_output(output):
    lines = output.split("\n")
    gpu_data = []

    for i in range(len(lines)):
        if "NVIDIA RTX A6000" in lines[i]:
            gpu = {}
            gpu["name"] = lines[i].split()[2]
            gpu["temperature"] = (
                lines[i + 1].split("|")[1].split()[1][:-1]
            )  # remove 'C'
            gpu["power"] = lines[i + 1].split("|")[1].split()[3][:-1]  # remove 'W'
            gpu["memory"] = lines[i + 1].split("|")[2].split()[1][:-3]  # remove 'MiB'
            gpu["utilization"] = (
                lines[i + 1].split("|")[3].split()[1][:-1]
            )  # remove '%'
            gpu_data.append(gpu)

    return gpu_data


if __name__ == "__main__":
    socketio.run(app, port=5001)
