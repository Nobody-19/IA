import os
import base64
import logging
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

BASE_DIR   = Path(__file__).parent.parent
ENV_FILE   = BASE_DIR / ".env"
CREDS_FILE = Path(__file__).parent / "credentials.json"
TOKEN_FILE = Path(__file__).parent / "token.json"
SCOPES     = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send"
]

load_dotenv(dotenv_path=ENV_FILE)
logging.basicConfig(level=logging.WARNING)

def get_service():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)

def extraire_corps(payload):
    corps = ""
    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain" and "data" in part.get("body", {}):
                corps = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="ignore")
                break
            elif part["mimeType"] == "text/html" and "data" in part.get("body", {}):
                corps = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="ignore")
    elif "data" in payload.get("body", {}):
        corps = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")
    return corps.strip()

def lire_emails(max_results=20, query=""):
    service  = get_service()
    params   = {"userId": "me", "maxResults": max_results}
    if query:
        params["q"] = query
    results  = service.users().messages().list(**params).execute()
    messages = results.get("messages", [])
    emails   = []
    for msg in messages:
        detail  = service.users().messages().get(userId="me", id=msg["id"], format="full").execute()
        headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
        emails.append({
            "id":     msg["id"],
            "sujet":  headers.get("Subject", "Sans sujet"),
            "de":     headers.get("From", "Inconnu"),
            "date":   headers.get("Date", ""),
            "corps":  extraire_corps(detail["payload"]),
            "source": "gmail"
        })
    return emails

def envoyer_email(destinataire, sujet, corps, html=False):
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
        userId="me",
        body={"raw": raw}
    ).execute()
    return message["id"]

def generer_et_envoyer(destinataire, sujet, instruction):
    from groq import Groq
    client   = Groq(api_key=os.environ["GROQ_API_KEY"])
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "Tu es un assistant professionnel. Redige un email clair et poli en francais."},
            {"role": "user",   "content": f"Redige un email avec les instructions suivantes :\n{instruction}\nDestinaire : {destinataire}\nSujet : {sujet}"}
        ]
    )
    corps  = response.choices[0].message.content
    msg_id = envoyer_email(destinataire, sujet, corps)
    return corps, msg_id

if __name__ == "__main__":
    emails = lire_emails(max_results=5)
    for e in emails:
        print(f"De : {e['de']}")
        print(f"Sujet : {e['sujet']}")
        print(f"Date : {e['date']}")
        print(f"Corps : {e['corps'][:200]}...")
        print("-"*50)