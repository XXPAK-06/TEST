from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import json
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///medical.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    national_id = db.Column(db.String(13), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    diagnoses = db.relationship('Diagnosis', backref='user', lazy=True)

class Diagnosis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    symptoms = db.Column(db.Text, nullable=False)
    diagnosis_results = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    severity = db.Column(db.String(20), nullable=False)
    recommendations = db.Column(db.Text, nullable=False)

# Load disease database
with open('diseases.json', 'r', encoding='utf-8') as f:
    DISEASES_DB = json.load(f)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        national_id = request.form.get('national_id')
        full_name = request.form.get('full_name')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        if User.query.filter_by(national_id=national_id).first():
            flash('National ID already registered')
            return redirect(url_for('register'))
        
        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            national_id=national_id,
            full_name=full_name
        )
        db.session.add(user)
        db.session.commit()
        
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('diagnosis'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/diagnosis', methods=['GET', 'POST'])
@login_required
def diagnosis():
    if request.method == 'POST':
        symptoms = request.form.getlist('symptoms')
        additional_info = request.form.get('additional_info')
        
        # Analyze symptoms and calculate probabilities
        results = analyze_symptoms(symptoms, additional_info)
        
        # Save diagnosis
        diagnosis = Diagnosis(
            user_id=current_user.id,
            symptoms=json.dumps(symptoms),
            diagnosis_results=json.dumps(results),
            severity=determine_severity(results),
            recommendations=generate_recommendations(results)
        )
        db.session.add(diagnosis)
        db.session.commit()
        
        return render_template('results.html', results=results)
    
    return render_template('diagnosis.html', symptoms=get_all_symptoms())

@app.route('/history')
@login_required
def history():
    diagnoses = Diagnosis.query.filter_by(user_id=current_user.id).order_by(Diagnosis.created_at.desc()).all()
    return render_template('history.html', diagnoses=diagnoses)

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        return redirect(url_for('home'))
    users = User.query.all()
    diagnoses = Diagnosis.query.all()
    return render_template('admin.html', users=users, diagnoses=diagnoses)

def analyze_symptoms(symptoms, additional_info):
    # Implement symptom analysis logic here
    results = []
    for disease in DISEASES_DB:
        match_score = calculate_match_score(symptoms, disease['symptoms'])
        if match_score > 0.3:  # Threshold for potential matches
            results.append({
                'disease': disease['name'],
                'probability': match_score,
                'severity': disease['severity'],
                'recommendations': disease['recommendations']
            })
    
    results.sort(key=lambda x: x['probability'], reverse=True)
    return results[:3]  # Return top 3 matches

def calculate_match_score(user_symptoms, disease_symptoms):
    # Implement matching algorithm here
    matched = set(user_symptoms) & set(disease_symptoms)
    return len(matched) / max(len(user_symptoms), len(disease_symptoms))

def determine_severity(results):
    if not results:
        return 'LOW'
    max_severity = max(r['severity'] for r in results)
    return max_severity

def generate_recommendations(results):
    if not results:
        return "Please consult a healthcare professional for proper diagnosis."
    
    recommendations = []
    for result in results:
        recommendations.extend(result['recommendations'])
    return json.dumps(recommendations)

def get_all_symptoms():
    symptoms = set()
    for disease in DISEASES_DB:
        symptoms.update(disease['symptoms'])
    return sorted(list(symptoms))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
