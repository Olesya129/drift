from flask import Flask, render_template, request, redirect, url_for, flash, session
import psycopg2
from psycopg2.extras import NamedTupleCursor
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'super_secret_key'  # Для сессий и флеш-сообщений

# Конфигурация базы данных
DB_CONFIG = {
    'dbname': 'drift',
    'user': 'postgres',
    'password': '123',
    'host': 'localhost',
    'port': '5432'
}

def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("Подключение к базе данных успешно!")
        return conn
    except Exception as e:
        print(f"Ошибка подключения к базе данных: {e}")
        return None

@app.route('/')
def index():
    status_filter = request.args.get('status', 'запланировано')
    if status_filter not in ['запланировано', 'завершено', 'отменено']:
        status_filter = 'запланировано'
    
    conn = get_db_connection()
    if conn is None:
        return "Ошибка подключения к базе данных", 500
    
    cur = conn.cursor(cursor_factory=NamedTupleCursor)  # Используем NamedTupleCursor
    cur.execute("""
        SELECT DISTINCT e.event_id, e.title, e.date, l.name, l.city, e.photo_url, e.description
        FROM Events e
        JOIN Locations l ON e.location_id = l.location_id
        WHERE e.status = %s
        ORDER BY e.date
    """, (status_filter,))
    events = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('index.html', events=events, user=session.get('user'), status_filter=status_filter)

@app.route('/event/<int:event_id>', methods=['GET', 'POST'])
def event_detail(event_id):
    conn = get_db_connection()
    if conn is None:
        flash('Ошибка подключения к базе данных', 'danger')
        return redirect(url_for('index'))
    cur = conn.cursor(cursor_factory=NamedTupleCursor)  # Используем NamedTupleCursor
    cur.execute("""
        SELECT e.event_id, e.title, e.date, l.name, l.city, e.photo_url, e.description, e.spectator_price, e.participant_price, e.status
        FROM Events e
        JOIN Locations l ON e.location_id = l.location_id
        WHERE e.event_id = %s
    """, (event_id,))
    event = cur.fetchone()
    if not event:
        cur.close()
        conn.close()
        flash('Мероприятие не найдено', 'danger')
        return redirect(url_for('index'))

    # Выборка отзывов
    cur.execute("""
        SELECT r.rating, r.comment, u.username, r.created_at, r.review_id
        FROM Reviews r
        JOIN Users u ON r.user_id = u.user_id
        WHERE r.event_id = %s
        ORDER BY r.created_at DESC
    """, (event_id,))
    reviews = cur.fetchall()

    user_registered = False
    registration_role = None
    can_review = False
    if 'user' in session:
        user_id = session['user']['user_id']
        cur.execute("""
            SELECT role FROM Registrations
            WHERE user_id = %s AND event_id = %s AND status = 'зарегистрировано'
        """, (user_id, event_id))
        registration = cur.fetchone()
        if registration:
            user_registered = True
            registration_role = registration.role
            can_review = True

    # Обработка добавления отзыва
    if request.method == 'POST' and can_review:
        rating = int(request.form['rating'])
        comment = request.form['comment']
        cur.execute("""
            INSERT INTO Reviews (user_id, event_id, rating, comment, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (session['user']['user_id'], event_id, rating, comment, datetime.now()))
        conn.commit()
        flash('Спасибо за ваш отзыв!', 'success')
        cur.close()
        conn.close()
        return redirect(url_for('event_detail', event_id=event_id))

    cur.close()
    conn.close()
    return render_template('event_detail.html', event=event, user=session.get('user'), user_registered=user_registered, registration_role=registration_role, reviews=reviews, can_review=can_review)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form.get('role', 'участник')
        
        conn = get_db_connection()
        if conn is None:
            flash('Ошибка подключения к базе данных', 'danger')
            return redirect(url_for('register'))
        
        try:
            cur = conn.cursor(cursor_factory=NamedTupleCursor)  # Используем NamedTupleCursor
            cur.execute(
                "INSERT INTO Users (username, email, password, role, city) VALUES (%s, %s, %s, %s, %s) RETURNING user_id",
                (username, email, password, role, 'Москва')
            )
            user_id = cur.fetchone().user_id
            conn.commit()
            cur.close()
            conn.close()
            flash('Регистрация прошла успешно!', 'success')
            session['user'] = {'user_id': user_id, 'username': username, 'role': role}
            return redirect(url_for('index'))
        except psycopg2.IntegrityError as e:
            conn.rollback()
            cur.close()
            conn.close()
            flash('Имя пользователя или email уже существуют', 'danger')
            return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        if conn is None:
            flash('Ошибка подключения к базе данных', 'danger')
            return redirect(url_for('login'))
        
        cur = conn.cursor(cursor_factory=NamedTupleCursor)  # Используем NamedTupleCursor
        cur.execute(
            "SELECT user_id, username, role FROM Users WHERE email = %s AND password = %s",
            (email, password)
        )
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user:
            session['user'] = {'user_id': user.user_id, 'username': user.username, 'role': user.role}
            flash(f'Добро пожаловать, {user.username}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверный email или пароль', 'danger')
            return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/event/<int:event_id>/register/<string:role>', methods=['POST'])
def register_event(event_id, role):
    if 'user' not in session:
        flash('Пожалуйста, войдите, чтобы зарегистрироваться на мероприятие', 'danger')
        return redirect(url_for('login'))
    
    if role not in ['зритель', 'участник']:
        flash('Неверная роль для регистрации', 'danger')
        return redirect(url_for('event_detail', event_id=event_id))
    
    user_id = session['user']['user_id']
    conn = get_db_connection()
    if conn is None:
        flash('Ошибка подключения к базе данных', 'danger')
        return redirect(url_for('index'))
    
    try:
        cur = conn.cursor(cursor_factory=NamedTupleCursor)  # Используем NamedTupleCursor
        price_field = 'participant_price' if role == 'участник' else 'spectator_price'
        cur.execute(f"SELECT {price_field} FROM Events WHERE event_id = %s", (event_id,))
        amount = cur.fetchone()[0]
        
        cur.execute(
            "INSERT INTO Registrations (user_id, event_id, registration_date, status, role) VALUES (%s, %s, %s, %s, %s) RETURNING registration_id",
            (user_id, event_id, datetime.now(), 'зарегистрировано', role)
        )
        registration_id = cur.fetchone().registration_id
        
        cur.execute(
            "INSERT INTO Payments (registration_id, amount, payment_date, status) VALUES (%s, %s, %s, %s)",
            (registration_id, amount, datetime.now(), 'ожидает оплаты')
        )
        
        conn.commit()
        cur.close()
        conn.close()
        flash('Вы успешно зарегистрировались! Произведите оплату в профиле.', 'success')
    except psycopg2.IntegrityError as e:
        conn.rollback()
        cur.close()
        conn.close()
        flash('Вы уже зарегистрированы на это мероприятие', 'danger')
    
    return redirect(url_for('event_detail', event_id=event_id))

@app.route('/event/<int:event_id>/unregister', methods=['POST'])
def unregister_event(event_id):
    if 'user' not in session:
        flash('Пожалуйста, войдите, чтобы отменить регистрацию', 'danger')
        return redirect(url_for('login'))
    
    user_id = session['user']['user_id']
    conn = get_db_connection()
    if conn is None:
        flash('Ошибка подключения к базе данных', 'danger')
        return redirect(url_for('index'))
    
    try:
        cur = conn.cursor(cursor_factory=NamedTupleCursor)  # Используем NamedTupleCursor
        cur.execute(
            "SELECT registration_id FROM Registrations WHERE user_id = %s AND event_id = %s",
            (user_id, event_id)
        )
        registration = cur.fetchone()
        if registration:
            registration_id = registration.registration_id
            cur.execute(
                "UPDATE Registrations SET status = 'отменено' WHERE registration_id = %s",
                (registration_id,)
            )
            cur.execute(
                "UPDATE Payments SET status = 'ожидает оплаты' WHERE registration_id = %s AND status != 'оплачено'",
                (registration_id,)
            )
            conn.commit()
            flash('Регистрация на мероприятие успешно отменена!', 'success')
        else:
            flash('Вы не зарегистрированы на это мероприятие', 'danger')
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        flash('Ошибка при отмене регистрации', 'danger')
    
    cur.close()
    conn.close()
    return redirect(url_for('profile'))

@app.route('/profile')
def profile():
    if 'user' not in session:
        flash('Пожалуйста, войдите, чтобы просмотреть профиль', 'danger')
        return redirect(url_for('login'))
    
    user_id = session['user']['user_id']
    conn = get_db_connection()
    if conn is None:
        flash('Ошибка подключения к базе данных', 'danger')
        return redirect(url_for('index'))
    
    cur = conn.cursor(cursor_factory=NamedTupleCursor)  # Используем NamedTupleCursor
    cur.execute("SELECT username, email, city FROM Users WHERE user_id = %s", (user_id,))
    user_data = cur.fetchone()
    
    registrations = None
    cars = None
    payments = None
    if session['user']['role'] == 'участник':
        cur.execute("""
            SELECT e.event_id, e.title, e.date, l.name, l.city, r.status, r.registration_id, r.role
            FROM Registrations r
            JOIN Events e ON r.event_id = e.event_id
            JOIN Locations l ON e.location_id = l.location_id
            WHERE r.user_id = %s
            ORDER BY e.date
        """, (user_id,))
        registrations = cur.fetchall()
        
        cur.execute("""
            SELECT c.car_id, c.model, c.year, c.color, c.photo_url, e.title
            FROM Cars c
            LEFT JOIN Events e ON c.event_id = e.event_id
            WHERE c.user_id = %s
        """, (user_id,))
        cars = cur.fetchall()
        
        cur.execute("""
            SELECT p.payment_id, p.amount, p.status, p.payment_date, e.title, r.registration_id, r.role
            FROM Payments p
            JOIN Registrations r ON p.registration_id = r.registration_id
            JOIN Events e ON r.event_id = e.event_id
            WHERE r.user_id = %s
            ORDER BY p.payment_date
        """, (user_id,))
        payments = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('profile.html', user_data=user_data, registrations=registrations, cars=cars, payments=payments, user=session.get('user'))

@app.route('/pay/<int:registration_id>', methods=['POST'])
def pay_registration(registration_id):
    if 'user' not in session:
        flash('Пожалуйста, войдите, чтобы оплатить', 'danger')
        return redirect(url_for('profile'))
    
    user_id = session['user']['user_id']
    conn = get_db_connection()
    if conn is None:
        flash('Ошибка подключения к базе данных', 'danger')
        return redirect(url_for('profile'))
    
    try:
        cur = conn.cursor(cursor_factory=NamedTupleCursor)  # Используем NamedTupleCursor
        cur.execute("""
            SELECT r.registration_id
            FROM Registrations r
            WHERE r.registration_id = %s AND r.user_id = %s AND r.status = 'зарегистрировано'
        """, (registration_id, user_id))
        if not cur.fetchone():
            cur.close()
            conn.close()
            flash('Регистрация не найдена или отменена', 'danger')
            return redirect(url_for('profile'))
        
        cur.execute("""
            UPDATE Payments
            SET status = 'оплачено', payment_date = %s
            WHERE registration_id = %s AND status = 'ожидает оплаты'
        """, (datetime.now(), registration_id))
        
        if cur.rowcount == 0:
            flash('Оплата уже завершена или не найдена', 'danger')
        else:
            flash('Оплата успешно завершена!', 'success')
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        flash('Ошибка при оплате', 'danger')
        print(f"Ошибка: {e}")
    
    cur.close()
    conn.close()
    return redirect(url_for('profile'))

@app.route('/profile/edit', methods=['GET', 'POST'])
def edit_profile():
    if 'user' not in session:
        flash('Пожалуйста, войдите, чтобы редактировать профиль', 'danger')
        return redirect(url_for('login'))
    
    user_id = session['user']['user_id']
    conn = get_db_connection()
    if conn is None:
        flash('Ошибка подключения к базе данных', 'danger')
        return redirect(url_for('profile'))
    
    cur = conn.cursor(cursor_factory=NamedTupleCursor)  # Используем NamedTupleCursor
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        city = request.form['city']
        
        try:
            cur.execute(
                "UPDATE Users SET username = %s, email = %s, city = %s WHERE user_id = %s",
                (username, email, city, user_id)
            )
            conn.commit()
            session['user']['username'] = username
            flash('Профиль успешно обновлен!', 'success')
        except psycopg2.IntegrityError as e:
            conn.rollback()
            flash('Имя пользователя или email уже существуют', 'danger')
        except Exception as e:
            conn.rollback()
            flash('Ошибка при обновлении профиля', 'danger')
        finally:
            cur.close()
            conn.close()
            return redirect(url_for('profile'))
    
    cur.execute("SELECT username, email, city FROM Users WHERE user_id = %s", (user_id,))
    user_data = cur.fetchone()
    cur.close()
    conn.close()
    
    return render_template('edit_profile.html', user_data=user_data)

@app.route('/add_car', methods=['GET', 'POST'])
def add_car():
    if 'user' not in session:
        flash('Пожалуйста, войдите, чтобы добавить машину', 'danger')
        return redirect(url_for('login'))
    if session['user']['role'] == 'организатор':
        flash('Организаторы не могут добавлять машины.', 'danger')
        return redirect(url_for('profile'))
    
    if request.method == 'POST':
        user_id = session['user']['user_id']
        model = request.form['model']
        year = request.form['year']
        color = request.form['color']
        photo_url = request.form['photo_url']
        event_id = request.form.get('event_id')

        conn = get_db_connection()
        if conn is None:
            flash('Ошибка подключения к базе данных', 'danger')
            return redirect(url_for('profile'))

        try:
            cur = conn.cursor(cursor_factory=NamedTupleCursor)  # Используем NamedTupleCursor
            cur.execute(
                "INSERT INTO Cars (user_id, model, year, color, photo_url, event_id, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (user_id, model, year, color, photo_url, event_id, datetime.now())
            )
            conn.commit()
            cur.close()
            conn.close()
            flash('Машина успешно добавлена!', 'success')
            return redirect(url_for('profile'))
        except Exception as e:
            conn.rollback()
            cur.close()
            conn.close()
            flash('Ошибка при добавлении машины', 'danger')

    conn = get_db_connection()
    if conn is None:
        flash('Ошибка подключения к базе данных', 'danger')
        return redirect(url_for('profile'))
    
    user_id = session['user']['user_id']
    cur = conn.cursor(cursor_factory=NamedTupleCursor)  # Используем NamedTupleCursor
    cur.execute("""
        SELECT e.event_id, e.title
        FROM Registrations r
        JOIN Events e ON r.event_id = e.event_id
        WHERE r.user_id = %s AND r.status = 'зарегистрировано'
    """, (user_id,))
    events = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('add_car.html', events=events)

@app.route('/edit_car/<int:car_id>', methods=['GET', 'POST'])
def edit_car(car_id):
    if 'user' not in session:
        flash('Пожалуйста, войдите, чтобы редактировать машину', 'danger')
        return redirect(url_for('login'))
    if session['user']['role'] == 'организатор':
        flash('Организаторы не могут редактировать машины.', 'danger')
        return redirect(url_for('profile'))
    
    user_id = session['user']['user_id']
    conn = get_db_connection()
    if conn is None:
        flash('Ошибка подключения к базе данных', 'danger')
        return redirect(url_for('profile'))

    cur = conn.cursor(cursor_factory=NamedTupleCursor)  # Используем NamedTupleCursor
    cur.execute("SELECT car_id, model, year, color, photo_url, event_id FROM Cars WHERE car_id = %s AND user_id = %s", (car_id, user_id))
    car = cur.fetchone()
    if not car:
        cur.close()
        conn.close()
        flash('Машина не найдена или не принадлежит вам', 'danger')
        return redirect(url_for('profile'))

    if request.method == 'POST':
        model = request.form['model']
        year = request.form['year']
        color = request.form['color']
        photo_url = request.form['photo_url']
        event_id = request.form.get('event_id') or None

        try:
            cur.execute(
                "UPDATE Cars SET model = %s, year = %s, color = %s, photo_url = %s, event_id = %s WHERE car_id = %s AND user_id = %s",
                (model, year, color, photo_url, event_id, car_id, user_id)
            )
            conn.commit()
            flash('Машина успешно обновлена!', 'success')
        except Exception as e:
            conn.rollback()
            flash('Ошибка при обновлении машины', 'danger')
        
        cur.close()
        conn.close()
        return redirect(url_for('profile'))

    cur.execute("""
        SELECT e.event_id, e.title
        FROM Registrations r
        JOIN Events e ON r.event_id = e.event_id
        WHERE r.user_id = %s AND r.status = 'зарегистрировано'
    """, (user_id,))
    events = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('edit_car.html', car=car, events=events)

@app.route('/delete_car/<int:car_id>', methods=['POST'])
def delete_car(car_id):
    if 'user' not in session:
        flash('Пожалуйста, войдите, чтобы удалить машину', 'danger')
        return redirect(url_for('login'))
    if session['user']['role'] == 'организатор':
        flash('Организаторы не могут удалять машины.', 'danger')
        return redirect(url_for('profile'))
    
    user_id = session['user']['user_id']
    conn = get_db_connection()
    if conn is None:
        flash('Ошибка подключения к базе данных', 'danger')
        return redirect(url_for('profile'))

    try:
        cur = conn.cursor(cursor_factory=NamedTupleCursor)  # Используем NamedTupleCursor
        cur.execute("DELETE FROM Cars WHERE car_id = %s AND user_id = %s", (car_id, user_id))
        conn.commit()
        if cur.rowcount == 0:
            flash('Машина не найдена или не принадлежит вам', 'danger')
        else:
            flash('Машина успешно удалена!', 'success')
    except Exception as e:
        conn.rollback()
        flash('Ошибка при удалении машины', 'danger')
    
    cur.close()
    conn.close()
    return redirect(url_for('profile'))

@app.route('/admin')
def admin():
    if 'user' not in session or session['user']['role'] != 'организатор':
        flash('Доступ запрещён. Требуются права организатора.', 'danger')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    if conn is None:
        flash('Ошибка подключения к базе данных', 'danger')
        return redirect(url_for('index'))
    
    cur = conn.cursor(cursor_factory=NamedTupleCursor)  # Используем NamedTupleCursor
    cur.execute("""
        SELECT e.event_id, e.title, e.date, l.name, l.city, e.status, e.photo_url, e.description, u.username, e.spectator_price, e.participant_price
        FROM Events e
        JOIN Locations l ON e.location_id = l.location_id
        LEFT JOIN Users u ON e.organizer_id = u.user_id
        ORDER BY e.date
    """)
    events = cur.fetchall()
    
    cur.execute("""
        SELECT r.registration_id, u.username, e.title, r.registration_date, r.status, p.status AS payment_status, r.role
        FROM Registrations r
        JOIN Users u ON r.user_id = u.user_id
        JOIN Events e ON r.event_id = e.event_id
        LEFT JOIN Payments p ON r.registration_id = p.registration_id
        ORDER BY r.registration_date
    """)
    registrations = cur.fetchall()
    
    cur.execute("""
        SELECT c.car_id, c.model, c.year, c.color, c.photo_url, e.title, u.username, e.date
        FROM Cars c
        JOIN Events e ON c.event_id = e.event_id
        JOIN Users u ON c.user_id = u.user_id
        ORDER BY e.date, c.model
    """)
    participant_cars = cur.fetchall()
    
    # Получаем статистику по участникам и зрителям для каждого мероприятия
    cur.execute("""
        SELECT e.event_id,
               COUNT(r.registration_id) AS total,
               COUNT(CASE WHEN r.role = 'зритель' THEN 1 END) AS spectators,
               COUNT(CASE WHEN r.role = 'участник' THEN 1 END) AS participants
        FROM Events e
        LEFT JOIN Registrations r ON e.event_id = r.event_id AND r.status = 'зарегистрировано'
        GROUP BY e.event_id
    """)
    event_counts = {row.event_id: {'total': row.total, 'spectators': row.spectators, 'participants': row.participants} for row in cur.fetchall()}
    
    cur.close()
    conn.close()
    return render_template('admin.html', events=events, registrations=registrations, participant_cars=participant_cars, event_counts=event_counts)

@app.route('/admin/create_event', methods=['GET', 'POST'])
def create_event():
    if 'user' not in session or session['user']['role'] != 'организатор':
        flash('Доступ запрещён. Требуются права организатора.', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        date = request.form['date']
        location_id = request.form['location_id']
        status = request.form['status']
        photo_url = request.form['photo_url']
        spectator_price = request.form['spectator_price']
        participant_price = request.form['participant_price']
        organizer_id = session['user']['user_id']
        
        conn = get_db_connection()
        if conn is None:
            flash('Ошибка подключения к базе данных', 'danger')
            return redirect(url_for('admin'))
        
        try:
            cur = conn.cursor(cursor_factory=NamedTupleCursor)  # Используем NamedTupleCursor
            cur.execute(
                "INSERT INTO Events (title, description, date, location_id, status, photo_url, organizer_id, spectator_price, participant_price) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (title, description, date, location_id, status, photo_url, organizer_id, spectator_price, participant_price)
            )
            conn.commit()
            cur.close()
            conn.close()
            flash('Мероприятие успешно создано!', 'success')
            return redirect(url_for('admin'))
        except Exception as e:
            conn.rollback()
            cur.close()
            conn.close()
            flash('Ошибка при создании мероприятия', 'danger')
            return redirect(url_for('admin'))
    
    conn = get_db_connection()
    if conn is None:
        flash('Ошибка подключения к базе данных', 'danger')
        return redirect(url_for('admin'))
    
    cur = conn.cursor(cursor_factory=NamedTupleCursor)  # Используем NamedTupleCursor
    cur.execute("SELECT location_id, name, city FROM Locations")
    locations = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('create_event.html', locations=locations)

@app.route('/admin/edit_event/<int:event_id>', methods=['GET', 'POST'])
def edit_event(event_id):
    if 'user' not in session or session['user']['role'] != 'организатор':
        flash('Доступ запрещён. Требуются права организатора.', 'danger')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    if conn is None:
        flash('Ошибка подключения к базе данных', 'danger')
        return redirect(url_for('admin'))
    
    cur = conn.cursor(cursor_factory=NamedTupleCursor)  # Используем NamedTupleCursor
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        date = request.form['date']
        location_id = request.form['location_id']
        status = request.form['status']
        photo_url = request.form['photo_url']
        spectator_price = request.form['spectator_price']
        participant_price = request.form['participant_price']
        
        try:
            cur.execute(
                "UPDATE Events SET title = %s, description = %s, date = %s, location_id = %s, status = %s, photo_url = %s, spectator_price = %s, participant_price = %s WHERE event_id = %s",
                (title, description, date, location_id, status, photo_url, spectator_price, participant_price, event_id)
            )
            conn.commit()
            flash('Мероприятие успешно обновлено!', 'success')
        except Exception as e:
            conn.rollback()
            flash('Ошибка при обновлении мероприятия', 'danger')
    
        cur.close()
        conn.close()
        return redirect(url_for('admin'))
    
    cur.execute("""
        SELECT e.title, e.description, e.date, e.location_id, e.status, e.photo_url, e.spectator_price, e.participant_price
        FROM Events e
        WHERE e.event_id = %s
    """, (event_id,))
    event = cur.fetchone()
    
    if not event:
        cur.close()
        conn.close()
        flash('Мероприятие не найдено', 'danger')
        return redirect(url_for('admin'))
    
    cur.execute("SELECT location_id, name, city FROM Locations")
    locations = cur.fetchall()
    cur.close()
    conn.close()
    
    return render_template('edit_event.html', event=event, locations=locations, event_id=event_id)

@app.route('/admin/delete_event/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    if 'user' not in session or session['user']['role'] != 'организатор':
        flash('Доступ запрещён. Требуются права организатора.', 'danger')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    if conn is None:
        flash('Ошибка подключения к базе данных', 'danger')
        return redirect(url_for('admin'))
    
    try:
        cur = conn.cursor(cursor_factory=NamedTupleCursor)  # Используем NamedTupleCursor
        cur.execute("DELETE FROM Registrations WHERE event_id = %s", (event_id,))
        cur.execute("UPDATE Cars SET event_id = NULL WHERE event_id = %s", (event_id,))
        cur.execute("DELETE FROM Events WHERE event_id = %s", (event_id,))
        conn.commit()
        flash('Мероприятие успешно удалено!', 'success')
    except Exception as e:
        conn.rollback()
        flash('Ошибка при удалении мероприятия', 'danger')
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Вы вышли из системы', 'success')
    return redirect(url_for('index'))

@app.route('/edit_review/<int:review_id>', methods=['GET', 'POST'])
def edit_review(review_id):
    if 'user' not in session:
        flash('Пожалуйста, войдите, чтобы редактировать отзыв', 'danger')
        return redirect(url_for('login'))
    user_id = session['user']['user_id']
    conn = get_db_connection()
    if conn is None:
        flash('Ошибка подключения к базе данных', 'danger')
        return redirect(url_for('index'))
    cur = conn.cursor(cursor_factory=NamedTupleCursor)  # Используем NamedTupleCursor
    cur.execute("SELECT event_id, rating, comment FROM Reviews WHERE review_id = %s AND user_id = %s", (review_id, user_id))
    review = cur.fetchone()
    if not review:
        cur.close()
        conn.close()
        flash('Отзыв не найден или вы не являетесь его автором', 'danger')
        return redirect(url_for('index'))
    event_id = review.event_id
    if request.method == 'POST':
        rating = int(request.form['rating'])
        comment = request.form['comment']
        cur.execute("UPDATE Reviews SET rating = %s, comment = %s WHERE review_id = %s", (rating, comment, review_id))
        conn.commit()
        cur.close()
        conn.close()
        flash('Отзыв успешно обновлен!', 'success')
        return redirect(url_for('event_detail', event_id=event_id))
    cur.close()
    conn.close()
    return render_template('edit_review.html', review=review, review_id=review_id)

@app.route('/delete_review/<int:review_id>', methods=['POST'])
def delete_review(review_id):
    if 'user' not in session:
        flash('Пожалуйста, войдите, чтобы удалить отзыв', 'danger')
        return redirect(url_for('login'))
    user_id = session['user']['user_id']
    conn = get_db_connection()
    if conn is None:
        flash('Ошибка подключения к базе данных', 'danger')
        return redirect(url_for('index'))
    cur = conn.cursor(cursor_factory=NamedTupleCursor)  # Используем NamedTupleCursor
    cur.execute("SELECT event_id FROM Reviews WHERE review_id = %s AND user_id = %s", (review_id, user_id))
    review = cur.fetchone()
    if not review:
        cur.close()
        conn.close()
        flash('Отзыв не найден или вы не являетесь его автором', 'danger')
        return redirect(url_for('index'))
    event_id = review.event_id
    cur.execute("DELETE FROM Reviews WHERE review_id = %s AND user_id = %s", (review_id, user_id))
    conn.commit()
    cur.close()
    conn.close()
    flash('Отзыв удален!', 'success')
    return redirect(url_for('event_detail', event_id=event_id))

if __name__ == '__main__':
    app.run(debug=True)