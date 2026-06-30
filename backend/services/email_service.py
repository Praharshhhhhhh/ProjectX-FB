import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

from config import get_settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str) -> None:
    """Send an email via SMTP. Uses config for connection details."""
    settings = get_settings()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg.attach(MIMEText(body, "plain"))

    try:
        context = ssl.create_default_context()
        if settings.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=context) as server:
                if settings.SMTP_USER:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM, to, msg.as_string())
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.ehlo()
                try:
                    server.starttls(context=context)
                except smtplib.SMTPNotSupportedError:
                    pass  # Server doesn't support STARTTLS (e.g. local dev)
                if settings.SMTP_USER:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM, to, msg.as_string())
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        raise


def send_otp_email(to: str, code: str) -> None:
    send_email(
        to,
        "Your SetuLink login code",
        f"Your one-time code is {code}. It expires in 5 minutes.",
    )


def send_activation_key_email(to: str, router_id: str, serial_number: str, key_code: str) -> None:
    print(f"[DEBUG] Generated Activation Key for {to}: {key_code}")
    send_email(
        to,
        "Your SetuLink router activation key",
        f"""Router ID: {router_id}
Serial Number: {serial_number}
Activation Key: {key_code}

Enter these in the SetuLink app under Devices > Add Device to claim your router.
""",
    )

def send_master_activation_email(to: str, activation_key: str, company_name: str) -> None:
    send_email(
        to,
        f"Activate your Master Account for {company_name}",
        f"""Hello,

Your SetuLink Master Account for {company_name} has been provisioned.
Please use the following activation key to activate your account:

Activation Key: {activation_key}

Open the SetuLink desktop app and click "Activate Master Account" to proceed.
""",
    )

def send_new_user_email(to: str, temp_password: str) -> None:
    send_email(
        to,
        "Welcome to SetuLink - Your Account Details",
        f"""Hello,

An account has been created for you on the SetuLink platform.

Your temporary password is: {temp_password}

Please log in and change your password immediately.
"""
    )
