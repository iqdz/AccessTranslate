"""Entry point for Access-Translate. This is what build.ps1 points
PyInstaller at to produce the single portable exe."""
from access_translate.main import main

if __name__ == "__main__":
    main()
