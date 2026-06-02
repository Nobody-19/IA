"""
module_email/oauth_flow.py
Flux OAuth2 Gmail integre dans Streamlit.
Permet a chaque utilisateur de connecter son propre compte Gmail
sans manipulation technique.
"""

import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR   = Path(__file__).parent.parent
ENV_FILE   = BASE_DIR / ".env"
CREDS_FILE = Path(__file__).parent / "credentials.json"
SCOPES     = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

load_dotenv(dotenv_path=ENV_FILE)
logger = logging.getLogger(__name__)


def get_redirect_uri() -> str:
    """
    Retourne l'URI de redirection selon l'environnement.
    Local : http://localhost:8501
    Streamlit Cloud : URL de l'app
    """
    try:
        import streamlit as st
        # Sur Streamlit Cloud, recuperer l'URL depuis les secrets
        base_url = st.secrets.get("APP_URL", "http://localhost:8501")
    except Exception:
        base_url = "http://localhost:8501"
    return base_url


def generer_url_autorisation() -> str:
    """
    Genere l'URL Google OAuth2 vers laquelle rediriger l'utilisateur.
    """
    from google_auth_oauthlib.flow import Flow

    if not CREDS_FILE.exists():
        raise FileNotFoundError(
            f"credentials.json introuvable : {CREDS_FILE}\n"
            "Telechargez-le depuis Google Cloud Console."
        )

    flow = Flow.from_client_secrets_file(
        str(CREDS_FILE),
        scopes=SCOPES,
        redirect_uri=get_redirect_uri(),
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url, state


def echanger_code_contre_token(code: str, state: str) -> dict:
    """
    Echange le code d'autorisation Google contre un token d'acces.
    Retourne le token sous forme de dict.
    """
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_secrets_file(
        str(CREDS_FILE),
        scopes=SCOPES,
        redirect_uri=get_redirect_uri(),
        state=state,
    )
    flow.fetch_token(code=code)
    creds = flow.credentials
    return json.loads(creds.to_json())


def get_service_depuis_token(token_dict: dict):
    """
    Construit le service Gmail depuis un token stocke en session.
    """
    import tempfile
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as tmp:
        json.dump(token_dict, tmp)
        tmp_path = tmp.name

    try:
        creds = Credentials.from_authorized_user_file(tmp_path, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return build("gmail", "v1", credentials=creds)
    finally:
        os.unlink(tmp_path)


def est_connecte() -> bool:
    """Verifie si l'utilisateur a un token Gmail en session."""
    try:
        import streamlit as st
        return bool(st.session_state.get("gmail_token"))
    except Exception:
        return False


def get_email_connecte() -> str:
    """Retourne l'email de l'utilisateur connecte."""
    try:
        import streamlit as st
        return st.session_state.get("gmail_email", "")
    except Exception:
        return ""


def deconnecter() -> None:
    """Supprime le token Gmail de la session."""
    import streamlit as st
    st.session_state.pop("gmail_token", None)
    st.session_state.pop("gmail_email", None)
    st.session_state.pop("emails_charges", None)
    st.session_state.pop("index_emails", None)
