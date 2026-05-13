from flask import Flask, jsonify, request
from flask_cors import CORS

import firebase_admin
from firebase_admin import credentials, db

import serial
import time
import threading

# =========================
# FLASK INIT
# =========================
app = Flask(__name__)
CORS(app)

# =========================
# FIREBASE INIT
# =========================
cred = credentials.Certificate("serviceAccountKey.json")

firebase_admin.initialize_app(cred, {
    "databaseURL": "https://test-fcb1f-default-rtdb.asia-southeast1.firebasedatabase.app/"
})

# =========================
# SERIAL CONFIG
# =========================
SERIAL_PORT = "COM5"
BAUD_RATE = 9600
ser = None

latest_rfid = ""
last_rfid_time = 0

# =========================
# SERIAL CONNECT
# =========================
def get_serial():
    global ser

    try:
        if ser and ser.is_open:
            return ser

        print("CONNECTING ESP32...")

        ser = serial.Serial(
            SERIAL_PORT,
            BAUD_RATE,
            timeout=1
        )

        time.sleep(2)
        print("ESP32 CONNECTED")

        return ser

    except Exception as e:
        print("SERIAL ERROR:", e)
        return None


# =========================
# SEND TO ESP32
# =========================
def send_command(command):
    try:
        conn = get_serial()
        if not conn:
            return {"success": False, "message": "No ESP32"}

        conn.write((command + "\n").encode())
        conn.flush()

        return {"success": True, "command": command}

    except Exception as e:
        return {"success": False, "message": str(e)}


# =========================
# SERIAL LISTENER (FIXED)
# =========================
def serial_listener():
    global latest_rfid, ser, last_rfid_time

    while True:
        try:
            conn = get_serial()
            if not conn:
                time.sleep(2)
                continue

            line = conn.readline().decode("utf-8", errors="ignore").strip()

            if not line:
                continue

            print("ESP32:", line)

            if "RFID_UID:" in line:

                uid = line.replace("RFID_UID:", "").strip().upper()

                now = time.time()

                # CHỐNG spam + đọc lặp cùng thẻ
                if uid != latest_rfid or (now - last_rfid_time > 3):

                    latest_rfid = uid
                    last_rfid_time = now

                    print("RFID:", latest_rfid)

        except Exception as e:
            print("SERIAL ERROR:", e)
            try:
                if ser:
                    ser.close()
            except:
                pass

            ser = None
            time.sleep(2)


# =========================
# UTIL
# =========================
def clean_digits(v):
    return "".join(filter(str.isdigit, str(v or "")))

def get_sessions():
    ref = db.reference("sessions")
    data = ref.get()
    return data if data else {}

def is_locker_busy(locker):
    sessions = get_sessions()

    for _, s in sessions.items():
        if s.get("active") and str(s.get("locker")) == str(locker):
            return True
    return False


# =========================
# HOME
# =========================
@app.route("/")
def home():
    return jsonify({"success": True, "message": "Backend running"})


# =========================
# RFID GET (SAFE)
# =========================
@app.route("/latest-rfid", methods=["GET"])
def get_rfid():
    global latest_rfid
    return jsonify({
        "success": True,
        "rfid": latest_rfid
    })


# =========================
# CLEAR RFID (IMPORTANT)
# =========================
@app.route("/clear-rfid", methods=["POST"])
def clear_rfid():
    global latest_rfid
    latest_rfid = ""
    return jsonify({"success": True})


# =========================
# DEPOSIT
# =========================
@app.route("/deposit", methods=["POST"])
def deposit():
    data = request.json

    name = data.get("name", "").strip()
    phone = clean_digits(data.get("phone"))
    cccd = clean_digits(data.get("cccd"))
    locker = str(data.get("locker", ""))
    pin = clean_digits(data.get("pin", ""))
    rfid = data.get("rfid", "").strip().upper()

    if not (name and phone and cccd and locker):
        return jsonify({"success": False, "message": "Missing data"}), 400

    if len(phone) != 10 or not phone.startswith("0"):
        return jsonify({"success": False, "message": "Phone invalid"}), 400

    if len(cccd) != 12:
        return jsonify({"success": False, "message": "CCCD invalid"}), 400

    if not pin and not rfid:
        return jsonify({"success": False, "message": "Need PIN or RFID"}), 400

    if is_locker_busy(locker):
        return jsonify({"success": False, "message": "Locker busy"}), 409

    # check RFID duplicate
    sessions = get_sessions()
    for s in sessions.values():
        if s.get("active") and s.get("rfid") == rfid and rfid:
            return jsonify({"success": False, "message": "RFID already used"}), 409

    cmd = f"OPEN_LOCKER_{locker}"

    ref = db.reference("sessions")
    new = ref.push({
        "name": name,
        "phone": phone,
        "cccd": cccd,
        "locker": locker,
        "pin": pin,
        "rfid": rfid,
        "active": True,
        "command": cmd
    })

    send_command(cmd)

    return jsonify({
        "success": True,
        "session_id": new.key,
        "esp32_command": cmd
    })


# =========================
# PICKUP
# =========================
@app.route("/pickup", methods=["POST"])
def pickup():
    data = request.json

    name = data.get("name", "").strip()
    phone = clean_digits(data.get("phone"))
    locker = str(data.get("locker", ""))
    pin = clean_digits(data.get("pin", ""))
    rfid = data.get("rfid", "").strip().upper()

    sessions = get_sessions()

    match_id = None

    for sid, s in sessions.items():

        if not s.get("active"):
            continue

        if str(s.get("locker")) != locker:
            continue

        if s.get("name", "").lower() != name.lower():
            continue

        if s.get("phone") != phone:
            continue

        ok_auth = (
            (pin and s.get("pin") == pin) or
            (rfid and s.get("rfid") == rfid)
        )

        if ok_auth:
            match_id = sid
            break

    if not match_id:
        return jsonify({"success": False, "message": "Not found"}), 404

    db.reference(f"sessions/{match_id}").update({"active": False})

    cmd = f"OPEN_LOCKER_{locker}"
    send_command(cmd)

    return jsonify({
        "success": True,
        "esp32_command": cmd
    })


# =========================
# START SERIAL THREAD
# =========================
threading.Thread(target=serial_listener, daemon=True).start()


# =========================
# RUN
# =========================
if __name__ == "__main__":
    print("SERVER STARTED")
    app.run(host="0.0.0.0", port=5000, debug=False)