"""
utils/historique.py
Sauvegarde et lecture de l'historique des conversations.
Base SQLite separee : historique.db
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent
DB_PATH  = BASE_DIR / "historique.db"

logger = logging.getLogger(__name__)


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                titre          TEXT    NOT NULL DEFAULT 'Nouvelle conversation',
                date_creation  TEXT    NOT NULL,
                date_maj       TEXT    NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                conv_id     INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role        TEXT    NOT NULL,
                contenu     TEXT    NOT NULL,
                module      TEXT    DEFAULT 'general',
                timestamp   TEXT    NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conv_id);
        """)


def nouvelle_conversation(titre: str = "Nouvelle conversation") -> int:
    init_db()
    now = datetime.now().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO conversations (titre, date_creation, date_maj) VALUES (?, ?, ?)",
            (titre, now, now)
        )
        return cur.lastrowid


def mettre_a_jour_titre(conv_id: int, titre: str) -> None:
    now = datetime.now().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE conversations SET titre = ?, date_maj = ? WHERE id = ?",
            (titre[:80], now, conv_id)
        )


def lister_conversations(limite: int = 30) -> list:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, titre, date_creation, date_maj FROM conversations ORDER BY date_maj DESC LIMIT ?",
            (limite,)
        ).fetchall()
    return [dict(r) for r in rows]


def supprimer_conversation(conv_id: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))


def sauvegarder_message(conv_id: int, role: str, contenu: str, module: str = "general") -> None:
    init_db()
    now = datetime.now().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO messages (conv_id, role, contenu, module, timestamp) VALUES (?, ?, ?, ?, ?)",
            (conv_id, role, contenu, module, now)
        )
        conn.execute(
            "UPDATE conversations SET date_maj = ? WHERE id = ?",
            (now, conv_id)
        )


def charger_messages(conv_id: int) -> list:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT role, contenu, module, timestamp FROM messages WHERE conv_id = ? ORDER BY id ASC",
            (conv_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def compter_messages(conv_id: int) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM messages WHERE conv_id = ?", (conv_id,)
        ).fetchone()[0]


def generer_titre(premier_message: str) -> str:
    titre = premier_message.strip().replace("\n", " ")
    return (titre[:57] + "...") if len(titre) > 60 else titre or "Conversation"


# ──────────────────────────────────────────
# EXPORT / IMPORT JSON (pour Streamlit Cloud)
# ──────────────────────────────────────────
def exporter_json() -> str:
    """Exporte tout l'historique en JSON — pour telechargement."""
    import json
    conversations = lister_conversations(limite=200)
    data = []
    for conv in conversations:
        msgs = charger_messages(conv["id"])
        data.append({
            "titre":         conv["titre"],
            "date_creation": conv["date_creation"],
            "date_maj":      conv["date_maj"],
            "messages":      msgs,
        })
    return json.dumps(data, ensure_ascii=False, indent=2)


def importer_json(json_str: str) -> int:
    """
    Importe un historique depuis un JSON precedemment exporte.
    Retourne le nombre de conversations importees.
    """
    import json
    data = json.loads(json_str)
    count = 0
    for conv_data in data:
        conv_id = nouvelle_conversation(conv_data.get("titre", "Importee"))
        for msg in conv_data.get("messages", []):
            sauvegarder_message(
                conv_id,
                msg["role"],
                msg["contenu"],
                msg.get("module", "general"),
            )
        count += 1
    return count

