from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import MySQLdb
from MySQLdb.cursors import DictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here-change-in-production')

# MySQL Configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',  # CHANGE THIS
    'database': 'notetask_db'
}

def get_db_connection():
    """Create a new database connection"""
    return MySQLdb.connect(**DB_CONFIG)

def get_db_cursor(connection):
    """Get a DictCursor from connection"""
    return connection.cursor(DictCursor)

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Validate inputs
        if not all([first_name, last_name, email, password]):
            flash('All fields are required!', 'error')
            return render_template('register.html')
        
        try:
            db = get_db_connection()
            cursor = get_db_cursor(db)
            
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            
            if user:
                flash('Email already exists!', 'error')
                cursor.close()
                db.close()
                return render_template('register.html')
            
            hashed_password = generate_password_hash(password)
            cursor.execute("INSERT INTO users (first_name, last_name, email, password_hash) VALUES (%s, %s, %s, %s)",
                          (first_name, last_name, email, hashed_password))
            db.commit()
            cursor.close()
            db.close()
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            print(f"Registration error: {str(e)}")
            import traceback
            traceback.print_exc()
            flash(f'An error occurred. Please try again.', 'error')
            return render_template('register.html')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('Please enter both email and password!', 'error')
            return render_template('login.html')
        
        try:
            db = get_db_connection()
            cursor = get_db_cursor(db)
            
            cursor.execute("SELECT id, first_name, last_name, email, password_hash FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            
            cursor.close()
            db.close()
            
            print(f"User found: {user is not None}")
            if user:
                print(f"User type: {type(user)}")
                print(f"User keys: {user.keys() if isinstance(user, dict) else 'Not a dict'}")
            
            if user and isinstance(user, dict) and 'password_hash' in user:
                if check_password_hash(user['password_hash'], password):
                    session['user_id'] = user['id']
                    session['user_name'] = user['first_name']
                    flash('Login successful!', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash('Invalid email or password!', 'error')
            else:
                flash('Invalid email or password!', 'error')
                
        except Exception as e:
            print(f"Login error: {str(e)}")
            import traceback
            traceback.print_exc()
            flash(f'An error occurred. Please try again.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        db = get_db_connection()
        cursor = get_db_cursor(db)
        
        # Get stats
        cursor.execute("SELECT COUNT(*) as count FROM notes WHERE user_id = %s", (session['user_id'],))
        notes_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM tasks WHERE user_id = %s AND status = 'active'", (session['user_id'],))
        active_tasks = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM tasks WHERE user_id = %s AND status = 'completed'", (session['user_id'],))
        completed_tasks = cursor.fetchone()['count']
        
        # Get recent notes
        cursor.execute("SELECT * FROM notes WHERE user_id = %s ORDER BY created_at DESC LIMIT 3", (session['user_id'],))
        recent_notes = cursor.fetchall()
        
        # Get today's tasks
        cursor.execute("SELECT * FROM tasks WHERE user_id = %s ORDER BY created_at DESC LIMIT 4", (session['user_id'],))
        today_tasks = cursor.fetchall()
        
        cursor.close()
        db.close()
        
        return render_template('dashboard.html', 
                             notes_count=notes_count,
                             active_tasks=active_tasks,
                             completed_tasks=completed_tasks,
                             recent_notes=recent_notes,
                             today_tasks=today_tasks)
    except Exception as e:
        print(f"Dashboard error: {str(e)}")
        import traceback
        traceback.print_exc()
        return render_template('dashboard.html', 
                             notes_count=0,
                             active_tasks=0,
                             completed_tasks=0,
                             recent_notes=[],
                             today_tasks=[])

@app.route('/notes')
@login_required
def notes():
    try:
        db = get_db_connection()
        cursor = get_db_cursor(db)
        cursor.execute("SELECT * FROM notes WHERE user_id = %s ORDER BY created_at DESC", (session['user_id'],))
        all_notes = cursor.fetchall()
        cursor.close()
        db.close()
        return render_template('notes.html', notes=all_notes)
    except Exception as e:
        print(f"Notes error: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'error')
        return render_template('notes.html', notes=[])

@app.route('/notes/create', methods=['POST'])
@login_required
def create_note():
    title = request.form.get('title')
    content = request.form.get('content')
    category = request.form.get('category')
    
    try:
        db = get_db_connection()
        cursor = get_db_cursor(db)
        cursor.execute("INSERT INTO notes (user_id, title, content, category) VALUES (%s, %s, %s, %s)",
                      (session['user_id'], title, content, category))
        db.commit()
        cursor.close()
        db.close()
        flash('Note created successfully!', 'success')
    except Exception as e:
        print(f"Create note error: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'error')
    
    return redirect(url_for('notes'))

@app.route('/notes/update/<int:note_id>', methods=['POST'])
@login_required
def update_note(note_id):
    title = request.form.get('title')
    content = request.form.get('content')
    category = request.form.get('category')
    
    try:
        db = get_db_connection()
        cursor = get_db_cursor(db)
        cursor.execute("UPDATE notes SET title = %s, content = %s, category = %s WHERE id = %s AND user_id = %s",
                      (title, content, category, note_id, session['user_id']))
        db.commit()
        cursor.close()
        db.close()
        flash('Note updated successfully!', 'success')
    except Exception as e:
        print(f"Update note error: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'error')
    
    return redirect(url_for('notes'))

@app.route('/notes/delete/<int:note_id>', methods=['POST'])
@login_required
def delete_note(note_id):
    try:
        db = get_db_connection()
        cursor = get_db_cursor(db)
        cursor.execute("DELETE FROM notes WHERE id = %s AND user_id = %s", (note_id, session['user_id']))
        db.commit()
        cursor.close()
        db.close()
        flash('Note deleted successfully!', 'success')
    except Exception as e:
        print(f"Delete note error: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'error')
    
    return redirect(url_for('notes'))

@app.route('/tasks')
@login_required
def tasks():
    try:
        db = get_db_connection()
        cursor = get_db_cursor(db)
        cursor.execute("SELECT * FROM tasks WHERE user_id = %s ORDER BY due_date ASC", (session['user_id'],))
        all_tasks = cursor.fetchall()
        cursor.close()
        db.close()
        return render_template('tasks.html', tasks=all_tasks)
    except Exception as e:
        print(f"Tasks error: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'error')
        return render_template('tasks.html', tasks=[])

@app.route('/tasks/create', methods=['POST'])
@login_required
def create_task():
    title = request.form.get('title')
    description = request.form.get('description')
    priority = request.form.get('priority')
    category = request.form.get('category')
    due_date = request.form.get('due_date')
    
    try:
        db = get_db_connection()
        cursor = get_db_cursor(db)
        cursor.execute("INSERT INTO tasks (user_id, title, description, priority, category, due_date) VALUES (%s, %s, %s, %s, %s, %s)",
                      (session['user_id'], title, description, priority, category, due_date if due_date else None))
        db.commit()
        cursor.close()
        db.close()
        flash('Task created successfully!', 'success')
    except Exception as e:
        print(f"Create task error: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'error')
    
    return redirect(url_for('tasks'))

@app.route('/tasks/update/<int:task_id>', methods=['POST'])
@login_required
def update_task(task_id):
    status = request.form.get('status', 'active')
    
    try:
        db = get_db_connection()
        cursor = get_db_cursor(db)
        cursor.execute("UPDATE tasks SET status = %s WHERE id = %s AND user_id = %s", 
                      (status, task_id, session['user_id']))
        db.commit()
        cursor.close()
        db.close()
        flash('Task updated successfully!', 'success')
    except Exception as e:
        print(f"Update task error: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'error')
    
    return redirect(url_for('tasks'))

@app.route('/tasks/update-full/<int:task_id>', methods=['POST'])
@login_required
def update_task_full(task_id):
    title = request.form.get('title')
    description = request.form.get('description')
    priority = request.form.get('priority')
    category = request.form.get('category')
    due_date = request.form.get('due_date')
    
    try:
        db = get_db_connection()
        cursor = get_db_cursor(db)
        cursor.execute("""UPDATE tasks 
                         SET title = %s, description = %s, priority = %s, category = %s, due_date = %s 
                         WHERE id = %s AND user_id = %s""",
                      (title, description, priority, category, due_date if due_date else None, task_id, session['user_id']))
        db.commit()
        cursor.close()
        db.close()
        flash('Task updated successfully!', 'success')
    except Exception as e:
        print(f"Update task error: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'error')
    
    return redirect(url_for('tasks'))

@app.route('/tasks/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    try:
        db = get_db_connection()
        cursor = get_db_cursor(db)
        cursor.execute("DELETE FROM tasks WHERE id = %s AND user_id = %s", (task_id, session['user_id']))
        db.commit()
        cursor.close()
        db.close()
        flash('Task deleted successfully!', 'success')
    except Exception as e:
        print(f"Delete task error: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'error')
    
    return redirect(url_for('tasks'))

@app.route('/calendar')
@login_required
def calendar():
    try:
        db = get_db_connection()
        cursor = get_db_cursor(db)
        cursor.execute("SELECT * FROM events WHERE user_id = %s ORDER BY start_date ASC", (session['user_id'],))
        all_events = cursor.fetchall()
        
        # Get tasks with due dates for calendar integration
        cursor.execute("SELECT id, title, due_date, priority, category, status FROM tasks WHERE user_id = %s AND due_date IS NOT NULL ORDER BY due_date ASC", (session['user_id'],))
        tasks_with_dates = cursor.fetchall()
        
        cursor.close()
        db.close()
        
        return render_template('calendar.html', events=all_events, tasks=tasks_with_dates)
    except Exception as e:
        print(f"Calendar error: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'error')
        return render_template('calendar.html', events=[], tasks=[])

@app.route('/events/create', methods=['POST'])
@login_required
def create_event():
    title = request.form.get('title')
    description = request.form.get('description')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    category = request.form.get('category')
    
    try:
        db = get_db_connection()
        cursor = get_db_cursor(db)
        cursor.execute("INSERT INTO events (user_id, title, description, start_date, end_date, category) VALUES (%s, %s, %s, %s, %s, %s)",
                      (session['user_id'], title, description, start_date, end_date, category))
        db.commit()
        cursor.close()
        db.close()
        flash('Event created successfully!', 'success')
    except Exception as e:
        print(f"Create event error: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'error')
    
    return redirect(url_for('calendar'))

if __name__ == '__main__':
    app.run(debug=True)