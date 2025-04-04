from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os
from PyPDF2 import PdfReader  # For PDF scanning

app = Flask(__name__)
app.secret_key = 'secretkey'  # For session management and flashing messages
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///exam_paper.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = './uploads'  # Folder for uploaded files
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.String(500), nullable=False)
    marks = db.Column(db.Integer, nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    difficulty = db.Column(db.String(100), nullable=False)

# Home route (redirects to login)
@app.route('/')
def index():
    return redirect(url_for('login'))

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))

        flash('Invalid username or password. Please try again.', 'danger')
        return redirect(url_for('login'))

    return render_template('login.html')

# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already taken', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

# Dashboard route
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    questions = Question.query.all()
    total_marks = sum([q.marks for q in questions])
    total_questions = len(questions)
    return render_template('dashboard.html', total_marks=total_marks, total_questions=total_questions, questions=questions)

# Add Question route
@app.route('/add_question', methods=['POST'])
def add_question():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    question_text = request.form['question_text']
    marks = int(request.form['marks'])
    subject = request.form['subject']
    difficulty = request.form['difficulty']

    new_question = Question(question_text=question_text, marks=marks, subject=subject, difficulty=difficulty)
    db.session.add(new_question)
    db.session.commit()

    flash('Question added successfully!', 'success')
    return redirect(url_for('dashboard'))

# Edit Question route
@app.route('/edit_question/<int:question_id>', methods=['GET', 'POST'])
def edit_question(question_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    question = Question.query.get_or_404(question_id)

    if request.method == 'POST':
        question.question_text = request.form['question_text']
        question.marks = int(request.form['marks'])
        question.subject = request.form['subject']
        question.difficulty = request.form['difficulty']

        db.session.commit()
        flash('Question updated successfully!', 'success')
        return redirect(url_for('question_bank'))

    return render_template('edit_question.html', question=question)

# Delete Question route
@app.route('/delete_question/<int:question_id>', methods=['POST'])
def delete_question(question_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    question = Question.query.get_or_404(question_id)
    db.session.delete(question)
    db.session.commit()

    flash('Question removed successfully!', 'success')
    return redirect(url_for('question_bank'))

# Generate Exam Paper route
@app.route('/generate_exam_paper', methods=['POST'])
def generate_exam_paper():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    flash('Exam Paper Generated Successfully!', 'success')
    return redirect(url_for('dashboard'))

# Create Exam route
@app.route('/create_exam', methods=['GET', 'POST'])
def create_exam():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    return render_template('create_exam.html')

# Route to view Question Bank
@app.route('/question_bank', methods=['GET'])
def question_bank():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    questions = Question.query.all()  # Fetch all questions from the database
    return render_template('question_bank.html', questions=questions)

# Route to upload and scan PDF
@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if 'pdf_file' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('dashboard'))

    file = request.files['pdf_file']
    if file.filename == '':
        flash('No selected file', 'danger')
        return redirect(url_for('dashboard'))

    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        extracted_questions = extract_questions_from_pdf(filepath)
        os.remove(filepath)  # Remove the file after processing

        for q_text in extracted_questions:
            new_question = Question(
                question_text=q_text,
                marks=1,  # Default marks for extracted questions
                subject="General",
                difficulty="Medium"
            )
            db.session.add(new_question)
        db.session.commit()

        flash(f'Successfully added {len(extracted_questions)} questions from the PDF.', 'success')
        return redirect(url_for('dashboard'))

# Function to extract questions from a PDF file
def extract_questions_from_pdf(filepath):
    reader = PdfReader(filepath)
    text = ""
    for page in reader.pages:
        text += page.extract_text()

    questions = [line.strip() for line in text.splitlines() if line.strip()]
    return questions

# Logout route
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)