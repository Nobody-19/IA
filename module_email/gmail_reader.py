"""
module_email/gmail_reader.py
Connexion Gmail — compatible local (token.json) et Streamlit Cloud (st.secrets).
"""

import os
import json
import base64
import logging
import tempfile
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

BASE_DIR   = Path(__file__).parent.parent
ENV_FILE   = BASE_DIR / ".env"
CREDS_FILE = Path(__file__).parent / "credentials.json"
TOKEN_FILE = Path(__file__).parent / "token.json"
SCOPES     = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

load_dotenv(dotenv_path=ENV_FILE)
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def _est_sur_cloud() -> bool:
    """Detecte si on tourne sur Streamlit Cloud."""
    try:
        import streamlit as st
        return hasattr(st, "secrets") and "gmail_token" in st.secrets
    except Exception:
        return False


def _creds_depuis_secrets() -> Credentials:
    """Charge les credentials Gmail depuis st.secrets (Streamlit Cloud)."""
    import streamlit as st
    token_data = dict(st.secrets["gmail_token"])

    # Ecrire dans un fichier temporaire pour google-auth
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as tmp:
        json.dump(token_data, tmp)
        tmp_path = tmp.name

    creds = Credentials.from_authorized_user_file(tmp_path, SCOPES)
    os.unlink(tmp_path)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    return creds


def _creds_depuis_fichier() -> Credentials:
    """Charge les credentials Gmail depuis token.json local."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow  = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return creds


def get_service():
    """Retourne le service Gmail — choisit automatiquement local ou cloud."""
    creds = _creds_depuis_secrets() if _est_sur_cloud() else _creds_depuis_fichier()
    return build("gmail", "v1", credentials=creds)


def extraire_corps(payload: dict) -> str:
    corps = ""
    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain" and "data" in part.get("body", {}):
                corps = base64.urlsafe_b64decode(
                    part["body"]["data"]
                ).decode("utf-8", errors="ignore")
                break
            elif part["mimeType"] == "text/html" and "data" in part.get("body", {}):
                corps = base64.urlsafe_b64decode(
                    part["body"]["data"]
                ).decode("utf-8", errors="ignore")
    elif "data" in payload.get("body", {}):
        corps = base64.urlsafe_b64decode(
            payload["body"]["data"]
        ).decode("utf-8", errors="ignore")
    return corps.strip()


def lire_emails(max_results: int = 20, query: str = "") -> list:
    service = get_service()
    params  = {"userId": "me", "maxResults": max_results}
    if query:
        params["q"] = query
    results  = service.users().messages().list(**params).execute()
    messages = results.get("messages", [])
    emails   = []
    for msg in messages:
        detail  = service.users().messages().get(
            userId="me", id=msg["id"], format="full"
        ).execute()
        headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
        emails.append({
            "id":     msg["id"],
            "sujet":  headers.get("Subject", "Sans sujet"),
            "de":     headers.get("From", "Inconnu"),
            "date":   headers.get("Date", ""),
            "corps":  extraire_corps(detail["payload"]),
            "source": "gmail",
        })
    return emails


def envoyer_email(destinataire: str, sujet: str, corps: str, html: bool = False) -> str:
    service = get_service()
    if html:
        msg            = MIMEMultipart("alternative")
        msg["Subject"] = sujet
        msg["To"]      = destinataire
        msg.attach(MIMEText(corps, "html"))
    else:
        msg            = MIMEText(corps, "plain", "utf-8")
        msg["Subject"] = sujet
        msg["To"]      = destinataire

    raw     = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    message = service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()
    return message["id"]


def generer_et_envoyer(destinataire: str, sujet: str, instruction: str):
    from groq import Groq
    client   = Groq(api_key=os.environ["GROQ_API_KEY"])
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "Tu es un assistant professionnel. Redige un email clair et poli en francais."},
            {"role": "user",   "content": f"Redige un email.\nInstruction : {instruction}\nDestinataire : {destinataire}\nSujet : {sujet}"},
        ],
    )
    corps  = response.choices[0].message.content
    msg_id = envoyer_email(destinataire, sujet, corps)
    return corps, msg_id

