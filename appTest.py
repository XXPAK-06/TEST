from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///medical.db'
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# เพิ่ม filter สำหรับแปลง JSON string
@app.template_filter('from_json')
def from_json(value):
    return json.loads(value)

# โมเดลผู้ใช้งาน
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    national_id = db.Column(db.String(13), unique=True, nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    medical_records = db.relationship('MedicalRecord', backref='user', lazy=True)

# โมเดลประวัติการตรวจ
class MedicalRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    symptoms = db.Column(db.Text, nullable=False)
    diagnosis = db.Column(db.Text, nullable=False)
    recommendations = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# เส้นทางหน้าหลัก
@app.route('/')
def index():
    return render_template('index.html')

# เส้นทางการลงทะเบียน
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        national_id = request.form.get('national_id')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        
        if User.query.filter_by(national_id=national_id).first():
            flash('เลขบัตรประชาชนนี้ถูกใช้งานแล้ว', 'error')
            return redirect(url_for('register'))
        
        new_user = User(national_id=national_id, first_name=first_name, last_name=last_name)
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user)
        return redirect(url_for('diagnosis'))
    
    return render_template('register.html')

# เส้นทางการเข้าสู่ระบบ
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        national_id = request.form.get('national_id')
        user = User.query.filter_by(national_id=national_id).first()
        
        if user:
            login_user(user)
            return redirect(url_for('diagnosis'))
        else:
            flash('ไม่พบข้อมูลผู้ใช้', 'error')
    
    return render_template('login.html')

# เส้นทางการวินิจฉัย
@app.route('/diagnosis', methods=['GET', 'POST'])
@login_required
def diagnosis():
    if request.method == 'POST':
        symptoms = request.form.getlist('symptoms')
        additional_info = request.form.get('additional_info', '')
        
        # ตรวจสอบว่ามีการเลือกอาการหรือไม่
        if not symptoms:
            flash('กรุณาเลือกอาการอย่างน้อย 3 อาการ', 'error')
            return redirect(url_for('diagnosis'))
        
        # วิเคราะห์โรคจากอาการ
        diagnosis_result = analyze_symptoms(symptoms, additional_info)
        
        # บันทึกผลการวินิจฉัย
        record = MedicalRecord(
            user_id=current_user.id,
            symptoms=json.dumps(symptoms),
            diagnosis=json.dumps(diagnosis_result['diseases']),
            recommendations=json.dumps(diagnosis_result['recommendations'])
        )
        db.session.add(record)
        db.session.commit()
        
        return render_template('result.html', 
                            diagnosis=diagnosis_result['diseases'],
                            recommendations=diagnosis_result['recommendations'])
    
    return render_template('diagnosis.html')

# เส้นทางประวัติการตรวจ
@app.route('/history')
@login_required
def history():
    records = MedicalRecord.query.filter_by(user_id=current_user.id).order_by(MedicalRecord.created_at.desc()).all()
    return render_template('history.html', records=records)

# เส้นทางออกจากระบบ
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

def analyze_symptoms(symptoms, additional_info):
    # ตัวอย่างการวิเคราะห์โรค (ในที่นี้เป็นตัวอย่างอย่างง่าย)
    diseases_database = {
        'ปวดศีรษะ': ['ไมเกรน', 'ความดันโลหิตสูง', 'ความเครียด'],
        'ไข้': ['ไข้หวัด', 'ไข้เลือดออก', 'โควิด-19'],
        'ไอ': ['หวัด', 'ภูมิแพ้', 'โควิด-19'],
        'เจ็บคอ': ['คออักเสบ', 'ไข้หวัด', 'โควิด-19'],
        'คัดจมูก': ['ภูมิแพ้', 'ไข้หวัด', 'ไซนัสอักเสบ'],
        'ปวดท้อง': ['กระเพาะอาหารอักเสบ', 'ลำไส้อักเสบ', 'อาหารเป็นพิษ'],
        'ท้องเสีย': ['อาหารเป็นพิษ', 'ลำไส้อักเสบ', 'แบคทีเรียในลำไส้'],
        'อ่อนเพลีย': ['โลหิตจาง', 'พักผ่อนไม่เพียงพอ', 'ขาดวิตามิน'],
        'เวียนศีรษะ': ['ความดันต่ำ', 'หินปูนในหูชั้นในผิดปกติ', 'ภาวะขาดน้ำ'],
        'ผื่นคัน': ['ภูมิแพ้ผิวหนัง', 'ลมพิษ', 'ผื่นแพ้'],
    }
    
    possible_diseases = []
    for symptom in symptoms:
        if symptom in diseases_database:
            possible_diseases.extend(diseases_database[symptom])
    
    # นับความถี่ของแต่ละโรค
    from collections import Counter
    disease_counts = Counter(possible_diseases)
    top_diseases = disease_counts.most_common(3)
    
    # สร้างคำแนะนำ
    recommendations = []
    severity = len(symptoms)
    
    if severity >= 5:
        recommendations.append("ควรไปพบแพทย์โดยเร็ว เนื่องจากมีอาการหลายอย่างร่วมกัน")
    elif severity >= 3:
        recommendations.append("ควรพักผ่อนให้เพียงพอและสังเกตอาการ หากอาการไม่ดีขึ้นภายใน 2-3 วัน ควรไปพบแพทย์")
    else:
        recommendations.append("สามารถดูแลรักษาตัวเองที่บ้านได้ โดย:")
        recommendations.append("- พักผ่อนให้เพียงพอ")
        recommendations.append("- ดื่มน้ำมากๆ")
        recommendations.append("- รับประทานยาตามอาการ")
        recommendations.append("- หากอาการไม่ดีขึ้นภายใน 1 สัปดาห์ ควรไปพบแพทย์")
    
    return {
        'diseases': [{'name': disease, 'probability': count/len(symptoms) * 100} 
                    for disease, count in top_diseases],
        'recommendations': recommendations
    }

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
