import os
import base64
import mimetypes
import traceback
from typing import Optional

# pip install -r requirements.txt
# uvicorn main:app --reload

# third-party imports
from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from pydantic import BaseModel, model_validator

# stdlib for email fallback (if you keep SMTP)
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

# HTTP client for Resend
import requests

app = FastAPI(title="CoRWA email backend")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# other imports you need...
# load .env in backend folder
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

# Load email config from environment
FROM_EMAIL = os.getenv("FROM_EMAIL")
TO_EMAIL = os.getenv("TO_EMAIL")
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT") or 0)
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
# --- END OF SECTION ---


RESEND_API_KEY = os.getenv("RESEND_API_KEY")

def send_via_resend(subject, body, to_emails=None, attachment=None, attachment_filename=None):
    """Send email via Resend API (HTTPS)."""
    if not RESEND_API_KEY:
        return False, "RESEND_API_KEY not configured"

    to_list = to_emails or ([TO_EMAIL] if TO_EMAIL else [FROM_EMAIL])
    payload = {
        "from": f"{os.getenv('FROM_NAME', '')} <{FROM_EMAIL}>",
        "to": to_list,
        "subject": subject,
        "text": body,
    }

    # Attachment (optional)
    if attachment and attachment_filename:
        mime_type, _ = mimetypes.guess_type(attachment_filename)
        if not mime_type:
            mime_type = "application/octet-stream"
        b64data = base64.b64encode(attachment).decode("ascii")
        payload["attachments"] = [{
            "filename": attachment_filename,
            "type": mime_type,
            "data": b64data
        }]

    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        r = requests.post("https://api.resend.com/emails", headers=headers, json=payload, timeout=15)
        if 200 <= r.status_code < 300:
            print("✅ Email sent via Resend")
            return True, "OK"
        else:
            print("❌ Resend API error:", r.status_code, r.text)
            return False, f"Resend API error {r.status_code}: {r.text}"
    except Exception as e:
        print("❌ Resend exception:", e)
        return False, str(e)


def send_email_background(subject, body, to_emails=None, attachment=None, attachment_filename=None):
    """Always use Resend; SMTP fallback optional."""
    ok, info = send_via_resend(subject, body, to_emails, attachment, attachment_filename)
    if not ok:
        print("Email send failed via Resend:", info)
    return ok

# ========== EMAIL SENDER HELPER ==========

# def _send_smtp_email_message(msg: EmailMessage) -> (bool, str):
#     if not (SMTP_HOST and SMTP_PORT and SMTP_USER and SMTP_PASS and FROM_EMAIL):
#         err = "SMTP not configured. Set SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS/FROM_EMAIL in backend/.env"
#         print("SMTP ERROR:", err)
#         return False, err

#     try:
#         context = ssl.create_default_context()
#         if SMTP_PORT == 465:
#             print("Using SMTP_SSL to", SMTP_HOST, SMTP_PORT)
#             with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=30) as server:
#                 server.login(SMTP_USER, SMTP_PASS)
#                 server.send_message(msg)
#         else:
#             print("Using SMTP with STARTTLS to", SMTP_HOST, SMTP_PORT)
#             with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
#                 server.ehlo()
#                 try:
#                     server.starttls(context=context)
#                     server.ehlo()
#                 except Exception as e:
#                     # STARTTLS may fail for some hosts; log and continue to login attempt
#                     print("Warning: starttls failed:", e)
#                 server.login(SMTP_USER, SMTP_PASS)
#                 server.send_message(msg)

#         print("Email sent OK")
#         return True, "OK"
#     except smtplib.SMTPAuthenticationError as e:
#         tb = traceback.format_exc()
#         print("SMTPAuthenticationError:", e, tb)
#         return False, f"SMTP auth error: {e}"
#     except smtplib.SMTPServerDisconnected as e:
#         tb = traceback.format_exc()
#         print("SMTPServerDisconnected:", e, tb)
#         return False, f"SMTP server disconnected: {e}"
#     except Exception as e:
#         tb = traceback.format_exc()
#         print("SMTP send exception:", e, tb)
#         return False, f"SMTP error: {e}"

# # # # Helper to build message
# def build_message(subject: str, body: str, to_emails: Optional[list]=None, attachment: Optional[bytes]=None, attachment_filename: Optional[str]=None):
#     to_list = to_emails or ([TO_EMAIL] if TO_EMAIL else [FROM_EMAIL])
#     msg = EmailMessage()
#     msg["Subject"] = subject
#     msg["From"] = formataddr((os.getenv("FROM_NAME") or "", FROM_EMAIL))
#     msg["To"] = ", ".join(to_list)
#     msg.set_content(body)
#     if attachment and attachment_filename:
#         # attach binary data as application/octet-stream
#         msg.add_attachment(attachment, maintype="application", subtype="octet-stream", filename=attachment_filename)
#     return msg

# # # Background wrapper
# def send_email_background(subject: str, body: str, to_emails: Optional[list]=None, attachment: Optional[bytes]=None, attachment_filename: Optional[str]=None):
#     msg = build_message(subject, body, to_emails, attachment, attachment_filename)
#     ok, info = _send_smtp_email_message(msg)
#     if not ok:
#         print("Background email failed:", info)
#     else:
#         print("Background email succeeded.")

# ========== API MODELS ==========

class ContactPayload(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    message: str

class DonatePayload(BaseModel):
    name: str
    phone: Optional[str] = None
    amount: Optional[float] = None
    txn_id: str
    note: Optional[str] = None

# Replace RsvpPayload with:
class RsvpPayload(BaseModel):
    event_id: Optional[int] = None
    event_name: Optional[str] = None
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None

    @model_validator(mode="after")
    def check_event(self):
        # require either event_id (non-null) or event_name (non-empty)
        if (self.event_id is None or (isinstance(self.event_id, int) and self.event_id == 0)) and not self.event_name:
            raise ValueError("Either event_id or event_name must be provided.")
        return self


# ========== ROUTES ==========

@app.get("/")
def root():
    return {"ok": True, "msg": "CoRWA backend running"}

@app.post("/contact")
async def contact(payload: ContactPayload, background: BackgroundTasks, request: Request):
    # build email body
    body = f"New contact message\n\nName: {payload.name}\nEmail: {payload.email}\nPhone: {payload.phone}\n\nMessage:\n{payload.message}"
    subject = f"Contact message from {payload.name}"
    # background send
    background.add_task(send_email_background, subject, body, None, None, None)
    return {"ok": True, "msg": "Contact received"}

@app.post("/donate")
async def donate(payload: DonatePayload, background: BackgroundTasks):
    body = f"New donation\n\nName: {payload.name}\nPhone: {payload.phone}\nAmount: {payload.amount}\nTxn ID: {payload.txn_id}\n\nNote:\n{payload.note}"
    subject = f"Donation: {payload.name} - {payload.txn_id}"
    background.add_task(send_email_background, subject, body, None, None, None)
    return {"ok": True, "msg": "Donation received"}

@app.post("/donate-with-file")
async def donate_with_file(
    background: BackgroundTasks,
    name: str = Form(...),
    txn_id: str = Form(...),
    phone: Optional[str] = Form(None),
    amount: Optional[str] = Form(None),
    note: Optional[str] = Form(None),
    receipt_file: Optional[UploadFile] = File(None),
):
    body = f"New donation (with file)\n\nName: {name}\nPhone: {phone}\nAmount: {amount}\nTxn ID: {txn_id}\n\nNote:\n{note}"
    subject = f"Donation (file): {name} - {txn_id}"
    attachment_bytes = None
    attachment_filename = None
    if receipt_file:
        attachment_bytes = await receipt_file.read()
        attachment_filename = receipt_file.filename
    background.add_task(send_email_background, subject, body, None, attachment_bytes, attachment_filename)
    return {"ok": True, "msg": "Donation with file received"}

# Replace /rsvp endpoint with this
@app.post("/rsvp")
async def rsvp(payload: RsvpPayload, background: BackgroundTasks):
    # prefer name (friendly) when available
    event_label = payload.event_name or (f"ID {payload.event_id}" if payload.event_id is not None else "Unknown event")

    body = (
        f"Event RSVP\n\nEvent: {event_label}\n"
        f"Name: {payload.name}\nEmail: {payload.email}\nPhone: {payload.phone}"
    )
    subject = f"Event RSVP: {payload.name} — {event_label}"
    # send background email
    background.add_task(send_email_background, subject, body, None, None, None)
    return {"ok": True, "msg": "RSVP received"}
