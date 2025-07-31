from flask import Flask, request, jsonify, render_template
import mysql.connector
from mysql.connector import Error
from datetime import date, datetime, time
import threading
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

# --- ATURAN JAM KERJA ---
WAKTU_MASUK_MULAI = time(7,0,0)# Jam 07:00:00
WAKTU_MASUK_AKHIR = time(9, 0, 0)   # Jam 09:00:00
WAKTU_PULANG_MULAI = time(17, 0, 0)  # Jam 17:00:00


# === Endpoint untuk Frontend Web ===

@app.route('/')
def dashboard():
    """Menyajikan halaman dashboard admin (index.html)."""
    return render_template('index.html')

# === API untuk CRUD Karyawan ===

# CREATE: Menambah karyawan baru
@app.route('/api/karyawan', methods=['POST'])
def add_karyawan():
    nama = request.json.get('nama')
    if not nama:
        return jsonify({"status": "error", "message": "Nama tidak boleh kosong"}), 400
    try:
        cnx = mysql.connector.connect(**db_config)
        cursor = cnx.cursor()
        cursor.execute("INSERT INTO karyawan (nama) VALUES (%s)", (nama,))
        cnx.commit()
        return jsonify({"status": "success", "message": "Karyawan berhasil ditambahkan"}), 201
    except Error as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if 'cnx' in locals() and cnx.is_connected():
            cursor.close()
            cnx.close()

# READ: Mengambil semua data karyawan
@app.route('/api/karyawan', methods=['GET'])
def get_karyawan():
    try:
        cnx = mysql.connector.connect(**db_config)
        cursor = cnx.cursor(dictionary=True)
        cursor.execute("SELECT id, nama, uid, status_aktif FROM karyawan ORDER BY nama ASC")
        karyawan = cursor.fetchall()
        # Konversi status_aktif dari byte ke string 'TRUE'/'FALSE' jika perlu
        for row in karyawan:
            if isinstance(row['status_aktif'], bytes):
                row['status_aktif'] = row['status_aktif'].decode('utf-8')
        return jsonify(karyawan)
    except Error as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cnx' in locals() and cnx.is_connected():
            cursor.close()
            cnx.close()

# UPDATE: Mengubah data karyawan
@app.route('/api/karyawan/<int:id>', methods=['PUT'])
def update_karyawan(id):
    data = request.json
    nama = data.get('nama')
    status = data.get('status_aktif')
    if not nama or not status:
        return jsonify({"status": "error", "message": "Data tidak lengkap"}), 400
    try:
        cnx = mysql.connector.connect(**db_config)
        cursor = cnx.cursor()
        cursor.execute("UPDATE karyawan SET nama = %s, status_aktif = %s WHERE id = %s", (nama, status, id))
        cnx.commit()
        return jsonify({"status": "success", "message": "Data karyawan berhasil diperbarui"})
    except Error as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if 'cnx' in locals() and cnx.is_connected():
            cursor.close()
            cnx.close()

# DELETE: Menghapus karyawan
@app.route('/api/karyawan/<int:id>', methods=['DELETE'])
def delete_karyawan(id):
    try:
        cnx = mysql.connector.connect(**db_config)
        cursor = cnx.cursor()
        cursor.execute("DELETE FROM karyawan WHERE id = %s", (id,))
        cnx.commit()
        return jsonify({"status": "success", "message": "Karyawan berhasil dihapus"})
    except Error as e:
        # Tangani error jika foreign key constraint gagal
        if e.errno == 1451:
            return jsonify({"status": "error", "message": "Tidak bisa menghapus, karyawan sudah memiliki data presensi."}), 409
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if 'cnx' in locals() and cnx.is_connected():
            cursor.close()
            cnx.close()


# === API untuk Registrasi Kartu ===

@app.route('/api/register/start', methods=['POST'])
def start_pairing():
    user_id = request.json.get('user_id')
    pairing_info.update({"is_active": True, "user_id_to_pair": user_id, "timestamp": time.time()})
    
    def cancel_pairing():
        if pairing_info["user_id_to_pair"] == user_id and (time.time() - pairing_info["timestamp"] > 29):
             pairing_info.update({"is_active": False, "user_id_to_pair": None})
    threading.Timer(30.0, cancel_pairing).start()
    return jsonify({"status": "success", "message": "Mode registrasi aktif. Tempelkan kartu."})


# === Endpoint Cerdas untuk Alat RFID ===

@app.route('/handle-tap', methods=['POST'])
def handle_tap():
    uid = request.json.get('uid')
    if not uid: return jsonify({"status": "error", "message": "UID tidak ada"}), 400
    try:
        cnx = mysql.connector.connect(**db_config)
        cursor = cnx.cursor(dictionary=True)

        # --- LOGIKA PAIRING ---
        if pairing_info["is_active"]:
            user_id = pairing_info["user_id_to_pair"]
            cursor.execute("SELECT nama FROM karyawan WHERE uid = %s", (uid,))
            if cursor.fetchone(): return jsonify({"status": "error", "message": "Kartu sudah dimiliki orang lain"})
            
            cursor.execute("UPDATE karyawan SET uid = %s WHERE id = %s", (uid, user_id))
            cnx.commit()
            pairing_info.update({"is_active": False, "user_id_to_pair": None})
            return jsonify({"status": "success", "message": "Registrasi Berhasil!"})
        
        # --- LOGIKA PRESENSI ---
        else:
            # 1. Cek apakah UID terdaftar dan aktif
            cursor.execute("SELECT * FROM karyawan WHERE uid = %s AND status_aktif = TRUE", (uid,))
            karyawan = cursor.fetchone()
            if not karyawan:
                return jsonify({"status": "error", "message": "Kartu Tidak Terdaftar"})

            # 2. Ambil data waktu
            nama_karyawan = karyawan['nama']
            today = date.today()
            now_time = datetime.now().time()

            # 3. Cek data presensi hari ini
            cursor.execute("SELECT id, jam_pulang FROM presensi WHERE uid = %s AND tanggal = %s", (uid, today))
            presensi_hari_ini = cursor.fetchone()

            if presensi_hari_ini is None:
                # === KONDISI 1: PRESENSI MASUK ===
                if now_time < WAKTU_MASUK_MULAI:
                    return jsonify({"status": "error", "message": "Belum Waktunya Presensi"})

                keterangan_masuk = 'TEPAT WAKTU' if now_time <= WAKTU_MASUK_AKHIR else 'TERLAMBAT'
                
                cursor.execute(
                    "INSERT INTO presensi (uid, tanggal, jam_masuk, keterangan) VALUES (%s, %s, %s, %s)",
                    (uid, today, now_time, keterangan_masuk)
                )
                cnx.commit()
                return jsonify({"status": "success", "message": f"Masuk: {nama_karyawan} ({keterangan_masuk})"})
            
            elif presensi_hari_ini['jam_pulang'] is None:
                # === KONDISI 2: PRESENSI PULANG atau DUPLIKAT MASUK ===
                if now_time >= WAKTU_PULANG_MULAI:
                    # Sudah waktunya pulang -> Lakukan presensi pulang
                    presensi_id = presensi_hari_ini['id']
                    cursor.execute(
                        "UPDATE presensi SET jam_pulang = %s WHERE id = %s",
                        (now_time, presensi_id)
                    )
                    cnx.commit()
                    return jsonify({"status": "success", "message": f"Pulang: {nama_karyawan}"})
                else:
                    # Belum waktunya pulang -> Dianggap duplikat tap masuk
                    return jsonify({"status": "done", "message": "Anda Sudah Presensi Masuk"})
            
            else:
                # === KONDISI 3: SUDAH PRESENSI MASUK & PULANG ===
                return jsonify({"status": "done", "message": "Anda Sudah Konfirmasi Pulang"})

    except Error as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if 'cnx' in locals() and cnx.is_connected():
            cursor.close()
            cnx.close()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)