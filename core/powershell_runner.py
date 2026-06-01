import subprocess


def run_powershell_script(script_path, args=None):
    command = [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        script_path
    ]

    if args:
        command.extend(args)

    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    return result.stdout, result.stderr