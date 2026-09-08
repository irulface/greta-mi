"""SMTP delivery for explicit buyer-approved RFI invitations.

Messages are queued with encrypted bodies; credentials stay in environment.
An ambiguous SMTP outcome is never retried automatically.
"""
import hashlib
import ipaddress
import json
import os
import re
import secrets
import smtplib
import ssl
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from urllib.parse import urlparse

import certifi
from fastapi import HTTPException
from sqlalchemy import select

from .db import EmailOutbox, Record, Session, now, uid
from .security import audit, cipher, visible


def env_bool(key, default=False):
    value = os.getenv(key, str(default)).lower()
    if value not in ('true', 'false', '1', '0'):
        raise ValueError(f'{key} must be true or false.')
    return value in ('true', '1')


def email_address(value):
    return isinstance(value, str) and len(value) <= 254 and bool(
        re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}", value)
    )


@dataclass(frozen=True)
class SMTPSettings:
    host: str
    port: int
    username: str
    password: str
    sender: str
    use_tls: bool
    use_ssl: bool
    timeout: int

    @classmethod
    def load(cls):
        try:
            settings = cls(
                os.getenv('SMTP_HOST', '').strip(), int(os.getenv('SMTP_PORT', '465')),
                os.getenv('SMTP_USERNAME', ''), os.getenv('SMTP_PASSWORD', ''),
                os.getenv('SMTP_FROM', '').strip(), env_bool('SMTP_USE_TLS'),
                env_bool('SMTP_USE_SSL', True), int(os.getenv('SMTP_TIMEOUT_SECONDS', '15')),
            )
        except ValueError as exc:
            raise HTTPException(503, 'Format konfigurasi SMTP tidak valid.') from exc
        if not all((settings.host, settings.username, settings.password)) or not email_address(settings.sender):
            raise HTTPException(503, 'Lengkapi SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, dan SMTP_FROM di server.')
        if settings.use_tls == settings.use_ssl:
            raise HTTPException(503, 'Aktifkan salah satu SMTP_USE_SSL atau SMTP_USE_TLS untuk koneksi terenkripsi.')
        if not 1 <= settings.port <= 65535 or not 1 <= settings.timeout <= 120:
            raise HTTPException(503, 'Port atau timeout SMTP tidak valid.')
        return settings


def public_app_url():
    value = os.getenv('PUBLIC_APP_URL', '').rstrip('/')
    parsed = urlparse(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
        raise HTTPException(503, 'Atur PUBLIC_APP_URL ke alamat HTTPS aplikasi yang dapat diakses supplier.')
    if parsed.hostname == 'localhost' or parsed.hostname.endswith(('.localhost', '.local', '.test')):
        raise HTTPException(503, 'PUBLIC_APP_URL tidak boleh menggunakan alamat localhost.')
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise HTTPException(503, 'PUBLIC_APP_URL harus dapat dijangkau supplier.')
    return value


@contextmanager
def smtp_connection(settings):
    context = ssl.create_default_context(cafile=certifi.where())
    if settings.use_ssl:
        client = smtplib.SMTP_SSL(settings.host, settings.port, timeout=settings.timeout, context=context)
    else:
        client = smtplib.SMTP(settings.host, settings.port, timeout=settings.timeout)
    try:
        client.ehlo()
        if settings.use_tls:
            client.starttls(context=context)
            client.ehlo()
        client.login(settings.username, settings.password)
        yield client
    finally:
        # A QUIT failure after DATA was accepted must not change SENT to UNKNOWN.
        try:
            client.quit()
        except (smtplib.SMTPException, OSError):
            try:
                client.close()
            except (smtplib.SMTPException, OSError):
                pass


def connection_test():
    settings = SMTPSettings.load()
    start = time.monotonic()
    try:
        with smtp_connection(settings) as client:
            code, _ = client.noop()
            if code != 250:
                raise smtplib.SMTPResponseException(code, b'SMTP NOOP failed')
    except (smtplib.SMTPException, OSError) as exc:
        raise HTTPException(502, f'Tes SMTP gagal ({type(exc).__name__}); detail kredensial tidak ditampilkan.') from exc
    return {'status': 'Connected', 'authenticated': True, 'transport': 'SSL' if settings.use_ssl else 'STARTTLS',
            'latency_ms': round((time.monotonic() - start) * 1000), 'email_sent': False}


def configuration_status():
    try:
        settings = SMTPSettings.load()
        configured, transport = True, 'SSL' if settings.use_ssl else 'STARTTLS'
    except HTTPException:
        configured, transport = False, None
    try:
        app_url = public_app_url()
    except HTTPException:
        app_url = None
    return {'configured': configured, 'host': os.getenv('SMTP_HOST', ''), 'port': os.getenv('SMTP_PORT', ''),
            'sender': os.getenv('SMTP_FROM', ''), 'transport': transport, 'public_app_url': app_url,
            'invitations_ready': configured and bool(app_url)}


def summary(row):
    return {key: getattr(row, key) for key in ('id', 'supplier_id', 'recipient', 'status', 'attempts', 'error_code', 'created_at', 'updated_at')}


def queue_invitations(db, user, rfi):
    settings, app_url = SMTPSettings.load(), public_app_url()
    if rfi.data['status'] not in ('Issued', 'Open', 'Response Received'):
        raise HTTPException(409, 'RFI harus diterbitkan sebelum undangan email dikirim.')
    expiry = int(datetime.fromisoformat(rfi.data['closing_date'] + 'T23:59:59+07:00').timestamp())
    if expiry <= time.time():
        raise HTTPException(409, 'RFI sudah melewati tanggal penutupan.')
    suppliers = []
    for sid in rfi.data.get('supplier_ids', []):
        supplier = db.get(Record, sid)
        if not supplier or supplier.kind != 'supplier' or not visible(user, supplier):
            raise HTTPException(404, 'Supplier tidak dapat diakses.')
        recipient = supplier.data.get('email', '')
        if not email_address(recipient) or recipient.lower().split('@')[-1] in ('example.com', 'example.org', 'example.net'):
            raise HTTPException(422, 'Lengkapi email supplier yang valid: ' + supplier.data['name'])
        if supplier.data.get('is_demo') or rfi.data.get('is_demo'):
            raise HTTPException(422, 'Email undangan hanya dapat dikirim untuk RFI dan supplier nyata, bukan data contoh.')
        suppliers.append(supplier)
    if not suppliers:
        raise HTTPException(422, 'Pilih setidaknya satu supplier.')
    result = []
    for supplier in suppliers:
        active = list(db.scalars(select(Record).where(
            Record.kind == 'invitation', Record.data['rfi_id'].as_string() == rfi.id,
            Record.data['supplier_id'].as_string() == supplier.id,
        )))
        already = None
        for invitation in active:
            if not invitation.data.get('revoked'):
                previous = db.scalar(select(EmailOutbox).where(EmailOutbox.invitation_id == invitation.id))
                if previous:
                    already = previous
                    break
        if already:
            # Repeated clicks never duplicate messages or retry ambiguous deliveries.
            result.append(summary(already))
            continue
        for invitation in active:
            invitation.data = {**invitation.data, 'revoked': True}
        token = secrets.token_urlsafe(40)
        invitation = Record(kind='invitation', owner=user.id, region=rfi.region, data={
            'rfi_id': rfi.id, 'supplier_id': supplier.id, 'token_hash': hashlib.sha256(token.encode()).hexdigest(),
            'expires': expiry, 'used': False, 'channel': 'email',
        })
        db.add(invitation)
        db.flush()
        payload = {
            'sender': settings.sender, 'subject': re.sub(r'[\r\n]+', ' ', f"Undangan RFI {rfi.data['number']} — {rfi.data['title']}"),
            'body': f"Yth. {supplier.data['name']},\n\nAnda diundang untuk memberikan informasi untuk RFI berikut:\n\n"
                    f"Referensi: {rfi.data['number']}\nJudul: {rfi.data['title']}\n"
                    f"Batas respons: {rfi.data['closing_date']} pukul 23:59 WIB\n\n"
                    f"Isi dan kirim respons melalui tautan aman berikut:\n{app_url}/?invitation={token}\n\n"
                    "Tautan ini khusus untuk perusahaan Anda. Simpan draft sebelum mengirim respons final. "
                    "Respons final akan dikunci setelah disubmit.\n\nSalam,\nTim Procurement\nGreta Market Intelligence",
        }
        row = EmailOutbox(rfi_id=rfi.id, supplier_id=supplier.id, invitation_id=invitation.id,
                          recipient=supplier.data['email'], payload=cipher().encrypt(json.dumps(payload).encode()).decode(),
                          message_id=make_msgid(domain=settings.sender.split('@')[1]))
        db.add(row)
        db.flush()
        audit(db, user, 'email.queued', row.id, {'rfi_id': rfi.id, 'supplier_id': supplier.id})
        result.append(summary(row))
    db.commit()
    return result


def process_pending_email():
    with Session() as db:
        row = db.scalar(select(EmailOutbox).where(EmailOutbox.status == 'PENDING')
                        .order_by(EmailOutbox.created_at).with_for_update(skip_locked=True).limit(1))
        if not row:
            return False
        row.status, row.attempts, row.updated_at = 'SENDING', row.attempts + 1, now()
        row_id = row.id
        db.commit()
    with Session() as db:
        row = db.get(EmailOutbox, row_id)
        rfi = db.scalar(select(Record).where(Record.id == row.rfi_id).with_for_update())
        invitation = db.get(Record, row.invitation_id)
        if not rfi or not invitation or invitation.data.get('revoked') or invitation.data.get('used') or invitation.data['expires'] <= time.time() or rfi.data['status'] not in ('Issued', 'Open', 'Response Received'):
            row.status, row.payload = 'CANCELLED', None
        else:
            attempted_data = False
            try:
                settings = SMTPSettings.load()
                payload = json.loads(cipher().decrypt(row.payload.encode()))
                message = EmailMessage()
                message['Subject'], message['From'], message['To'] = payload['subject'], payload['sender'], row.recipient
                message['Message-ID'], message['Date'] = row.message_id, format_datetime(datetime.now().astimezone())
                message.set_content(payload['body'])
                with smtp_connection(settings) as client:
                    attempted_data = True
                    refused = client.send_message(message, from_addr=payload['sender'], to_addrs=[row.recipient])
                    if refused:
                        raise smtplib.SMTPRecipientsRefused(refused)
                row.status, row.payload = 'SENT', None
            except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused, smtplib.SMTPDataError) as exc:
                row.status, row.error_code = 'FAILED', type(exc).__name__
            except Exception as exc:
                row.status = 'UNKNOWN' if attempted_data else 'FAILED'
                row.error_code = type(exc).__name__
        row.updated_at = now()
        audit(db, 'email-worker', 'email.' + row.status.lower(), row.id,
              {'rfi_id': row.rfi_id, 'error_code': row.error_code})
        db.commit()
    return True
