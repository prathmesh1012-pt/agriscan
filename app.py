import os
from flask import Flask, jsonify, request, render_template, redirect, url_for, flash, session, jsonify
from database import get_db_connection
from auth import auth_bp
from fertilizer import fert_bp
import numpy as np
import mysql.connector
import pickle
from flask_mail import Mail, Message
import random
import os

from dotenv import load_dotenv

load_dotenv()


#  मॉडेल आणि स्केलर्स लोड

model = pickle.load(open('model.pkl', 'rb'))
sc = pickle.load(open('standscaler.pkl', 'rb'))
ms = pickle.load(open('minmaxscaler.pkl', 'rb'))

# Flask अ‍ॅप
app = Flask(__name__)
app.secret_key = 'agriscan_secret_key_123'
app.register_blueprint(auth_bp)
app.register_blueprint(fert_bp)


#  होम पेज
@app.route('/')
def index():
    return render_template("index.html")

@app.route('/crop')
def crop():
    return render_template("crop.html")

@app.route('/WeatherInsights')
def weather_insights():
    return render_template("WeatherInsights.html")

@app.route('/services')
def services():
    return render_template("services.html")

@app.route('/contact')
def contacts():
    return render_template("contact.html")

@app.route('/about')
def about():
    return render_template("about.html")
@app.route('/settings')
def settings_page():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('settings.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    uid = session['user_id']
    name = session.get('name', 'Farmer') # सेशनमधून नाव घेणे
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True) # dictionary=True मुळे डेटा कॉलमच्या नावाने वापरता येतो

    try:
        # १. Fertilizer चे एकूण रिपोर्ट्स मोजणे
        cursor.execute("SELECT COUNT(*) as total FROM prediction_history WHERE user_id = %s", (uid,))
        total_fert = cursor.fetchone()['total']

        # २. Crop Analysis चे एकूण रिपोर्ट्स मोजणे
        cursor.execute("SELECT COUNT(*) as total FROM crop_history WHERE user_id = %s", (uid,))
        total_crop = cursor.fetchone()['total']

        # ३. Fertilizer चे शेवटचे ५ रेकॉर्ड्स मिळवणे
        cursor.execute("""
            SELECT crop_name, prediction, created_at 
            FROM prediction_history 
            WHERE user_id = %s 
            ORDER BY created_at DESC LIMIT 5
        """, (uid,))
        fert_reports = cursor.fetchall()

        # ४. Crop चे शेवटचे ५ रेकॉर्ड्स मिळवणे
        cursor.execute("""
            SELECT crop_1_name, crop_1_conf, created_at 
            FROM crop_history 
            WHERE user_id = %s 
            ORDER BY created_at DESC LIMIT 5
        """, (uid,))
        crop_reports = cursor.fetchall()

    except Exception as e:
        print(f"Database Error: {e}")
        total_fert = total_crop = 0
        fert_reports = crop_reports = []
    
    finally:
        cursor.close()
        conn.close()

    # ५. सर्व डेटा HTML कडे पाठवणे
    return render_template('dashboard.html', 
                           name=session['user_name'],
                           fert_reports=fert_reports, 
                           crop_reports=crop_reports)

#  प्रेडिक्शन रूट
@app.route("/predict", methods=['POST'])
def predict():
    try:
        # १. फॉर्ममधून डेटा घेणे (HTML मधील 'name' ॲट्रिब्यूट नुसार)
        N = float(request.form.get('Nitrogen') or 0)
        P = float(request.form.get('Phosporus') or 0) # HTML मध्ये 'S' मिसिंग आहे, म्हणून हेच ठेवा
        K = float(request.form.get('Potassium') or 0)
        temp = float(request.form.get('Temperature') or 0)
        humidity = float(request.form.get('Humidity') or 0)
        ph = float(request.form.get('Ph') or 0)
        rainfall = float(request.form.get('Rainfall') or 0)

        # २. मॉडेल प्रेडिक्शन लॉजिक
        feature_list = [N, P, K, temp, humidity, ph, rainfall]
        single_pred = np.array(feature_list).reshape(1, -1)
        
        # स्केलिंग (ms आणि sc आधीच लोड केलेले असावेत)
        scaled_features = ms.transform(single_pred)
        final_features = sc.transform(scaled_features)

        probabilities = model.predict_proba(final_features)[0]
        top_indices = np.argsort(probabilities)[::-1][:3] 

        crop_dict = {
            1: "Rice", 2: "Maize", 3: "Jute", 4: "Cotton", 5: "Coconut",
            6: "Papaya", 7: "Orange", 8: "Apple", 9: "Muskmelon",
            10: "Watermelon", 11: "Grapes", 12: "Mango", 13: "Banana",
            14: "Pomegranate", 15: "Lentil", 16: "Blackgram", 17: "Mungbean",
            18: "Mothbeans", 19: "Pigeonpeas", 20: "Kidneybeans",
            21: "Chickpea", 22: "Coffee", 23 : "Wheat" , 24 : "Jowar", 25 : "Mustard"
        }

        results = []
        for idx in top_indices:
            conf = round(probabilities[idx] * 100, 1)
            actual_crop_id = model.classes_[idx] 
            crop_name = crop_dict.get(actual_crop_id, "Unknown")
            results.append({"name": crop_name, "confidence": conf})

        # ३. डेटाबेसमध्ये सेव्ह करणे (Try-Except ब्लॉकसह)
        if 'user_id' in session:
            try:
                uid = session['user_id']
                conn = get_db_connection()
                cursor = conn.cursor()

                query = """
                INSERT INTO crop_history 
                (user_id, nitrogen, phosphorus, potassium, ph_level, temperature, humidity, rainfall, 
                 crop_1_name, crop_1_conf, crop_2_name, crop_2_conf, crop_3_name, crop_3_conf) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """

                values = (uid, N, P, K, ph, temp, humidity, rainfall, 
                          results[0]['name'], results[0]['confidence'], 
                          results[1]['name'], results[1]['confidence'], 
                          results[2]['name'], results[2]['confidence'])
                
                cursor.execute(query, values)
                conn.commit()
                cursor.close()
                conn.close()
            except Exception as db_err:
                # जर DB मध्ये एरर आला तरी प्रेडिक्शन रिझल्ट पेजवर दिसावेत
                print(f"Database Saving Error: {db_err}")

        # ४. शेवटी रिझल्ट्स पेजवर पाठवणे
        return render_template('crop.html', results=results)

    except Exception as e:
        print(f"Prediction Error: {e}")
        # जर 'crop.html' मध्ये एरर दाखवायचा असेल तर:
        return render_template('crop.html', error="तांत्रिक त्रुटी: कृपया सर्व व्हॅल्यूज नीट तपासा.")
    

@app.route('/history')
def history():
    uid = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # UNION मध्ये क्रॉप्सचे तिन्ही पर्याय आणि त्यांचे स्कोर्स ॲड करू
    query = """
    SELECT id, crop_name, 
           prediction AS res_1, NULL AS conf_1, 
           NULL AS res_2, NULL AS conf_2, 
           NULL AS res_3, NULL AS conf_3, 
           created_at, 'Fertilizer' AS entry_type 
    FROM prediction_history WHERE user_id = %s
    UNION ALL
    SELECT id, 'Multiple Crops' AS crop_name, 
           crop_1_name AS res_1, crop_1_conf AS conf_1, 
           crop_2_name AS res_2, crop_2_conf AS conf_2, 
           crop_3_name AS res_3, crop_3_conf AS conf_3, 
           created_at, 'Crop' AS entry_type 
    FROM crop_history WHERE user_id = %s
    ORDER BY created_at DESC
    """
    
    cursor.execute(query, (uid, uid))
    all_records = cursor.fetchall()
    
    cursor.close()
    conn.close()

    return render_template('history.html', history_records=all_records, total_count=len(all_records))

@app.route('/get-crop-details/<int:record_id>')
def get_crop_details(record_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM crop_history WHERE id = %s", (record_id,))
    details = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return jsonify(details) # डेटा JSON फॉरमॅटमध्ये पाठवा
@app.route('/update-profile', methods=['POST'])
def update_profile():
    # १. आधी खात्री करा की युजर लॉगिन आहे का
    if 'user_id' not in session:
        return redirect('/login') 
    
    uid = session['user_id']
    new_name = request.form.get('name')
    new_mobile = request.form.get('mobile')
    new_address = request.form.get('address')

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # २. डेटाबेस अपडेट करा
        cursor.execute("UPDATE users SET fullname = %s, mobile = %s, address = %s WHERE id = %s", 
                       (new_name, new_mobile, new_address, uid))
        conn.commit()
        
        # ३. सर्वात महत्त्वाचे: सेशनमधील नाव सुद्धा अपडेट करा
        session['user_name'] = new_name 
        session['user_mobile'] = new_mobile
        session['user_address'] = new_address
        
        print("Profile Updated Successfully!") # टर्मिनलमध्ये चेक करा
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback() # एरर आल्यास बदल मागे घ्या
    finally:
        cursor.close()
        conn.close()
        
    # ४. डॅशबोर्डवर परत पाठवा
    return redirect('/dashboard?updated=true#profile')

# email_configuration for OTP
app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER")
app.config['MAIL_PORT'] = os.getenv("MAIL_PORT")
app.config['MAIL_USE_TLS'] = os.getenv("MAIL_USE_TLS").lower() == 'true'
app.config['MAIL_USERNAME'] =os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] =os.getenv("MAIL_PASSWORD") 
mail = Mail(app)

# १. OTP पाठवण्यासाठी रूट
@app.route('/send-otp', methods=['POST'])
def send_otp():
    email = session.get('email')
    otp = str(random.randint(100000, 999999))
    session['otp'] = otp 
    
    msg = Message('Password Change OTP - AgriTech', 
                  sender='agriscanintelligence@gmail.com', 
                  recipients=[email])
    msg.body = f"Your OTP for changing password is: {otp}. Do not share it with anyone."
    mail.send(msg)
    
    return jsonify({"success": True, "message": "OTP sent to your email!"})

# २. पासवर्ड आणि OTP व्हेरिफाय करण्याचा रूट
@app.route('/verify-and-change-password', methods=['POST'])
def verify_and_change_password():
    user_otp = request.form.get('otp')
    new_pass = request.form.get('new_password')
    uid = session.get('user_id') # लॉगिन असलेल्या युजरचा ID

   
        
    # १. आधी OTP तपासा
    if user_otp == session.get('otp'):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # २. पासवर्ड अपडेट करण्याची मुख्य क्वेरी
            query = "UPDATE users SET password = %s WHERE id = %s"
            cursor.execute(query, (new_pass, uid))
            
            conn.commit() # डेटाबेसमध्ये बदल सेव्ह करा
            cursor.close()
            conn.close()

            # ३. काम झाल्यावर OTP सेशनमधून काढून टाका
            session.pop('otp', None)
            flash("Password updated successfully! ✅", "update_success")
            # यश आल्याचा मेसेज देऊन रिडायरेक्ट करा
            return redirect('/settings?updated=true')
            
        except Exception as e:
            return f"Error: {str(e)}"
    else:
       flash("Invalid OTP! Please try again.", "update_danger")
       return redirect('/settings')
if __name__ == "__main__":
    app.run(debug=True)