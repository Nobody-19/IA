import logging
from pathlib import Path
from dotenv import load_dotenv
import os
from exchangelib import Credentials, Account, DELEGATE, Configuration
from exchangelib.protocol import BaseProtocol, NoVerifyHTTPAdapter

BASE_DIR = Path(__file__).parent.parent
ENV_FILE = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE)
logging.basicConfig(level=logging.WARNING)

def get_account():
    email    = os.environ.get("OUTLOOK_EMAIL", "")
    password = os.environ.get("OUTLOOK_PASSWORD", "")
    if not email or not password:
        raise ValueError("Ajoute OUTLOOK_EMAIL et OUTLOOK_PASSWORD dans ton .env")
    creds   = Credentials(email, password)
    config  = Configuration(server="outlook.office365.com", credentials=creds)
    account = Account(
        primary_smtp_address=email,
        config=config,
        autodiscover=False,
        access_type=DELEGATE
    )
    return account

def lire_emails(max_results=20, query=""):
    account = get_account()
    emails  = []
    items   = account.inbox.all().order_by("-datetime_received")[:max_results]
    for item in items:
        corps = ""
        if hasattr(item, "text_body") and item.text_body:
            corps = item.text_body
        elif hasattr(item, "body") and item.body:
            corps = str(item.body)
        sujet = str(item.subject or "Sans sujet")
        if query and query.lower() not in sujet.lower() and query.lower() not in corps.lower():
            continue
        emails.append({
            "id":     str(item.id),
            "sujet":  sujet,
            "de":     str(item.sender.email_address if item.sender else "Inconnu"),
            "date":   str(item.datetime_received),
            "corps":  corps.strip(),
            "source": "outlook"
        })
    return emails

if __name__ == "__main__":
    emails = lire_emails(max_results=5)
    for e in emails:
        print(f"De : {e['de']}")
        print(f"Sujet : {e['sujet']}")
        print(f"Corps : {e['corps'][:200]}...")
        print("-"*50)