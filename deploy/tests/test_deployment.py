import base64
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]

def module(name, path):
    spec=importlib.util.spec_from_file_location(name,path);loaded=importlib.util.module_from_spec(spec);spec.loader.exec_module(loaded);return loaded

boot=module('greta_bootstrap',ROOT/'deploy/bootstrap.py')
release=module('greta_release',ROOT/'scripts/release.py')

def settings():
    return {'repo':'irulface/greta-mi','domain':'mi.greta.id','admin_email':'admin@example.com',
        'admin_password':'test $dollar \'quote\' "double" #hash \\slash !',
        'acme_email':'admin@example.com','db_user':'gretami','db_name':'gretamidb',
        'db_password':'database $ \' " # \\ @:/?%','postgres_password':'ephemeral-test-root-password',
        'master_key':base64.urlsafe_b64encode(b't'*32).decode(),
        'smtp':{'SMTP_HOST':'smtp.example.com','SMTP_PASSWORD':'smtp $ \' " # \\ special'}}

class ValidationTests(unittest.TestCase):
    def test_untrusted_shell_arguments_rejected(self):
        for value in ['-oProxyCommand=bad','host;id','name/path','name@host','$(id)','a\nb']:
            with self.assertRaises(release.ReleaseError):release.validate_target(value,'root',22)
        for user in ['root;id','-o','a b','$(id)']:
            with self.assertRaises(release.ReleaseError):release.validate_target('mi.greta.id',user,22)
        for port in [0,65536]:
            with self.assertRaises(release.ReleaseError):release.validate_target('mi.greta.id','root',port)
        for repo in ['https://token@github.com/a/b','a/b;id','../repo','a/../../b']:
            with self.assertRaises(release.ReleaseError):release.repo_name(repo)
        release.validate_target('192.0.2.10','ubuntu',2222)
        self.assertEqual(boot.repo_name('irulface/greta-mi'),'irulface/greta-mi')

    def test_commit_domain_and_database_inputs(self):
        self.assertEqual(boot.commit_sha('a'*40),'a'*40)
        for sha in ['HEAD','main','a'*39,'a'*40+';id']:
            with self.assertRaises(boot.DeploymentError):boot.commit_sha(sha)
        for domain in ['mi.greta.id/path','localhost','x\nfoo','-bad.example.com','https://mi.greta.id']:
            with self.assertRaises(boot.DeploymentError):boot.domain_name(domain)

    def test_environment_injection_blocked_without_printing_secret(self):
        for value in ['one\nAPP_ENV=development','one\rnext','nul\0value']:
            with self.assertRaises(boot.DeploymentError):boot.raw_env({'SMTP_PASSWORD':value})
        self.assertIn('SMTP_PASSWORD=$unchanged # \' " \\',boot.raw_env({'SMTP_PASSWORD':'$unchanged # \' " \\'}))

    def test_private_files_are_atomic_and_mode_0600(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'app.env';boot.write_private(p,'first');boot.write_private(p,'second')
            self.assertEqual(p.read_text(),'second');self.assertEqual(stat.S_IMODE(p.stat().st_mode),0o600)
            target=Path(tmp)/'link';target.symlink_to(p)
            with self.assertRaises(boot.DeploymentError):boot.write_private(target,'no')
            self.assertEqual(p.read_text(),'second')

    def test_existing_credentials_preserved(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(boot,'CONFIG',Path(tmp)):
            original=settings();boot.write_private(Path(tmp)/'settings.json',json.dumps(original))
            with patch('builtins.input',side_effect=AssertionError('Unexpected credential prompt')):
                self.assertEqual(boot.configure(original['repo'],original['domain']),original)
            with self.assertRaises(boot.DeploymentError):boot.configure('wrong/repo',original['domain'])

    def test_generated_credentials_and_first_admin(self):
        answers=['admin@example.com','admin@example.com','gretami','gretamidb','n']
        with tempfile.TemporaryDirectory() as tmp, patch.object(boot,'CONFIG',Path(tmp)), \
             patch.object(boot,'ask',side_effect=answers),patch.object(boot,'password',side_effect=['admin-test-password','database-test-password']):
            s=boot.configure('irulface/greta-mi','mi.greta.id')
            self.assertEqual(s['admin_email'],'admin@example.com');self.assertEqual(len(base64.urlsafe_b64decode(s['master_key'])),32)
            self.assertNotEqual(s['postgres_password'],s['db_password']);self.assertEqual(s['smtp'],{})

    def test_github_host_key_matches_published_fingerprint(self):
        encoded=boot.GITHUB_KEY.split()[2]
        fingerprint='SHA256:'+base64.b64encode(hashlib.sha256(base64.b64decode(encoded)).digest()).decode().rstrip('=')
        self.assertEqual(fingerprint,'SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU')
        env=boot.git_environment()
        self.assertIn('StrictHostKeyChecking=yes',env['GIT_SSH_COMMAND']);self.assertNotIn('StrictHostKeyChecking=no',env['GIT_SSH_COMMAND'])

    def test_secret_guard_blocks_private_files_and_values(self):
        for name in ['backend/.env','backend/data/file.txt','x/id_ed25519','deploy/local/settings.json','backup.dump','.env.production','a/private.key']:
            with self.assertRaises(release.ReleaseError):release.check_blob(name,b'content',[])
        private_key=b'-----BEGIN '+b'PRIVATE KEY-----'
        token=b'ghp_'+b'x'*36
        for content in [private_key,token,b'known-local-sensitive-value']:
            with self.assertRaises(release.ReleaseError):release.check_blob('app.py',content,[b'known-local-sensitive-value'])
        release.check_blob('backend/.env.example',b'APP_ENV=production\n',[])

    def test_history_guard_detects_removed_secret(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(release,'ROOT',Path(tmp)):
            def git(*args):subprocess.run(['git',*args],cwd=tmp,check=True,capture_output=True)
            git('init');git('config','user.name','Deployment test');git('config','user.email','test@example.com')
            p=Path(tmp)/'accident.txt';p.write_text('ghp_'+'x'*36);git('add','.');git('commit','-m','accidental secret')
            p.unlink();(Path(tmp)/'safe.py').write_text('print("safe")');git('add','--all');git('commit','-m','remove')
            with self.assertRaises(release.ReleaseError):release.check_source()

class LifecycleTests(unittest.TestCase):
    def setup_activation(self,tmp,fail=None):
        root=Path(tmp).resolve();old=root/'releases'/('a'*40);new=root/'releases'/('b'*40)
        old.mkdir(parents=True);new.mkdir();(root/'current').symlink_to(old)
        events=[]
        def compose(where,*args,**kwargs):
            events.append(('compose',where.name,args))
            if fail and args[0]==fail:raise subprocess.CalledProcessError(1,['docker'])
        return root,old,new,events,compose

    def test_backup_before_migration_and_exact_commit_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,old,new,events,compose=self.setup_activation(tmp)
            with patch.object(boot,'ROOT',root),patch.object(boot,'compose',side_effect=compose), \
                 patch.object(boot,'backup',side_effect=lambda *a,**k:events.append(('backup',))), \
                 patch.object(boot,'verify_https',side_effect=lambda *a:events.append(('https',))):
                boot.activate(new,settings(),old)
            migration=next(i for i,e in enumerate(events) if e[0]=='compose' and e[2][:2]==('run','--rm'))
            self.assertLess(events.index(('backup',)),migration)
            self.assertEqual((root/'current').resolve(),new)
            self.assertEqual(json.loads((root/'deployment.json').read_text())['stage'],'healthy')
            api=next(e for e in events if e[0]=='compose' and e[2][-1]=='api')
            self.assertIn('--no-deps',api[2])

    def test_failed_migration_never_promotes_or_restarts_old_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,old,new,events,compose=self.setup_activation(tmp,fail='run')
            with patch.object(boot,'ROOT',root),patch.object(boot,'compose',side_effect=compose),patch.object(boot,'backup'),patch.object(boot,'verify_https') as verify:
                with self.assertRaises(subprocess.CalledProcessError):boot.activate(new,settings(),old)
            self.assertEqual((root/'current').resolve(),old);verify.assert_not_called()
            self.assertFalse(any(e[0]=='compose' and e[2][0]=='start' for e in events))
            self.assertEqual(json.loads((root/'deployment.json').read_text())['stage'],'migrating')

    def test_failed_backup_resumes_previous_without_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,old,new,events,compose=self.setup_activation(tmp)
            with patch.object(boot,'ROOT',root),patch.object(boot,'compose',side_effect=compose),patch.object(boot,'backup',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):boot.activate(new,settings(),old)
            self.assertIn(('compose',old.name,('start',*boot.WRITERS)),events)
            self.assertFalse(any(e[0]=='compose' and e[2][0]=='run' for e in events))

    def test_failed_https_does_not_mark_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,old,new,events,compose=self.setup_activation(tmp)
            with patch.object(boot,'ROOT',root),patch.object(boot,'compose',side_effect=compose),patch.object(boot,'backup'), \
                 patch.object(boot,'verify_https',side_effect=boot.DeploymentError('TLS')):
                with self.assertRaises(boot.DeploymentError):boot.activate(new,settings(),old)
                self.assertEqual(boot.active_release(),new)
            self.assertEqual((root/'current').resolve(),old)
            self.assertEqual(json.loads((root/'deployment.json').read_text())['stage'],'starting')

    def test_https_verification_requires_the_expected_release_and_production_mode(self):
        sha='b'*40
        for wrong_sha,demo in [(False,False),(True,False),(False,True)]:
            def response(url,timeout):
                body={'status':'ok','database':'postgresql'} if '/health/' in url else {'demo':demo} if '/bootstrap' in url else {}
                item=io.BytesIO(json.dumps(body).encode());item.headers={'X-Greta-Release':'a'*40 if wrong_sha else sha};item.status=200
                return item
            with patch.object(boot.urllib.request,'urlopen',side_effect=response),patch.object(boot.time,'sleep'):
                if wrong_sha or demo:
                    with self.assertRaises(boot.DeploymentError):boot.verify_https('mi.greta.id',sha)
                else:boot.verify_https('mi.greta.id',sha)

    def test_dry_run_performs_no_publish_or_ssh(self):
        with patch.object(release,'check_source'),patch.object(release,'publish') as publish,patch.object(release,'deploy') as deploy:
            release.main(['deploy','--dry-run'])
            publish.assert_not_called();deploy.assert_not_called()

class ComposeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('docker-compose') or shutil.which('docker'),'Compose CLI not installed')
    def test_real_compose_parser_preserves_credentials_and_isolates_ports(self):
        with tempfile.TemporaryDirectory() as tmp:
            config=Path(tmp);s=settings();boot.render_environment(s,config)
            cli=['docker-compose'] if shutil.which('docker-compose') else ['docker','compose']
            env={**os.environ,'GRETA_RELEASE':'b'*40,'GRETA_CONFIG_DIR':tmp,'GRETA_VOLUME_PREFIX':'greta-ci-test'}
            result=subprocess.run([*cli,'-f',str(ROOT/'deploy/compose.production.yaml'),'config','--format','json'],env=env,capture_output=True,text=True,check=True)
            services=json.loads(result.stdout)['services'];app=services['api']['environment']
            self.assertEqual(app['BOOTSTRAP_ADMIN_PASSWORD'].replace('$$','$'),s['admin_password'])
            self.assertEqual(app['SMTP_PASSWORD'].replace('$$','$'),s['smtp']['SMTP_PASSWORD'])
            from urllib.parse import urlparse,unquote
            self.assertEqual(unquote(urlparse(app['DATABASE_URL']).password),s['db_password'])
            self.assertEqual(app['APP_ENV'],'production');self.assertEqual(app['PUBLIC_APP_URL'],'https://mi.greta.id')
            for name in ['api','db','web','worker','agent','migrate']:self.assertFalse(services[name].get('ports'))
            self.assertEqual(Path(services['migrate']['build']['context']).resolve(),ROOT/'backend')
            self.assertEqual(Path(services['web']['build']['context']).resolve(),ROOT)
            self.assertEqual(services['db']['environment']['POSTGRES_USER'],'postgres')
            self.assertNotIn('POSTGRES_PASSWORD',app)
            self.assertEqual(services['api']['depends_on']['migrate']['condition'],'service_completed_successfully')
            self.assertEqual(services['agent']['depends_on']['api']['condition'],'service_healthy')
            self.assertEqual(stat.S_IMODE((config/'app.env').stat().st_mode),0o600)

if __name__=='__main__':unittest.main()
