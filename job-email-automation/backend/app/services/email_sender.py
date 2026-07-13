import mimetypes
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import formataddr, parseaddr

import aiosmtplib

from app.config import resolve_resume_path
from app.models import GeneratedEmail, SenderProfile, SmtpConfig


def _clean_display_name(name: str | None) -> str:
    if not name:
        return ""
    # parseaddr handles "Name <email>" format; take display name only
    display, _ = parseaddr(name)
    display = display or name
    # Strip anything that looks like an email address
    display = display.split("<")[0].strip()
    if "@" in display:
        return display.split()[0]
    return display


def _build_message(
    email: GeneratedEmail,
    sender: SenderProfile,
    resume_filename: str | None,
) -> EmailMessage:
    msg = EmailMessage(policy=SMTP)

    msg["From"] = formataddr((sender.name, str(sender.email)))
    msg["Subject"] = email.subject

    # Single To header only — Gmail rejects duplicate To headers
    to_name = _clean_display_name(email.to_name)
    if to_name:
        msg["To"] = formataddr((to_name, email.to_email))
    else:
        msg["To"] = email.to_email

    msg.set_content(email.body)

    resume_path = resolve_resume_path(resume_filename)
    if resume_path:
        attach_name = resume_path.name
        mime_type, _ = mimetypes.guess_type(str(resume_path))
        maintype, _, subtype = (mime_type or "application/octet-stream").partition("/")
        with open(resume_path, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype=maintype,
                subtype=subtype or "octet-stream",
                filename=attach_name,
            )

    return msg


async def send_email_with_resume(
    email: GeneratedEmail,
    sender: SenderProfile,
    smtp: SmtpConfig,
    resume_filename: str | None = None,
) -> None:
    if not email.to_email:
        raise ValueError("Recipient email is missing. Cannot send.")

    msg = _build_message(email, sender, resume_filename)

    await aiosmtplib.send(
        msg,
        hostname=smtp.host,
        port=smtp.port,
        username=smtp.user,
        password=smtp.password,
        start_tls=smtp.use_tls,
    )
