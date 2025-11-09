import json
import os
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_mail import Mail, Message 
from werkzeug.utils import secure_filename

try:  # Supabase client is optional until installed
    from supabase import Client, create_client  # type: ignore
except ImportError:  # pragma: no cover - package not installed yet
    Client = Any  # type: ignore
    create_client = None  # type: ignore


ALLOWED_EXTENSIONS = {".csv", ".xlsx"}
COLUMN_ALIASES = {
    "roll no": "roll_number",
    "roll number": "roll_number",
    "roll": "roll_number",
    "student id": "roll_number",
    "studentid": "roll_number",
    "id": "roll_number",
    "student name": "student_name",
    "name": "student_name",
    "full name": "student_name",
    "course": "course",
    "course name": "course",
    "programme": "course",
    "attendance": "attendance_percent",
    "attendance %": "attendance_percent",
    "attendance percent": "attendance_percent",
    "attendance percentage": "attendance_percent",
    "email": "email",
    "email address": "email",
    "phone": "phone_number",
    "phone no": "phone_number",
    "phone number": "phone_number",
    "contact": "phone_number",
    "contact number": "phone_number",
    "alert status": "alert_status",
}

DISPLAY_LABELS = {
    "roll_number": "Roll Number",
    "student_name": "Student Name",
    "course": "Course",
    "attendance_percent": "Attendance %",
    "email": "Email",
    "phone_number": "Phone Number",
    "alert_status": "Alert Status",
}

PRIMARY_COLUMN_ORDER = [
    "roll_number",
    "student_name",
    "course",
    "attendance_percent",
    "email",
    "phone_number",
    "alert_status",
]

DATA_CACHE: Dict[str, Dict[str, Any]] = {}
USER_SETTINGS: Dict[str, Dict[str, Any]] = {}

DEFAULT_MESSAGE_TEMPLATE = (
    "Dear {student_name},\n\n"
    "Your current attendance is {attendance_percent:.1f}%, which is below the required threshold of {threshold:.1f}%.\n"
    "Please connect with your course advisor to plan a recovery strategy.\n\n"
    "Regards,\nAttendance Monitoring Team"
)

INSIGHTS_LOWEST_LIMIT = 5
MAX_TEMPLATE_LENGTH = 4000
MESSAGE_TEMPLATE_PLACEHOLDERS = [
    {"key": "student_name", "description": "Student's full name"},
    {"key": "roll_number", "description": "Student roll number or ID"},
    {"key": "course", "description": "Course or program name"},
    {"key": "attendance_percent", "description": "Attendance value as a number"},
    {"key": "attendance_percent_formatted", "description": "Attendance formatted with one decimal"},
    {"key": "threshold", "description": "Current threshold value"},
    {"key": "threshold_formatted", "description": "Threshold formatted with one decimal"},
    {"key": "email", "description": "Student email address"},
    {"key": "phone_number", "description": "Student phone number"},
]


def load_env(file_name: str = "env.txt") -> None:
    """Populate os.environ from a simple KEY=VALUE env file."""
    env_path = Path(__file__).with_name(file_name)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def load_json_secrets(file_name: str = "secret.json") -> None:
    """Load flat JSON secrets into the environment if present."""
    json_path = Path(__file__).with_name(file_name)
    if not json_path.exists():
        return

    try:
        secrets = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return

    for key, value in secrets.items():
        if isinstance(value, (dict, list)):
            continue
        os.environ.setdefault(key, str(value))


load_env()
load_json_secrets()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "replace-with-a-secure-secret")

secret_path = Path(__file__).with_name("secret.json")
if secret_path.exists():
    try:
        secrets = json.loads(secret_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        secrets = {}
else:
    secrets = {}


def get_setting(key: str, default: Optional[Any] = None) -> Optional[Any]:
    if key in os.environ:
        return os.environ[key]
    return secrets.get(key, default)


def str_to_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    value_str = str(value).strip().lower()
    if value_str in {"1", "true", "yes", "on"}:
        return True
    if value_str in {"0", "false", "no", "off"}:
        return False
    return default


def to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


app.config.update(
    MAIL_SERVER=get_setting("MAIL_SERVER", "smtp.gmail.com"),
    MAIL_PORT=to_int(get_setting("MAIL_PORT", 587), 587),
    MAIL_USE_TLS=str_to_bool(get_setting("MAIL_USE_TLS", True), True),
    MAIL_USE_SSL=str_to_bool(get_setting("MAIL_USE_SSL", False), False),
    MAIL_USERNAME=get_setting("MAIL_USERNAME"),
    MAIL_PASSWORD=get_setting("MAIL_PASSWORD"),
    MAIL_DEFAULT_SENDER=get_setting("MAIL_DEFAULT_SENDER", get_setting("MAIL_USERNAME")),
    MAIL_SUPPRESS_SEND=str_to_bool(get_setting("MAIL_SUPPRESS_SEND", False), False),
)

mail = Mail(app)


def get_user_settings(user_key: Optional[str]) -> Dict[str, Any]:
    if not user_key:
        return {"template": DEFAULT_MESSAGE_TEMPLATE}
    settings = USER_SETTINGS.setdefault(user_key, {})
    if not settings.get("template"):
        settings["template"] = DEFAULT_MESSAGE_TEMPLATE
    return settings


def get_message_template(user_key: Optional[str]) -> str:
    return get_user_settings(user_key).get("template", DEFAULT_MESSAGE_TEMPLATE)


def set_message_template(user_key: str, template: str) -> None:
    USER_SETTINGS.setdefault(user_key, {})["template"] = template or DEFAULT_MESSAGE_TEMPLATE


class SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:  # pragma: no cover - graceful fallback
        return "{" + key + "}"


def render_message_template(template: str, context: Dict[str, Any]) -> str:
    try:
        return template.format_map(SafeFormatDict(context))
    except Exception:  # pragma: no cover - fallback if formatting fails
        return template


def build_message_context(row: pd.Series, threshold: float) -> Dict[str, Any]:
    attendance_value = float(row.get("attendance_percent", 0.0))
    threshold_value = float(threshold)
    context: Dict[str, Any] = {
        "student_name": row.get("student_name") or "Student",
        "roll_number": row.get("roll_number", ""),
        "course": row.get("course", ""),
        "attendance_percent": attendance_value,
        "attendance_percent_formatted": f"{attendance_value:.1f}",
        "threshold": threshold_value,
        "threshold_formatted": f"{threshold_value:.1f}",
        "email": row.get("email", ""),
        "phone_number": row.get("phone_number", ""),
    }
    return context


def build_insights(
    df: pd.DataFrame,
    threshold: float,
    charts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    suggestions: List[str] = []
    lowest_records: List[Dict[str, Any]] = []
    stats: Dict[str, Any] = {"threshold": round(float(threshold), 2)}

    if df.empty:
        suggestions.append("Upload a CSV/XLSX file to unlock attendance insights.")
        return {"suggestions": suggestions, "lowest": lowest_records, "stats": stats}

    total_students = int(len(df))
    threshold_value = float(threshold)
    attendance_series = df["attendance_percent"].astype(float)
    below_mask = attendance_series < threshold_value
    below_count = int(below_mask.sum())
    below_pct = round((below_count / total_students) * 100, 1) if total_students else 0.0
    median_attendance = round(float(attendance_series.median()), 2)
    average_attendance = round(float(attendance_series.mean()), 2)

    stats.update(
        {
            "total_students": total_students,
            "below_threshold_count": below_count,
            "below_threshold_pct": below_pct,
            "at_or_above_threshold_pct": round(max(0.0, 100.0 - below_pct), 1),
            "median_attendance": median_attendance,
            "average_attendance": average_attendance,
        }
    )

    if below_count:
        suggestions.append(
            f"{below_pct}% of students ({below_count}/{total_students}) are below the {threshold_value:.1f}% threshold."
        )
    else:
        suggestions.append("Great work! All students currently meet the attendance threshold.")

    if "course" in df.columns and not df["course"].isna().all():
        course_means = df.groupby("course")["attendance_percent"].mean().sort_values()
        if not course_means.empty:
            stats["lowest_course"] = str(course_means.index[0])
            stats["lowest_course_average"] = round(float(course_means.iloc[0]), 1)
            stats["highest_course"] = str(course_means.index[-1])
            stats["highest_course_average"] = round(float(course_means.iloc[-1]), 1)

            low_courses = course_means[course_means < threshold_value]
            if not low_courses.empty:
                focus_courses = ", ".join(
                    f"{course} ({avg:.1f}%)" for course, avg in low_courses.head(3).items()
                )
                suggestions.append(
                    f"Focus support on courses with the lowest averages: {focus_courses}."
                )
            else:
                strong_courses = ", ".join(
                    f"{course} ({avg:.1f}%)" for course, avg in course_means.tail(min(3, len(course_means))).items()
                )
                suggestions.append(
                    f"Course averages look healthy. Top performers: {strong_courses}."
                )

    distribution = (charts or {}).get("distribution") if charts else None
    if isinstance(distribution, list) and distribution:
        top_bucket = max(distribution, key=lambda item: item.get("value", 0), default=None)
        if top_bucket and top_bucket.get("value"):
            stats["top_bucket_label"] = top_bucket.get("label")
            stats["top_bucket_value"] = int(top_bucket.get("value", 0))
            suggestions.append(
                f"Most students cluster in the {top_bucket.get('label')}% range—use this to set realistic targets."
            )

    columns = [
        column
        for column in [
            "roll_number",
            "student_name",
            "course",
            "attendance_percent",
            "email",
            "phone_number",
        ]
        if column in df.columns
    ]
    if columns:
        lowest_df = df.nsmallest(min(INSIGHTS_LOWEST_LIMIT, len(df)), "attendance_percent")
        lowest_records = lowest_df[columns].to_dict(orient="records")
        for record in lowest_records:
            if "attendance_percent" in record:
                try:
                    record["attendance_percent"] = round(float(record["attendance_percent"]), 1)
                except (TypeError, ValueError):
                    pass

    if below_count and lowest_records:
        focus_names = ", ".join(
            str(entry.get("student_name") or entry.get("roll_number"))
            for entry in lowest_records[:3]
            if entry.get("student_name") or entry.get("roll_number")
        )
        if focus_names:
            suggestions.append(f"Check in with: {focus_names} to prevent further drop.")

    return {"suggestions": suggestions, "lowest": lowest_records, "stats": stats}

SUPABASE_URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
supabase: Optional[Client] = None

if SUPABASE_URL and SUPABASE_KEY and create_client:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as exc:  # pragma: no cover - defensive logging
        supabase = None
        app.logger.error("Failed to initialise Supabase client: %s", exc)
else:
    app.logger.warning("Supabase credentials missing; auth actions will fail")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_email" not in session:
            flash("Please sign in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def get_user_key() -> Optional[str]:
    return session.get("user_email")


def store_dataset(
    key: str,
    df: pd.DataFrame,
    columns: List[Dict[str, Any]],
    identifier: str,
    threshold: float,
) -> None:
    DATA_CACHE[key] = {
        "df": df.reset_index(drop=True),
        "columns": columns,
        "identifier": identifier,
        "last_threshold": float(threshold),
    }


def fetch_dataset(key: str) -> Optional[Dict[str, Any]]:
    dataset = DATA_CACHE.get(key)
    if dataset is None:
        return None
    return dataset


def parse_dataframe(file_storage) -> pd.DataFrame:
    filename = secure_filename(file_storage.filename or "")
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported file type. Use CSV or XLSX.")

    if extension == ".xlsx":
        df = pd.read_excel(file_storage)
    else:
        df = pd.read_csv(file_storage)

    if df.empty:
        raise ValueError("Uploaded file is empty.")

    normalized: Dict[str, str] = {}
    for column in df.columns:
        normalized_name = COLUMN_ALIASES.get(str(column).strip().lower())
        if normalized_name and normalized_name not in normalized:
            normalized[normalized_name] = column

    required = {"roll_number", "student_name", "attendance_percent", "email", "phone_number"}
    if not required.issubset(normalized):
        missing = ", ".join(sorted(required - set(normalized)))
        raise ValueError(f"Missing required columns: {missing}")

    df = df.rename(columns={original: alias for alias, original in normalized.items()})
    if "attendance_percent" in df.columns:
        df["attendance_percent"] = (
            df["attendance_percent"].astype(str).str.replace("%", "", regex=False)
        )
        df["attendance_percent"] = pd.to_numeric(df["attendance_percent"], errors="coerce")
    df = df.dropna(subset=["attendance_percent", "email"]).reset_index(drop=True)
    for column in ("roll_number", "student_name", "course", "email", "phone_number"):
        if column in df.columns:
            df[column] = df[column].astype(str)
    if "alert_status" not in df.columns:
        df["alert_status"] = "Pending"
    else:
        df["alert_status"] = df["alert_status"].fillna("Pending").astype(str)
    return df


def build_column_config(df: pd.DataFrame) -> List[Dict[str, Any]]:
    columns = list(df.columns)
    ordered_columns = sorted(
        columns,
        key=lambda col: (
            PRIMARY_COLUMN_ORDER.index(col) if col in PRIMARY_COLUMN_ORDER else len(PRIMARY_COLUMN_ORDER),
            columns.index(col),
        ),
    )
    config: List[Dict[str, Any]] = []
    for column in ordered_columns:
        label = DISPLAY_LABELS.get(column, column.replace("_", " ").title())
        field_format = "percent" if column == "attendance_percent" else "text"
        entry: Dict[str, Any] = {
            "key": column,
            "label": label,
            "format": field_format,
        }
        if column == "roll_number":
            entry["isIdentifier"] = True
        config.append(entry)
    return config


def filter_records(df: pd.DataFrame, threshold: float, columns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    filtered = df[df["attendance_percent"] < threshold].copy()
    if "alert_status" not in filtered.columns:
        filtered["alert_status"] = "Pending"
    else:
        filtered["alert_status"] = filtered["alert_status"].fillna("Pending").astype(str)
    column_keys = [column["key"] for column in columns]
    available = [column for column in column_keys if column in filtered.columns]
    return filtered[available].to_dict(orient="records")


def build_summary(df: pd.DataFrame, threshold: float) -> Dict[str, Any]:
    total = int(len(df))
    below = int((df["attendance_percent"] < threshold).sum())
    average = round(float(df["attendance_percent"].mean()), 2) if total else 0
    lowest = round(float(df["attendance_percent"].min()), 2) if total else 0
    highest = round(float(df["attendance_percent"].max()), 2) if total else 0
    return {
        "total": total,
        "below": below,
        "average": average,
        "lowest": lowest,
        "highest": highest,
    }


def build_chart_payload(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty:
        return {"byCourse": [], "distribution": []}

    if "course" in df.columns and not df["course"].isna().all():
        by_course_series = (
            df.groupby("course")["attendance_percent"].mean().round(2).sort_values(ascending=False)
        )
        by_course = [
            {"label": str(course), "value": value}
            for course, value in by_course_series.items()
        ]
    else:
        by_course = []

    bucket_labels = ["0-50", "50-60", "60-70", "70-80", "80-90", "90-100"]
    bucket_counts = (
        pd.cut(
            df["attendance_percent"].clip(upper=100, lower=0),
            bins=[0, 50, 60, 70, 80, 90, 100],
            labels=bucket_labels,
            include_lowest=True,
            right=True,
        )
        .value_counts()
        .reindex(bucket_labels, fill_value=0)
    )
    distribution = [
        {"label": label, "value": int(count)}
        for label, count in bucket_counts.items()
    ]

    return {"byCourse": by_course, "distribution": distribution}


def mail_configured() -> bool:
    return bool(app.config.get("MAIL_USERNAME") and app.config.get("MAIL_PASSWORD"))


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please provide both email and password.", "error")
        elif not supabase:
            flash("Supabase is not configured. Check env.txt.", "error")
        else:
            try:
                supabase.auth.sign_in_with_password({"email": email, "password": password})
                session["user_email"] = email
                flash("Signed in successfully.", "success")
                return redirect(url_for("dashboard"))
            except Exception as exc:  # pragma: no cover - supabase error handling
                app.logger.warning("Sign-in failed for %s: %s", email, exc)
                flash("Invalid credentials or Supabase error.", "error")

    if "user_email" in session:
        return redirect(url_for("dashboard"))

    return render_template("login.html", mode="login")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please provide both email and password.", "error")
        elif not supabase:
            flash("Supabase is not configured. Check env.txt.", "error")
        else:
            try:
                supabase.auth.sign_up({"email": email, "password": password})
                flash("Account created! Confirm your email before signing in.", "success")
                return redirect(url_for("login"))
            except Exception as exc:  # pragma: no cover - supabase error handling
                app.logger.warning("Sign-up failed for %s: %s", email, exc)
                flash("Unable to create account. Try a different email or password.", "error")

    return render_template("login.html", mode="signup")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", template_max_length=MAX_TEMPLATE_LENGTH)


@app.get("/api/message-template")
@login_required
def api_get_message_template():
    user_key = get_user_key()
    settings = get_user_settings(user_key)
    return jsonify(
        {
            "template": settings.get("template", DEFAULT_MESSAGE_TEMPLATE),
            "placeholders": MESSAGE_TEMPLATE_PLACEHOLDERS,
            "max_length": MAX_TEMPLATE_LENGTH,
        }
    )


@app.post("/api/message-template")
@login_required
def api_update_message_template():
    if not request.is_json:
        return jsonify({"error": "Invalid payload."}), 400

    payload = request.get_json() or {}
    template_value = payload.get("template", "")

    if not isinstance(template_value, str):
        return jsonify({"error": "Template must be text."}), 400

    if not template_value.strip():
        return jsonify({"error": "Template cannot be empty."}), 400

    if len(template_value) > MAX_TEMPLATE_LENGTH:
        return jsonify({"error": f"Template exceeds {MAX_TEMPLATE_LENGTH} characters."}), 400

    user_key = get_user_key()
    set_message_template(user_key, template_value)

    return jsonify(
        {
            "template": template_value,
            "placeholders": MESSAGE_TEMPLATE_PLACEHOLDERS,
            "max_length": MAX_TEMPLATE_LENGTH,
        }
    )


@app.post("/api/upload")
@login_required
def api_upload():
    user_key = get_user_key()
    file_storage = request.files.get("file")
    threshold = request.form.get("threshold", type=float)
    if threshold is None:
        threshold = 75.0

    if not file_storage or not user_key:
        return jsonify({"error": "Missing file upload."}), 400

    try:
        dataframe = parse_dataframe(file_storage)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # pragma: no cover - defensive catch
        app.logger.exception("Failed to parse upload")
        return jsonify({"error": "Failed to read the uploaded file."}), 500

    columns_config = build_column_config(dataframe)
    identifier = next(
        (column["key"] for column in columns_config if column.get("isIdentifier")),
        columns_config[0]["key"] if columns_config else "roll_number",
    )
    dataframe[identifier] = dataframe[identifier].astype(str)
    store_dataset(user_key, dataframe, columns_config, identifier, threshold)

    records = filter_records(dataframe, threshold, columns_config)
    summary = build_summary(dataframe, threshold)
    charts = build_chart_payload(dataframe)
    insights = build_insights(dataframe, threshold, charts)

    return jsonify(
        {
            "records": records,
            "summary": summary,
            "charts": charts,
            "columns": columns_config,
            "identifier": identifier,
            "insights": insights,
        }
    )


@app.post("/api/filter")
@login_required
def api_filter():
    user_key = get_user_key()
    threshold = request.json.get("threshold") if request.is_json else request.form.get("threshold", type=float)
    if threshold is None:
        return jsonify({"error": "Threshold missing."}), 400

    dataset = fetch_dataset(user_key) if user_key else None
    if dataset is None:
        return jsonify({"error": "Upload data before filtering."}), 400

    dataframe = dataset["df"]
    columns_config = dataset.get("columns", [])
    identifier = dataset.get("identifier", "roll_number")
    threshold_value = float(threshold)
    dataset["last_threshold"] = threshold_value

    records = filter_records(dataframe, threshold_value, columns_config)
    summary = build_summary(dataframe, threshold_value)
    charts = build_chart_payload(dataframe)
    insights = build_insights(dataframe, threshold_value, charts)
    return jsonify(
        {
            "records": records,
            "summary": summary,
            "charts": charts,
            "columns": columns_config,
            "identifier": identifier,
            "insights": insights,
        }
    )


@app.get("/api/plot-data")
@login_required
def api_plot_data():
    user_key = get_user_key()
    dataset = fetch_dataset(user_key) if user_key else None
    df = dataset["df"] if dataset is not None else pd.DataFrame()
    threshold = float(dataset.get("last_threshold", 75.0)) if dataset else 75.0
    charts = build_chart_payload(df)
    insights = build_insights(df, threshold, charts)
    return jsonify({"charts": charts, "insights": insights})


@app.post("/api/send-alerts")
@login_required
def api_send_alerts():
    if not request.is_json:
        return jsonify({"error": "Invalid payload."}), 400

    payload = request.get_json() or {}
    selected_ids = payload.get("students", [])
    user_key = get_user_key()

    if not selected_ids or not isinstance(selected_ids, list):
        return jsonify({"error": "No students supplied."}), 400

    dataset = fetch_dataset(user_key) if user_key else None
    if dataset is None:
        return jsonify({"error": "Upload data before sending alerts."}), 400

    dataframe = dataset["df"]
    identifier = dataset.get("identifier", "roll_number")
    if identifier not in dataframe.columns:
        return jsonify({"error": "Identifier column missing in dataset."}), 500

    dataframe[identifier] = dataframe[identifier].astype(str)
    selected_keys = {str(value) for value in selected_ids}
    mask = dataframe[identifier].isin(selected_keys)
    selected_df = dataframe[mask].copy()
    if selected_df.empty:
        return jsonify({"error": "No matching students found."}), 400

    if not mail_configured():
        return jsonify({"error": "Mail server is not configured."}), 500

    threshold_raw = payload.get("threshold", dataset.get("last_threshold", 0.0))
    try:
        threshold_value = float(threshold_raw)
    except (TypeError, ValueError):
        threshold_value = float(dataset.get("last_threshold", 0.0) or 0.0)

    dataset["last_threshold"] = threshold_value

    template = get_message_template(user_key)

    sent_emails: List[str] = []
    sent_identifiers: List[str] = []
    failures: List[str] = []
    for _, row in selected_df.iterrows():
        context = build_message_context(row, threshold_value)
        body = render_message_template(template, context)
        message = Message(subject="Attendance Alert", recipients=[row["email"]], body=body)
        try:
            mail.send(message)
            sent_emails.append(row["email"])
            sent_identifiers.append(str(row[identifier]))
        except Exception as exc:  # pragma: no cover - SMTP failures are environment-specific
            app.logger.warning("Failed to send alert to %s: %s", row["email"], exc)
            failures.append(row["email"])

    if sent_identifiers:
        dataframe.loc[dataframe[identifier].isin(sent_identifiers), "alert_status"] = "Sent"

    return jsonify({"sent": sent_emails, "sent_ids": sent_identifiers, "failed": failures})


if __name__ == "__main__":
    app.run(debug=True)
