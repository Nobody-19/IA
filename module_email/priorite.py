# module_email/priorite.py
import os
from groq import Groq
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

GROQ_MODEL = "llama-3.3-70b-versatile"

PRIORITE_PROMPT = """Analyse cet email et détermine son niveau de priorité.
Réponds UNIQUEMENT par un seul mot : URGENT, NORMAL ou FAIBLE.

Règles :
- URGENT  → action requise aujourd'hui, deadline imminente, problème critique, mot-clé "urgent/immédiat/asap"
- NORMAL  → demande standard, réunion, information importante
- FAIBLE  → newsletter, notification automatique, accusé de réception, publicité

Email :
De : {expediteur}
Sujet : {sujet}
Corps : {corps}"""


def analyser_priorite(email: dict) -> str:
    """Retourne 'URGENT', 'NORMAL' ou 'FAIBLE'."""
    try:
        client = Groq(api_key=os.environ["GROQ_API_KEY"])
        prompt = PRIORITE_PROMPT.format(
            expediteur=email.get("de", ""),
            sujet=email.get("sujet", ""),
            corps=email.get("corps", "")[:500],
        )
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=10,
        )
        niveau = resp.choices[0].message.content.strip().upper()
        if niveau not in ["URGENT", "NORMAL", "FAIBLE"]:
            return "NORMAL"
        return niveau
    except Exception:
        return "NORMAL"


def analyser_priorites_batch(emails: list) -> list:
    """Analyse la priorité de tous les emails et ajoute le champ 'priorite'."""
    for email in emails:
        email["priorite"] = analyser_priorite(email)
    return emails


def badge_priorite(niveau: str) -> str:
    """Retourne le badge HTML coloré selon la priorité."""
    badges = {
        "URGENT": '<span style="background:#8b0000;color:#ffaaaa;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700;">🔴 URGENT</span>',
        "NORMAL": '<span style="background:#7a6000;color:#ffd970;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700;">🟡 NORMAL</span>',
        "FAIBLE": '<span style="background:#1a4a1a;color:#90ee90;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700;">🟢 FAIBLE</span>',
    }
    return badges.get(niveau, badges["NORMAL"])