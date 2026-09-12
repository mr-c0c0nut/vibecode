"""
ĐỀ THI SIÊU KHÓ — single-file Flask backend
--------------------------------------------
- 5 câu trắc nghiệm (A/B/C/D) + 10 câu tự luận, KHÔNG có đáp án mẫu.
- Mỗi IP chỉ được làm bài đúng 1 lần.
- Người ra đề (bạn) chấm tay từng câu qua trang /admin, được bảo vệ bằng mã:
      102980180280
- Người làm bài xem điểm của chính mình (theo IP) tại /result sau khi được chấm.

CHỈNH SỬA ĐỀ BÀI: sửa danh sách MCQ_QUESTIONS và ESSAY_QUESTIONS bên dưới.

LƯU Ý THẬT LÒNG về "anti Google Lens":
Không có cách nào từ phía trình duyệt/server chặn tuyệt đối việc ai đó
chụp màn hình hay dùng Google Lens (đó là hành vi ở tầng hệ điều hành,
ngoài tầm với của một trang web). Mình đã thêm các lớp "gây khó dễ + có
thể truy vết" phổ biến nhất:
  - chặn bôi đen / copy / chuột phải / các phím tắt DevTools thường gặp
  - làm mờ toàn bộ đề khi tab mất focus (đổi cửa sổ, mở tool chụp ảnh...)
  - watermark động (IP + thời gian) chạy khắp màn hình, để nếu ai đó vẫn
    chụp được thì ảnh có "dấu vết" gắn với đúng người đã làm bài.
Đây là "deterrent" (làm nản lòng + truy được nguồn), không phải khóa cứng.
"""

import json
import os
import time
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash
)

app = Flask(__name__)
app.secret_key = os.environ.get("EXAM_SECRET_KEY", "doi-chuoi-nay-truoc-khi-deploy-that")

ADMIN_CODE = "102980180280"
DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "submissions.json")

# ---------------------------------------------------------------------------
# ĐỀ BÀI — sửa nội dung tại đây (giữ nguyên cấu trúc key)
# ---------------------------------------------------------------------------
MCQ_QUESTIONS = [
    {"id": "mcq1", "text": "Câu trắc nghiệm 1 — [nhập đề bài của bạn tại đây]",
     "options": {"A": "[phương án A]", "B": "[phương án B]",
                 "C": "[phương án C]", "D": "[phương án D]"}},
    {"id": "mcq2", "text": "Câu trắc nghiệm 2 — [nhập đề bài của bạn tại đây]",
     "options": {"A": "[phương án A]", "B": "[phương án B]",
                 "C": "[phương án C]", "D": "[phương án D]"}},
    {"id": "mcq3", "text": "Câu trắc nghiệm 3 — [nhập đề bài của bạn tại đây]",
     "options": {"A": "[phương án A]", "B": "[phương án B]",
                 "C": "[phương án C]", "D": "[phương án D]"}},
    {"id": "mcq4", "text": "Câu trắc nghiệm 4 — [nhập đề bài của bạn tại đây]",
     "options": {"A": "[phương án A]", "B": "[phương án B]",
                 "C": "[phương án C]", "D": "[phương án D]"}},
    {"id": "mcq5", "text": "Câu trắc nghiệm 5 — [nhập đề bài của bạn tại đây]",
     "options": {"A": "[phương án A]", "B": "[phương án B]",
                 "C": "[phương án C]", "D": "[phương án D]"}},
]

ESSAY_QUESTIONS = [
    {"id": f"essay{i}", "text": f"Câu tự luận {i} — [nhập đề bài của bạn tại đây]"}
    for i in range(1, 11)
]

ALL_QUESTION_IDS = [q["id"] for q in MCQ_QUESTIONS] + [q["id"] for q in ESSAY_QUESTIONS]

# ---------------------------------------------------------------------------
# Lưu trữ dữ liệu (JSON file, đơn giản, không cần DB)
# ---------------------------------------------------------------------------

def _ensure_store():
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)


def load_data():
    _ensure_store()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    _ensure_store()
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_client_ip():
    # Ưu tiên header từ reverse proxy (Render, Nginx...) rồi mới tới remote_addr
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Trang thi
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    ip = get_client_ip()
    data = load_data()
    if ip in data:
        return redirect(url_for("result"))
    return render_template(
        "index.html",
        mcq_questions=MCQ_QUESTIONS,
        essay_questions=ESSAY_QUESTIONS,
        client_ip=ip,
    )


@app.route("/submit", methods=["POST"])
def submit():
    ip = get_client_ip()
    data = load_data()
    if ip in data:
        # IP này đã nộp bài rồi -> không cho nộp lại
        return redirect(url_for("result"))

    answers = {qid: request.form.get(qid, "").strip() for qid in ALL_QUESTION_IDS}

    data[ip] = {
        "ip": ip,
        "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "answers": answers,
        "graded": False,
        "grades": {},   # qid -> "correct" | "incorrect"
        "comments": {}, # qid -> ghi chú của người chấm
        "total_score": None,
    }
    save_data(data)
    return redirect(url_for("result"))


@app.route("/result", methods=["GET"])
def result():
    ip = get_client_ip()
    data = load_data()
    submission = data.get(ip)
    return render_template(
        "result.html",
        submission=submission,
        mcq_questions=MCQ_QUESTIONS,
        essay_questions=ESSAY_QUESTIONS,
    )


# ---------------------------------------------------------------------------
# Khu vực admin (ẩn) — chấm bài
# ---------------------------------------------------------------------------
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        code = request.form.get("code", "")
        if code == ADMIN_CODE:
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Mã bảo mật không đúng.")
        return redirect(url_for("admin_login"))
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("index"))


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    data = load_data()
    submissions = sorted(data.values(), key=lambda s: s["submitted_at"], reverse=True)
    return render_template("admin_dashboard.html", submissions=submissions)


@app.route("/admin/grade/<ip_key>", methods=["GET", "POST"])
@admin_required
def admin_grade(ip_key):
    data = load_data()
    submission = data.get(ip_key)
    if not submission:
        flash("Không tìm thấy bài làm của IP này.")
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        grades = {}
        comments = {}
        correct_count = 0
        for qid in ALL_QUESTION_IDS:
            verdict = request.form.get(f"grade_{qid}", "unmarked")
            grades[qid] = verdict
            comments[qid] = request.form.get(f"comment_{qid}", "").strip()
            if verdict == "correct":
                correct_count += 1
        submission["grades"] = grades
        submission["comments"] = comments
        submission["total_score"] = correct_count
        submission["graded"] = True
        data[ip_key] = submission
        save_data(data)
        flash("Đã lưu kết quả chấm.")
        return redirect(url_for("admin_dashboard"))

    return render_template(
        "admin_grade.html",
        submission=submission,
        mcq_questions=MCQ_QUESTIONS,
        essay_questions=ESSAY_QUESTIONS,
    )


@app.route("/admin/reset/<ip_key>", methods=["POST"])
@admin_required
def admin_reset(ip_key):
    """Xoá bài làm của 1 IP để họ được thi lại (dùng khi cần, không bắt buộc)."""
    data = load_data()
    if ip_key in data:
        del data[ip_key]
        save_data(data)
        flash(f"Đã xoá bài làm của IP {ip_key} — IP này có thể thi lại.")
    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    _ensure_store()
    app.run(host="0.0.0.0", port=5000, debug=True)
