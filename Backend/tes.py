from flask import Flask, request, jsonify
import mysql.connector
from mysql.connector import Error

import os
from dotenv import load_dotenv

load_dotenv() # Memuat variabel dari file .env

#Konfigurasi database
db_config = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME')
}

app = Flask(__name__)

@app.route('/ambiluid', methods=['POST'])

def ambil_uid():
    data = request.get_json()
    if not data or 'uid' not in data:
        return jsonify({"status": "error", "message": "UID tidak ditemukan dalam request"}), 400

    uid = data.get('uid')
    print(f"UID diterima: {uid}")

    # Variabel untuk koneksi dan cursor
    cnx = None
    cursor = None

    try:
        # Membuat koneksi ke database
        cnx = mysql.connector.connect(**db_config)
        cursor = cnx.cursor()

        # Perintah SQL untuk memasukkan data (MENGGUNAKAN PARAMETERISASI UNTUK KEAMANAN)
        query = "INSERT INTO log_rfid (uid) VALUES (%s)"
        
        # Eksekusi perintah dengan UID yang diterima
        cursor.execute(query, (uid,))

        # Commit perubahan ke database
        cnx.commit()

        print(f"UID '{uid}' berhasil disimpan ke database.")
        return jsonify({"status": "success", "message": "UID berhasil diterima dan disimpan", "received_uid": uid})

    except Error as e:
        # Jika terjadi error, cetak errornya
        print(f"Error: {e}")
        return jsonify({"status": "error", "message": f"Anda sudah melakukan presensi: {e}"}), 500

    finally:
        # Pastikan koneksi dan cursor selalu ditutup, baik berhasil maupun gagal
        if cursor:
            cursor.close()
        if cnx and cnx.is_connected():
            cnx.close()
            print("Koneksi ke database ditutup.")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=10000)
# UPLOAD UID -> SIMPAN KE DB 

