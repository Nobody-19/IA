import os
import base64
import sys
from pathlib import Path
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

sys.path.append(str(Path(__file__).parent))
from email_agent import indexer_emails, resumer_emails
from gmail_reader import lire_emails, generer_et_envoyer, envoyer_email

def afficher_menu():
    print("\n" + "="*55)
    print("      AGENT IA - Module Email")
    print("="*55)
    print("  [1]  Envoyer un email manuellement")
    print("  [2]  Generer un email avec l'IA")
    print("  [3]  Repondre a un email existant avec l'IA")
    print("  [0]  Quitter")
    print("="*55)

def saisir_destinataires():
    print("\nDestinataires (separez par des virgules si plusieurs)")
    print("Exemple : alice@gmail.com, bob@outlook.com")
    entree = input("Destinataires : ").strip()
    destinataires = [d.strip() for d in entree.split(",") if d.strip()]
    if not destinataires:
        print("Aucun destinataire valide.")
        return []
    print(f"\n{len(destinataires)} destinataire(s) :")
    for d in destinataires:
        print(f"  > {d}")
    confirmation = input("Confirmer ? (o/n) : ").strip().lower()
    if confirmation != "o":
        return []
    return destinataires

def envoyer_manuel():
    print("\n--- ENVOI MANUEL ---")
    destinataires = saisir_destinataires()
    if not destinataires:
        return
    sujet = input("Sujet : ").strip()
    print("Corps du message (ligne vide pour terminer) :")
    lignes = []
    while True:
        ligne = input()
        if ligne == "":
            break
        lignes.append(ligne)
    corps = "\n".join(lignes)
    if not corps:
        print("Corps vide, envoi annule.")
        return
    print(f"\nApercu :")
    print(f"  A : {', '.join(destinataires)}")
    print(f"  Sujet : {sujet}")
    print(f"  Corps : {corps[:100]}...")
    confirm = input("\nEnvoyer ? (o/n) : ").strip().lower()
    if confirm != "o":
        print("Envoi annule.")
        return
    for dest in destinataires:
        try:
            msg_id = envoyer_email(dest, sujet, corps)
            print(f"  OK : Email envoye a {dest} (ID: {msg_id})")
        except Exception as e:
            print(f"  ERREUR : {dest} -> {e}")

def envoyer_avec_ia():
    print("\n--- GENERATION IA ---")
    destinataires = saisir_destinataires()
    if not destinataires:
        return
    sujet       = input("Sujet : ").strip()
    instruction = input("Instructions pour l'IA : ").strip()
    print("\nL'IA redige l'email...")
    corps, _ = generer_et_envoyer(destinataires[0], sujet, instruction)
    print(f"\nEmail genere :\n{'-'*40}\n{corps}\n{'-'*40}")
    confirm = input("\nEnvoyer a tous les destinataires ? (o/n) : ").strip().lower()
    if confirm != "o":
        print("Envoi annule.")
        return
    for dest in destinataires:
        try:
            msg_id = envoyer_email(dest, sujet, corps)
            print(f"  OK : Email envoye a {dest} (ID: {msg_id})")
        except Exception as e:
            print(f"  ERREUR : {dest} -> {e}")

def repondre_avec_ia():
    print("\n--- REPONDRE A UN EMAIL ---")
    print("Chargement de tes emails recents...")
    emails = lire_emails(max_results=10)
    if not emails:
        print("Aucun email trouve.")
        return
    print(f"\n{len(emails)} email(s) disponible(s) :\n")
    for i, e in enumerate(emails, 1):
        print(f"  [{i}] De : {e['de']}")
        print(f"       Sujet : {e['sujet']}")
        print(f"       Date  : {e['date'][:30]}")
        print()
    choix = input("Choisir un email (numero) : ").strip()
    try:
        idx   = int(choix) - 1
        email = emails[idx]
    except (ValueError, IndexError):
        print("Choix invalide.")
        return
    print(f"\nEmail selectionne : {email['sujet']}")
    print(f"De : {email['de']}")
    destinataires_supp = input("\nAjouter d'autres destinataires ? (laisser vide pour non) : ").strip()
    destinataires = [email['de']]
    if destinataires_supp:
        extras = [d.strip() for d in destinataires_supp.split(",") if d.strip()]
        destinataires.extend(extras)
    instruction = input("Instructions pour la reponse (ex: accepter le RDV, demander plus d'info) : ").strip()
    contexte    = f"Email original :\nDe : {email['de']}\nSujet : {email['sujet']}\nCorps : {email['corps'][:500]}"
    sujet       = f"Re: {email['sujet']}"
    corps, _    = generer_et_envoyer(destinataires[0], sujet, f"{instruction}\n\nContexte : {contexte}")
    print(f"\nReponse generee :\n{'-'*40}\n{corps}\n{'-'*40}")
    confirm = input("\nEnvoyer ? (o/n) : ").strip().lower()
    if confirm != "o":
        print("Envoi annule.")
        return
    for dest in destinataires:
        try:
            msg_id = envoyer_email(dest, sujet, corps)
            print(f"  OK : Reponse envoyee a {dest} (ID: {msg_id})")
        except Exception as e:
            print(f"  ERREUR : {dest} -> {e}")

def main():
    print("\nAgent Email demarre !")
    while True:
        afficher_menu()
        choix = input("\nTon choix : ").strip()
        if choix == "1":
            envoyer_manuel()
        elif choix == "2":
            envoyer_avec_ia()
        elif choix == "3":
            repondre_avec_ia()
        elif choix == "0":
            print("Au revoir !")
            break
        else:
            print("Choix invalide.")

if __name__ == "__main__":
    main()