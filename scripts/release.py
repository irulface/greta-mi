#!/usr/bin/env python3
"""Publish reviewed source to GitHub, then bootstrap the exact commit on Ubuntu."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO = 'irulface/greta-mi'


class ReleaseError(RuntimeError):
    pass


def run(args, capture=False, **kwargs):
    return subprocess.run([str(a) for a in args], cwd=ROOT, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None, **kwargs)


def git(*args):
    return run(['git', *args], capture=True).stdout.strip()


def repo_name(value):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]+', value):
        raise ReleaseError('Gunakan GitHub owner/repository, tanpa URL, token, atau opsi shell.')
    return value


def forbidden_path(name):
    p = PurePosixPath(name); parts = p.parts
    return (any(part in ('node_modules', '.venv', '__pycache__', '.pytest_cache', '.git') for part in parts)
        or name.startswith(('backend/data/', 'deploy/local/', 'dist/', '.vinext/', 'outputs/', 'work/'))
        or (p.name.startswith('.env') and p.name != '.env.example')
        or p.name in ('.master-key', '.DS_Store', 'settings.json', 'app.env', 'bootstrap.env', 'db.env', 'edge.env')
        or p.suffix in ('.dump', '.db', '.sqlite', '.sqlite3', '.pem', '.key', '.pyc')
        or p.name.startswith(('id_rsa', 'id_ed25519')))


def known_local_secrets():
    # Compare without printing values. Never evaluate dotenv values as shell code.
    result = []
    for path in (ROOT / '.env', ROOT / 'backend/.env'):
        if not path.exists(): continue
        for line in path.read_text().splitlines():
            match = re.match(r'(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=\s*(.*)$', line.strip())
            if not match or not re.search(r'(PASSWORD|SECRET|TOKEN|KEY)', match[1]): continue
            value = match[2].strip()
            if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'": value = value[1:-1]
            if len(value) >= 8: result.append(value.encode())
    return result


def check_blob(name, content, local_secrets):
    if forbidden_path(name): raise ReleaseError('File privat/generated tidak boleh diunggah: ' + name)
    if len(content) > 25 * 1024 * 1024: raise ReleaseError('File terlalu besar untuk source release: ' + name)
    patterns = [rb'-----BEGIN (?:OPENSSH|RSA|EC|DSA|ENCRYPTED)? ?PRIVATE KEY-----',
                rb'gh[pousr]_[A-Za-z0-9]{30,}', rb'github_pat_[A-Za-z0-9_]{30,}']
    if any(re.search(pattern, content) for pattern in patterns) or any(secret in content for secret in local_secrets):
        raise ReleaseError('Kemungkinan secret terdeteksi pada ' + name + '. Nilainya tidak ditampilkan.')


def check_source(staged=False, history=True):
    secrets = known_local_secrets()
    if staged:
        entries = run(['git', 'ls-files', '--stage', '-z'], capture=True).stdout.split('\0')
        for entry in filter(None, entries):
            metadata, name = entry.split('\t', 1); mode, oid, stage = metadata.split()
            if mode in ('120000', '160000') or stage != '0': raise ReleaseError('Symlink/submodule/conflict tidak diperbolehkan pada release: ' + name)
            content = subprocess.check_output(['git', 'cat-file', 'blob', oid], cwd=ROOT)
            check_blob(name, content, secrets)
    else:
        names = run(['git', 'ls-files', '-co', '--exclude-standard', '-z'], capture=True).stdout.split('\0')
        for name in sorted(set(filter(None, names))):
            path = ROOT / name
            if not path.exists(): continue
            if path.is_symlink(): raise ReleaseError('Symlink tidak diperbolehkan pada source release: ' + name)
            check_blob(name, path.read_bytes(), secrets)
    exists = subprocess.run(['git', 'rev-parse', '--verify', 'HEAD'], cwd=ROOT, capture_output=True).returncode == 0
    if history and exists:
        # A deleted secret in an ancestor would still be uploaded by git push.
        entries = git('rev-list', '--objects', 'HEAD').splitlines()
        for line in entries:
            oid, _, name = line.partition(' ')
            if not name or git('cat-file', '-t', oid) != 'blob': continue
            check_blob(name, subprocess.check_output(['git', 'cat-file', 'blob', oid], cwd=ROOT), secrets)
    print('Pemeriksaan source, index, dan history: tidak ada file privat atau secret yang terdeteksi.')


def github_json(*args):
    return json.loads(run(['gh', *args], capture=True).stdout)


def publish(repo, message):
    repo = repo_name(repo)
    if not shutil.which('gh'): raise ReleaseError('Pasang GitHub CLI terlebih dahulu: https://cli.github.com/')
    try: profile = github_json('api', 'user')
    except subprocess.CalledProcessError: raise ReleaseError('Autentikasi diperlukan: gh auth login --hostname github.com --git-protocol https --web')
    branch = git('branch', '--show-current')
    if not branch: raise ReleaseError('Checkout branch sebelum publish; detached HEAD tidak didukung.')
    if git('rev-parse', '--show-toplevel') != str(ROOT): raise ReleaseError('Git root tidak cocok dengan project Greta MI.')
    check_source()
    run(['git', 'add', '--all'])
    check_source(staged=True)
    for key, value in [('user.name', profile.get('name') or profile['login']),
                       ('user.email', str(profile['id']) + '+' + profile['login'] + '@users.noreply.github.com')]:
        if subprocess.run(['git', 'config', '--get', key], cwd=ROOT, capture_output=True).returncode:
            run(['git', 'config', '--local', key, value])
    if subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=ROOT).returncode:
        run(['git', 'commit', '-m', message])
    sha = git('rev-parse', 'HEAD')
    if git('status', '--porcelain'): raise ReleaseError('Working tree berubah setelah commit; publish dihentikan.')
    view = subprocess.run(['gh', 'repo', 'view', repo, '--json', 'nameWithOwner,isPrivate,viewerPermission'],
                          cwd=ROOT, capture_output=True, text=True)
    if view.returncode:
        # Creation fails safely if the name is already occupied or permission is absent.
        run(['gh', 'repo', 'create', repo, '--private', '--description', 'Greta market intelligence and RFI repository'])
        info = github_json('repo', 'view', repo, '--json', 'nameWithOwner,isPrivate,viewerPermission')
    else: info = json.loads(view.stdout)
    print('Repo tujuan: ' + info['nameWithOwner'] + ' (' + ('private' if info['isPrivate'] else 'PUBLIC') + ').')
    if info['viewerPermission'] not in ('ADMIN', 'MAINTAIN', 'WRITE'): raise ReleaseError('Akun GitHub tidak mempunyai write access pada repo tujuan.')
    remote = 'https://github.com/' + repo + '.git'
    if 'origin' in git('remote').splitlines():
        existing = git('remote', 'get-url', 'origin')
        if existing not in (remote, remote[:-4], 'git@github.com:' + repo + '.git'):
            raise ReleaseError('Origin mengarah ke repo berbeda; tidak akan diganti otomatis.')
        run(['git', 'remote', 'set-url', 'origin', remote])
    else: run(['git', 'remote', 'add', 'origin', remote])
    run(['git', '-c', 'credential.helper=', '-c', 'credential.https://github.com.helper=!gh auth git-credential',
         'push', '--set-upstream', 'origin', branch])
    published = github_json('api', 'repos/' + repo + '/commits/' + sha)
    if published['sha'] != sha: raise ReleaseError('GitHub commit verification failed.')
    print('Source tersimpan: https://github.com/' + repo + '/commit/' + sha)
    return sha


def validate_target(host, user, port):
    # Hostnames and IPv4; shell options, whitespace and URL credentials are rejected.
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*', host): raise ReleaseError('SSH host/IP tidak valid.')
    if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', user): raise ReleaseError('SSH username tidak valid.')
    if not 1 <= port <= 65535: raise ReleaseError('SSH port tidak valid.')


def deploy(repo, sha, args):
    host = args.host or input('Hostname/IP VPS [mi.greta.id]: ').strip() or 'mi.greta.id'
    user = args.user or input('SSH username VPS [root]: ').strip() or 'root'
    port = args.port or int(input('SSH port [22]: ').strip() or '22')
    validate_target(host, user, port)
    target = user + '@' + host
    print('SSH meminta password VPS melalui terminal. Password tidak disimpan oleh script.')
    with tempfile.TemporaryDirectory(prefix='greta-ssh-') as temp:
        bootstrap_file = Path(temp) / 'bootstrap.py'
        bootstrap_file.write_bytes(subprocess.check_output(['git', 'show', sha + ':deploy/bootstrap.py'], cwd=ROOT))
        bootstrap_file.chmod(0o600)
        options = ['-o', 'ControlMaster=auto', '-o', 'ControlPersist=60', '-o', 'ControlPath=' + temp + '/socket',
                   '-o', 'StrictHostKeyChecking=ask', '-o', 'ConnectTimeout=15']
        if args.identity:
            key = Path(args.identity).expanduser().resolve()
            if not key.is_file(): raise ReleaseError('SSH identity file tidak ditemukan.')
            options += ['-i', str(key), '-o', 'IdentitiesOnly=yes']
        else:
            options += ['-o', 'PubkeyAuthentication=no', '-o', 'PreferredAuthentications=keyboard-interactive,password']
        ssh = ['ssh', '-p', str(port), *options]
        remote_dir = None
        try:
            remote_dir = run([*ssh, target, 'umask 077; mktemp -d /tmp/greta-mi.XXXXXXXX'], capture=True).stdout.strip()
            if not re.fullmatch(r'/tmp/greta-mi\.[A-Za-z0-9]{8}', remote_dir): raise ReleaseError('Temporary deployment path tidak valid.')
            run(['scp', '-q', '-P', str(port), *options, bootstrap_file, target + ':' + remote_dir + '/bootstrap.py'])
            command = ['python3', remote_dir + '/bootstrap.py', '--repo', repo, '--commit', sha, '--domain', 'mi.greta.id']
            if user != 'root': command.insert(0, 'sudo')
            run([*ssh, '-tt', target, shlex.join(command)])
        finally:
            if remote_dir and re.fullmatch(r'/tmp/greta-mi\.[A-Za-z0-9]{8}', remote_dir):
                subprocess.run([*ssh, '-o', 'BatchMode=yes', target,
                    'rm -f -- ' + shlex.quote(remote_dir + '/bootstrap.py') + ' && rmdir -- ' + shlex.quote(remote_dir)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run([*ssh, '-O', 'exit', target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'publish', 'deploy'])
    parser.add_argument('--repo', default=DEFAULT_REPO, type=repo_name)
    parser.add_argument('--message', default='Prepare Greta MI production deployment')
    parser.add_argument('--host')
    parser.add_argument('--user')
    parser.add_argument('--port', type=int)
    parser.add_argument('--identity', help='Optional SSH private key path; otherwise SSH requests password.')
    parser.add_argument('--dry-run', action='store_true', help='Read-only preview: no commit, push, SSH connection or package installation.')
    args = parser.parse_args(argv)
    if args.action == 'check' or args.dry_run:
        check_source()
        print('Repo: ' + args.repo + '; target: ' + (args.host or 'mi.greta.id') + '; action: ' + args.action)
        return
    if not sys.stdin.isatty(): raise ReleaseError('Jalankan dari terminal interaktif untuk autentikasi dan password.')
    sha = publish(args.repo, args.message)
    if args.action == 'deploy': deploy(args.repo, sha, args)


if __name__ == '__main__':
    try: main()
    except (ReleaseError, subprocess.CalledProcessError, OSError, ValueError, EOFError, KeyboardInterrupt) as exc:
        print('Release dihentikan: ' + (str(exc) if isinstance(exc, ReleaseError) else type(exc).__name__), file=sys.stderr)
        sys.exit(1)
