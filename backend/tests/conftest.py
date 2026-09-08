"""Never use the configured application database or SMTP credentials in tests."""
import os
import tempfile
from pathlib import Path
import smtplib
import pytest

os.environ['GRETA_ENV_FILE'] = os.devnull
os.environ['APP_ENV'] = 'development'
os.environ['DATA_DIR'] = tempfile.mkdtemp(prefix='greta-test-')
os.environ['DATABASE_URL'] = os.environ.get(
    'GRETA_TEST_DATABASE_URL',
    'sqlite:///' + str(Path(os.environ['DATA_DIR']) / 'test.db'),
)
for key in ('SMTP_HOST', 'SMTP_USERNAME', 'SMTP_PASSWORD', 'SMTP_FROM'):
    os.environ[key] = ''
os.environ['PUBLIC_APP_URL'] = 'https://greta-test.example'


@pytest.fixture(autouse=True)
def prevent_real_email(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError('Tests must mock SMTP; real email connections are disabled.')
    monkeypatch.setattr(smtplib, 'SMTP', blocked)
    monkeypatch.setattr(smtplib, 'SMTP_SSL', blocked)
