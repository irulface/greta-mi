#!/usr/bin/env python3
"""Interactive Ubuntu bootstrap. Standard library only; run on the VPS with sudo."""
import argparse
import base64
import fcntl
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import socket
import subprocess
import sys
import tarfile
import time
import urllib.parse
import urllib.request

ROOT = Path('/opt/greta-mi')
CONFIG = Path('/etc/greta-mi')
GITHUB_KEY = 'github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl\n'
WRITERS = ['web', 'agent', 'worker', 'api']


class DeploymentError(RuntimeError):
    pass


def run(args, *, capture=False, **kwargs):
    """Commands never contain passwords. Keep Docker config output out of logs."""
    return subprocess.run([str(a) for a in args], check=True, text=True,
                          stdout=subprocess.PIPE if capture else None, **kwargs)


def checked(value, pattern, label):
    if not re.fullmatch(pattern, value):
        raise DeploymentError('Nilai ' + label + ' tidak valid.')
    return value


def repo_name(value):
    return checked(value, r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]+', 'GitHub owner/repository')


def commit_sha(value):
    return checked(value, r'[a-f0-9]{40}', 'commit SHA 40 karakter')


def domain_name(value):
    value = value.lower().strip()
    return checked(value, r'(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}', 'domain')


def email_address(value):
    return checked(value.strip().lower(), r'[A-Za-z0-9.!#$%&*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}', 'email')


def ask(label, default=''):
    answer = input(label + (' [' + default + ']' if default else '') + ': ').strip()
    return answer or default


def password(label, minimum=14, generate=False):
    while True:
        value = getpass.getpass(label + (' (kosong = generate)' if generate else '') + ': ')
        if not value and generate:
            return secrets.token_urlsafe(32)
        if len(value) < minimum or any(c in value for c in '\r\n\x00'):
            print('Minimum ' + str(minimum) + ' karakter; harus satu baris.')
            continue
        if value != getpass.getpass('Ulangi password: '):
            print('Password tidak sama.'); continue
        return value


def write_private(path, text):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink():
        raise DeploymentError('Menolak menulis melalui symlink: ' + str(path))
    temp = path.with_name(path.name + '.tmp-' + secrets.token_hex(6))
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(text); f.flush(); os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists(): temp.unlink()


def raw_env(values):
    result = []
    for key, value in values.items():
        if not re.fullmatch(r'[A-Z][A-Z0-9_]*', key): raise DeploymentError('Invalid environment key')
        value = str(value)
        if any(c in value for c in '\r\n\x00'): raise DeploymentError('Environment values must be single-line')
        result.append(key + '=' + value)
    return '\n'.join(result) + '\n'


def render_environment(settings, destination=CONFIG):
    """Compose format:raw preserves $, quotes, # and backslashes verbatim."""
    app = {
        'APP_ENV': 'production', 'DATA_DIR': '/data', 'REPOSITORY_ROOT': '/data/repository',
        'DATABASE_URL': 'postgresql+psycopg://' + urllib.parse.quote(settings['db_user'], safe='') + ':' +
            urllib.parse.quote(settings['db_password'], safe='') + '@db:5432/' + settings['db_name'],
        'APP_MASTER_KEY': settings['master_key'], 'PUBLIC_APP_URL': 'https://' + settings['domain'],
        'MCP_ALLOWED_HOSTS': settings.get('mcp_hosts', ''),
        'MARKET_API_ALLOWED_HOSTS': settings.get('market_hosts', ''),
        'ENTERPRISE_ALLOWED_HOSTS': settings.get('enterprise_hosts', ''),
        **settings.get('smtp', {}),
    }
    files = {
        'app.env': app,
        'db.env': {'POSTGRES_USER': 'postgres', 'POSTGRES_DB': 'postgres',
                   'POSTGRES_PASSWORD': settings['postgres_password'],
                   'APP_DB_USER': settings['db_user'], 'APP_DB_NAME': settings['db_name'],
                   'APP_DB_PASSWORD': settings['db_password']},
        'bootstrap.env': {'BOOTSTRAP_ADMIN_EMAIL': settings['admin_email'],
                          'BOOTSTRAP_ADMIN_PASSWORD': settings['admin_password']},
        'edge.env': {'GRETA_DOMAIN': settings['domain'], 'ACME_EMAIL': settings['acme_email']},
    }
    for name, values in files.items(): write_private(destination / name, raw_env(values))


def configure(repo, domain):
    path = CONFIG / 'settings.json'
    if path.exists():
        settings = json.loads(path.read_text())
        if settings['repo'] != repo or settings['domain'] != domain:
            raise DeploymentError('Instalasi sudah memakai repo/domain berbeda; tidak akan ditimpa.')
        print('Memakai konfigurasi production yang tersimpan; password dan master key dipertahankan.')
        return settings
    settings = {'repo': repo, 'domain': domain}
    settings['admin_email'] = email_address(ask('Email/user admin aplikasi pertama', 'admin@greta.id'))
    settings['admin_password'] = password('Password admin aplikasi')
    settings['acme_email'] = email_address(ask('Email untuk sertifikat HTTPS', settings['admin_email']))
    settings['db_user'] = checked(ask('User database aplikasi', 'gretami'), r'[a-z][a-z0-9_]{0,30}', 'database user')
    if settings['db_user'] == 'postgres': raise DeploymentError('User aplikasi harus berbeda dari postgres.')
    settings['db_name'] = checked(ask('Nama database', 'gretamidb'), r'[a-z][a-z0-9_]{0,30}', 'database name')
    if settings['db_name'] in ('postgres', 'template0', 'template1'): raise DeploymentError('Pilih nama database aplikasi.')
    settings['db_password'] = password('Password database aplikasi', generate=True)
    settings['postgres_password'] = secrets.token_urlsafe(48)
    settings['master_key'] = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    settings['smtp'] = {}
    if ask('Konfigurasikan SMTP sekarang? y/n', 'y').lower() == 'y':
        host = domain_name(ask('SMTP host', 'asia.emailarray.com'))
        port = int(checked(ask('SMTP port', '465'), r'[0-9]{1,5}', 'SMTP port'))
        if not 1 <= port <= 65535: raise DeploymentError('Port tidak valid.')
        mode = ask('SMTP encryption: ssl atau starttls', 'ssl').lower()
        if mode not in ('ssl', 'starttls'): raise DeploymentError('Pilih ssl atau starttls.')
        settings['smtp'] = {'SMTP_HOST': host, 'SMTP_PORT': port,
            'SMTP_USERNAME': ask('SMTP username', 'admin@greta.id'),
            'SMTP_PASSWORD': password('SMTP password', minimum=1),
            'SMTP_FROM': email_address(ask('SMTP sender', 'admin@greta.id')),
            'SMTP_USE_SSL': str(mode == 'ssl').lower(), 'SMTP_USE_TLS': str(mode == 'starttls').lower(),
            'SMTP_TIMEOUT_SECONDS': 15}
    write_private(path, json.dumps(settings, indent=2) + '\n')
    return settings


def install_prerequisites():
    release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    if release.get('ID', '').strip('"') != 'ubuntu' or release.get('VERSION_ID', '').strip('"') not in ('22.04', '24.04', '26.04'):
        raise DeploymentError('Bootstrap mendukung Ubuntu 22.04, 24.04, atau 26.04 LTS.')
    run(['apt-get', 'update'])
    run(['apt-get', 'install', '-y', 'ca-certificates', 'curl', 'git', 'openssh-client', 'python3', 'tar'])
    if not shutil.which('docker'):
        # Do not remove another application's container runtime or conflicting packages.
        for package in ('docker.io', 'podman-docker', 'containerd', 'runc'):
            result = subprocess.run(['dpkg-query', '-W', '-f=${Status}', package], capture_output=True, text=True)
            if result.returncode == 0 and 'install ok installed' in result.stdout:
                raise DeploymentError('Package ' + package + ' sudah terpasang; migrasikan runtime secara eksplisit terlebih dahulu.')
        Path('/etc/apt/keyrings').mkdir(exist_ok=True, mode=0o755)
        run(['curl', '-fsSL', 'https://download.docker.com/linux/ubuntu/gpg', '-o', '/etc/apt/keyrings/docker.asc'])
        os.chmod('/etc/apt/keyrings/docker.asc', 0o644)
        arch = run(['dpkg', '--print-architecture'], capture=True).stdout.strip()
        codename = release['VERSION_CODENAME'].strip('"')
        Path('/etc/apt/sources.list.d/docker.sources').write_text(
            'Types: deb\nURIs: https://download.docker.com/linux/ubuntu\nSuites: ' + codename +
            '\nComponents: stable\nArchitectures: ' + arch + '\nSigned-By: /etc/apt/keyrings/docker.asc\n')
        run(['apt-get', 'update'])
        run(['apt-get', 'install', '-y', 'docker-ce', 'docker-ce-cli', 'containerd.io', 'docker-buildx-plugin', 'docker-compose-plugin'])
    version = run(['docker', 'compose', 'version', '--short'], capture=True).stdout.strip().lstrip('v')
    parts = re.match(r'(\d+)\.(\d+)\.(\d+)', version)
    if not parts or tuple(map(int, parts.groups())) < (2, 30, 0):
        raise DeploymentError('Docker Compose >=2.30 diperlukan untuk menjaga password secara literal.')
    run(['systemctl', 'enable', '--now', 'docker'])
    run(['docker', 'info'], capture=True)


def git_environment():
    env = os.environ.copy()
    env['GIT_TERMINAL_PROMPT'] = '0'
    env['GIT_SSH_COMMAND'] = 'ssh -i ' + shlex.quote(str(CONFIG / 'github_ed25519')) + \
        ' -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlgorithms=ssh-ed25519' + \
        ' -o UserKnownHostsFile=' + shlex.quote(str(CONFIG / 'github_known_hosts'))
    return env


def prepare_github(repo):
    public_remote = 'https://github.com/' + repo + '.git'
    public = subprocess.run(['git', 'ls-remote', public_remote, 'HEAD'],
        env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'}, capture_output=True, text=True)
    if public.returncode == 0: return public_remote
    key = CONFIG / 'github_ed25519'
    if not key.exists():
        run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'greta-mi read-only deploy key', '-f', key])
    os.chmod(key, 0o600)
    write_private(CONFIG / 'github_known_hosts', GITHUB_KEY)
    remote = 'git@github.com:' + repo + '.git'
    attempt = subprocess.run(['git', 'ls-remote', remote, 'HEAD'], env=git_environment(), capture_output=True, text=True)
    if attempt.returncode:
        print('\nTambahkan public deploy key berikut pada https://github.com/' + repo + '/settings/keys')
        print('Pilih Add deploy key dan JANGAN centang Allow write access.\n')
        print(key.with_suffix('.pub').read_text())
        input('Tekan Enter sesudah read-only deploy key ditambahkan: ')
        run(['git', 'ls-remote', remote, 'HEAD'], env=git_environment(), capture=True)
    return remote


def checkout(repo, sha):
    remote = prepare_github(repo)
    bare = ROOT / 'source.git'
    if not bare.exists():
        run(['git', 'init', '--bare', bare])
        run(['git', '--git-dir', bare, 'remote', 'add', 'origin', remote])
    existing = run(['git', '--git-dir', bare, 'remote', 'get-url', 'origin'], capture=True).stdout.strip()
    allowed_remotes = {'https://github.com/' + repo + '.git', 'git@github.com:' + repo + '.git'}
    if existing not in allowed_remotes: raise DeploymentError('Git origin VPS tidak cocok dengan repo yang diminta.')
    if existing != remote: run(['git', '--git-dir', bare, 'remote', 'set-url', 'origin', remote])
    run(['git', '--git-dir', bare, 'fetch', '--no-tags', 'origin', sha], env=git_environment())
    fetched = run(['git', '--git-dir', bare, 'rev-parse', 'FETCH_HEAD^{commit}'], capture=True).stdout.strip()
    if fetched != sha: raise DeploymentError('Commit sumber tidak cocok.')
    release = ROOT / 'releases' / sha
    if not release.exists():
        release.parent.mkdir(parents=True, exist_ok=True)
        run(['git', '-c', 'core.hooksPath=/dev/null', '--git-dir', bare, 'worktree', 'add', '--detach', release, sha])
    if run(['git', '-C', release, 'status', '--porcelain'], capture=True).stdout:
        raise DeploymentError('Release VPS mempunyai perubahan lokal. Tidak akan ditimpa.')
    if run(['git', '-C', release, 'rev-parse', 'HEAD'], capture=True).stdout.strip() != sha:
        raise DeploymentError('Release directory memiliki commit berbeda.')
    # These two bind-mounted files must be readable by non-root container users.
    os.chmod(release / 'deploy/init-db.sh', 0o755)
    os.chmod(release / 'deploy/Caddyfile', 0o644)
    return release


def compose(release, *args, capture=False, **kwargs):
    env = os.environ.copy()
    env.update(GRETA_RELEASE=release.name, GRETA_CONFIG_DIR=str(CONFIG))
    return run(['docker', 'compose', '--project-name', 'greta-mi',
                '-f', release / 'deploy/compose.production.yaml', *args], env=env, capture=capture, **kwargs)


def active_release():
    state_path = ROOT / 'deployment.json'
    if state_path.exists():
        state = json.loads(state_path.read_text())
        if state.get('stage') != 'healthy' and state.get('candidate'):
            return ROOT / 'releases' / commit_sha(state['candidate'])
    current = ROOT / 'current'
    return current.resolve() if current.is_symlink() else None


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''): digest.update(block)
    return digest.hexdigest()


def volume_archive(release, volume, output):
    with output.open('wb') as target:
        subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--read-only', '--user', '0:0',
            '-v', volume + ':/snapshot:ro', 'greta-mi-api:' + release.name,
            'tar', '-C', '/snapshot', '-czf', '-', '.'], stdout=target, check=True)


def backup(release, resume=True):
    destination = ROOT / 'backups' / (time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '-' + secrets.token_hex(3))
    destination.mkdir(parents=True, mode=0o700)
    try:
        compose(release, 'stop', *WRITERS)
        with (destination / 'database.dump').open('wb') as target:
            env = os.environ.copy(); env.update(GRETA_RELEASE=release.name, GRETA_CONFIG_DIR=str(CONFIG))
            subprocess.run(['docker', 'compose', '-p', 'greta-mi',
                '-f', str(release / 'deploy/compose.production.yaml'), 'exec', '-T', 'db', 'sh', '-c',
                'exec pg_dump -U postgres -Fc "$APP_DB_NAME"'], env=env, stdout=target, check=True)
        volume_archive(release, 'greta-mi_app_data', destination / 'app-data.tar.gz')
        with tarfile.open(destination / 'configuration.tar.gz', 'w:gz') as archive:
            archive.add(CONFIG, arcname='greta-mi')
        checksums = {p.name: file_sha256(p) for p in destination.iterdir()}
        write_private(destination / 'manifest.json', json.dumps({'commit': release.name, 'complete': True, 'sha256': checksums}, indent=2))
        print('Backup database, file aplikasi, dan konfigurasi: ' + str(destination))
    finally:
        if resume: compose(release, 'start', *WRITERS)
    return destination


def preflight_ports(first_install):
    if not first_install: return
    for port in (80, 443):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try: sock.bind(('0.0.0.0', port))
            except OSError as exc:
                raise DeploymentError('Port ' + str(port) + ' sudah dipakai. Bootstrap tidak akan menghentikan service lain.') from exc


def verify_https(domain):
    last = None
    for _ in range(24):
        try:
            with urllib.request.urlopen('https://' + domain + '/health/ready', timeout=8) as response:
                if json.load(response) != {'status': 'ok', 'database': 'postgresql'}:
                    raise DeploymentError('Health response tidak sesuai.')
            with urllib.request.urlopen('https://' + domain + '/api/v1/bootstrap', timeout=8) as response:
                if json.load(response).get('demo') is not False: raise DeploymentError('Mode demo masih aktif!')
            with urllib.request.urlopen('https://' + domain + '/', timeout=8) as response:
                if response.status != 200: raise DeploymentError('Frontend belum siap.')
            return
        except (OSError, ValueError, DeploymentError) as exc: last = exc
        time.sleep(5)
    raise DeploymentError('HTTPS belum tervalidasi. Periksa DNS A/AAAA, akses port 80/443, dan log edge; sertifikat tidak dilewati.') from last


def save_state(**state):
    write_private(ROOT / 'deployment.json', json.dumps({**state, 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}, indent=2))


def activate(release, settings, previous):
    """Build first; stop writers and back up before any schema change."""
    compose(release, 'config', '--quiet')
    compose(release, 'build', '--pull', 'migrate', 'web')
    compose(release, 'pull', 'db', 'edge')
    if previous:
        try: backup(previous, resume=False)
        except Exception:
            compose(previous, 'start', *WRITERS)
            raise
    save_state(stage='migrating', candidate=release.name, previous=previous.name if previous else None)
    # Once migration starts we never automatically run old code against a changed schema.
    compose(release, 'up', '-d', '--wait', '--wait-timeout', '180', 'db')
    compose(release, 'run', '--rm', '--no-deps', 'migrate')
    save_state(stage='starting', candidate=release.name, previous=previous.name if previous else None)
    # Migration has already completed explicitly above; do not run it a second time.
    compose(release, 'up', '-d', '--no-deps', '--wait', '--wait-timeout', '180', 'api')
    compose(release, 'up', '-d', '--no-deps', '--wait', '--wait-timeout', '180', 'web', 'worker', 'agent', 'edge')
    verify_https(settings['domain'])
    current = ROOT / 'current'
    temp = ROOT / ('current-' + secrets.token_hex(4))
    temp.symlink_to(release); os.replace(temp, current)
    save_state(stage='healthy', current=release.name, previous=previous.name if previous else None)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo')
    parser.add_argument('--commit', type=commit_sha)
    parser.add_argument('--domain', default='mi.greta.id', type=domain_name)
    parser.add_argument('--action', choices=['deploy', 'backup', 'status', 'stop', 'start'], default='deploy')
    args = parser.parse_args(argv)
    if os.geteuid() != 0: raise DeploymentError('Jalankan melalui sudo python3 deploy/bootstrap.py ...')
    if args.action == 'deploy' and (not args.repo or not args.commit):
        parser.error('--repo owner/name dan --commit SHA wajib diisi untuk deploy.')
    os.umask(0o077)
    ROOT.mkdir(mode=0o700, parents=True, exist_ok=True); CONFIG.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (ROOT / 'deployment.lock').open('w') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise DeploymentError('Deployment/backup lain masih berjalan.')
        previous = active_release()
        if args.action != 'deploy':
            state = json.loads((ROOT / 'deployment.json').read_text()) if (ROOT / 'deployment.json').exists() else {}
            if args.action == 'status': print(json.dumps(state, indent=2))
            if not previous: raise DeploymentError('Belum ada deployment yang selesai; periksa deployment.json.')
            if args.action == 'start' and state.get('stage') != 'healthy':
                raise DeploymentError('Deployment sebelumnya belum berhasil. Jalankan deployment ulang agar migrasi diverifikasi sebelum start.')
            if args.action == 'backup': backup(previous)
            elif args.action == 'status': compose(previous, 'ps')
            elif args.action == 'stop': compose(previous, 'stop')
            elif args.action == 'start':
                compose(previous, 'start'); verify_https(json.loads((CONFIG / 'settings.json').read_text())['domain'])
            return
        repo = repo_name(args.repo)
        print('Deploy ' + repo + ' @ ' + args.commit + ' ke https://' + args.domain)
        preflight_ports(previous is None)
        install_prerequisites()
        volume = subprocess.run(['docker', 'volume', 'inspect', 'greta-mi_postgres_data'], capture_output=True)
        if not (CONFIG / 'settings.json').exists() and volume.returncode == 0:
            raise DeploymentError('Volume database sudah ada tetapi konfigurasi hilang; restore /etc/greta-mi dari backup dahulu.')
        settings = configure(repo, args.domain)
        render_environment(settings)
        release = checkout(repo, args.commit)
        install_copy = ROOT / 'bootstrap.py'
        write_private(install_copy, Path(__file__).read_text())
        wrapper = '#!/bin/sh\nexec python3 /opt/greta-mi/bootstrap.py "$@"\n'
        write_private(Path('/usr/local/bin/greta-mi'), wrapper); os.chmod('/usr/local/bin/greta-mi', 0o755)
        activate(release, settings, previous)
        print('\nDeployment terverifikasi: https://' + args.domain)
        print('Login admin: ' + settings['admin_email'])
        print('Operasional: sudo greta-mi --action status|backup|stop|start')


if __name__ == '__main__':
    try: main()
    except (DeploymentError, subprocess.CalledProcessError, OSError, ValueError, EOFError, KeyboardInterrupt) as exc:
        # Never interpolate a subprocess stderr or settings dict: either can contain secrets.
        print('\nDeployment dihentikan: ' + (str(exc) if isinstance(exc, DeploymentError) else type(exc).__name__) +
              '. Tidak ada volume/data yang dihapus. Periksa status dan log sebelum melanjutkan.', file=sys.stderr)
        sys.exit(1)
