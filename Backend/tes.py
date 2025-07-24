from flask import Flask, request, jsonify, render_template
import mysql.connector
from mysql.connector import Error
from datetime import date, datetime
import threading
import time
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

# --- Variabel Global untuk Pairing Mode ---
# Tahap Development.
pairing_info = {
    "is_active": False,
    "user_id_to_pair": None,
    "timestamp": 0
}

# --- Endpoint untuk Halaman Web ---
@app.route('/')
def dashboard():
    """Menyajikan halaman dashboard admin (index.html)."""
    return render_template('index.html')

@app.route('/api/karyawan', methods=['GET'])
def get_karyawan():
    """API untuk mengambil semua data karyawan."""
    try:
        cnx = mysql.connector.connect(**db_config)
        cursor = cnx.cursor(dictionary=True)
        cursor.execute("SELECT id, nama, uid, status_aktif FROM karyawan ORDER BY nama ASC")
        karyawan = cursor.fetchall()
        return jsonify(karyawan)
    except Error as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cnx' in locals() and cnx.is_connected():
            cursor.close()
            cnx.close()

@app.route('/api/register/start', methods=['POST'])
def start_pairing():
    """API yang dipanggil oleh tombol 'Daftarkan Kartu' di frontend."""
    user_id = request.json.get('user_id')
    pairing_info.update({"is_active": True, "user_id_to_pair": user_id, "timestamp": time.time()})
    
    def cancel_pairing():
        if pairing_info["user_id_to_pair"] == user_id and (time.time() - pairing_info["timestamp"] > 29):
             pairing_info.update({"is_active": False, "user_id_to_pair": None})
             print(f"Pairing mode untuk user ID {user_id} telah berakhir (timeout).")
    threading.Timer(30.0, cancel_pairing).start()

    print(f"Pairing mode DIAKTIFKAN untuk user ID: {user_id}")
    return jsonify({"status": "success", "message": "Mode registrasi aktif selama 30 detik. Silakan tempelkan kartu."})

# === Endpoint untuk Alat RFID ===

@app.route('/handle-tap', methods=['POST'])
def handle_tap():
    """Endpoint cerdas yang menerima semua tap kartu dari alat RFID."""
    uid = request.json.get('uid')
    if not uid:
        return jsonify({"status": "error", "message": "UID tidak ada"}), 400

    try:
        cnx = mysql.connector.connect(**db_config)
        cursor = cnx.cursor(dictionary=True)

        # --- LOGIKA PAIRING ---
        if pairing_info["is_active"]:
            user_id = pairing_info["user_id_to_pair"]
            cursor.execute("SELECT nama FROM karyawan WHERE uid = %s", (uid,))
            if cursor.fetchone():
                return jsonify({"status": "error", "message": "Kartu sudah dimiliki orang lain"})
            
            cursor.execute("UPDATE karyawan SET uid = %s WHERE id = %s", (uid, user_id))
            cnx.commit()
            pairing_info.update({"is_active": False, "user_id_to_pair": None})
            return jsonify({"status": "success", "message": "Registrasi Berhasil!"})

        # --- LOGIKA PRESENSI ---
        else:
            # 1. Cek apakah UID terdaftar
            cursor.execute("SELECT * FROM karyawan WHERE uid = %s AND status_aktif = TRUE", (uid,))
            karyawan = cursor.fetchone()
            if not karyawan:
                return jsonify({"status": "error", "message": "Kartu Tidak Terdaftar"})
            
            # 2. Cek data presensi hari ini
            nama_karyawan = karyawan['nama']
            today = date.today()
            now_time = datetime.now().time()
            cursor.execute("SELECT id, jam_pulang FROM presensi WHERE uid = %s AND tanggal = %s", (uid, today))
            presensi_hari_ini = cursor.fetchone()
            
            if presensi_hari_ini is None:
                # Presensi Masuk
                cursor.execute("INSERT INTO presensi (uid, tanggal, jam_masuk) VALUES (%s, %s, %s)", (uid, today, now_time))
                cnx.commit()
                return jsonify({"status": "success", "message": f"Masuk: {nama_karyawan}"})
            
            elif presensi_hari_ini['jam_pulang'] is None:
                # Presensi Pulang
                cursor.execute("UPDATE presensi SET jam_pulang = %s WHERE id = %s", (now_time, presensi_hari_ini['id']))
                cnx.commit()
                return jsonify({"status": "success", "message": f"Pulang: {nama_karyawan}"})
            
            else:
                # Sudah presensi masuk dan pulang
                return jsonify({"status": "done", "message": "Anda Sudah Presensi"})

    except Error as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if 'cnx' in locals() and cnx.is_connected():
            cursor.close()
            cnx.close()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=10000)