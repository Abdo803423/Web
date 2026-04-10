from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3, os, datetime

app = Flask(__name__)
app.secret_key = 'skillbridge-secret-2025'

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'zip', 'png', 'jpg', 'jpeg', 'fig', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── DATABASE ──────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect('skillbridge.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ("student","company")),
            bio TEXT DEFAULT "",
            points INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            points INTEGER NOT NULL,
            deadline TEXT NOT NULL,
            tags TEXT DEFAULT "",
            status TEXT DEFAULT "open",
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(company_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            file_path TEXT,
            link TEXT DEFAULT "",
            notes TEXT DEFAULT "",
            score INTEGER DEFAULT NULL,
            status TEXT DEFAULT "pending",
            feedback TEXT DEFAULT "",
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(task_id) REFERENCES tasks(id),
            FOREIGN KEY(student_id) REFERENCES users(id)
        );
    ''')
    db.commit()

    # Seed demo data if empty
    cur = db.execute('SELECT COUNT(*) FROM users')
    if cur.fetchone()[0] == 0:
        companies = [
            ('EcoShop', 'eco@ecoshop.com', generate_password_hash('demo123'), 'company'),
            ('Café Social', 'cafe@social.com', generate_password_hash('demo123'), 'company'),
            ('TechFlow', 'tech@techflow.com', generate_password_hash('demo123'), 'company'),
            ('GreenBrand', 'green@brand.com', generate_password_hash('demo123'), 'company'),
        ]
        for c in companies:
            db.execute('INSERT INTO users (name,email,password,role) VALUES (?,?,?,?)', c)
        db.execute('INSERT INTO users (name,email,password,role,points) VALUES (?,?,?,?,?)',
                   ('أحمد كريم', 'ahmed@student.com', generate_password_hash('demo123'), 'student', 840))
        db.commit()

        # Seed tasks
        cur = db.execute('SELECT id FROM users WHERE email=?', ('eco@ecoshop.com',))
        eco_id = cur.fetchone()[0]
        cur2 = db.execute('SELECT id FROM users WHERE email=?', ('cafe@social.com',))
        cafe_id = cur2.fetchone()[0]
        cur3 = db.execute('SELECT id FROM users WHERE email=?', ('tech@techflow.com',))
        tech_id = cur3.fetchone()[0]
        cur4 = db.execute('SELECT id FROM users WHERE email=?', ('green@brand.com',))
        green_id = cur4.fetchone()[0]

        tasks = [
            (eco_id, 'إعادة تصميم واجهة التطبيق', 'أعد تصميم واجهة تطبيق EcoShop المحمول بأسلوب عصري وصديق للبيئة. يشمل التسليم نظام ألوان جديد ومكتبة مكونات ونموذج تفاعلي.', 'design', 'متوسط', 80, '2025-05-15', 'Figma,UI/UX,Prototyping'),
            (cafe_id, 'استراتيجية السوشيال ميديا', 'أنشئ تقويم محتوى لمدة 30 يوماً لكافيه محلي، يتضمن نصوص المنشورات واستراتيجية الهاشتاق وخطة التفاعل.', 'marketing', 'سهل', 60, '2025-05-20', 'محتوى,تسويق,Strategy'),
            (tech_id, 'تكامل REST API', 'ابنِ تكاملاً بين داشبورد TechFlow الداخلي وأدوات تحليلات طرف ثالث مع توثيق كامل.', 'dev', 'صعب', 100, '2025-05-25', 'Node.js,REST API,Analytics'),
            (green_id, 'هوية بصرية كاملة', 'أنشئ نظام هوية بصرية متكامل يشمل شعار، دليل خطوط، لوحة ألوان، وإرشادات الاستخدام.', 'design', 'صعب', 90, '2025-05-10', 'Branding,Illustrator,Typography'),
            (tech_id, 'داشبورد تحليل البيانات', 'صمم وابنِ داشبورد تحليلات تفاعلي لفريق DataMinds الداخلي باستخدام بيانات حقيقية.', 'data', 'متوسط', 85, '2025-05-30', 'Python,Data Viz,Tableau'),
        ]
        db.executemany('INSERT INTO tasks (company_id,title,description,category,difficulty,points,deadline,tags) VALUES (?,?,?,?,?,?,?,?)', tasks)
        db.commit()

    db.close()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('سجّل دخولك أولاً', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def role_required(role):
    from functools import wraps
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get('role') != role:
                flash('غير مصرح لك بالوصول', 'error')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated
    return decorator

# ── ROUTES ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    db = get_db()
    tasks = db.execute('''
        SELECT t.*, u.name as company_name
        FROM tasks t JOIN users u ON t.company_id=u.id
        WHERE t.status="open" ORDER BY t.created_at DESC LIMIT 6
    ''').fetchall()
    stats = {
        'tasks': db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0],
        'students': db.execute('SELECT COUNT(*) FROM users WHERE role="student"').fetchone()[0],
        'companies': db.execute('SELECT COUNT(*) FROM users WHERE role="company"').fetchone()[0],
        'submissions': db.execute('SELECT COUNT(*) FROM submissions').fetchone()[0],
    }
    db.close()
    return render_template('index.html', tasks=tasks, stats=stats)

# ── AUTH ──────────────────────────────────────────────────────────────────────

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        role = request.form['role']

        if not name or not email or not password or role not in ('student','company'):
            flash('يرجى ملء جميع الحقول بشكل صحيح', 'error')
            return redirect(url_for('register'))

        db = get_db()
        existing = db.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()
        if existing:
            flash('البريد الإلكتروني مستخدم بالفعل', 'error')
            db.close()
            return redirect(url_for('register'))

        hashed = generate_password_hash(password)
        db.execute('INSERT INTO users (name,email,password,role) VALUES (?,?,?,?)',
                   (name, email, hashed, role))
        db.commit()
        user = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        db.close()

        session['user_id'] = user['id']
        session['name'] = user['name']
        session['role'] = user['role']
        flash(f'مرحباً {name}! تم إنشاء حسابك بنجاح 🎉', 'success')
        return redirect(url_for('dashboard_student') if role == 'student' else url_for('dashboard_company'))

    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        db.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['name'] = user['name']
            session['role'] = user['role']
            flash(f'أهلاً {user["name"]}! 👋', 'success')
            return redirect(url_for('dashboard_student') if user['role'] == 'student' else url_for('dashboard_company'))

        flash('البريد الإلكتروني أو كلمة المرور غير صحيحة', 'error')
        return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('تم تسجيل الخروج بنجاح', 'success')
    return redirect(url_for('index'))

# ── TASKS ─────────────────────────────────────────────────────────────────────

@app.route('/tasks')
def tasks():
    cat = request.args.get('cat', 'all')
    db = get_db()
    if cat == 'all':
        tasks = db.execute('''SELECT t.*,u.name as company_name FROM tasks t
            JOIN users u ON t.company_id=u.id WHERE t.status="open"
            ORDER BY t.created_at DESC''').fetchall()
    else:
        tasks = db.execute('''SELECT t.*,u.name as company_name FROM tasks t
            JOIN users u ON t.company_id=u.id WHERE t.status="open" AND t.category=?
            ORDER BY t.created_at DESC''', (cat,)).fetchall()
    db.close()
    return render_template('tasks.html', tasks=tasks, active_cat=cat)

@app.route('/tasks/<int:task_id>')
def task_detail(task_id):
    db = get_db()
    task = db.execute('''SELECT t.*,u.name as company_name,u.email as company_email
        FROM tasks t JOIN users u ON t.company_id=u.id WHERE t.id=?''', (task_id,)).fetchone()
    if not task:
        db.close()
        flash('المهمة غير موجودة', 'error')
        return redirect(url_for('tasks'))

    submissions_count = db.execute('SELECT COUNT(*) FROM submissions WHERE task_id=?', (task_id,)).fetchone()[0]
    already_submitted = False
    if 'user_id' in session and session['role'] == 'student':
        already_submitted = db.execute(
            'SELECT id FROM submissions WHERE task_id=? AND student_id=?',
            (task_id, session['user_id'])).fetchone() is not None
    db.close()
    return render_template('task_detail.html', task=task,
                           submissions_count=submissions_count,
                           already_submitted=already_submitted)

# ── SUBMIT TASK ───────────────────────────────────────────────────────────────

@app.route('/submit/<int:task_id>', methods=['POST'])
@login_required
def submit_task(task_id):
    if session['role'] != 'student':
        flash('فقط الطلاب يمكنهم تسليم المهام', 'error')
        return redirect(url_for('task_detail', task_id=task_id))

    db = get_db()
    existing = db.execute('SELECT id FROM submissions WHERE task_id=? AND student_id=?',
                          (task_id, session['user_id'])).fetchone()
    if existing:
        flash('سبق وسلّمت هذه المهمة', 'error')
        db.close()
        return redirect(url_for('task_detail', task_id=task_id))

    link = request.form.get('link', '').strip()
    notes = request.form.get('notes', '').strip()
    file_path = None

    if 'file' in request.files:
        file = request.files['file']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(f"{session['user_id']}_{task_id}_{file.filename}")
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

    db.execute('INSERT INTO submissions (task_id,student_id,file_path,link,notes) VALUES (?,?,?,?,?)',
               (task_id, session['user_id'], file_path, link, notes))
    db.commit()
    db.close()
    flash('✅ تم إرسال تسليمك بنجاح! ستصلك نتيجة التقييم قريباً.', 'success')
    return redirect(url_for('dashboard_student'))

# ── STUDENT DASHBOARD ──────────────────────────────────────────────────────────

@app.route('/dashboard/student')
@login_required
def dashboard_student():
    if session['role'] != 'student':
        return redirect(url_for('dashboard_company'))
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    submissions = db.execute('''
        SELECT s.*,t.title,t.points,t.category,u.name as company_name
        FROM submissions s
        JOIN tasks t ON s.task_id=t.id
        JOIN users u ON t.company_id=u.id
        WHERE s.student_id=? ORDER BY s.submitted_at DESC
    ''', (session['user_id'],)).fetchall()
    open_tasks = db.execute('''SELECT t.*,u.name as company_name FROM tasks t
        JOIN users u ON t.company_id=u.id WHERE t.status="open"
        ORDER BY t.created_at DESC LIMIT 4''').fetchall()
    db.close()
    return render_template('dashboard_student.html', user=user,
                           submissions=submissions, open_tasks=open_tasks)

# ── COMPANY DASHBOARD ──────────────────────────────────────────────────────────

@app.route('/dashboard/company')
@login_required
def dashboard_company():
    if session['role'] != 'company':
        return redirect(url_for('dashboard_student'))
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    my_tasks = db.execute('''SELECT t.*,
        (SELECT COUNT(*) FROM submissions s WHERE s.task_id=t.id) as sub_count
        FROM tasks t WHERE t.company_id=? ORDER BY t.created_at DESC
    ''', (session['user_id'],)).fetchall()
    pending_subs = db.execute('''
        SELECT s.*,t.title,u.name as student_name,u.email as student_email
        FROM submissions s
        JOIN tasks t ON s.task_id=t.id
        JOIN users u ON s.student_id=u.id
        WHERE t.company_id=? AND s.status="pending"
        ORDER BY s.submitted_at DESC
    ''', (session['user_id'],)).fetchall()
    db.close()
    return render_template('dashboard_company.html', user=user,
                           my_tasks=my_tasks, pending_subs=pending_subs)

# ── POST TASK (Company) ────────────────────────────────────────────────────────

@app.route('/tasks/new', methods=['GET','POST'])
@login_required
def new_task():
    if session['role'] != 'company':
        flash('فقط الشركات يمكنها نشر المهام', 'error')
        return redirect(url_for('tasks'))

    if request.method == 'POST':
        title = request.form['title'].strip()
        description = request.form['description'].strip()
        category = request.form['category']
        difficulty = request.form['difficulty']
        points = int(request.form['points'])
        deadline = request.form['deadline']
        tags = request.form['tags'].strip()

        db = get_db()
        db.execute('''INSERT INTO tasks (company_id,title,description,category,difficulty,points,deadline,tags)
            VALUES (?,?,?,?,?,?,?,?)''',
            (session['user_id'], title, description, category, difficulty, points, deadline, tags))
        db.commit()
        db.close()
        flash('✅ تم نشر المهمة بنجاح!', 'success')
        return redirect(url_for('dashboard_company'))

    return render_template('new_task.html')

# ── REVIEW SUBMISSION ─────────────────────────────────────────────────────────

@app.route('/review/<int:sub_id>', methods=['POST'])
@login_required
def review_submission(sub_id):
    if session['role'] != 'company':
        return jsonify({'error': 'Unauthorized'}), 403

    score = int(request.form['score'])
    feedback = request.form.get('feedback', '').strip()
    status = 'approved' if score >= 50 else 'rejected'

    db = get_db()
    sub = db.execute('SELECT s.*,t.company_id,t.points FROM submissions s JOIN tasks t ON s.task_id=t.id WHERE s.id=?', (sub_id,)).fetchone()
    if not sub or sub['company_id'] != session['user_id']:
        db.close()
        flash('غير مصرح لك', 'error')
        return redirect(url_for('dashboard_company'))

    db.execute('UPDATE submissions SET score=?,feedback=?,status=? WHERE id=?',
               (score, feedback, status, sub_id))
    if status == 'approved':
        earned = int(sub['points'] * score / 100)
        db.execute('UPDATE users SET points=points+? WHERE id=?', (earned, sub['student_id']))
    db.commit()
    db.close()
    flash('✅ تم تقييم التسليم بنجاح!', 'success')
    return redirect(url_for('dashboard_company'))

# ── PORTFOLIO ─────────────────────────────────────────────────────────────────

@app.route('/portfolio')
def portfolio():
    db = get_db()
    approved = db.execute('''
        SELECT s.*,t.title,t.category,t.tags,u.name as student_name,c.name as company_name
        FROM submissions s
        JOIN tasks t ON s.task_id=t.id
        JOIN users u ON s.student_id=u.id
        JOIN users c ON t.company_id=c.id
        WHERE s.status="approved" ORDER BY s.score DESC
    ''').fetchall()
    top_students = db.execute('''SELECT name,points,level FROM users WHERE role="student"
        ORDER BY points DESC LIMIT 5''').fetchall()
    db.close()
    return render_template('portfolio.html', approved=approved, top_students=top_students)

# ── PROFILE ───────────────────────────────────────────────────────────────────

@app.route('/profile', methods=['GET','POST'])
@login_required
def profile():
    db = get_db()
    if request.method == 'POST':
        name = request.form['name'].strip()
        bio = request.form['bio'].strip()
        db.execute('UPDATE users SET name=?,bio=? WHERE id=?', (name, bio, session['user_id']))
        db.commit()
        session['name'] = name
        flash('✅ تم تحديث بياناتك', 'success')
    user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    db.close()
    return render_template('profile.html', user=user)

# ── API ───────────────────────────────────────────────────────────────────────

@app.route('/api/tasks')
def api_tasks():
    db = get_db()
    tasks = db.execute('''SELECT t.*,u.name as company_name FROM tasks t
        JOIN users u ON t.company_id=u.id WHERE t.status="open"''').fetchall()
    db.close()
    return jsonify([dict(t) for t in tasks])

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
