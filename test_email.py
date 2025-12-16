# backend/test_email.py
from email.message import EmailMessage
from main import build_message, _send_smtp_email_message, FROM_EMAIL, TO_EMAIL

msg = build_message("Backend test email", "This is a test body from backend/test_email.py", to_emails=[TO_EMAIL or FROM_EMAIL])
ok, info = _send_smtp_email_message(msg)
print("OK:", ok, "INFO:", info)
