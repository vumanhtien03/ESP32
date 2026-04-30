from flask import Flask, jsonify, request
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)
CORS(app)

cred = credentials.Certificate("serviceAccountKey.json")

firebase_admin.initialize_app(cred, {
    "databaseURL": "https://test-fcb1f-default-rtdb.asia-southeast1.firebasedatabase.app/"
})


# =========================
# HÀM PHỤ
# =========================

def clean_digits(value):
    if value is None:
        return ""
    return "".join(filter(str.isdigit, str(value).strip()))


def validate_phone(phone):
    return len(phone) == 10 and phone.startswith("0")


def validate_cccd(cccd):
    return len(cccd) == 12 and cccd.isdigit()


def validate_pin(pin):
    return pin == "" or (pin.isdigit() and 4 <= len(pin) <= 6)


def normalize_text(text):
    return str(text or "").strip().lower()


def get_all_sessions():
    ref = db.reference("sessions")
    data = ref.get()

    if data is None:
        return {}

    return data


def is_locker_busy(locker):
    sessions = get_all_sessions()

    for session_id, session in sessions.items():
        if (
            str(session.get("locker")) == str(locker)
            and session.get("active") == True
        ):
            return True

    return False


# =========================
# 1. API TRA CỨU TỦ
# =========================

@app.route("/lookup", methods=["POST"])
def lookup_lockers():
    data = request.get_json()

    name = data.get("name", "").strip()
    phone = clean_digits(data.get("phone", ""))
    cccd = clean_digits(data.get("cccd", ""))

    if not name or not phone or not cccd:
        return jsonify({
            "success": False,
            "message": "Vui lòng nhập đầy đủ họ tên, số điện thoại và CCCD."
        }), 400

    if not validate_phone(phone):
        return jsonify({
            "success": False,
            "message": "Số điện thoại phải đủ 10 số và bắt đầu bằng số 0."
        }), 400

    if not validate_cccd(cccd):
        return jsonify({
            "success": False,
            "message": "CCCD phải đúng 12 chữ số."
        }), 400

    sessions = get_all_sessions()
    matches = []

    for session_id, session in sessions.items():
        if (
            session.get("active") == True
            and normalize_text(session.get("name")) == normalize_text(name)
            and session.get("phone") == phone
            and session.get("cccd") == cccd
        ):
            matches.append({
                "session_id": session_id,
                "locker": session.get("locker"),
                "name": session.get("name"),
                "phone": session.get("phone"),
                "cccd": session.get("cccd"),
                "rfid": session.get("rfid", ""),
                "active": session.get("active")
            })

    if not matches:
        return jsonify({
            "success": False,
            "message": "Không tìm thấy tủ nào đang được gửi bởi khách hàng này."
        }), 404

    return jsonify({
        "success": True,
        "message": "Tra cứu thành công",
        "lockers": matches
    }), 200


# =========================
# 2. API GỬI ĐỒ
# =========================

@app.route("/deposit", methods=["POST"])
def deposit_locker():
    data = request.get_json()

    name = data.get("name", "").strip()
    phone = clean_digits(data.get("phone", ""))
    cccd = clean_digits(data.get("cccd", ""))
    locker = str(data.get("locker", "")).strip()
    pin = clean_digits(data.get("pin", ""))
    rfid = data.get("rfid", "").strip().upper()

    if not name or not phone or not cccd or not locker:
        return jsonify({
            "success": False,
            "message": "Vui lòng nhập đầy đủ họ tên, số điện thoại, CCCD và chọn tủ."
        }), 400

    if not validate_phone(phone):
        return jsonify({
            "success": False,
            "message": "Số điện thoại phải đủ 10 số và bắt đầu bằng số 0."
        }), 400

    if not validate_cccd(cccd):
        return jsonify({
            "success": False,
            "message": "CCCD phải đúng 12 chữ số."
        }), 400

    if locker not in ["1", "2", "3", "4", "5", "6", "7", "8"]:
        return jsonify({
            "success": False,
            "message": "Tủ không hợp lệ. Chỉ được chọn tủ từ 1 đến 8."
        }), 400

    if not pin and not rfid:
        return jsonify({
            "success": False,
            "message": "Khách phải nhập ít nhất một cách mở tủ: mã PIN hoặc RFID."
        }), 400

    if pin and not validate_pin(pin):
        return jsonify({
            "success": False,
            "message": "PIN phải từ 4 đến 6 chữ số."
        }), 400

    if is_locker_busy(locker):
        return jsonify({
            "success": False,
            "message": "Tủ này hiện đã có người dùng, vui lòng chọn tủ khác."
        }), 409

    session_data = {
        "locker": locker,
        "name": name,
        "phone": phone,
        "cccd": cccd,
        "pin": pin,
        "rfid": rfid,
        "active": True,
        "cardReturned": False if rfid else True,
        "command": f"OPEN_LOCKER_{locker}"
    }

    ref = db.reference("sessions")
    new_session = ref.push(session_data)

    return jsonify({
        "success": True,
        "message": "Gửi đồ thành công",
        "session_id": new_session.key,
        "data": session_data,
        "esp32_command": f"OPEN_LOCKER_{locker}"
    }), 201


# =========================
# 3. API LẤY ĐỒ
# =========================

@app.route("/pickup", methods=["POST"])
def pickup_locker():
    data = request.get_json()

    name = data.get("name", "").strip()
    phone = clean_digits(data.get("phone", ""))
    locker = str(data.get("locker", "")).strip()
    pin = clean_digits(data.get("pin", ""))
    rfid = data.get("rfid", "").strip().upper()

    if not name or not phone or not locker:
        return jsonify({
            "success": False,
            "message": "Vui lòng nhập họ tên, số điện thoại và chọn tủ cần mở."
        }), 400

    if not validate_phone(phone):
        return jsonify({
            "success": False,
            "message": "Số điện thoại phải đủ 10 số và bắt đầu bằng số 0."
        }), 400

    if not pin and not rfid:
        return jsonify({
            "success": False,
            "message": "Khách phải nhập ít nhất mã PIN hoặc RFID để lấy đồ."
        }), 400

    if pin and not validate_pin(pin):
        return jsonify({
            "success": False,
            "message": "PIN phải từ 4 đến 6 chữ số."
        }), 400

    sessions = get_all_sessions()
    matched_id = None
    matched_session = None

    for session_id, session in sessions.items():
        correct_user = (
            session.get("active") == True
            and str(session.get("locker")) == locker
            and normalize_text(session.get("name")) == normalize_text(name)
            and session.get("phone") == phone
        )

        correct_auth = (
            (pin and session.get("pin") == pin)
            or
            (rfid and session.get("rfid") == rfid)
        )

        if correct_user and correct_auth:
            matched_id = session_id
            matched_session = session
            break

    if not matched_session:
        return jsonify({
            "success": False,
            "message": "Thông tin không khớp với tủ đã chọn. Vui lòng kiểm tra lại."
        }), 404

    update_ref = db.reference(f"sessions/{matched_id}")
    update_ref.update({
        "active": False,
        "command": f"OPEN_LOCKER_{locker}"
    })

    return jsonify({
        "success": True,
        "message": "Lấy đồ thành công",
        "session_id": matched_id,
        "data": matched_session,
        "esp32_command": f"OPEN_LOCKER_{locker}"
    }), 200


# =========================
# 4. API TRA CỨU PHIÊN LẤY ĐỒ
# Dùng để tìm khách có những tủ nào trước khi bấm lấy đồ
# =========================

@app.route("/pickup/search", methods=["POST"])
def search_pickup_sessions():
    data = request.get_json()

    name = data.get("name", "").strip()
    phone = clean_digits(data.get("phone", ""))
    pin = clean_digits(data.get("pin", ""))
    rfid = data.get("rfid", "").strip().upper()

    if not name or not phone:
        return jsonify({
            "success": False,
            "message": "Vui lòng nhập họ tên và số điện thoại."
        }), 400

    if not validate_phone(phone):
        return jsonify({
            "success": False,
            "message": "Số điện thoại phải đủ 10 số và bắt đầu bằng số 0."
        }), 400

    if not pin and not rfid:
        return jsonify({
            "success": False,
            "message": "Khách phải nhập ít nhất mã PIN hoặc RFID để tra cứu phiên lấy đồ."
        }), 400

    sessions = get_all_sessions()
    matches = []

    for session_id, session in sessions.items():
        correct_user = (
            session.get("active") == True
            and normalize_text(session.get("name")) == normalize_text(name)
            and session.get("phone") == phone
        )

        correct_auth = (
            (pin and session.get("pin") == pin)
            or
            (rfid and session.get("rfid") == rfid)
        )

        if correct_user and correct_auth:
            matches.append({
                "session_id": session_id,
                "locker": session.get("locker"),
                "name": session.get("name"),
                "phone": session.get("phone"),
                "rfid": session.get("rfid", ""),
                "active": session.get("active")
            })

    if not matches:
        return jsonify({
            "success": False,
            "message": "Không tìm thấy phiên lấy đồ phù hợp."
        }), 404

    return jsonify({
        "success": True,
        "message": "Tra cứu phiên lấy đồ thành công",
        "sessions": matches
    }), 200


# =========================
# 5. API XEM TẤT CẢ PHIÊN
# Dùng để debug
# =========================

@app.route("/sessions", methods=["GET"])
def list_sessions():
    sessions = get_all_sessions()

    return jsonify({
        "success": True,
        "data": sessions
    }), 200


if __name__ == "__main__":
    app.run(debug=True)