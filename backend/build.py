"""Vercel build hook: run migrations against Neon."""
import os
import subprocess
import sys


def main():
    print("Running Django migrations...")
    env = os.environ.copy()
    env.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    result = subprocess.run(
        [sys.executable, "manage.py", "migrate", "--noinput"],
        env=env,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    print("Migrations complete.")


if __name__ == "__main__":
    main()
