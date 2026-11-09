"""Container entry point: prepare Railway's root-owned mount, drop privileges, exec."""
import os
import stat
import sys
from pathlib import Path

UID = GID = 10001


def own_volume(directory):
    # Only the mount and known SQLite files; never recursively chown user data.
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fchown(descriptor, UID, GID)
        os.fchmod(descriptor, 0o700)
        for name in ['saathi.db', 'saathi.db-wal', 'saathi.db-shm', 'saathi.db-journal']:
            try:
                file_descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
            except FileNotFoundError:
                continue
            try:
                metadata = os.fstat(file_descriptor)
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                    raise RuntimeError('Refusing unsafe SQLite storage entry.')
                os.fchown(file_descriptor, UID, GID)
                os.fchmod(file_descriptor, 0o600)
            finally:
                os.close(file_descriptor)
    finally:
        os.close(descriptor)


def prepare_storage():
    mount = os.getenv('RAILWAY_VOLUME_MOUNT_PATH')
    if mount is not None and (mount != '/data' or os.getenv('SAATHI_DB_PATH') != '/data/saathi.db'):
        raise RuntimeError('Railway requires its volume at /data and SAATHI_DB_PATH=/data/saathi.db.')
    if hasattr(os, 'geteuid') and os.geteuid() == 0:
        if os.getenv('RAILWAY_RUN_UID') != '0' or mount != '/data':
            raise RuntimeError('Root startup is allowed only to initialize the configured Railway volume.')
        own_volume(Path('/data'))
        os.setgroups([])
        os.setgid(GID)
        os.setuid(UID)
        if os.geteuid() != UID:
            raise RuntimeError('Could not drop container privileges.')
    os.umask(0o077)
    if mount and not os.access(mount, os.W_OK | os.X_OK):
        raise RuntimeError('The /data volume is not writable by the application user.')


def command():
    try:
        port = int(os.getenv('PORT', '8000'))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise RuntimeError('PORT must be an integer from 1 to 65535.') from None
    return [sys.executable, '-m', 'uvicorn', 'app:app', '--host', '0.0.0.0', '--port', str(port),
            '--workers', '1', '--proxy-headers', '--forwarded-allow-ips', os.getenv('FORWARDED_ALLOW_IPS', '127.0.0.1'),
            '--no-access-log']


if __name__ == '__main__':
    arguments = command()
    prepare_storage()
    if os.name == 'nt':
        # Windows exec spawns a replacement PID; keep local startup/test cleanup
        # in this process instead. Linux containers still use a direct exec.
        from uvicorn.main import main
        main(args=arguments[3:])
    else:
        os.execv(sys.executable, arguments)
