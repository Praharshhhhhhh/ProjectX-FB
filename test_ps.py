import subprocess

exe = r'C:\Program Files\WireGuard\wireguard.exe'
args_str = r"'/uninstalltunnelservice', 'wg-client'"
ps_cmd = f"$p = Start-Process -FilePath '{exe}' -ArgumentList {args_str} -Verb RunAs -WindowStyle Hidden -Wait -PassThru; exit $p.ExitCode"

try:
    res = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
    print("STDOUT:", res.stdout.decode('utf-8'))
    print("STDERR:", res.stderr.decode('utf-8'))
    print("EXIT CODE:", res.returncode)
except Exception as e:
    print(f"FAILED: {e}")
