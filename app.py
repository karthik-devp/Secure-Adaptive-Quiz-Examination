"""
app.py - Main Flask application for Secure Adaptive Quiz Engine
Handles authentication, admin CRUD, adaptive quiz engine, and result visualization.
"""

import os
import csv
import io
import random
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, Response
)
from werkzeug.security import generate_password_hash, check_password_hash

from models import get_db, init_db, seed_data

# ──────────────────────────── App Configuration ────────────────────────────
app = Flask(__name__)
# Use a fixed secret key (required for Vercel — os.urandom resets on cold start)
app.secret_key = os.environ.get('SECRET_KEY', 'quiz-engine-secret-key-change-in-production-2024')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Auto-initialize DB on each request (Vercel /tmp is ephemeral between cold starts)
_db_initialized = False

@app.before_request
def ensure_db():
    global _db_initialized
    if not _db_initialized:
        init_db()
        seed_data()
        _db_initialized = True


# ──────────────────────────── Auth Decorators ──────────────────────────────
def login_required(f):
    """Require login for a route."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Require admin role for a route."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'warning')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('student_dashboard'))
        return f(*args, **kwargs)
    return decorated


# ──────────────────────────── Authentication Routes ────────────────────────
@app.route('/')
def index():
    """Redirect to appropriate dashboard or login."""
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Please fill in all fields.', 'danger')
            return render_template('login.html')

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']
            session['role'] = user['role']
            flash(f'Welcome back, {user["name"]}!', 'success')
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid email or password.', 'danger')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handle student registration."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not all([name, email, password, confirm]):
            flash('Please fill in all fields.', 'danger')
            return render_template('register.html')

        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('register.html')

        conn = get_db()
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            conn.close()
            flash('Email already registered.', 'danger')
            return render_template('register.html')

        hashed = generate_password_hash(password)
        conn.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                     (name, email, hashed, 'student'))
        conn.commit()
        conn.close()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/logout')
def logout():
    """Clear session and logout."""
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))


# ──────────────────────────── Admin Routes ─────────────────────────────────
@app.route('/admin')
@admin_required
def admin_dashboard():
    """Admin dashboard with overview cards."""
    conn = get_db()
    quiz_count = conn.execute("SELECT COUNT(*) FROM quizzes").fetchone()[0]
    student_count = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'student'").fetchone()[0]
    question_count = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    result_count = conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]

    quizzes = conn.execute("SELECT * FROM quizzes ORDER BY id DESC").fetchall()
    recent_results = conn.execute("""
        SELECT r.*, u.name as student_name, q.title as quiz_title
        FROM results r
        JOIN users u ON r.user_id = u.id
        JOIN quizzes q ON r.quiz_id = q.id
        ORDER BY r.date DESC LIMIT 10
    """).fetchall()
    conn.close()

    return render_template('admin_dashboard.html',
                           quiz_count=quiz_count,
                           student_count=student_count,
                           question_count=question_count,
                           result_count=result_count,
                           quizzes=quizzes,
                           recent_results=recent_results)


@app.route('/admin/quiz/new', methods=['GET', 'POST'])
@admin_required
def create_quiz():
    """Create a new quiz."""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        total_marks = request.form.get('total_marks', 0, type=int)
        time_limit = request.form.get('time_limit', 30, type=int)

        if not title:
            flash('Quiz title is required.', 'danger')
            return render_template('quiz_form.html', quiz=None, questions=[])

        conn = get_db()
        cursor = conn.execute("INSERT INTO quizzes (title, total_marks, time_limit) VALUES (?, ?, ?)",
                              (title, total_marks, time_limit))
        quiz_id = cursor.lastrowid
        conn.commit()
        conn.close()
        flash('Quiz created! Now add questions.', 'success')
        return redirect(url_for('edit_quiz', quiz_id=quiz_id))

    return render_template('quiz_form.html', quiz=None, questions=[])


@app.route('/admin/quiz/<int:quiz_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_quiz(quiz_id):
    """Edit an existing quiz and its questions."""
    conn = get_db()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        total_marks = request.form.get('total_marks', 0, type=int)
        time_limit = request.form.get('time_limit', 30, type=int)

        conn.execute("UPDATE quizzes SET title = ?, total_marks = ?, time_limit = ? WHERE id = ?",
                     (title, total_marks, time_limit, quiz_id))
        conn.commit()
        flash('Quiz updated successfully.', 'success')

    quiz = conn.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
    questions = conn.execute("SELECT * FROM questions WHERE quiz_id = ? ORDER BY id", (quiz_id,)).fetchall()
    conn.close()

    if not quiz:
        flash('Quiz not found.', 'danger')
        return redirect(url_for('admin_dashboard'))

    return render_template('quiz_form.html', quiz=quiz, questions=questions)


@app.route('/admin/quiz/<int:quiz_id>/delete', methods=['POST'])
@admin_required
def delete_quiz(quiz_id):
    """Delete a quiz and all its questions."""
    conn = get_db()
    conn.execute("DELETE FROM questions WHERE quiz_id = ?", (quiz_id,))
    conn.execute("DELETE FROM results WHERE quiz_id = ?", (quiz_id,))
    conn.execute("DELETE FROM quizzes WHERE id = ?", (quiz_id,))
    conn.commit()
    conn.close()
    flash('Quiz deleted successfully.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/quiz/<int:quiz_id>/question/add', methods=['POST'])
@admin_required
def add_question(quiz_id):
    """Add a question to a quiz."""
    question_text = request.form.get('question_text', '').strip()
    option1 = request.form.get('option1', '').strip()
    option2 = request.form.get('option2', '').strip()
    option3 = request.form.get('option3', '').strip()
    option4 = request.form.get('option4', '').strip()
    correct_answer = request.form.get('correct_answer', '').strip()
    difficulty = request.form.get('difficulty', 'medium')
    marks = request.form.get('marks', 1, type=int)

    if not all([question_text, option1, option2, option3, option4, correct_answer]):
        flash('All question fields are required.', 'danger')
        return redirect(url_for('edit_quiz', quiz_id=quiz_id))

    conn = get_db()
    conn.execute("""
        INSERT INTO questions (quiz_id, question_text, option1, option2, option3, option4, correct_answer, difficulty, marks)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (quiz_id, question_text, option1, option2, option3, option4, correct_answer, difficulty, marks))

    # Update total marks
    total = conn.execute("SELECT SUM(marks) FROM questions WHERE quiz_id = ?", (quiz_id,)).fetchone()[0] or 0
    conn.execute("UPDATE quizzes SET total_marks = ? WHERE id = ?", (total, quiz_id))
    conn.commit()
    conn.close()
    flash('Question added successfully.', 'success')
    return redirect(url_for('edit_quiz', quiz_id=quiz_id))


@app.route('/admin/question/<int:question_id>/delete', methods=['POST'])
@admin_required
def delete_question(question_id):
    """Delete a question."""
    conn = get_db()
    q = conn.execute("SELECT quiz_id FROM questions WHERE id = ?", (question_id,)).fetchone()
    if q:
        quiz_id = q['quiz_id']
        conn.execute("DELETE FROM questions WHERE id = ?", (question_id,))
        total = conn.execute("SELECT SUM(marks) FROM questions WHERE quiz_id = ?", (quiz_id,)).fetchone()[0] or 0
        conn.execute("UPDATE quizzes SET total_marks = ? WHERE id = ?", (total, quiz_id))
        conn.commit()
        conn.close()
        flash('Question deleted.', 'success')
        return redirect(url_for('edit_quiz', quiz_id=quiz_id))
    conn.close()
    flash('Question not found.', 'danger')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/results')
@admin_required
def admin_results():
    """View all student results."""
    conn = get_db()
    results = conn.execute("""
        SELECT r.*, u.name as student_name, u.email as student_email, q.title as quiz_title
        FROM results r
        JOIN users u ON r.user_id = u.id
        JOIN quizzes q ON r.quiz_id = q.id
        ORDER BY r.date DESC
    """).fetchall()
    conn.close()
    return render_template('admin_results.html', results=results)


@app.route('/admin/results/export')
@admin_required
def export_results():
    """Export all results as CSV."""
    conn = get_db()
    results = conn.execute("""
        SELECT r.id, u.name, u.email, q.title, r.score, r.total, r.percentage,
               r.correct_count, r.wrong_count, r.time_taken, r.date
        FROM results r
        JOIN users u ON r.user_id = u.id
        JOIN quizzes q ON r.quiz_id = q.id
        ORDER BY r.date DESC
    """).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Student Name', 'Email', 'Quiz', 'Score', 'Total',
                     'Percentage', 'Correct', 'Wrong', 'Time (sec)', 'Date'])
    for r in results:
        writer.writerow([r['id'], r['name'], r['email'], r['title'], r['score'],
                         r['total'], f"{r['percentage']:.1f}%", r['correct_count'],
                         r['wrong_count'], r['time_taken'], r['date']])

    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = 'attachment; filename=quiz_results.csv'
    return response


# ──────────────────────────── Student Routes ───────────────────────────────
@app.route('/dashboard')
@login_required
def student_dashboard():
    """Student dashboard with available quizzes and past results."""
    conn = get_db()
    quizzes = conn.execute("""
        SELECT q.*, COUNT(qu.id) as question_count
        FROM quizzes q
        LEFT JOIN questions qu ON q.id = qu.quiz_id
        GROUP BY q.id
        ORDER BY q.id DESC
    """).fetchall()

    my_results = conn.execute("""
        SELECT r.*, q.title as quiz_title
        FROM results r
        JOIN quizzes q ON r.quiz_id = q.id
        WHERE r.user_id = ?
        ORDER BY r.date DESC
    """, (session['user_id'],)).fetchall()
    conn.close()

    return render_template('student_dashboard.html', quizzes=quizzes, results=my_results)


# ──────────────────────────── Adaptive Quiz Engine ─────────────────────────
@app.route('/quiz/<int:quiz_id>/start')
@login_required
def start_quiz(quiz_id):
    """Start an adaptive quiz session."""
    conn = get_db()
    quiz = conn.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
    if not quiz:
        conn.close()
        flash('Quiz not found.', 'danger')
        return redirect(url_for('student_dashboard'))

    question_count = conn.execute("SELECT COUNT(*) FROM questions WHERE quiz_id = ?", (quiz_id,)).fetchone()[0]
    if question_count == 0:
        conn.close()
        flash('This quiz has no questions yet.', 'warning')
        return redirect(url_for('student_dashboard'))

    # Initialize quiz session
    session['quiz_id'] = quiz_id
    session['quiz_start_time'] = datetime.now().isoformat()
    session['current_difficulty'] = 'medium'
    session['answered_questions'] = []
    session['answers'] = {}
    session['question_difficulties'] = {}

    conn.close()
    return render_template('quiz.html', quiz=quiz, total_questions=question_count)


@app.route('/quiz/next_question', methods=['POST'])
@login_required
def next_question():
    """Get the next adaptive question based on performance."""
    quiz_id = session.get('quiz_id')
    if not quiz_id:
        return jsonify({'error': 'No active quiz session'}), 400

    current_difficulty = session.get('current_difficulty', 'medium')
    answered = session.get('answered_questions', [])

    conn = get_db()

    # Try to get a question at current difficulty that hasn't been answered
    placeholders = ','.join(['?'] * len(answered)) if answered else '0'
    query = f"""
        SELECT * FROM questions
        WHERE quiz_id = ? AND difficulty = ? AND id NOT IN ({placeholders})
        ORDER BY RANDOM() LIMIT 1
    """
    params = [quiz_id, current_difficulty] + answered
    question = conn.execute(query, params).fetchone()

    # If no question at current difficulty, try other difficulties
    if not question:
        query = f"""
            SELECT * FROM questions
            WHERE quiz_id = ? AND id NOT IN ({placeholders})
            ORDER BY RANDOM() LIMIT 1
        """
        params = [quiz_id] + answered
        question = conn.execute(query, params).fetchone()

    conn.close()

    if not question:
        return jsonify({'done': True})

    # Shuffle options
    options = [question['option1'], question['option2'], question['option3'], question['option4']]
    random.shuffle(options)

    total_questions = len(answered) + 1
    conn2 = get_db()
    total_available = conn2.execute("SELECT COUNT(*) FROM questions WHERE quiz_id = ?", (quiz_id,)).fetchone()[0]
    conn2.close()

    return jsonify({
        'done': False,
        'question': {
            'id': question['id'],
            'text': question['question_text'],
            'options': options,
            'difficulty': question['difficulty'],
            'marks': question['marks'],
            'number': total_questions,
            'total': total_available
        }
    })


@app.route('/quiz/answer', methods=['POST'])
@login_required
def submit_answer():
    """Submit an answer and adapt difficulty."""
    data = request.get_json()
    question_id = data.get('question_id')
    answer = data.get('answer')

    if not question_id or not answer:
        return jsonify({'error': 'Missing data'}), 400

    conn = get_db()
    question = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
    conn.close()

    if not question:
        return jsonify({'error': 'Question not found'}), 404

    is_correct = answer == question['correct_answer']

    # Track answered questions
    answered = session.get('answered_questions', [])
    answered.append(question_id)
    session['answered_questions'] = answered

    # Track answers
    answers = session.get('answers', {})
    answers[str(question_id)] = {
        'selected': answer,
        'correct': question['correct_answer'],
        'is_correct': is_correct,
        'marks': question['marks'],
        'difficulty': question['difficulty']
    }
    session['answers'] = answers

    # Track difficulty of each question asked
    question_difficulties = session.get('question_difficulties', {})
    question_difficulties[str(question_id)] = question['difficulty']
    session['question_difficulties'] = question_difficulties

    # Adaptive difficulty adjustment
    current = session.get('current_difficulty', 'medium')
    if is_correct:
        # Increase difficulty
        if current == 'easy':
            session['current_difficulty'] = 'medium'
        elif current == 'medium':
            session['current_difficulty'] = 'hard'
    else:
        # Decrease difficulty
        if current == 'hard':
            session['current_difficulty'] = 'medium'
        elif current == 'medium':
            session['current_difficulty'] = 'easy'

    session.modified = True

    return jsonify({
        'correct': is_correct,
        'correct_answer': question['correct_answer'],
        'new_difficulty': session['current_difficulty']
    })


@app.route('/quiz/submit', methods=['POST'])
@login_required
def submit_quiz():
    """Submit the entire quiz and calculate results."""
    quiz_id = session.get('quiz_id')
    if not quiz_id:
        flash('No active quiz session.', 'danger')
        return redirect(url_for('student_dashboard'))

    answers = session.get('answers', {})
    start_time = session.get('quiz_start_time')

    # Calculate time taken
    time_taken = 0
    if start_time:
        start = datetime.fromisoformat(start_time)
        time_taken = int((datetime.now() - start).total_seconds())

    # Calculate score
    score = 0
    total = 0
    correct_count = 0
    wrong_count = 0
    easy_correct = 0
    easy_total = 0
    medium_correct = 0
    medium_total = 0
    hard_correct = 0
    hard_total = 0

    for qid, ans in answers.items():
        marks = ans.get('marks', 1)
        total += marks
        diff = ans.get('difficulty', 'medium')

        if diff == 'easy':
            easy_total += 1
        elif diff == 'medium':
            medium_total += 1
        else:
            hard_total += 1

        if ans.get('is_correct'):
            score += marks
            correct_count += 1
            if diff == 'easy':
                easy_correct += 1
            elif diff == 'medium':
                medium_correct += 1
            else:
                hard_correct += 1
        else:
            wrong_count += 1

    percentage = (score / total * 100) if total > 0 else 0

    # Save result to database
    conn = get_db()
    cursor = conn.execute("""
        INSERT INTO results (user_id, quiz_id, score, total, percentage, correct_count, wrong_count,
                             time_taken, easy_correct, easy_total, medium_correct, medium_total,
                             hard_correct, hard_total)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (session['user_id'], quiz_id, score, total, percentage, correct_count, wrong_count,
          time_taken, easy_correct, easy_total, medium_correct, medium_total, hard_correct, hard_total))
    result_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Clear quiz session
    for key in ['quiz_id', 'quiz_start_time', 'current_difficulty', 'answered_questions',
                'answers', 'question_difficulties']:
        session.pop(key, None)

    return redirect(url_for('view_result', result_id=result_id))


@app.route('/result/<int:result_id>')
@login_required
def view_result(result_id):
    """View quiz result with charts."""
    conn = get_db()
    result = conn.execute("""
        SELECT r.*, q.title as quiz_title, u.name as student_name
        FROM results r
        JOIN quizzes q ON r.quiz_id = q.id
        JOIN users u ON r.user_id = u.id
        WHERE r.id = ?
    """, (result_id,)).fetchone()
    conn.close()

    if not result:
        flash('Result not found.', 'danger')
        return redirect(url_for('student_dashboard'))

    # Only allow viewing own results (or admin)
    if result['user_id'] != session.get('user_id') and session.get('role') != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('student_dashboard'))

    return render_template('result.html', result=result)


# ──────────────────────────── Initialize & Run ─────────────────────────────
if __name__ == '__main__':
    init_db()
    seed_data()
    print("\n" + "=" * 60)
    print("  Secure Adaptive Quiz Engine")
    print("  Running at: http://localhost:5000")
    print("=" * 60)
    print("  Admin Login:   admin@quiz.com / admin123")
    print("  Student Login: student@quiz.com / student123")
    print("=" * 60 + "\n")
    app.run(debug=True, port=5000)
