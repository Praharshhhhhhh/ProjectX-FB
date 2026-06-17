import subprocess
import ctypes
exe = r'C:\Program Files\WireGuard\wireguard.exe'
args = "'/uninstalltunnelservice', 'wg-client'"
ps_cmd = f"Start-Process -FilePath '{exe}' -ArgumentList {args} -Verb RunAs -WindowStyle Hidden -Wait"
try:
    subprocess.run(['powershell', '-Command', ps_cmd], check=True)
    print('Success')
except Exception as e:
    print('Failed:', e)
