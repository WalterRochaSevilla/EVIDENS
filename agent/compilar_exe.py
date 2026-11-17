"""Script automatizado para empaquetar el cliente portable EVIDENS en un ejecutable .exe."""

import subprocess
import sys
from pathlib import Path


def compilar() -> None:
    """Empaqueta main.py junto con el icono evidens.ico y manifiesto UAC de Administrador."""
    carpeta_agent = Path(__file__).resolve().parent
    ruta_main = carpeta_agent / "main.py"
    ruta_icono = carpeta_agent / "assets" / "evidens.ico"
    carpeta_assets = carpeta_agent / "assets"

    comando = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--noconsole",
        "--uac-admin",
        "--name",
        "EVIDENS_Cliente",
        "--icon",
        str(ruta_icono),
        "--add-data",
        f"{carpeta_assets};assets",
        str(ruta_main),
    ]

    print("Iniciando compilación de EVIDENS_Cliente.exe...")
    resultado = subprocess.run(comando, cwd=str(carpeta_agent), check=False)
    if resultado.returncode == 0:
        ruta_exe = carpeta_agent / "dist" / "EVIDENS_Cliente.exe"
        print(f"\n✔ Ejecutable generado con éxito en:\n  {ruta_exe}")
    else:
        print("\n✖ Error al compilar. Asegúrese de instalar PyInstaller: pip install pyinstaller")
        sys.exit(resultado.returncode)


if __name__ == "__main__":
    compilar()
