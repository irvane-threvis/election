import os
import csv
import uuid
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timezone, timedelta
from io import BytesIO
import base64
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, send_from_directory,
    flash, Response
)

# --- Configuration de l'application Flask et des dossiers ---
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24).hex())
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
UPLOAD_DIR = os.path.join(BASE_DIR, 'static', 'uploads')

# --- Initialisation des fichiers CSV nécessaires à l'application ---
def init_env():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    files = {
        'elections.csv': ['id', 'title', 'start', 'end', 'active'],
        'candidats.csv': ['election_id', 'id', 'nom', 'aspirations', 'image'],
        'electeurs.csv': ['election_id', 'nom', 'prenom', 'email'],
        'votes.csv': ['election_id', 'email', 'id_candidat', 'horodatage']
    }
    for fname, headers in files.items():
        path = os.path.join(DATA_DIR, fname)
        if not os.path.exists(path):
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)

# --- Fonctions utilitaires pour manipuler les fichiers CSV ---
def load_csv(fname):
    path = os.path.join(DATA_DIR, fname)
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def append_csv(fname, row):
    path = os.path.join(DATA_DIR, fname)
    with open(path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if os.stat(path).st_size == 0:
            writer.writeheader()
        writer.writerow(row)

def update_csv(fname, rows):
    path = os.path.join(DATA_DIR, fname)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        # Si rows est vide, on écrit juste l'en-tête
        if not rows:
            headers = {
                'candidats.csv': ['election_id', 'id', 'nom', 'aspirations', 'image'],
                'electeurs.csv': ['election_id', 'nom', 'prenom', 'email'],
                'votes.csv': ['election_id', 'email', 'id_candidat', 'horodatage']
            }
            writer = csv.DictWriter(f, fieldnames=headers.get(fname, []))
            writer.writeheader()
            return
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

# --- Récupère l'élection active (celle dont le champ 'active' est à 'true') ---
def get_active_election():
    for e in load_csv('elections.csv'):
        if e.get('active') == 'true':
            return e
    return None

# --- Retourne l'heure actuelle en GMT (UTC) ---
def get_gmt_time():
    return datetime.now(timezone.utc)

# --- Formate une date ISO en format lisible (français, GMT) ---
def format_gmt_date(dt_str):
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.strftime('%d/%m/%Y %H:%M GMT')
    except:
        return dt_str

# --- Expose les fonctions utilitaires aux templates Jinja ---
app.jinja_env.globals.update(
    get_gmt_time=get_gmt_time,
    format_gmt_date=format_gmt_date
)

# --- Génère un graphique de progression des votes pour une élection ---
def generate_progress_chart(election_id):
    votes = [v for v in load_csv('votes.csv') if v.get('election_id') == election_id]
    if not votes:
        return
    candidats = [c for c in load_csv('candidats.csv') if c.get('election_id') == election_id]
    df = pd.DataFrame(votes)
    df['horodatage'] = pd.to_datetime(df['horodatage'])
    df.sort_values('horodatage', inplace=True)
    plt.figure(figsize=(10, 6))
    for c in candidats:
        cumul = (df['id_candidat'] == c.get('id')).cumsum()
        plt.plot(df['horodatage'], cumul, label=c.get('nom'), linewidth=2)
    plt.title('Progression des votes')
    plt.xlabel('Heure (GMT)')
    plt.ylabel('Votes cumulés')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(UPLOAD_DIR, 'progress.png'))
    plt.close()

# --- ROUTES PUBLIQUES ---

# Redirige la racine vers la page de vote
@app.route('/')
def home():
    return redirect(url_for('vote'))

# Page de vote (GET: affiche le formulaire, POST: enregistre le vote)
@app.route('/vote', methods=['GET', 'POST'])
def vote():
    active = get_active_election()
    now = get_gmt_time().isoformat()
    if not active:
        return render_template('vote_closed.html', message="Aucune élection en cours.", title="Fermé", now=get_gmt_time())
    if now < active.get('start', ''):
        return render_template('vote_closed.html', message=f"Vote débutera le {format_gmt_date(active.get('start', ''))}", title="À venir", now=get_gmt_time())
    if now > active.get('end', ''):
        return render_template('vote_closed.html', message=f"Vote terminé le {format_gmt_date(active.get('end', ''))}", title="Terminé", now=get_gmt_time())
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        electeurs = load_csv('electeurs.csv')
        # Vérifie si l'utilisateur a déjà voté
        if any(e.get('email') == email and e.get('election_id') == active.get('id') for e in electeurs):
            error = "Vous avez déjà voté."
            candidats = [c for c in load_csv('candidats.csv') if c.get('election_id') == active.get('id')]
            return render_template('vote.html', candidats=candidats, title=active.get('title'), error=error, now=get_gmt_time())
        # Vérifie que tous les champs sont remplis
        if not all(request.form.get(f) for f in ['nom', 'prenom', 'email', 'candidat']):
            error = "Tous les champs sont requis."
            candidats = [c for c in load_csv('candidats.csv') if c.get('election_id') == active.get('id')]
            return render_template('vote.html', candidats=candidats, title=active.get('title'), error=error, now=get_gmt_time())
        # Enregistre l'électeur et son vote
        append_csv('electeurs.csv', { 'election_id': active.get('id'), 'nom': request.form.get('nom'), 'prenom': request.form.get('prenom'), 'email': email })
        append_csv('votes.csv', { 'election_id': active.get('id'), 'email': email, 'id_candidat': request.form.get('candidat'), 'horodatage': now })
        # Enregistre l'ID de l'élection dans la session pour l'utilisateur
        session['user_election_id'] = active.get('id')
        return redirect(url_for('vote_success', candidate_id=request.form.get('candidat')))
    # Affiche le formulaire de vote
    candidats = [c for c in load_csv('candidats.csv') if c.get('election_id') == active.get('id')]
    return render_template('vote.html', candidats=candidats, title=active.get('title'), now=get_gmt_time())

# Page de succès après vote
@app.route('/vote/success')
def vote_success():
    active = get_active_election()
    now = get_gmt_time()
    cid = request.args.get('candidate_id')
    cand = next((c for c in load_csv('candidats.csv') if c.get('id') == cid and c.get('election_id') == active.get('id')), None)
    name = cand.get('nom', 'candidat') if cand else 'candidat'
    return render_template('vote_success.html', title=active.get('title'), candidate_name=name, now=now)

# Affiche les résultats globaux de l'élection active
@app.route('/results')
def results():
    active = get_active_election()
    now = get_gmt_time()
    if not active:
        return render_template('vote_closed.html', message="Pas de résultats.", title="N/A", now=now)
    votes = [v for v in load_csv('votes.csv') if v.get('election_id') == active.get('id')]
    if not votes:
        return render_template('results.html', no_data=True, title=active.get('title'), now=now)
    candidats = [c for c in load_csv('candidats.csv') if c.get('election_id') == active.get('id')]
    total = len(votes)
    counts = {c.get('id'): 0 for c in candidats}
    for v in votes:
        counts[v.get('id_candidat')] = counts.get(v.get('id_candidat'), 0) + 1
    summary = [ { 'nom': c.get('nom'), 'votes': counts.get(c.get('id'), 0), 'pourcentage': f"{counts.get(c.get('id'), 0)/total*100:.1f}%" } for c in candidats ]
    return render_template('results.html', summary=summary, total_votes=total, title=active.get('title'), now=now)

# Affiche les résultats personnalisés pour l'utilisateur (après vote)
@app.route('/results/user')
def user_results():
    election_id = session.get('user_election_id')
    if not election_id:
        return render_template('results.html', no_data=True, title="Aucun résultat", now=get_gmt_time())
    # Récupère l'élection correspondante
    election = next((e for e in load_csv('elections.csv') if e.get('id') == election_id), None)
    if not election:
        return render_template('results.html', no_data=True, title="Aucun résultat", now=get_gmt_time())
    votes = [v for v in load_csv('votes.csv') if v.get('election_id') == election_id]
    if not votes:
        return render_template('results.html', no_data=True, title=election.get('title'), now=get_gmt_time())
    candidats = [c for c in load_csv('candidats.csv') if c.get('election_id') == election_id]
    total = len(votes)
    counts = {c.get('id'): 0 for c in candidats}
    for v in votes:
        counts[v.get('id_candidat')] = counts.get(v.get('id_candidat'), 0) + 1
    summary = [ { 'nom': c.get('nom'), 'votes': counts.get(c.get('id'), 0), 'pourcentage': f"{counts.get(c.get('id'), 0)/total*100:.1f}%" } for c in candidats ]
    return render_template('results.html', summary=summary, total_votes=total, title=election.get('title'), now=get_gmt_time())

# --- ROUTES ADMIN ---

# Page de connexion admin
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin'):
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        if request.form.get('user')=='admin' and request.form.get('pwd')=='ComplexPassword123!':
            session.permanent = True
            session['admin'] = True
            flash('Connexion réussie','success')
            return redirect(url_for('admin_dashboard'))
        flash('Identifiants incorrects','danger')
    return render_template('admin_login.html')

# Déconnexion admin
@app.route('/admin/logout')
def admin_logout():
    session.clear()
    flash('Déconnexion','info')
    return redirect(url_for('admin_login'))

# Tableau de bord admin (création/sélection d'élection, ajout de candidats, etc.)
@app.route('/admin/dashboard', methods=['GET','POST'])
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    elections = load_csv('elections.csv')

    # --- Suppression automatique des votes/candidats/électeurs si l'élection est terminée ---
    active = get_active_election()
    now = get_gmt_time()
    if active and now.isoformat() > active.get('end', ''):
        update_csv('candidats.csv', [])
        update_csv('electeurs.csv', [])
        update_csv('votes.csv', [])
        flash("L'ancien vote a été supprimé car l'élection est terminée.", "info")

    # Gestion des actions POST (création, sélection, ajout candidat)
    if request.method == 'POST':
        if 'create_election' in request.form:
            try:
                start = datetime.fromisoformat(request.form.get('start', '')).astimezone(timezone.utc).isoformat()
                end = datetime.fromisoformat(request.form.get('end', '')).astimezone(timezone.utc).isoformat()
                if start >= end:
                    flash('La date de fin doit être après la date de début.', 'danger')
                else:
                    new_id = str(uuid.uuid4())
                    append_csv('elections.csv', {'id': new_id, 'title': request.form.get('title', ''), 'start': start, 'end': end, 'active': 'false'})
                    # Réinitialise les fichiers pour la nouvelle élection
                    update_csv('candidats.csv', [])
                    update_csv('electeurs.csv', [])
                    update_csv('votes.csv', [])
                    flash('Élection créée et anciennes données supprimées', 'success')
                    elections = load_csv('elections.csv')
            except Exception as e:
                flash('Format de date invalide', 'danger')
        elif 'select_election' in request.form:
            sel = request.form.get('election_id', '')
            for e in elections:
                e['active'] = 'true' if e.get('id') == sel else 'false'
            update_csv('elections.csv', elections)
            flash('Élection activée', 'success')
        elif 'add_candidat' in request.form:
            active = get_active_election()
            img = request.files.get('img_c')
            if img and img.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                cid = str(uuid.uuid4())
                fname = f"{cid}_{img.filename}"
                img.save(os.path.join(UPLOAD_DIR, fname))
                append_csv('candidats.csv', {'election_id': active.get('id'), 'id': cid, 'nom': request.form.get('nom_c'), 'aspirations': request.form.get('asp_c'), 'image': fname})
                flash('Candidat ajouté', 'success')

    active = get_active_election()
    candidats = [c for c in load_csv('candidats.csv') if active and c.get('election_id') == active.get('id')]
    votes_count = len([v for v in load_csv('votes.csv') if active and v.get('election_id') == active.get('id')])
    if active:
        generate_progress_chart(active.get('id'))
    return render_template('admin_dashboard.html', elections=elections, active=active, candidats=candidats, votes=votes_count, now=get_gmt_time())

# Affiche les résultats détaillés pour l'admin (tableau, graphiques)
@app.route('/admin/results')
def admin_results():
    if not session.get('admin'):
        return redirect(url_for('admin_dashboard'))
    active = get_active_election()
    now = get_gmt_time()
    if not active:
        flash('Pas d\'élection', 'warning')
        return redirect(url_for('admin_dashboard'))
    votes_list = load_csv('votes.csv')
    cand_list = load_csv('candidats.csv')
    elect_list = load_csv('electeurs.csv')
    votes_df = pd.DataFrame(votes_list)
    cand_df = pd.DataFrame(cand_list)
    elect_df = pd.DataFrame(elect_list)
    # Sécurité : vérifie la présence des colonnes
    if votes_df.empty or 'election_id' not in votes_df.columns:
        return render_template('results.html', no_data=True, title=active.get('title'), active_election=active, now=now)
    if cand_df.empty or 'id' not in cand_df.columns:
        return render_template('results.html', no_data=True, title=active.get('title'), active_election=active, now=now)
    if elect_df.empty or 'email' not in elect_df.columns:
        return render_template('results.html', no_data=True, title=active.get('title'), active_election=active, now=now)
    votes = votes_df[votes_df['election_id'] == active.get('id')]
    if votes.empty:
        return render_template('results.html', no_data=True, title=active.get('title'), active_election=active, now=now)
    # Fusionne les données pour obtenir les infos complètes sur chaque vote
    res = votes.merge(cand_df, left_on='id_candidat', right_on='id').merge(elect_df, on=['election_id', 'email'])
    buf = BytesIO()
    plt.figure(figsize=(12,8))
    res['nom_y'].value_counts().plot(kind='bar', title='Répartition des votes')
    plt.subplot(2,2,2)
    res['horodatage'] = pd.to_datetime(res['horodatage'])
    res['hour'] = res['horodatage'].dt.hour
    res.groupby(['hour','nom_y']).size().unstack().plot(marker='o', title='Votes par heure')
    plt.subplot(2,2,3)
    res['nom_y'].value_counts().plot(kind='pie', autopct='%1.1f%%', title='Pourcentage')
    plt.tight_layout()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close()
    img_data = base64.b64encode(buf.getvalue()).decode()
    table = res[['nom_y','prenom','email','horodatage','nom_x']].copy()
    table['horodatage'] = table['horodatage'].dt.strftime('%d/%m/%Y %H:%M GMT')
    table.columns = ['Électeur', 'Prénom', 'Email', 'Date/Heure (GMT)', 'Candidat']
    counts = res['nom_y'].value_counts().to_dict()
    total = len(votes)
    summary = [{'nom': n, 'votes': c, 'pourcentage': f"{c/total*100:.1f}%"} for n, c in counts.items()]
    return render_template('results.html', img_data=img_data, table_data=table.to_dict('records'), summary=summary, total_votes=total, title=active.get('title'), active_election=active, now=now, no_data=False)

# Export des résultats au format CSV pour l'admin
@app.route('/admin/export/csv')
def export_results_csv():
    if not session.get('admin'):
        return redirect(url_for('admin_dashboard'))
    active = get_active_election()
    now = get_gmt_time()
    votes_list = load_csv('votes.csv')
    cand_list = load_csv('candidats.csv')
    elect_list = load_csv('electeurs.csv')
    if not votes_list or not cand_list or not elect_list:
        flash("Aucune donnée à exporter.", "warning")
        return redirect(url_for('admin_results'))
    votes_df = pd.DataFrame(votes_list)
    cand_df = pd.DataFrame(cand_list)
    elect_df = pd.DataFrame(elect_list)
    if votes_df.empty or 'election_id' not in votes_df.columns:
        flash("Aucune donnée à exporter.", "warning")
        return redirect(url_for('admin_results'))
    df = votes_df.merge(cand_df, left_on='id_candidat', right_on='id').merge(elect_df, on=['election_id', 'email'])
    out = df[['election_id','nom_y','prenom','email','horodatage','nom_x']]
    out['horodatage'] = pd.to_datetime(out['horodatage']).dt.strftime('%d/%m/%Y %H:%M GMT')
    out.columns = ['ID Election','Nom Électeur','Prénom','Email','Date/Heure (GMT)','Candidat choisi']
    buf = BytesIO()
    out.to_csv(buf, index=False, encoding='utf-8-sig')
    buf.seek(0)
    return Response(buf, mimetype='text/csv', headers={'Content-disposition': f"attachment; filename=resultats_{active.get('title')}_{now.strftime('%Y%m%d')}.csv"})

# Sert les fichiers statiques (images, css, etc.)
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(os.path.join(BASE_DIR,'static'), filename)

# --- Point d'entrée principal ---
if __name__ == '__main__':
    init_env()  # Initialise les dossiers et fichiers CSV si besoin
    app.run(debug=True, host='0.0.0.0', port=5000)