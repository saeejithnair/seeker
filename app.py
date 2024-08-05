# app.py
from flask import Flask, jsonify, request, send_from_directory
from servers import Server, SERVERS, SERVERS_LIST
import json

app = Flask(__name__)


def parse_nvidia_smi_output(output):
    gpu_data = []
    lines = output.split("\n")[1:]
    for line in lines:
        if line:
            elements = [element.strip() for element in line.split(",")]
            try:
                gpu_info = {
                    "name": elements[0],
                    "temperature": f"{elements[6]}°C",
                    "power": f"{elements[1]} / {elements[5]}",
                    "memory": f"{elements[2]} / {elements[3]}",
                    "utilization": elements[4],
                }
                gpu_data.append(gpu_info)
            except IndexError as e:
                print(f"Error parsing line: {line}")
                raise e
    return gpu_data


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/servers")
def get_servers():
    return jsonify(SERVERS_LIST)


@app.route("/gpu_data/<hostname>")
def gpu_data(hostname):
    server = SERVERS.get(hostname)
    if not server:
        return jsonify({"error": "Unknown server"}), 404

    transport = server.ssh.get_transport()
    if transport is None or not transport.is_active():
        return jsonify({"error": "Server is not connected"}), 500

    command = (
        f"nvidia-smi --query-gpu=name,power.draw,memory.used,memory.total,"
        f"utilization.gpu,power.max_limit,temperature.gpu --format=csv"
    )

    output = server.exec_command_sync(command)
    try:
        gpu_data = parse_nvidia_smi_output(output)
    except Exception as e:
        print(f"Error parsing nvidia-smi output for {hostname}. Error: {e}")
        return jsonify({"error": "Error parsing GPU data"}), 500

    return jsonify(gpu_data)


@app.route("/launch_experiment", methods=["POST"])
def launch_experiment():
    data = request.json
    servers = data["servers"]
    gpu_selections = data["gpu_selections"]
    project = data["project"]
    command = data["command"]

    results = []

    for hostname in servers:
        server = SERVERS.get(hostname)
        if not server:
            results.append({"hostname": hostname, "error": "Unknown server"})
            continue

        try:
            # Pull the latest project changes
            pull_command = f"cd {project} && git pull"
            pull_output = server.exec_command_sync(pull_command)
            print(f"Git pull output for {hostname}: {pull_output}")

            gpu_results = []
            for gpu_id in gpu_selections.get(hostname, []):
                arch_command = f"nvidia-smi --query-gpu=compute_cap --format=csv,noheader -i {gpu_id}"
                architecture = server.exec_command_sync(arch_command).strip()
                architecture = architecture.replace(".", "")
                print(f"GPU {gpu_id} architecture on {hostname}: {architecture}")

                env_vars = f"GPU_IDS={gpu_id} CUDA_ARCHITECTURES={architecture}"
                full_command = f"cd {project} && {env_vars} {command}"
                print(f"Executing command for {hostname} GPU {gpu_id}: {full_command}")

                output = server.exec_command_sync(full_command)
                gpu_results.append(
                    {
                        "gpu_id": gpu_id,
                        "architecture": architecture,
                        "command": full_command,
                        "output": output,
                    }
                )

            results.append(
                {
                    "hostname": hostname,
                    "pull_output": pull_output,
                    "gpu_results": gpu_results,
                }
            )

        except Exception as e:
            print(f"Error launching experiment on {hostname}: {str(e)}")
            results.append({"hostname": hostname, "error": str(e)})

    return jsonify({"results": results})


@app.route("/get_gpu_architectures/<hostname>")
def get_gpu_architectures(hostname):
    server = SERVERS.get(hostname)
    if not server:
        return jsonify({"error": "Unknown server"}), 404

    command = "nvidia-smi --query-gpu=compute_cap --format=csv,noheader"
    output = server.exec_command_sync(command)
    architectures = output.strip().split("\n")

    return jsonify({"architectures": architectures})


if __name__ == "__main__":
    app.run(port=5001, debug=True)
