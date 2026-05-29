# module_email/scheduler.py
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.memory import MemoryJobStore

BASE_DIR = Path(__file__).parent.parent
ENV_FILE = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE)

logging.basicConfig(level=logging.WARNING)

# ── Instance globale du scheduler ──
_scheduler = None

def get_scheduler() -> BackgroundScheduler:
    """Retourne l'instance unique du scheduler (singleton)."""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(
            jobstores={"default": MemoryJobStore()},
            timezone="Africa/Lome"  # adapte à ton fuseau horaire
        )
        _scheduler.start()
    return _scheduler


def programmer_email(
    destinataire: str,
    sujet: str,
    corps: str,
    quand,           # datetime OU timedelta
    html: bool = False,
) -> dict:
    """
    Programme l'envoi d'un email.
    - quand = datetime précis  → envoi à cette date/heure
    - quand = timedelta        → envoi dans X minutes/heures
    Retourne les infos du job créé.
    """
    from module_email.gmail_reader import envoyer_email

    scheduler = get_scheduler()

    # Calculer la date d'exécution
    if isinstance(quand, timedelta):
        run_date = datetime.now() + quand
    elif isinstance(quand, datetime):
        run_date = quand
    else:
        raise ValueError("'quand' doit être un datetime ou un timedelta")

    job = scheduler.add_job(
        func=envoyer_email,
        trigger="date",
        run_date=run_date,
        kwargs={
            "destinataire": destinataire,
            "sujet":        sujet,
            "corps":        corps,
            "html":         html,
        },
        id=f"email_{destinataire}_{run_date.strftime('%Y%m%d%H%M%S')}",
        name=f"Email → {destinataire} | {sujet[:30]}",
        misfire_grace_time=300,  # 5 min de tolérance
    )

    return {
        "job_id":      job.id,
        "destinataire": destinataire,
        "sujet":        sujet,
        "run_date":     run_date.strftime("%d/%m/%Y à %H:%M"),
    }


def lister_emails_programmes() -> list:
    """Retourne la liste des emails en attente d'envoi."""
    scheduler = get_scheduler()
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id":           job.id,
            "nom":          job.name,
            "run_date":     job.next_run_time.strftime("%d/%m/%Y à %H:%M")
                            if job.next_run_time else "inconnu",
        })
    return jobs


def annuler_email_programme(job_id: str) -> bool:
    """Annule un email programmé par son ID."""
    scheduler = get_scheduler()
    try:
        scheduler.remove_job(job_id)
        return True
    except Exception:
        return False