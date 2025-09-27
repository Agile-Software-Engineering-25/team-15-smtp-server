import os, ipaddress, smtplib, logging
from email import policy
from email.parser import BytesParser
from email.utils import formatdate, make_msgid
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP as SMTPServer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("py-smtp-relay")

GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
FROM_NAME = os.environ.get("FROM_NAME", "SAU Portal")
LISTEN_HOST = os.environ.get("LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "2525"))  # non-root port
SMTP_OUT_HOST = os.environ.get("SMTP_OUT_HOST", "smtp.gmail.com")
SMTP_OUT_PORT = int(os.environ.get("SMTP_OUT_PORT", "587"))
OVERRIDE_HEADER_FROM = os.environ.get("OVERRIDE_HEADER_FROM", "true").lower() == "true"
MAX_SIZE = int(os.environ.get("MAX_SIZE", "20971520"))  # 20 MB
ALLOW_NETS = [ipaddress.ip_network(n.strip(), strict=False)
              for n in os.environ.get("ALLOW_NETS",
                                       "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.0/8,::1/128"
                                      ).split(",") if n.strip()]

def allowed_peer(ip: str) -> bool:
    try:
        pip = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(pip in net for net in ALLOW_NETS)

class GmailRelayHandler:
    async def handle_DATA(self, server, session, envelope):
        peer_ip = session.peer[0] if session.peer else "0.0.0.0"
        if not allowed_peer(peer_ip):
            log.warning("Rejecting %s (not in allow list %s)", peer_ip, ALLOW_NETS)
            return "554 5.7.1 Relay access denied"

        if envelope.content and len(envelope.content) > MAX_SIZE:
            return "552 5.3.4 Message size exceeds fixed maximum size"

        # Parse incoming message
        msg = BytesParser(policy=policy.SMTP).parsebytes(envelope.content or b"")

        # Ensure basic headers
        if "Date" not in msg:
            msg["Date"] = formatdate(localtime=True)
        if "Message-Id" not in msg and "Message-ID" not in msg:
            msg["Message-Id"] = make_msgid(domain="gmail.com")

        # Normalize human-friendly From (header) to Gmail (helps DMARC)
        if OVERRIDE_HEADER_FROM:
            from_value = f"{FROM_NAME} <{GMAIL_USER}>"
            if "From" in msg:
                msg.replace_header("From", from_value)
            else:
                msg["From"] = from_value

        # Envelope addresses
        envelope_from = GMAIL_USER                     # align Return-Path to gmail
        rcpts = envelope.rcpt_tos

        try:
            with smtplib.SMTP(SMTP_OUT_HOST, SMTP_OUT_PORT, timeout=30) as s:
                s.starttls()
                s.login(GMAIL_USER, GMAIL_APP_PASSWORD)
                s.sendmail(envelope_from, rcpts, msg.as_bytes())
            log.info("Relayed OK peer=%s to=%s msgid=%s", peer_ip, rcpts, msg.get("Message-Id"))
            return "250 2.0.0 OK"
        except smtplib.SMTPException as e:
            log.error("Upstream SMTP error: %s", e)
            return "451 4.3.0 Upstream SMTP error"
        except Exception as e:
            log.exception("Internal error: %s", e)
            return "451 4.3.0 Internal error"

if __name__ == "__main__":
    handler = GmailRelayHandler()
    # Advertise reasonable limits; SMTPUTF8 enabled
    controller = Controller(
        handler,
        hostname=LISTEN_HOST,
        port=LISTEN_PORT,
        ready_timeout=5.0
    )
    # Provide custom SMTP factory to set data_size_limit & UTF8
    controller.factory = lambda: SMTPServer(handler,
                                            data_size_limit=MAX_SIZE,
                                            decode_data=False,
                                            enable_SMTPUTF8=True)
    controller.start()
    log.info("SMTP relay listening on %s:%s (ALLOW_NETS=%s)", LISTEN_HOST, LISTEN_PORT, ALLOW_NETS)
    # Keep alive
    import signal, time
    signal.pause()
