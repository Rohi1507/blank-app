import sqlite3
import hashlib
import sys
from typing import Dict
import streamlit as st

DB_PATH = "pathgenerator.db"

# ---------------------------
# Utility & DB initialization
# ---------------------------
def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # Users table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Pathgenerator table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS pathgenerator (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_type TEXT,
            standard TEXT,
            marks TEXT,
            desired_course TEXT,
            chosen_subfield TEXT,
            chosen_stream TEXT,
            career_options TEXT,
            entrance_exams TEXT,
            extra_info TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()

# ---------------------------
# Password hashing
# ---------------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

# ---------------------------
# Authentication
# ---------------------------
def signup(username, password):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hash_password(password)))
        conn.commit()
        conn.close()
        return True, "Signup successful. You can login now."
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Username already exists. Choose a different username."

def login(username, password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, password FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    if row and row[1] == hash_password(password):
        return row[0], f"Welcome, {username}!"
    else:
        return None, "Invalid username or password."

def forgot_password(username, new_password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False, "Username not found."
    cur.execute("UPDATE users SET password = ? WHERE username = ?", (hash_password(new_password), username))
    conn.commit()
    conn.close()
    return True, "Password reset successful. You can login now."

# ---------------------------
# Static Data
# ---------------------------
STREAM_DESCRIPTIONS = {
    "Science (PCM)": "Physics, Chemistry, Mathematics — Ideal for Engineering, Computer Science, and Research.",
    "Science (PCB)": "Physics, Chemistry, Biology — Ideal for Medicine, Biotechnology, and Life Sciences.",
    "Commerce": "Accounts, Business Studies, Economics — Ideal for CA, Business, and Finance.",
    "Commerce with Maths": "Commerce subjects + Maths — Ideal for Finance, Analytics, and Management.",
    "Arts": "History, Political Science, Literature — Ideal for Law, Humanities, and Creative fields.",
}

COURSE_SUBFIELDS = {
    "engineering": ["Computer Engineering", "Mechanical Engineering", "Civil Engineering", "Electrical Engineering", "Biomedical Engineering", "Aerospace Engineering"],
    "medicine": ["MBBS", "Dentistry", "Nursing", "Pharmacy", "Ayurveda", "Homeopathy"],
    "commerce": ["Chartered Accountancy", "Company Secretary", "Banking", "Finance", "Business Administration"],
    "arts": ["Law", "Psychology", "Journalism", "Sociology", "Fine Arts", "Political Science"],
    "design": ["Fashion Design", "Interior Design", "Graphic Design", "Product Design", "UI/UX Design", "Animation Design"],
    "science": ["Biotechnology", "Microbiology", "Environmental Science", "Zoology", "Botany", "Physics", "Chemistry", "Mathematics"],
}

COURSE_STREAMS = {
    "engineering": ["Science (PCM)", "Commerce with Maths"],
    "medicine": ["Science (PCB)"],
    "commerce": ["Commerce", "Commerce with Maths"],
    "arts": ["Arts", "Commerce"],
    "design": ["Arts", "Science (PCM)"],
    "science": ["Science (PCM)", "Science (PCB)"],
}

CAREER_OPTIONS = {
    "Computer Engineering": ["Software Developer", "AI Engineer", "System Analyst"],
    "Mechanical Engineering": ["Automobile Engineer", "Robotics Engineer", "Production Engineer"],
    "Civil Engineering": ["Structural Engineer", "Construction Manager", "Urban Planner"],
    "Electrical Engineering": ["Power Engineer", "Control Systems Engineer", "Electronics Engineer"],
    "Biomedical Engineering": ["Clinical Engineer", "Rehabilitation Engineer", "Medical Device Designer"],
    "Aerospace Engineering": ["Aircraft Designer", "Aviation Engineer", "Space Research Scientist"],
    "MBBS": ["Doctor", "Surgeon", "Medical Researcher"],
    "Dentistry": ["Dentist", "Orthodontist", "Dental Surgeon"],
    "Ayurveda": ["Ayurvedic Doctor", "Therapist", "Pharma Researcher"],
    "Homeopathy": ["Homeopathic Doctor", "Alternative Medicine Specialist"],
    "Nursing": ["Nurse", "Healthcare Administrator", "Clinical Nurse Specialist"],
    "Pharmacy": ["Pharmacist", "Drug Inspector", "Pharma Research Scientist"],
    "Chartered Accountancy": ["Auditor", "Tax Consultant", "Finance Manager"],
    "Company Secretary": ["Corporate Advisor", "Legal Consultant", "Business Strategist"],
    "Banking": ["Bank PO", "Investment Banker", "Credit Analyst"],
    "Finance": ["Financial Analyst", "Wealth Manager", "Stock Broker"],
    "Business Administration": ["HR Manager", "Operations Manager", "Marketing Specialist"],
    "Law": ["Advocate", "Judge", "Legal Advisor"],
    "Psychology": ["Counselor", "Clinical Psychologist", "HR Specialist"],
    "Journalism": ["Reporter", "Editor", "Media Analyst"],
    "Sociology": ["Social Worker", "Policy Analyst", "Researcher"],
    "Fine Arts": ["Artist", "Graphic Designer", "Animator"],
    "Political Science": ["Civil Services", "Political Analyst", "Diplomat"],
    "Biotechnology": ["Biotech Researcher", "Lab Scientist", "Genetic Engineer"],
    "Microbiology": ["Microbiologist", "Lab Technician", "Food Safety Officer"],
    "Environmental Science": ["Environmental Consultant", "Ecologist", "Sustainability Specialist"],
    "Zoology": ["Wildlife Biologist", "Zookeeper", "Research Scientist"],
    "Botany": ["Plant Scientist", "Agricultural Researcher", "Forestry Officer"],
    "Physics": ["Physicist", "Research Scientist", "Astrophysicist"],
    "Chemistry": ["Chemist", "Pharmaceutical Scientist", "Forensic Analyst"],
    "Mathematics": ["Data Scientist", "Statistician", "Actuary"],
}

ENTRANCE_EXAMS = {
    "Engineering": ["JEE Main", "JEE Advanced", "BITSAT", "VITEEE"],
    "Medicine": ["NEET-UG", "AIIMS", "JIPMER"],
    "Commerce": ["CA Foundation", "CPT", "CS Foundation", "ICWA Foundation"],
    "Arts": ["CUET", "TISSNET", "NIFT", "NID"],
    "Science": ["CUET", "IISER Aptitude Test", "ICAR AIEEA"],
}

# ---------------------------
# Save guidance
# ---------------------------
def save_guidance(user_id: int, data: Dict):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO pathgenerator
            (user_id, user_type, standard, marks, desired_course, chosen_subfield, chosen_stream, career_options, entrance_exams, extra_info)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, data['user_type'], data['standard'], data['marks'], data['desired_course'],
             data['chosen_subfield'], data['chosen_stream'], data['career_options'], data['entrance_exams'], data['extra_info']))
        conn.commit()
    except sqlite3.Error as e:
        st.error(f"Error saving data: {e}")
    finally:
        conn.close()

# ---------------------------
# Streamlit UI
# ---------------------------
st.title("Career Guidance System")
init_db()

# Authentication
st.sidebar.header("Authentication")
auth_choice = st.sidebar.radio("Select Action", ["Login", "Signup", "Forgot Password"])

if auth_choice == "Signup":
    username = st.sidebar.text_input("New Username", key="signup_user")
    password = st.sidebar.text_input("New Password", type="password", key="signup_pass")
    if st.sidebar.button("Signup"):
        success, message = signup(username, password)
        if success:
            st.success(message)
        else:
            st.error(message)

elif auth_choice == "Login":
    username = st.sidebar.text_input("Username", key="login_user")
    password = st.sidebar.text_input("Password", type="password", key="login_pass")
    if st.sidebar.button("Login"):
        user_id, message = login(username, password)
        if user_id:
            st.success(message)
            st.session_state['user_id'] = user_id
        else:
            st.error(message)

elif auth_choice == "Forgot Password":
    username = st.sidebar.text_input("Username", key="forgot_user")
    new_password = st.sidebar.text_input("New Password", type="password", key="forgot_pass")
    if st.sidebar.button("Reset Password"):
        success, message = forgot_password(username, new_password)
        if success:
            st.success(message)
        else:
            st.error(message)

# Main career guidance form
if 'user_id' in st.session_state:
    st.subheader("Career Guidance Form")

    user_type = st.selectbox("Are you a Student or Parent?", ["Student", "Parent"])
    standard = st.text_input("Current Standard/Class (1-12)")
    marks = st.text_input("Average Marks (%)")
    desired_course = st.selectbox(
        "Select Desired Course Field",
        ["engineering","medicine","commerce","arts","design","science"]
    )
    subfields = COURSE_SUBFIELDS[desired_course]
    chosen_subfield = st.selectbox("Choose Specialization", subfields)
    streams = COURSE_STREAMS[desired_course]
    chosen_stream = st.selectbox("Recommended Stream", streams)
    st.write(STREAM_DESCRIPTIONS[chosen_stream])
    career_paths = CAREER_OPTIONS[chosen_subfield]
    career_options = ", ".join(career_paths)
    st.write("Possible Career Paths:", career_options)
    exams = ENTRANCE_EXAMS.get(desired_course.title(), [])
    entrance_exams = ", ".join(exams)
    st.write("Relevant Entrance Exams:", entrance_exams)
    extra_info = st.text_area("Extra Information / Questions")

    if st.button("Save Guidance"):
        data = {
            "user_type": user_type,
            "standard": standard,
            "marks": marks,
            "desired_course": desired_course,
            "chosen_subfield": chosen_subfield,
            "chosen_stream": chosen_stream,
            "career_options": career_options,
            "entrance_exams": entrance_exams,
            "extra_info": extra_info
        }
        save_guidance(st.session_state['user_id'], data)
        st.success("✅ Career guidance information saved successfully!")
