# create_db.py
from sqlalchemy import create_engine, text

# Crée le fichier SQLite dans mon_agent/
engine = create_engine("sqlite:///./entreprise.db", echo=False)

with engine.connect() as conn:

    # Table des employés
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS employes (
            id INTEGER PRIMARY KEY,
            nom TEXT,
            prenom TEXT,
            poste TEXT,
            departement TEXT,
            salaire REAL,
            date_embauche TEXT
        )
    """))

    # Table des ventes
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS ventes (
            id INTEGER PRIMARY KEY,
            produit TEXT,
            montant REAL,
            quantite INTEGER,
            date_vente TEXT,
            client TEXT,
            vendeur_id INTEGER
        )
    """))

    # Table des produits
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS produits (
            id INTEGER PRIMARY KEY,
            nom TEXT,
            categorie TEXT,
            prix REAL,
            stock INTEGER
        )
    """))

    # Insertion des employés
    conn.execute(text("""
        INSERT OR IGNORE INTO employes VALUES
        (1, 'Dupont', 'Marie', 'Directrice', 'Direction', 5500, '2018-03-01'),
        (2, 'Martin', 'Paul', 'Commercial', 'Ventes', 3200, '2020-06-15'),
        (3, 'Kofi', 'Ama', 'Développeur', 'Tech', 3800, '2021-01-10'),
        (4, 'Mensah', 'Kojo', 'Commercial', 'Ventes', 3100, '2021-09-01'),
        (5, 'Asante', 'Efua', 'Comptable', 'Finance', 3400, '2019-11-20'),
        (6, 'Traoré', 'Moussa', 'Commercial', 'Ventes', 3050, '2022-04-05'),
        (7, 'Leclerc', 'Sophie', 'RH Manager', 'RH', 4000, '2017-07-12'),
        (8, 'Diallo', 'Ibrahim', 'Développeur', 'Tech', 3700, '2022-08-01')
    """))

    # Insertion des produits
    conn.execute(text("""
        INSERT OR IGNORE INTO produits VALUES
        (1, 'Logiciel CRM', 'Logiciel', 1200.0, 50),
        (2, 'Logiciel ERP', 'Logiciel', 2500.0, 30),
        (3, 'Formation Python', 'Formation', 800.0, 100),
        (4, 'Consultation IA', 'Service', 3000.0, 20),
        (5, 'Maintenance annuelle', 'Service', 600.0, 200)
    """))

    # Insertion des ventes
    conn.execute(text("""
        INSERT OR IGNORE INTO ventes VALUES
        (1,  'Logiciel CRM',      1200.0, 2, '2024-01-15', 'Client A', 2),
        (2,  'Formation Python',   800.0, 5, '2024-01-22', 'Client B', 4),
        (3,  'Consultation IA',   3000.0, 1, '2024-02-03', 'Client C', 2),
        (4,  'Logiciel ERP',      2500.0, 1, '2024-02-18', 'Client A', 6),
        (5,  'Maintenance',        600.0, 3, '2024-03-05', 'Client D', 4),
        (6,  'Logiciel CRM',      1200.0, 3, '2024-03-20', 'Client E', 2),
        (7,  'Consultation IA',   3000.0, 2, '2024-04-10', 'Client B', 6),
        (8,  'Formation Python',   800.0, 4, '2024-04-25', 'Client C', 4),
        (9,  'Logiciel ERP',      2500.0, 2, '2024-05-08', 'Client F', 2),
        (10, 'Maintenance',        600.0, 5, '2024-05-30', 'Client A', 6),
        (11, 'Logiciel CRM',      1200.0, 1, '2024-06-14', 'Client G', 4),
        (12, 'Consultation IA',   3000.0, 3, '2024-06-28', 'Client D', 2)
    """))

    conn.commit()

print("Base de données créée : entreprise.db")
print("Tables : employes, ventes, produits")