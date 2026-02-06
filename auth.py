from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_db_connection
import mysql.connector

# Blueprint create kara
auth_bp = Blueprint('auth', __name__)


# Ata tumchi login logic ashi disel:
@auth_bp.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True) # dictionary=True mule result easy vachata yeto
    
    # Database madhe user shodha
    cursor.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
    user = cursor.fetchone()

    cursor.close()
    conn.close()
   

    if user:
        # User sapadla tar session madhe save kara
        session['user_id'] = user['id']
        session['user_name'] = user['fullname']
        session['email'] = user['email']
        flash(f"Welcome back, {user['fullname']}!", "success")
        return redirect(url_for('index'))
    else:
        flash("Invalid Email or Password", "danger") 
    return redirect(url_for('index'))

@auth_bp.route('/register', methods=['POST'])
def register():
    name = request.form.get('fullname')
    email = request.form.get('email')
    pwd = request.form.get('password')
    mobile = request.form.get('mobile')
    address = request.form.get('address')   

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("INSERT INTO users (fullname, email, password, mobile, address) VALUES (%s, %s, %s, %s, %s)", 
                       (name, email, pwd, mobile, address))
        conn.commit()
        flash("Registration Successful! Please Login.")

    except mysql.connector.Error as err:
        flash("email alrady");
    
    cursor.close()
    conn.close()
    return redirect(url_for('index'))
@auth_bp.route('/logout')
def logout():
    session.clear()
    # Logout nantar ek special parameter pathvuya popup dakhvnya sathi
    return redirect(url_for('index', action='loggedout'))
# @auth_bp.route('/dashboard')
# def dashboard():
#     if 'user_id' not in session:
#         flash("Please login first", "warning")
#         return redirect(url_for('index'))
#     return render_template('dashboard.html', name=session['user_name'])

@auth_bp.route('/contact_submit', methods=['POST'])
def contact_submit():
    if request.method == 'POST':
        # Form madhun data ghene
        fullname = request.form.get('fullname')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Database madhe insert karne
            query = "INSERT INTO contact_messages (fullname, email, subject, message) VALUES (%s, %s, %s, %s)"
            cursor.execute(query, (fullname, email, subject, message))
            
            conn.commit() # Changes save kara
            cursor.close()
            conn.close()
            
            flash("Tumcha sandesh amchyaparyant pohochala aahe! Dhanyavad.", "success")
        except Exception as e:
            print(f"Error: {e}")
            flash("Kahi tari chukle aahe, parat prayatna kara.", "danger")

        return redirect(url_for('contacts')) 