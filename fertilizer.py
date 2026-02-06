from flask import Flask, request, render_template, redirect, url_for, flash, session,make_response
import pickle  # ही ओळ वेगळी लिहा
import pdfkit
import numpy as np
import pandas as pd
from database import get_db_connection
import mysql.connector

path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)

from flask import Blueprint
fert_bp = Blueprint('fertilizer', __name__)

@fert_bp.route('/fertilizer')
def crop():
    return render_template("fertilizer.html")

# नवीन मॉडेल्स लोड करा
fert_model = pickle.load(open('fert_model.pkl', 'rb'))
le_soil = pickle.load(open('le_soil.pkl', 'rb'))
le_crop = pickle.load(open('le_crop.pkl', 'rb'))

@fert_bp.route("/predict_fertilizer", methods=['POST'])
def predict_fertilizer():
    try:
        df_fert = pd.read_csv('data_core.csv')
        
        # १. फॉर्ममधून डेटा मिळवणे
        temp = float(request.form.get('temperature', 30.0))
        humid = float(request.form.get('humidity', 50.0))
        soil = request.form.get('soil_type')
        crop = request.form.get('crop_type')
        n_user = float(request.form.get('nitrogen', 0.0))
        p_user = float(request.form.get('phosphorous', 0.0))
        k_user = float(request.form.get('potassium', 0.0))

        # २. 'Unseen Labels' साठी चेक (जर पिकाचे नाव एन्कोडरमध्ये नसेल तर)
        if crop not in le_crop.classes_:
            return render_template('fertilizer.html', error=f"क्षमस्व, '{crop}' या पिकासाठी मॉडेल ट्रेनिंग झालेले नाही. कृपया दुसरे पीक निवडा.")
        if soil not in le_soil.classes_:
            return render_template('fertilizer.html', error=f"क्षमस्व, '{soil}' या मातीचा प्रकार उपलब्ध नाही.")

        # ३. मॉडेल प्रेडिक्शन
        soil_enc = le_soil.transform([soil])[0]
        crop_enc = le_crop.transform([crop])[0]
        
        # मॉडेलच्या ट्रेनिंग कॉलम क्रमानुसार डेटा तयार करणे
        input_df = pd.DataFrame([[temp, humid, soil_enc, crop_enc, n_user, k_user, p_user]], 
                               columns=['Temparature', 'Humidity', 'Soil Type', 'Crop Type', 'Nitrogen', 'Potassium', 'Phosphorous'])
        
        prediction = fert_model.predict(input_df)[0]

        # ४. कमतरता विश्लेषण (N-P-K Comparison)
        missing_list = []
        crop_data = df_fert[df_fert['Crop Type'].str.lower() == crop.lower()]

        if not crop_data.empty:
            avg_n = crop_data['Nitrogen'].mean()
            avg_p = crop_data['Phosphorous'].mean()
            avg_k = crop_data['Potassium'].mean()

            if n_user < avg_n: missing_list.append("Nitrogen (N)")
            if p_user < avg_p: missing_list.append("Phosphorous (P)")
            if k_user < avg_k: missing_list.append("Potassium (K)")

        if 'user_id' in session:
            user_id = session['user_id'] # Session madhun ID ghene
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = "INSERT INTO prediction_history (user_id, crop_name, soil_type, prediction, nitrogen, phosphorous, potassium) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        cursor.execute(query, (user_id, crop, soil, prediction, n_user, p_user, k_user))
        
        conn.commit()
        cursor.close()
        conn.close()

    
        # ५. डेटाबेसमध्ये स्टोर न करता थेट रिझल्ट दाखवणे
        return render_template('fertilizer.html', 
                               prediction=prediction, 
                               missing=missing_list, 
                               crop=crop, 
                               soil=soil)

    except Exception as e:
        print(f"Error: {e}")
        return render_template('fertilizer.html', error="तांत्रिक त्रुटी आली आहे. कृपया पुन्हा प्रयत्न करा.")


    
@fert_bp.route('/download_pdf/<int:record_id>')
def download_pdf(record_id):
    # १. डेटाबेस मधून त्या विशिष्ट रेकॉर्डचा डेटा मिळवा
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM prediction_history WHERE id = %s", (record_id,))
    record = cursor.fetchone()
    cursor.close()
    conn.close()

    if record:
        # २. PDF साठी एक वेगळा छोटा HTML टेम्प्लेट वापरा (किंवा स्ट्रिंग बनवा)
        html_content = render_template('pdf_template.html', r=record)
        
        # ३. PDF जनरेट करा
        pdf = pdfkit.from_string(html_content, False, configuration=config)
        
        # ४. Response पाठवा जेणेकरून फाईल डाउनलोड होईल
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=AgriScan_Report_{record_id}.pdf'
        return response
    
    return "Record not found", 404