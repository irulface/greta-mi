#!/usr/bin/env python3
"""Disposable Docker production smoke test. Never uses the real greta-mi volumes."""
import base64
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import tempfile
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('bootstrap',ROOT/'deploy/bootstrap.py')
bootstrap=importlib.util.module_from_spec(spec);spec.loader.exec_module(bootstrap)


def main():
    prefix='greta-ci-'+secrets.token_hex(6)
    assert prefix.startswith('greta-ci-') and prefix!='greta-mi'
    cli=['docker-compose'] if shutil.which('docker-compose') else ['docker','compose']
    with tempfile.TemporaryDirectory(prefix='greta-ci-config-') as tmp:
        directory=Path(tmp)
        settings={'repo':'irulface/greta-mi','domain':'mi.greta.id','admin_email':'admin@example.com',
            'admin_password':secrets.token_urlsafe(18)+'$special#quote\'"\\end',
            'db_user':'gretami','db_name':'gretamidb','db_password':secrets.token_urlsafe(18)+'@$#\'"\\end',
            'postgres_password':secrets.token_urlsafe(32),'master_key':base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
            'acme_email':'admin@example.com','smtp':{}}
        bootstrap.render_environment(settings,directory)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        override=directory/'smoke.yaml'
        override.write_text(json.dumps({'services':{'edge':{'profiles':['tls']},'web':{'ports':['127.0.0.1:'+str(port)+':80']}}}))
        env={**os.environ,'GRETA_CONFIG_DIR':tmp,'GRETA_RELEASE':prefix,'GRETA_VOLUME_PREFIX':prefix}
        cmd=[*cli,'-p',prefix,'-f',str(ROOT/'deploy/compose.production.yaml'),'-f',str(override)]
        def dc(*args,**kwargs):return subprocess.run([*cmd,*args],env=env,check=True,**kwargs)
        try:
            dc('config','--quiet')
            # Provision/validate the real edge config without starting HTTPS or ordering certificates.
            adapted=dc('run','--rm','--no-deps','edge','caddy','adapt',
                '--config','/etc/caddy/Caddyfile','--adapter','caddyfile','--validate',
                stdout=subprocess.PIPE,text=True)
            policies=json.loads(adapted.stdout)['apps']['tls']['automation']['policies']
            assert len(policies)==1
            assert policies[0]['issuers']==[{'module':'acme',
                'ca':'https://acme-v02.api.letsencrypt.org/directory','email':settings['acme_email']}]
            print("Production TLS configuration validated: Let's Encrypt is the sole issuer.",flush=True)
            dc('build','migrate','web')
            dc('up','-d','--wait','--wait-timeout','180','db')
            dc('run','--rm','--no-deps','migrate')
            dc('up','-d','--no-deps','--wait','--wait-timeout','180','api')
            dc('up','-d','--no-deps','--wait','--wait-timeout','180','web','worker','agent')
            origin='http://127.0.0.1:'+str(port)
            def request(path,body=None,headers=None):
                return urllib.request.urlopen(urllib.request.Request(origin+path,
                    data=json.dumps(body).encode() if body is not None else None,
                    headers={'Content-Type':'application/json',**(headers or {})}),timeout=15)
            with request('/health/ready') as response:
                assert json.load(response)=={'status':'ok','database':'postgresql'}
                assert response.headers.get('X-Greta-Release')==prefix
            with request('/api/v1/bootstrap') as response:assert json.load(response)['demo'] is False
            with request('/') as response:assert b'<html' in response.read().lower()
            with request('/api/v1/auth/login',{'email':settings['admin_email'],'password':settings['admin_password']}, {'Origin':origin}) as response:
                assert json.load(response)['role']=='Admin'
                cookie=response.headers['set-cookie'].lower();assert 'secure' in cookie and 'httponly' in cookie
            for path,body,headers,expected in [('/api/v1/auth/demo',{'role':'Buyer'},{},404),
                ('/api/v1/auth/login',{'email':settings['admin_email'],'password':settings['admin_password']},{'Origin':'https://evil.example'},403)]:
                try:request(path,body,headers)
                except urllib.error.HTTPError as exc:assert exc.code==expected
                else:raise AssertionError('Expected rejection')
            code="from sqlalchemy import text; from app.db import Session; s=Session(); assert not s.execute(text('select rolsuper from pg_roles where rolname=current_user')).scalar(); print('Database role is not superuser')"
            dc('exec','-T','api','python','-c',code)
            # Verify the exact password reached the container, without logging it.
            probe=dc('exec','-T','api','python','-c',"import json,os; print(json.dumps(os.environ['BOOTSTRAP_ADMIN_PASSWORD']))",capture_output=True,text=True)
            assert json.loads(probe.stdout)==settings['admin_password']
            # Init is repeat-safe and credentials/admin identity survive container recreation.
            dc('run','--rm','--no-deps','migrate')
            dc('restart','api')
            dc('up','-d','--no-deps','--wait','--wait-timeout','180','api')
            with request('/api/v1/auth/login',{'email':settings['admin_email'],'password':settings['admin_password']}) as response:
                assert json.load(response)['role']=='Admin'
            print('Production container smoke: PostgreSQL + vector, migrations, frontend, login, secure cookies, CSRF, non-superuser role, literal passwords and restart passed.')
        finally:
            # This project is always unique and disposable; production names cannot reach this path.
            assert env['GRETA_VOLUME_PREFIX'].startswith('greta-ci-')
            subprocess.run([*cmd,'--profile','*','down','--volumes','--remove-orphans'],env=env,check=True)

if __name__=='__main__':main()
