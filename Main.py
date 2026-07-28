import os
import sys
import sqlite3
import shutil
import csv
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Support optionnel de ReportLab pour l'impression PDF
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# =========================================================================
# 1. GESTION DYNAMIQUE DES CHEMINS (COMPATIBILITÉ PYINSTALLER .EXE & PYTHON)
# =========================================================================
if getattr(sys, 'frozen', False):
    # Mode exécutable .EXE (Dossier contenant l'exécutable)
    APP_DIR = os.path.dirname(sys.executable)
else:
    # Mode script Python classique
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

DB_DIR = os.path.join(APP_DIR, "data")
DB_PATH = os.path.join(DB_DIR, "centre_lait.db")
BACKUP_DIR = os.path.join(APP_DIR, "backups")
EXPORTS_DIR = os.path.join(APP_DIR, "exports")

os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)

# =========================================================================
# 2. BASE DE DONNÉES (PERSISTENCE & SCHÉMA SQL)
# =========================================================================
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Centre de Collecte
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS centre_info (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        agrement_num TEXT NOT NULL,
        date_delivrance DATE NOT NULL,
        date_expiration DATE NOT NULL,
        autorite TEXT NOT NULL,
        observations TEXT
    );""")

    # Éleveurs / Producteurs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS eleveurs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code_eleveur TEXT UNIQUE NOT NULL,
        nom TEXT NOT NULL,
        prenom TEXT NOT NULL,
        adresse TEXT,
        commune TEXT NOT NULL,
        wilaya TEXT NOT NULL,
        telephone TEXT,
        num_ccp_banque TEXT,
        num_identification TEXT,
        cooperative TEXT,
        date_inscription DATE NOT NULL,
        statut TEXT DEFAULT 'Actif',
        agrement_num TEXT,
        agrement_delivrance DATE,
        agrement_expiration DATE,
        certificat_num TEXT,
        certificat_delivrance DATE,
        certificat_expiration DATE,
        observations TEXT
    );""")

    # Collectes de Lait
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS collectes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        num_collecte TEXT UNIQUE NOT NULL,
        date_collecte DATE NOT NULL,
        heure_collecte TIME NOT NULL,
        eleveur_id INTEGER NOT NULL,
        quantite_litres REAL NOT NULL,
        temperature REAL,
        acidite REAL,
        matiere_grasse REAL,
        densite REAL,
        qualite TEXT DEFAULT 'Bonne',
        agent_collecteur TEXT NOT NULL,
        statut TEXT DEFAULT 'Valide',
        observations TEXT,
        FOREIGN KEY (eleveur_id) REFERENCES eleveurs(id)
    );""")

    # Expéditions vers Laiteries
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expeditions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        num_expedition TEXT UNIQUE NOT NULL,
        date_expedition DATE NOT NULL,
        heure_expedition TIME NOT NULL,
        laiterie_destinataire TEXT NOT NULL,
        chauffeur TEXT NOT NULL,
        camion TEXT NOT NULL,
        immatriculation TEXT NOT NULL,
        quantite_litres REAL NOT NULL,
        temperature REAL,
        type_conteneur TEXT NOT NULL,
        nombre_bidons INTEGER DEFAULT 0,
        observations TEXT
    );""")

    # Stock Aliments
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS aliments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        designation TEXT NOT NULL,
        categorie TEXT NOT NULL,
        prix_vente REAL NOT NULL,
        stock_actuel REAL NOT NULL DEFAULT 0,
        stock_minimum REAL NOT NULL DEFAULT 10,
        fournisseur TEXT
    );""")

    # Ventes d'Aliments
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ventes_aliments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date_vente DATE NOT NULL,
        eleveur_id INTEGER NOT NULL,
        aliment_id INTEGER NOT NULL,
        quantite REAL NOT NULL,
        prix_unitaire REAL NOT NULL,
        montant_total REAL NOT NULL,
        facture_id INTEGER,
        FOREIGN KEY (eleveur_id) REFERENCES eleveurs(id),
        FOREIGN KEY (aliment_id) REFERENCES aliments(id)
    );""")

    # Agréments Véhicules
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agrements_vehicules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        immatriculation TEXT UNIQUE NOT NULL,
        marque TEXT NOT NULL,
        modele TEXT,
        chauffeur TEXT NOT NULL,
        agrement_num TEXT NOT NULL,
        date_delivrance DATE NOT NULL,
        date_expiration DATE NOT NULL,
        observations TEXT
    );""")

    # Factures
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS factures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        num_facture TEXT UNIQUE NOT NULL,
        eleveur_id INTEGER NOT NULL,
        periode_debut DATE NOT NULL,
        periode_fin DATE NOT NULL,
        date_facture DATE NOT NULL,
        total_litres REAL NOT NULL,
        prix_litre REAL NOT NULL,
        montant_lait REAL NOT NULL,
        montant_achats_aliments REAL DEFAULT 0,
        avances REAL DEFAULT 0,
        autres_retenues REAL DEFAULT 0,
        total_retenues REAL NOT NULL,
        ancien_report REAL DEFAULT 0,
        solde_final REAL NOT NULL,
        net_a_payer REAL NOT NULL,
        nouveau_report REAL DEFAULT 0,
        statut TEXT DEFAULT 'Émise',
        FOREIGN KEY (eleveur_id) REFERENCES eleveurs(id)
    );""")

    # Injection initiale si base vide
    cursor.execute("SELECT COUNT(*) FROM eleveurs")
    if cursor.fetchone()[0] == 0:
        seed_initial_data(cursor)

    conn.commit()
    conn.close()

def seed_initial_data(cursor):
    today = datetime.now().date()
    date_exp_7d = (today + timedelta(days=5)).strftime("%Y-%m-%d")
    date_exp_ok = (today + timedelta(days=180)).strftime("%Y-%m-%d")
    date_deliv = today.strftime("%Y-%m-%d")

    cursor.execute("""
    INSERT INTO centre_info (nom, agrement_num, date_delivrance, date_expiration, autorite, observations)
    VALUES (?, ?, ?, ?, ?, ?)""",
    ("Centre Laitier Espoir", "AGR-CENTRE-2026", date_deliv, date_exp_ok, "Direction Services Agricoles", "Centre Principal"))

    cursor.execute("""
    INSERT INTO eleveurs (code_eleveur, nom, prenom, adresse, commune, wilaya, telephone, num_ccp_banque, num_identification, cooperative, date_inscription, agrement_num, agrement_delivrance, agrement_expiration, certificat_num, certificat_delivrance, certificat_expiration)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    ("ELV-001", "Benali", "Mohamed", "Ferme N°12", "Blida", "Blida", "0550123456", "0079999901", "NID-8841", "Coopérative El-Baraka", date_deliv, "AGR-ELV-01", date_deliv, date_exp_7d, "CERT-ELV-01", date_deliv, date_exp_ok))

    cursor.execute("""
    INSERT INTO eleveurs (code_eleveur, nom, prenom, adresse, commune, wilaya, telephone, num_ccp_banque, num_identification, cooperative, date_inscription, agrement_num, agrement_delivrance, agrement_expiration, certificat_num, certificat_delivrance, certificat_expiration)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    ("ELV-002", "Khadir", "Ahmed", "Route Soumma", "Boufarik", "Blida", "0661987654", "0079999902", "NID-3321", "Coopérative El-Baraka", date_deliv, "AGR-ELV-02", date_deliv, date_exp_ok, "CERT-ELV-02", date_deliv, date_exp_ok))

    cursor.execute("""
    INSERT INTO aliments (code, designation, categorie, prix_vente, stock_actuel, stock_minimum, fournisseur)
    VALUES (?, ?, ?, ?, ?, ?, ?)""",
    ("ALM-01", "Sons de Blé (Sac 50kg)", "Concentrés", 2200.0, 45.0, 10.0, "OAIC"))

    cursor.execute("""
    INSERT INTO aliments (code, designation, categorie, prix_vente, stock_actuel, stock_minimum, fournisseur)
    VALUES (?, ?, ?, ?, ?, ?, ?)""",
    ("ALM-02", "Complément Vache Laitière", "Aliment Composé", 3800.0, 5.0, 15.0, "Provende Algérie"))

    cursor.execute("""
    INSERT INTO agrements_vehicules (immatriculation, marque, modele, chauffeur, agrement_num, date_delivrance, date_expiration, observations)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
    ("00123-316-09", "Isuzu", "NKR", "Karim", "AGR-VEH-01", date_deliv, date_exp_7d, "Camion Isuzu Citerne"))

# =========================================================================
# 3. APPLICATION GRAPHIQUE (TKINTER / TTK)
# =========================================================================
class ApplicationLaitiere(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestion du Centre de Collecte de Lait v2026 - Coopératives & Centres")
        self.geometry("1280x768")
        self.minsize(1024, 600)

        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        self.configure_styles()

        init_db()

        self.create_menu()
        self.create_toolbar()
        self.create_statusbar()

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Onglets MDI
        self.tab_dashboard = ttk.Frame(self.notebook)
        self.tab_eleveurs = ttk.Frame(self.notebook)
        self.tab_collecte = ttk.Frame(self.notebook)
        self.tab_expedition = ttk.Frame(self.notebook)
        self.tab_aliments = ttk.Frame(self.notebook)
        self.tab_factures = ttk.Frame(self.notebook)
        self.tab_agrements = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_dashboard, text=" 📊 Tableau de Bord ")
        self.notebook.add(self.tab_eleveurs, text=" 👨‍🌾 Éleveurs ")
        self.notebook.add(self.tab_collecte, text=" 🥛 Collecte ")
        self.notebook.add(self.tab_expedition, text=" 🚛 Expéditions ")
        self.notebook.add(self.tab_aliments, text=" 🌾 Stocks & Aliments ")
        self.notebook.add(self.tab_factures, text=" 🧾 Facturation ")
        self.notebook.add(self.tab_agrements, text=" 🛡️ Agréments Véhicules ")

        self.build_dashboard()
        self.build_eleveurs()
        self.build_collecte()
        self.build_expedition()
        self.build_aliments()
        self.build_factures()
        self.build_agrements()

        self.update_status("Logiciel prêt. Connecté à la base de données SQLite.")

    def configure_styles(self):
        self.style.configure('.', font=('Segoe UI', 10))
        self.style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'), background='#e1e1e1')
        self.style.configure('Header.TLabel', font=('Segoe UI', 14, 'bold'), foreground='#1a365d')
        self.style.configure('Card.TFrame', background='#f8fafc', relief='solid', borderwidth=1)

    def create_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Sauvegarder la base de données", command=self.backup_db)
        file_menu.add_command(label="Restaurer une sauvegarde", command=self.restore_db)
        file_menu.add_separator()
        file_menu.add_command(label="Quitter", command=self.quit)
        menubar.add_cascade(label="Fichier", menu=file_menu)

        mod_menu = tk.Menu(menubar, tearoff=0)
        mod_menu.add_command(label="Tableau de Bord", command=lambda: self.notebook.select(self.tab_dashboard))
        mod_menu.add_command(label="Éleveurs", command=lambda: self.notebook.select(self.tab_eleveurs))
        mod_menu.add_command(label="Collectes", command=lambda: self.notebook.select(self.tab_collecte))
        mod_menu.add_command(label="Expéditions", command=lambda: self.notebook.select(self.tab_expedition))
        mod_menu.add_command(label="Aliments & Stocks", command=lambda: self.notebook.select(self.tab_aliments))
        mod_menu.add_command(label="Facturation", command=lambda: self.notebook.select(self.tab_factures))
        mod_menu.add_command(label="Agréments Véhicules", command=lambda: self.notebook.select(self.tab_agrements))
        menubar.add_cascade(label="Modules", menu=mod_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="À Propos", command=self.show_about)
        menubar.add_cascade(label="Aide", menu=help_menu)

        self.config(menu=menubar)

    def create_toolbar(self):
        toolbar = ttk.Frame(self, padding=3)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(toolbar, text="📊 Tableau de Bord", command=lambda: self.notebook.select(self.tab_dashboard)).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="👨‍🌾 Éleveurs", command=lambda: self.notebook.select(self.tab_eleveurs)).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🥛 Collecte", command=lambda: self.notebook.select(self.tab_collecte)).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🚛 Expédition", command=lambda: self.notebook.select(self.tab_expedition)).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🧾 Factures", command=lambda: self.notebook.select(self.tab_factures)).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="💾 Sauvegarder DB", command=self.backup_db).pack(side=tk.RIGHT, padx=2)

    def create_statusbar(self):
        self.statusbar = ttk.Label(self, text="Prêt", anchor=tk.W, padding=(5, 2))
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)

    def update_status(self, message):
        self.statusbar.config(text=f" [{datetime.now().strftime('%H:%M:%S')}] {message}")

    # --- MODULE 0: TABLEAU DE BORD ---
    def build_dashboard(self):
        for widget in self.tab_dashboard.winfo_children():
            widget.destroy()

        header = ttk.Label(self.tab_dashboard, text="Tableau de Bord & Indicateurs Clés", style="Header.TLabel")
        header.pack(anchor=tk.W, padx=15, pady=10)

        kpi_frame = ttk.Frame(self.tab_dashboard)
        kpi_frame.pack(fill=tk.X, padx=15, pady=5)

        conn = get_db_connection()
        cur = conn.cursor()

        today_str = datetime.now().strftime("%Y-%m-%d")
        month_str = datetime.now().strftime("%Y-%m-")

        cur.execute("SELECT COALESCE(SUM(quantite_litres), 0) FROM collectes WHERE date_collecte = ? AND statut='Valide'", (today_str,))
        litres_today = cur.fetchone()[0]

        cur.execute("SELECT COALESCE(SUM(quantite_litres), 0) FROM collectes WHERE date_collecte LIKE ? AND statut='Valide'", (f"{month_str}%",))
        litres_month = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM eleveurs WHERE statut='Actif'")
        nb_eleveurs = cur.fetchone()[0]

        cur.execute("SELECT COALESCE(SUM(stock_actuel * prix_vente), 0) FROM aliments")
        valeur_stock = cur.fetchone()[0]

        cards = [
            ("Collecte Aujourd'hui", f"{litres_today:.1f} L", "#2b6cb0"),
            ("Collecte Ce Mois", f"{litres_month:.1f} L", "#2c7a7b"),
            ("Éleveurs Actifs", f"{nb_eleveurs}", "#2f855a"),
            ("Valeur Stock Aliments", f"{valeur_stock:,.2f} DZD", "#7b341e")
        ]

        for idx, (title, val, color) in enumerate(cards):
            card = ttk.Frame(kpi_frame, style="Card.TFrame", padding=15)
            card.grid(row=0, column=idx, padx=10, pady=5, sticky="nsew")
            kpi_frame.columnconfigure(idx, weight=1)

            ttk.Label(card, text=title, font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
            tk.Label(card, text=val, font=("Segoe UI", 16, "bold"), fg=color, bg="#f8fafc").pack(anchor=tk.W, pady=(5,0))

        alert_frame = ttk.LabelFrame(self.tab_dashboard, text=" ⚠️ Alertes Sanitaires & Stock Minimum (< 7 Jours) ", padding=10)
        alert_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        cols = ("type", "element", "echeance", "status")
        self.tree_alerts = ttk.Treeview(alert_frame, columns=cols, show="headings", height=8)
        self.tree_alerts.heading("type", text="Type d'Alerte")
        self.tree_alerts.heading("element", text="Élément Concerné")
        self.tree_alerts.heading("echeance", text="Échéance / Quantité")
        self.tree_alerts.heading("status", text="Niveau de Risque")

        for c, w in [("type", 200), ("element", 280), ("echeance", 160), ("status", 160)]:
            self.tree_alerts.column(c, width=w)

        self.tree_alerts.pack(fill=tk.BOTH, expand=True)

        limit_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        
        # Alertes Éleveurs
        cur.execute("SELECT nom, prenom, agrement_expiration FROM eleveurs WHERE agrement_expiration <= ?", (limit_date,))
        for r in cur.fetchall():
            self.tree_alerts.insert("", tk.END, values=("Agrément Sanitaire Éleveur", f"{r['nom']} {r['prenom']}", r['agrement_expiration'], "CRITIQUE (EXPIRATION PROCHE)"))

        # Alertes Véhicules
        cur.execute("SELECT immatriculation, chauffeur, date_expiration FROM agrements_vehicules WHERE date_expiration <= ?", (limit_date,))
        for r in cur.fetchall():
            self.tree_alerts.insert("", tk.END, values=("Agrément Sanitaire Véhicule", f"Camion {r['immatriculation']} ({r['chauffeur']})", r['date_expiration'], "CRITIQUE (EXPIRATION PROCHE)"))

        # Alertes Stock
        cur.execute("SELECT designation, stock_actuel, stock_minimum FROM aliments WHERE stock_actuel <= stock_minimum")
        for r in cur.fetchall():
            self.tree_alerts.insert("", tk.END, values=("Rupture Stock Aliment", r['designation'], f"Reste: {r['stock_actuel']} (Min: {r['stock_minimum']})", "STOCK BAS"))

        conn.close()

    # --- MODULE 1: ÉLEVEURS ---
    def build_eleveurs(self):
        frame = self.tab_eleveurs
        top_bar = ttk.Frame(frame, padding=5)
        top_bar.pack(fill=tk.X)

        ttk.Label(top_bar, text="Rechercher :").pack(side=tk.LEFT, padx=5)
        self.search_elv_var = tk.StringVar()
        self.search_elv_var.trace("w", lambda *args: self.load_eleveurs())
        ttk.Entry(top_bar, textvariable=self.search_elv_var, width=25).pack(side=tk.LEFT, padx=5)

        ttk.Button(top_bar, text="+ Nouveau Producteur", command=self.dialog_add_eleveur).pack(side=tk.RIGHT, padx=5)
        ttk.Button(top_bar, text="Exporter CSV", command=lambda: self.export_tree_to_csv(self.tree_eleveurs, "eleveurs.csv")).pack(side=tk.RIGHT, padx=5)

        cols = ("id", "code", "nom", "prenom", "commune", "wilaya", "phone", "exp_agrement", "exp_certif")
        self.tree_eleveurs = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")

        headers = {"id": "ID", "code": "Code", "nom": "Nom", "prenom": "Prénom", "commune": "Commune", "wilaya": "Wilaya", "phone": "Téléphone", "exp_agrement": "Exp. Agrément", "exp_certif": "Exp. Certificat"}
        for c, h in headers.items():
            self.tree_eleveurs.heading(c, text=h)
            self.tree_eleveurs.column(c, width=110)

        self.tree_eleveurs.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.load_eleveurs()

    def load_eleveurs(self):
        for item in self.tree_eleveurs.get_children():
            self.tree_eleveurs.delete(item)

        query = self.search_elv_var.get().strip().lower()
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM eleveurs WHERE lower(nom) LIKE ? OR lower(prenom) LIKE ? OR lower(code_eleveur) LIKE ?", 
                    (f"%{query}%", f"%{query}%", f"%{query}%"))
        for row in cur.fetchall():
            vals = (row["id"], row["code_eleveur"], row["nom"], row["prenom"], row["commune"], row["wilaya"], row["telephone"], row["agrement_expiration"], row["certificat_expiration"])
            self.tree_eleveurs.insert("", tk.END, values=vals)
        conn.close()

