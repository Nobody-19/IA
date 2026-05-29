from sqlalchemy import create_engine, text
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "entreprise.db"
engine  = create_engine(f"sqlite:///{DB_PATH}", echo=False)

SCHEMA = """
CREATE TABLE IF NOT EXISTS employes (
    id            INTEGER PRIMARY KEY,
    nom           TEXT NOT NULL,
    prenom        TEXT NOT NULL,
    poste         TEXT,
    departement   TEXT,
    salaire       REAL,
    date_embauche TEXT
);
CREATE TABLE IF NOT EXISTS produits (
    id        INTEGER PRIMARY KEY,
    nom       TEXT NOT NULL,
    categorie TEXT,
    prix      REAL,
    stock     INTEGER
);
CREATE TABLE IF NOT EXISTS clients (
    id      INTEGER PRIMARY KEY,
    nom     TEXT NOT NULL,
    email   TEXT,
    ville   TEXT,
    pays    TEXT
);
CREATE TABLE IF NOT EXISTS ventes (
    id          INTEGER PRIMARY KEY,
    produit_id  INTEGER REFERENCES produits(id),
    client_id   INTEGER REFERENCES clients(id),
    vendeur_id  INTEGER REFERENCES employes(id),
    quantite    INTEGER,
    montant     REAL,
    date_vente  TEXT
);
"""

DONNEES = """
INSERT OR IGNORE INTO employes VALUES
(1,'Dupont','Marie','Directrice','Direction',5500,'2018-03-01'),
(2,'Martin','Paul','Commercial','Ventes',3200,'2020-06-15'),
(3,'Kofi','Ama','Developpeur','Tech',3800,'2021-01-10'),
(4,'Mensah','Kojo','Commercial','Ventes',3100,'2021-09-01'),
(5,'Asante','Efua','Comptable','Finance',3400,'2019-11-20'),
(6,'Traore','Moussa','Commercial','Ventes',3050,'2022-04-05'),
(7,'Leclerc','Sophie','RH Manager','RH',4000,'2017-07-12'),
(8,'Diallo','Ibrahim','Developpeur','Tech',3700,'2022-08-01');

INSERT OR IGNORE INTO produits VALUES
(1,'Logiciel CRM','Logiciel',1200.0,50),
(2,'Logiciel ERP','Logiciel',2500.0,30),
(3,'Formation Python','Formation',800.0,100),
(4,'Consultation IA','Service',3000.0,20),
(5,'Maintenance annuelle','Service',600.0,200);

INSERT OR IGNORE INTO clients VALUES
(1,'Entreprise Alpha','alpha@mail.com','Paris','France'),
(2,'Societe Beta','beta@mail.com','Lyon','France'),
(3,'Groupe Gamma','gamma@mail.com','Abidjan','Cote Ivoire'),
(4,'Holding Delta','delta@mail.com','Dakar','Senegal'),
(5,'Compagnie Epsilon','epsilon@mail.com','Lome','Togo'),
(6,'Firm Zeta','zeta@mail.com','Accra','Ghana');

INSERT OR IGNORE INTO ventes VALUES
(1, 1,1,2,2,2400.0,'2024-01-15'),
(2, 3,2,4,5,4000.0,'2024-01-22'),
(3, 4,3,2,1,3000.0,'2024-02-03'),
(4, 2,1,6,1,2500.0,'2024-02-18'),
(5, 5,4,4,3,1800.0,'2024-03-05'),
(6, 1,5,2,3,3600.0,'2024-03-20'),
(7, 4,2,6,2,6000.0,'2024-04-10'),
(8, 3,3,4,4,3200.0,'2024-04-25'),
(9, 2,6,2,2,5000.0,'2024-05-08'),
(10,5,1,6,5,3000.0,'2024-05-30'),
(11,1,5,4,1,1200.0,'2024-06-14'),
(12,4,4,2,3,9000.0,'2024-06-28');
"""

def creer_base():
    with engine.connect() as conn:
        for stmt in SCHEMA.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
        for stmt in DONNEES.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
        conn.commit()
    print(f"Base creee : {DB_PATH}")
    print("Tables : employes, produits, clients, ventes")

if __name__ == "__main__":
    creer_base()