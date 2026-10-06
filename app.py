from html import escape
from datetime import datetime
import sqlite3
from flask import Flask, render_template, request, redirect, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)


# =========================================================
# CORS
# =========================================================

@app.after_request
def add_cors_headers(response):

    origin = request.headers.get("Origin")

    allowed_origins = [
        "http://127.0.0.1:5500",
        "http://localhost:5500"
    ]

    if origin in allowed_origins:

        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"

    return response


# =========================================================
# DATABASE
# =========================================================

DATABASE = "appointments.db"


def init_db():

    with sqlite3.connect(DATABASE) as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT NOT NULL,
                date TEXT NOT NULL,
                message TEXT
            )
        """)

        columns = [
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(appointments)"
            ).fetchall()
        ]

        if "status" not in columns:

            conn.execute("""
                ALTER TABLE appointments
                ADD COLUMN status TEXT NOT NULL DEFAULT 'Pending'
            """)


init_db()


# =========================================================
# ADMIN SECURITY
# =========================================================

app.secret_key = "doctor-website-secret-key"

ADMIN_USERNAME = "admin"

ADMIN_PASSWORD_HASH = generate_password_hash("SAEE@1630")


# =========================================================
# APPOINTMENT API
# =========================================================

@app.route("/api/appointments", methods=["POST"])
def save_appointment():

    data = request.get_json(silent=True) or {}

    name = data.get("name", "").strip()
    phone = data.get("phone", "").strip()
    email = data.get("email", "").strip()
    date = data.get("date", "").strip()
    message = data.get("message", "").strip()

    if not name or not phone or not email or not date:

        return jsonify({
            "error": "Please fill all required fields."
        }), 400

    try:

        with sqlite3.connect(DATABASE) as conn:

            conn.execute("""
                INSERT INTO appointments
                (name, phone, email, date, message)
                VALUES (?, ?, ?, ?, ?)
            """, (
                name,
                phone,
                email,
                date,
                message
            ))

        return jsonify({
            "message": "Appointment saved successfully!"
        }), 201

    except sqlite3.Error:

        app.logger.exception("Could not save appointment")

        return jsonify({
            "error": "Could not save appointment."
        }), 500


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return "Dr. Dipika Thorat Website Backend is Working!"


# =========================================================
# ADMIN LOGIN PAGE
# =========================================================

@app.route("/admin")
def admin_login():

    if session.get("admin_logged_in"):

        return redirect("/admin/dashboard")

    return render_template("admin_login.html")


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route("/admin/login", methods=["POST"])
def admin_login_submit():

    username = request.form.get("username", "")
    password = request.form.get("password", "")

    if (
        ADMIN_USERNAME
        and ADMIN_PASSWORD_HASH
        and username == ADMIN_USERNAME
        and check_password_hash(
            ADMIN_PASSWORD_HASH,
            password
        )
    ):

        session["admin_logged_in"] = True

        return redirect("/admin/dashboard")

    return "Invalid username or password. Go back and try again.", 401


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin/dashboard")
def admin_dashboard():

    search = request.args.get(
        "search",
        ""
    ).strip().lower()

    filter_status = request.args.get(
        "status",
        ""
    ).strip()

    if not session.get("admin_logged_in"):

        return redirect("/admin")

    # -----------------------------------------------------
    # GET APPOINTMENTS
    # -----------------------------------------------------

    with sqlite3.connect(DATABASE) as conn:

        conn.row_factory = sqlite3.Row

        appointments = conn.execute("""
            SELECT
                id,
                name,
                phone,
                email,
                date,
                message,
                status
            FROM appointments
            ORDER BY id ASC
        """).fetchall()

    # -----------------------------------------------------
    # SEARCH + STATUS FILTER
    # -----------------------------------------------------

    filtered_appointments = []

    for a in appointments:

        current_status = a["status"] or "Pending"

        search_text = (
            str(a["name"] or "") + " " +
            str(a["phone"] or "") + " " +
            str(a["email"] or "")
        ).lower()

        matches_search = (
            not search
            or search in search_text
        )

        matches_status = (
            not filter_status
            or current_status == filter_status
        )

        if matches_search and matches_status:

            filtered_appointments.append(a)

    appointments = filtered_appointments

    # -----------------------------------------------------
    # STATUS COUNTS
    # -----------------------------------------------------

    total = len(appointments)

    pending = sum(
        1
        for a in appointments
        if (a["status"] or "Pending") == "Pending"
    )

    confirmed = sum(
        1
        for a in appointments
        if (a["status"] or "Pending") == "Confirmed"
    )

    completed = sum(
        1
        for a in appointments
        if (a["status"] or "Pending") == "Completed"
    )

    cancelled = sum(
        1
        for a in appointments
        if (a["status"] or "Pending") == "Cancelled"
    )

    # -----------------------------------------------------
    # CREATE TABLE ROWS
    # -----------------------------------------------------

    rows = ""

    for a in appointments:

        current_status = a["status"] or "Pending"

        status_class = current_status.lower()

        # Format appointment date
        appointment_date = "Not provided"

        if a["date"]:

            try:

                appointment_date = datetime.strptime(
                    str(a["date"]),
                    "%Y-%m-%d"
                ).strftime("%d-%m-%Y")

            except ValueError:

                appointment_date = str(a["date"])

        rows += f"""
        <tr>

            <td>
                {a['id']}
            </td>

            <td>
                <strong>
                    {escape(str(a['name'] or ''))}
                </strong>
            </td>

            <td>
                {escape(str(a['phone'] or ''))}
            </td>

            <td>
                {escape(str(a['email'] or ''))}
            </td>

            <td>
                {escape(appointment_date)}
            </td>

            <td class="message">
                {escape(str(a['message'] or ''))}
            </td>

            <td>

                <span class="status-badge {status_class}">
                    {escape(current_status)}
                </span>

                <!-- UPDATE STATUS -->

                <form
                    action="/admin/update-status"
                    method="POST"
                    class="status-form"
                >

                    <input
                        type="hidden"
                        name="appointment_id"
                        value="{a['id']}"
                    >

                    <select name="status">

                        <option value="Pending"
                            {"selected" if current_status == "Pending" else ""}>
                            Pending
                        </option>

                        <option value="Confirmed"
                            {"selected" if current_status == "Confirmed" else ""}>
                            Confirmed
                        </option>

                        <option value="Completed"
                            {"selected" if current_status == "Completed" else ""}>
                            Completed
                        </option>

                        <option value="Cancelled"
                            {"selected" if current_status == "Cancelled" else ""}>
                            Cancelled
                        </option>

                    </select>

                    <button
                        type="submit"
                        class="update-btn"
                    >
                        Update
                    </button>

                </form>


                <!-- DELETE APPOINTMENT -->

                <form
                    action="/admin/delete-appointment"
                    method="POST"
                    class="delete-form"
                    onsubmit="return confirm('Are you sure you want to delete this appointment?');"
                >

                    <input
                        type="hidden"
                        name="appointment_id"
                        value="{a['id']}"
                    >

                    <button
                        type="submit"
                        class="delete-btn"
                    >
                        Delete
                    </button>

                </form>

            </td>

        </tr>
        """

    # -----------------------------------------------------
    # NO DATA
    # -----------------------------------------------------

    if not appointments:

        rows = """
        <tr>

            <td
                colspan="7"
                class="no-data"
            >
                No appointments found.
            </td>

        </tr>
        """

    # =====================================================
    # DASHBOARD HTML
    # =====================================================

    return f"""
    <!DOCTYPE html>

    <html lang="en">

    <head>

        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1"
        >

        <title>
            Admin Dashboard | Dr. Dipika Thorat
        </title>

        <style>

            * {{
                box-sizing: border-box;
            }}

            body {{
                margin: 0;
                font-family: Arial, sans-serif;
                background: #f4f8f7;
                color: #222;
            }}

            /* HEADER */

            .header {{
                background: #176b63;
                color: white;
                padding: 22px 30px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 15px;
            }}

            .header h1 {{
                margin: 0;
                font-size: 26px;
            }}

            .header p {{
                margin: 6px 0 0;
                opacity: 0.9;
            }}

            .logout {{
                text-decoration: none;
                background: white;
                color: #176b63;
                padding: 9px 16px;
                border-radius: 6px;
                font-weight: bold;
            }}

            /* CONTAINER */

            .container {{
                max-width: 1400px;
                margin: 30px auto;
                padding: 0 20px;
            }}

            /* CARDS */

            .cards {{
                display: grid;
                grid-template-columns:
                    repeat(5, minmax(150px, 1fr));
                gap: 18px;
                margin-bottom: 30px;
            }}

            .card {{
                background: white;
                border-radius: 12px;
                padding: 20px;
                box-shadow:
                    0 3px 12px rgba(0,0,0,0.08);
                border-left: 5px solid #176b63;
            }}

            .card h3 {{
                margin: 0;
                font-size: 15px;
                color: #666;
            }}

            .card .number {{
                font-size: 30px;
                font-weight: bold;
                margin-top: 8px;
            }}

            .card.pending {{
                border-left-color: #f0a500;
            }}

            .card.confirmed {{
                border-left-color: #198754;
            }}

            .card.completed {{
                border-left-color: #2878c8;
            }}

            .card.cancelled {{
                border-left-color: #dc3545;
            }}

            /* TABLE BOX */

            .table-box {{
                background: white;
                border-radius: 12px;
                padding: 20px;
                box-shadow:
                    0 3px 12px rgba(0,0,0,0.08);
            }}

            .table-box h2 {{
                margin-top: 0;
                color: #176b63;
            }}

            /* SEARCH & FILTER */

            .filter-form {{
                display: flex;
                gap: 10px;
                margin-bottom: 20px;
                flex-wrap: wrap;
            }}

            .filter-form input {{
                padding: 10px;
                border: 1px solid #ccc;
                border-radius: 6px;
                min-width: 280px;
            }}

            .filter-form select {{
                padding: 10px;
                border: 1px solid #ccc;
                border-radius: 6px;
                background: white;
            }}

            .filter-form button {{
                padding: 10px 16px;
                border: none;
                border-radius: 6px;
                background: #087f8c;
                color: white;
                font-weight: bold;
                cursor: pointer;
            }}

            .filter-form button:hover {{
                background: #055c65;
            }}

            .clear-filter {{
                padding: 10px 14px;
                background: #eee;
                color: #333;
                text-decoration: none;
                border-radius: 6px;
            }}

            .clear-filter:hover {{
                background: #ddd;
            }}

            /* TABLE */

            .table-container {{
                overflow-x: auto;
            }}

            table {{
                width: 100%;
                min-width: 1000px;
                border-collapse: collapse;
            }}

            th {{
                background: #176b63;
                color: white;
                padding: 12px;
                text-align: left;
                white-space: nowrap;
            }}

            td {{
                padding: 12px;
                border-bottom: 1px solid #e5e5e5;
                vertical-align: middle;
            }}

            tr:hover {{
                background: #f7fbfa;
            }}

            .message {{
                max-width: 250px;
                word-break: break-word;
            }}

            /* STATUS BADGES */

            .status-badge {{
                display: inline-block;
                padding: 5px 10px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: bold;
                margin-bottom: 8px;
            }}

            .status-badge.pending {{
                background: #fff3cd;
                color: #856404;
            }}

            .status-badge.confirmed {{
                background: #d1e7dd;
                color: #0f5132;
            }}

            .status-badge.completed {{
                background: #cfe2ff;
                color: #084298;
            }}

            .status-badge.cancelled {{
                background: #f8d7da;
                color: #842029;
            }}

            /* STATUS FORM */

            .status-form {{
                display: flex;
                align-items: center;
                gap: 6px;
            }}

            select {{
                padding: 7px;
                border: 1px solid #ccc;
                border-radius: 5px;
                background: white;
            }}

            /* UPDATE BUTTON */

            .update-btn {{
                padding: 7px 12px;
                border: none;
                border-radius: 5px;
                background: #176b63;
                color: white;
                cursor: pointer;
                font-weight: bold;
            }}

            .update-btn:hover {{
                background: #12534d;
            }}

            /* DELETE BUTTON */

            .delete-form {{
                margin-top: 8px;
            }}

            .delete-btn {{
                padding: 7px 12px;
                border: none;
                border-radius: 5px;
                background: #dc3545;
                color: white;
                cursor: pointer;
                font-weight: bold;
            }}

            .delete-btn:hover {{
                background: #b02a37;
            }}

            /* NO DATA */

            .no-data {{
                text-align: center;
                padding: 30px;
                color: #777;
            }}

            /* TABLE HEADING */

            th:last-child {{
                min-width: 190px;
            }}

            /* RESPONSIVE */

            @media (max-width: 900px) {{

                .cards {{
                    grid-template-columns:
                        repeat(2, 1fr);
                }}

            }}

            @media (max-width: 500px) {{

                .header {{
                    padding: 18px;
                }}

                .header h1 {{
                    font-size: 21px;
                }}

                .container {{
                    padding: 0 12px;
                }}

                .cards {{
                    grid-template-columns: 1fr;
                }}

                .table-box {{
                    padding: 12px;
                }}

                .filter-form input {{
                    min-width: 100%;
                }}

            }}

        </style>

    </head>


    <body>

        <!-- HEADER -->

        <div class="header">

            <div>

                <h1>
                    Admin Dashboard
                </h1>

                <p>
                    Dr. Dipika Thorat Family Physician
                </p>

            </div>

            <a
                href="/admin/logout"
                class="logout"
            >
                Logout
            </a>

        </div>


        <!-- MAIN CONTAINER -->

        <div class="container">


            <!-- DASHBOARD CARDS -->

            <div class="cards">

                <div class="card">

                    <h3>
                        Total Appointments
                    </h3>

                    <div class="number">
                        {total}
                    </div>

                </div>


                <div class="card pending">

                    <h3>
                        Pending
                    </h3>

                    <div class="number">
                        {pending}
                    </div>

                </div>


                <div class="card confirmed">

                    <h3>
                        Confirmed
                    </h3>

                    <div class="number">
                        {confirmed}
                    </div>

                </div>


                <div class="card completed">

                    <h3>
                        Completed
                    </h3>

                    <div class="number">
                        {completed}
                    </div>

                </div>


                <div class="card cancelled">

                    <h3>
                        Cancelled
                    </h3>

                    <div class="number">
                        {cancelled}
                    </div>

                </div>

            </div>


            <!-- APPOINTMENT TABLE -->

            <div class="table-box">

                <h2>
                    Appointment Requests
                </h2>


                <!-- SEARCH & FILTER -->

                <form
                    method="GET"
                    action="/admin/dashboard"
                    class="filter-form"
                >

                    <input
                        type="text"
                        name="search"
                        placeholder="Search patient, phone or email"
                        value="{escape(search)}"
                    >


                    <select name="status">

                        <option value="">
                            All Status
                        </option>


                        <option value="Pending"
                            {"selected" if filter_status == "Pending" else ""}>
                            Pending
                        </option>


                        <option value="Confirmed"
                            {"selected" if filter_status == "Confirmed" else ""}>
                            Confirmed
                        </option>


                        <option value="Completed"
                            {"selected" if filter_status == "Completed" else ""}>
                            Completed
                        </option>


                        <option value="Cancelled"
                            {"selected" if filter_status == "Cancelled" else ""}>
                            Cancelled
                        </option>

                    </select>


                    <button type="submit">
                        Search
                    </button>


                    <a
                        href="/admin/dashboard"
                        class="clear-filter"
                    >
                        Clear
                    </a>

                </form>


                <!-- TABLE -->

                <div class="table-container">

                    <table>

                        <thead>

                            <tr>

                                <th>
                                    ID
                                </th>

                                <th>
                                    Patient Name
                                </th>

                                <th>
                                    Phone
                                </th>

                                <th>
                                    Email
                                </th>

                                <th>
                                    Date
                                </th>

                                <th>
                                    Message
                                </th>

                                <th>
                                    Status / Actions
                                </th>

                            </tr>

                        </thead>


                        <tbody>

                            {rows}

                        </tbody>

                    </table>

                </div>

            </div>

        </div>

    </body>

    </html>
    """

# =========================================================
# UPDATE APPOINTMENT STATUS
# =========================================================

@app.route("/admin/update-status", methods=["POST"])
def update_status():

    if not session.get("admin_logged_in"):

        return redirect("/admin")

    appointment_id = request.form.get(
        "appointment_id"
    )

    status = request.form.get(
        "status"
    )

    allowed_statuses = [
        "Pending",
        "Confirmed",
        "Completed",
        "Cancelled"
    ]

    if status not in allowed_statuses:

        return "Invalid status.", 400

    try:

        with sqlite3.connect(DATABASE) as conn:

            conn.execute("""
                UPDATE appointments
                SET status = ?
                WHERE id = ?
            """, (
                status,
                appointment_id
            ))

        return redirect("/admin/dashboard")

    except sqlite3.Error:

        app.logger.exception(
            "Could not update appointment status"
        )

        return "Could not update appointment status.", 500


# =========================================================
# DELETE APPOINTMENT
# =========================================================

@app.route(
    "/admin/delete-appointment",
    methods=["POST"]
)
def delete_appointment():

    if not session.get("admin_logged_in"):

        return redirect("/admin")

    appointment_id = request.form.get(
        "appointment_id"
    )

    try:

        with sqlite3.connect(DATABASE) as conn:

            conn.execute(
                "DELETE FROM appointments WHERE id = ?",
                (appointment_id,)
            )

            conn.commit()

        return redirect("/admin/dashboard")

    except sqlite3.Error:

        app.logger.exception(
            "Could not delete appointment"
        )

        return "Could not delete appointment.", 500


# =========================================================
# LOGOUT
# =========================================================

@app.route("/admin/logout")
def admin_logout():

    session.clear()

    return redirect("/admin")


# =========================================================
# RUN FLASK
# =========================================================

if __name__ == "__main__":

    app.run(debug=True)