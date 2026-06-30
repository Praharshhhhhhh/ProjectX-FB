import os
import sys
import subprocess
from pathlib import Path

def build():
    # Ensure PyInstaller is installed
    try:
        import PyInstaller.__main__
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        import PyInstaller.__main__

    project_root = Path(__file__).resolve().parent.parent
    client_dir = project_root / "client"
    
    main_script = str(client_dir / "main.py")
    assets_dir = str(client_dir / "assets")
    bin_dir = str(client_dir / ".bin")
    
    # Path format for --add-data and --add-binary: "source;dest" on Windows
    assets_arg = f"{assets_dir};assets"
    
    wg_exe = os.path.join(bin_dir, "wg.exe")
    wireguard_exe = os.path.join(bin_dir, "wireguard.exe")
    
    bin_args = []
    if os.path.exists(wg_exe) and os.path.exists(wireguard_exe):
        bin_args.extend([
            "--add-binary", f"{wg_exe};.bin",
            "--add-binary", f"{wireguard_exe};.bin"
        ])
    else:
        print("WARNING: wg.exe or wireguard.exe not found in client/.bin! Bundling without them.")
        print("Ensure they exist before releasing to production.")

    icon_path = str(client_dir / "assets" / "logo-square.ico")
    icon_arg = []
    if os.path.exists(icon_path):
        icon_arg = [f"--icon={icon_path}"]

    args = [
        main_script,
        "--name=SetuLink",
        "--onefile",
        "--windowed",       # hide console
        "--clean",
        "--noconfirm",      # overwrite output
        f"--add-data={assets_arg}",
    ]
    
    args.extend(bin_args)
    args.extend(icon_arg)

    # Change CWD to project root so dist and build folders are created there
    os.chdir(project_root)

    print(f"Running PyInstaller with args: {args}")
    PyInstaller.__main__.run(args)

    print("\nBuild complete! Executable is in the 'dist' directory.")

if __name__ == "__main__":
    build()
