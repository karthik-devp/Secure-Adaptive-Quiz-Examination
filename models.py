"""
models.py - Database layer for Secure Adaptive Quiz Engine
Uses SQLite with helper functions for CRUD operations.
"""

import sqlite3
import os
import sys
from werkzeug.security import generate_password_hash

# On Vercel (Linux serverless), only /tmp is writable
# On local (Windows/dev), use project directory
if os.environ.get('VERCEL') or (sys.platform == 'linux' and not os.access(os.path.dirname(os.path.abspath(__file__)), os.W_OK)):
    DATABASE = '/tmp/quiz_engine.db'
else:
    DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'quiz_engine.db')


def get_db():
    """Get a database connection with Row factory."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Initialize database tables."""
    conn = get_db()
    cursor = conn.cursor()

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student'
        )
    ''')

    # Quizzes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            total_marks INTEGER NOT NULL DEFAULT 0,
            time_limit INTEGER NOT NULL DEFAULT 30
        )
    ''')

    # Questions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            option1 TEXT NOT NULL,
            option2 TEXT NOT NULL,
            option3 TEXT NOT NULL,
            option4 TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            difficulty TEXT NOT NULL DEFAULT 'medium',
            marks INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE
        )
    ''')

    # Results table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            quiz_id INTEGER NOT NULL,
            score INTEGER NOT NULL DEFAULT 0,
            total INTEGER NOT NULL DEFAULT 0,
            percentage REAL NOT NULL DEFAULT 0,
            correct_count INTEGER NOT NULL DEFAULT 0,
            wrong_count INTEGER NOT NULL DEFAULT 0,
            time_taken INTEGER NOT NULL DEFAULT 0,
            easy_correct INTEGER DEFAULT 0,
            easy_total INTEGER DEFAULT 0,
            medium_correct INTEGER DEFAULT 0,
            medium_total INTEGER DEFAULT 0,
            hard_correct INTEGER DEFAULT 0,
            hard_total INTEGER DEFAULT 0,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
        )
    ''')

    conn.commit()
    conn.close()


def seed_data():
    """Seed the database with sample admin, student, quizzes, and questions."""
    conn = get_db()
    cursor = conn.cursor()

    # Check if data already exists
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    # --- Create Admin and Student ---
    admin_pw = generate_password_hash('admin123')
    student_pw = generate_password_hash('student123')

    cursor.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                   ('Admin User', 'admin@quiz.com', admin_pw, 'admin'))
    cursor.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                   ('John Student', 'student@quiz.com', student_pw, 'student'))

    # --- Create Quizzes ---
    cursor.execute("INSERT INTO quizzes (title, total_marks, time_limit) VALUES (?, ?, ?)",
                   ('Python Fundamentals', 50, 15))
    cursor.execute("INSERT INTO quizzes (title, total_marks, time_limit) VALUES (?, ?, ?)",
                   ('Web Development Basics', 40, 10))
    cursor.execute("INSERT INTO quizzes (title, total_marks, time_limit) VALUES (?, ?, ?)",
                   ('Data Structures & Algorithms', 60, 20))

    # --- Python Fundamentals Questions (Quiz 1) ---
    python_questions = [
        # Easy
        ('What is the output of print(2 + 3)?', '5', '23', '6', 'Error', '5', 'easy', 2),
        ('Which keyword is used to define a function in Python?', 'func', 'define', 'def', 'function', 'def', 'easy', 2),
        ('What data type is the result of: type(3.14)?', 'int', 'float', 'str', 'double', 'float', 'easy', 2),
        ('How do you start a comment in Python?', '//', '#', '/*', '--', '#', 'easy', 2),
        ('What is the correct file extension for Python files?', '.py', '.python', '.pt', '.pyt', '.py', 'easy', 2),
        # Medium
        ('What does len([1, 2, 3]) return?', '2', '3', '4', '1', '3', 'medium', 3),
        ('Which method adds an element to the end of a list?', 'insert()', 'add()', 'append()', 'push()', 'append()', 'medium', 3),
        ('What is the output of "Hello"[1]?', 'H', 'e', 'l', 'o', 'e', 'medium', 3),
        ('What does the "pass" statement do?', 'Exits loop', 'Does nothing', 'Skips iteration', 'Raises error', 'Does nothing', 'medium', 3),
        ('Which of these is a mutable data type?', 'tuple', 'str', 'list', 'int', 'list', 'medium', 3),
        # Hard
        ('What is the output of bool("")?', 'True', 'False', 'None', 'Error', 'False', 'hard', 5),
        ('What does *args do in a function definition?', 'Keyword args', 'Variable positional args', 'Default args', 'No args', 'Variable positional args', 'hard', 5),
        ('What is a decorator in Python?', 'A loop construct', 'A function modifier', 'An error handler', 'A class type', 'A function modifier', 'hard', 5),
        ('What is the time complexity of dictionary lookup?', 'O(n)', 'O(log n)', 'O(1)', 'O(n²)', 'O(1)', 'hard', 5),
        ('Which module is used for regular expressions?', 'regex', 're', 'regexp', 'match', 're', 'hard', 5),
    ]
    for q in python_questions:
        cursor.execute(
            "INSERT INTO questions (quiz_id, question_text, option1, option2, option3, option4, correct_answer, difficulty, marks) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)",
            q)

    # --- Web Development Questions (Quiz 2) ---
    web_questions = [
        ('What does HTML stand for?', 'Hyper Text Markup Language', 'High Tech Modern Language', 'Hyper Transfer Markup Language', 'Home Tool Markup Language', 'Hyper Text Markup Language', 'easy', 2),
        ('Which tag is used for the largest heading?', '<h6>', '<heading>', '<h1>', '<head>', '<h1>', 'easy', 2),
        ('What does CSS stand for?', 'Computer Style Sheets', 'Cascading Style Sheets', 'Creative Style System', 'Colorful Style Sheets', 'Cascading Style Sheets', 'easy', 2),
        ('Which property changes text color in CSS?', 'font-color', 'text-color', 'color', 'foreground', 'color', 'easy', 2),
        ('Which HTML element is used for links?', '<link>', '<a>', '<href>', '<url>', '<a>', 'easy', 2),
        ('What is the default position value in CSS?', 'relative', 'absolute', 'static', 'fixed', 'static', 'medium', 3),
        ('Which event fires when a page finishes loading?', 'onchange', 'onload', 'onclick', 'onready', 'onload', 'medium', 3),
        ('What does "DOM" stand for?', 'Document Object Model', 'Data Output Manager', 'Display Object Method', 'Document Order Mode', 'Document Object Model', 'medium', 3),
        ('Which CSS property creates rounded corners?', 'corner-radius', 'border-radius', 'round-corner', 'edge-radius', 'border-radius', 'medium', 3),
        ('What is Flexbox used for?', 'Database queries', 'Layout alignment', 'Image editing', 'Server routing', 'Layout alignment', 'hard', 4),
        ('Which HTTP method is idempotent?', 'POST', 'GET', 'PATCH', 'None', 'GET', 'hard', 4),
        ('What is the purpose of a CDN?', 'Database management', 'Content delivery', 'Code deployment', 'Version control', 'Content delivery', 'hard', 4),
    ]
    for q in web_questions:
        cursor.execute(
            "INSERT INTO questions (quiz_id, question_text, option1, option2, option3, option4, correct_answer, difficulty, marks) VALUES (2, ?, ?, ?, ?, ?, ?, ?, ?)",
            q)

    # --- DSA Questions (Quiz 3) ---
    dsa_questions = [
        ('What is an array?', 'Collection of elements', 'A single variable', 'A function', 'A loop', 'Collection of elements', 'easy', 2),
        ('What is LIFO?', 'Queue principle', 'Stack principle', 'Tree principle', 'Graph principle', 'Stack principle', 'easy', 2),
        ('Which data structure uses FIFO?', 'Stack', 'Queue', 'Tree', 'Graph', 'Queue', 'easy', 2),
        ('What is the head of a linked list?', 'Last node', 'First node', 'Middle node', 'Null node', 'First node', 'easy', 2),
        ('What is a leaf node?', 'Root node', 'Node with no children', 'Node with one child', 'Any node', 'Node with no children', 'easy', 2),
        ('What is the time complexity of binary search?', 'O(n)', 'O(log n)', 'O(n²)', 'O(1)', 'O(log n)', 'medium', 3),
        ('Which sorting algorithm is divide-and-conquer?', 'Bubble Sort', 'Merge Sort', 'Selection Sort', 'Insertion Sort', 'Merge Sort', 'medium', 3),
        ('What is a hash collision?', 'Empty bucket', 'Two keys same index', 'Overflow error', 'Memory leak', 'Two keys same index', 'medium', 4),
        ('What is BFS?', 'Depth-first search', 'Breadth-first search', 'Binary search', 'Best-first search', 'Breadth-first search', 'medium', 3),
        ('What is the worst case of quicksort?', 'O(n)', 'O(n log n)', 'O(n²)', 'O(log n)', 'O(n²)', 'medium', 3),
        ('What is a balanced BST?', 'All leaves same level', 'Height diff ≤ 1', 'Complete binary tree', 'Full binary tree', 'Height diff ≤ 1', 'hard', 5),
        ('What is dynamic programming?', 'Recursive only', 'Optimal substructure + overlapping', 'Greedy approach', 'Brute force', 'Optimal substructure + overlapping', 'hard', 5),
        ('What is amortized analysis?', 'Worst case', 'Average over sequence', 'Best case', 'Space analysis', 'Average over sequence', 'hard', 5),
        ('What is a spanning tree?', 'Any subgraph', 'Connected acyclic subgraph', 'Complete graph', 'Directed graph', 'Connected acyclic subgraph', 'hard', 5),
        ('Dijkstra fails with?', 'Large graphs', 'Negative weights', 'Undirected graphs', 'Dense graphs', 'Negative weights', 'hard', 5),
    ]
    for q in dsa_questions:
        cursor.execute(
            "INSERT INTO questions (quiz_id, question_text, option1, option2, option3, option4, correct_answer, difficulty, marks) VALUES (3, ?, ?, ?, ?, ?, ?, ?, ?)",
            q)

    conn.commit()
    conn.close()
    print("[OK] Database seeded with sample data.")
