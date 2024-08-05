# app.py
from flask import Flask, jsonify, request, send_from_directory
from servers import Server, SERVERS

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
    hostname = data["hostname"]
    gpu_ids = data["gpu_ids"]
    project = data["project"]
    command = data["command"]

    server = SERVERS.get(hostname)
    if not server:
        return jsonify({"error": "Unknown server"}), 404

    try:
        # Pull the latest project changes
        pull_command = f"cd {project} && git pull"
        pull_output = server.exec_command_sync(pull_command)
        print(f"Git pull output: {pull_output}")

        results = []
        for gpu_id in gpu_ids:
            arch_command = (
                f"nvidia-smi --query-gpu=compute_cap --format=csv,noheader -i {gpu_id}"
            )
            architecture = server.exec_command_sync(arch_command).strip()
            # Convert architecture from "8.6" format to "86" format
            architecture = architecture.replace(".", "")
            print(f"GPU {gpu_id} architecture: {architecture}")

            env_vars = f"GPU_IDS={gpu_id} CUDA_ARCHITECTURES={architecture}"
            full_command = f"cd {project} && {env_vars} {command}"
            print(f"Executing command for GPU {gpu_id}: {full_command}")

            output = server.exec_command_sync(full_command)
            results.append(
                {
                    "gpu_id": gpu_id,
                    "architecture": architecture,
                    "command": full_command,
                    "output": output,
                }
            )

        return jsonify(
            {"success": True, "pull_output": pull_output, "results": results}
        )
    except Exception as e:
        print(f"Error launching experiment: {str(e)}")
        return jsonify({"error": str(e)}), 500


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
    app.run(port=5001)
