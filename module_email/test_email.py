import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from gmail_reader import lire_emails
from email_agent import resumer_emails, rechercher_emails, indexer_emails, repondre_sur_emails

print("Chargement des emails...")
emails = lire_emails(max_results=10)
print(f"{len(emails)} email(s) recuperes\n")

print("="*50)
print("RESUME DES EMAILS")
print("="*50)
resume = resumer_emails(emails)
print(resume)

print("\n" + "="*50)
print("INDEXATION DANS RAG")
print("="*50)
index = indexer_emails(emails)
if index:
    print("Emails indexes avec succes !")

    print("\n" + "="*50)
    print("QUESTIONS SUR LES EMAILS")
    print("  'quitter' pour arreter")
    print("="*50 + "\n")

    while True:
        question = input("Ta question : ").strip()
        if not question:
            continue
        if question.lower() == "quitter":
            break
        reponse = repondre_sur_emails(index, question)
        print(f"\nReponse : {reponse}\n")
        print("-"*50)