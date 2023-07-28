from flask import Flask, jsonify
from flask import send_from_directory

from servers import Server, SERVERS

app = Flask(__name__)


def parse_nvidia_smi_output(output):
    gpu_data = []

    # Split the output by lines and skip the first line (header)
    lines = output.split("\n")[1:]

    for line in lines:
        if line:  # if line is not empty
            # Split the line by comma and strip each element
            elements = [element.strip() for element in line.split(",")]

            gpu_info = {
                "name": elements[0],
                "temperature": f"{elements[6]}",
                "power": f"{elements[1]} / {elements[5]}",
                "memory": f"{elements[2]} / {elements[3]}",
                "utilization": elements[4],
            }

            gpu_data.append(gpu_info)

    return gpu_data


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/gpu_data/<hostname>")
def gpu_data(hostname):
    server = SERVERS.get(hostname)
    if not server:
        return jsonify({"error": "Unknown server"}), 404

    def callback(output):
        # Parse the nvidia-smi output and store it in the server object.
        server.gpu_data = parse_nvidia_smi_output(output)

    command = (
        f"nvidia-smi --query-gpu=name,power.draw,memory.used,memory.total,"
        f"utilization.gpu,power.max_limit,temperature.gpu --format=csv"
    )
    server.exec_command(command, callback)

    # Wait for the command to finish.
    server.queue.join()

    return jsonify(server.gpu_data)


if __name__ == "__main__":
    app.run(port=5001)
