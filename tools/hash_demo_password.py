"""Print a salted application password hash; never accept a plaintext CLI argument."""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from saathi.demo_security import password_hash


if __name__ == '__main__':
    password = getpass.getpass('Unique demo password (at least 16 characters): ')
    if password != getpass.getpass('Repeat password: '):
        raise SystemExit('Passwords did not match.')
    try:
        print(password_hash(password))
    except ValueError as error:
        raise SystemExit(str(error)) from None
