import streamlit as st
import os
import re
import json
import tempfile
import pdfplumber
import docx2txt
from rapidfuzz import fuzz, process
from datetime import datetime
import google.generativeai as genai
from sqlalchemy import create_engine, Column, Integer, String, Float, JSON, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import pandas as pd

# ---------------- Gemini Setup ----------------
API_KEY = "AIzaSyB50KX7024Ojb4MDIL9rZVzM3e3GjIGx0s"  
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ---------------- Database Setup ----------------
DATABASE_URL = "sqlite:///results.db"
engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)

class ResumeResult(Base):
    __tablename__ = "resume_results"

    id = Column(Integer, primary_key=True, index=True)
    resume_file = Column(String, nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    hard_score = Column(Float, nullable=False)
    semantic_score = Column(Float, nullable=False)
    final_score = Column(Float, nullable=False)
    verdict = Column(String, nullable=False)
    missing_skills = Column(JSON, nullable=True)
    feedback = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# ---------------- Skills Dictionary ----------------
JOB_TERMS = {
    "python","pandas","numpy","sql","r","excel","powerbi","tableau",
    "nlp","ai","ml","machinelearning","deeplearning","automation",
    "analysis","analytics","visualization","exploration","engineering",
    "automotive","mechanical","manufacturing","production","databricks",
    "cloud","azure","aws","docker","git","kubernetes",
    "statistics","modelling","science","stakeholders","product",
    "spark","kafka","hadoop","etl","bigdata","datavisualization"
}

# ---------------- Utility Functions (Same as your original code) ----------------
def extract_text(file_path):
    """Extract text from PDF or DOCX"""
    if file_path.lower().endswith(".pdf"):
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text.strip()
    elif file_path.lower().endswith(".docx"):
        return docx2txt.process(file_path).strip()
    return ""

def compute_hard_score(resume_keywords, jd_keywords):
    matched_count = 0
    for jd_kw in jd_keywords:
        for res_kw in resume_keywords:
            if fuzz.ratio(jd_kw, res_kw) >= 70:
                matched_count += 1
                break
    return round((matched_count / len(jd_keywords)) * 100, 2) if jd_keywords else 0

def compute_semantic_score(resume_text, jd_text):
    def get_phrases(text):
        words = text.split()
        return {f"{words[i]} {words[i+1]}" for i in range(len(words)-1)}

    resume_phrases = get_phrases(resume_text)
    jd_phrases = get_phrases(jd_text)
    if not jd_phrases:
        return 0

    matched = 0
    for jd_phrase in jd_phrases:
        best_match_tuple = process.extractOne(jd_phrase, resume_phrases)
        if best_match_tuple and best_match_tuple[1] >= 70:
            matched += 1
    return round((matched / len(jd_phrases)) * 100, 2)

def extract_candidate_info(text):
    info = {}
    emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', text)
    info['email'] = emails[0] if emails else 'Not found'

    phones = re.findall(r'(\+91[\-\s]?)?[6-9]\d{9}', text)
    phones = [p for p in phones if p]
    info['phone'] = phones[0] if phones else 'Not found'

    lines = text.strip().split('\n')
    name = 'Unknown'
    for line in lines[:5]:
        line_clean = re.sub(r'[^\w\s]', '', line).strip()
        if 2 <= len(line_clean.split()) <= 4 and not any(c.isdigit() for c in line_clean):
            name = line_clean
            break
    info['name'] = name
    return info

def get_missing_skills(resume_keywords, jd_keywords):
    resume_set = set(word.lower() for word in resume_keywords)
    missing = {kw.lower() for kw in jd_keywords if kw.lower() in JOB_TERMS and kw.lower() not in resume_set}
    return list(missing)

def generate_feedback(name, missing_skills, hard_score, semantic_score, final_score):
    if not missing_skills and final_score > 70:
        return f"{name} has a strong resume matching the job description well. Keep it up!"

    prompt = f"""
Generate professional resume feedback for {name}, who applied for a technical job.
Missing skills: {', '.join(missing_skills) if missing_skills else 'None'}.
Hard score: {hard_score}/100, Semantic score: {semantic_score}/100, Final score: {final_score}/100.
Suggest practical advice to improve their resume, skills, and employability.
"""
    response = model.generate_content(prompt)
    return response.text

def save_uploaded_file(uploaded_file):
    """Save uploaded file to temporary location and return path"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        return tmp_file.name

def process_resumes(jd_file_path, resume_files):
    """Process resumes against job description"""
    HARD_WEIGHT = 0.7
    SEMANTIC_WEIGHT = 0.3
    
    results = []
    
    jd_text = extract_text(jd_file_path)
    jd_keywords = jd_text.lower().split()

    db = SessionLocal()

    for resume_file, resume_file_path in resume_files:
        resume_text = extract_text(resume_file_path)
        resume_keywords = resume_text.lower().split()

        hard_score = compute_hard_score(resume_keywords, jd_keywords)
        semantic_score = compute_semantic_score(resume_text.lower(), jd_text.lower())
        final_score = round(hard_score * HARD_WEIGHT + semantic_score * SEMANTIC_WEIGHT, 2)

        if final_score >= 70:
            verdict = "🟢 High Fit"
        elif final_score >= 50:
            verdict = "🟡 Medium Fit"
        elif final_score >= 30:
            verdict = "🟠 Low Fit"
        else:
            verdict = "🔴 Poor Fit"

        info = extract_candidate_info(resume_text)
        missing_skills = get_missing_skills(resume_keywords, jd_keywords)
        feedback = generate_feedback(info['name'], missing_skills, hard_score, semantic_score, final_score)

        # Save to DB
        record = ResumeResult(
            resume_file=resume_file.name,
            name=info['name'],
            email=info['email'],
            phone=info['phone'],
            hard_score=hard_score,
            semantic_score=semantic_score,
            final_score=final_score,
            verdict=verdict,
            missing_skills=missing_skills,
            feedback=feedback
        )
        db.add(record)
        db.commit()

        results.append({
            'resume_file': resume_file.name,
            'name': info['name'],
            'email': info['email'],
            'phone': info['phone'],
            'hard_score': hard_score,
            'semantic_score': semantic_score,
            'final_score': final_score,
            'verdict': verdict,
            'missing_skills': missing_skills,
            'feedback': feedback
        })

    db.close()
    return results

# ---------------- Streamlit UI ----------------
def main():
    st.set_page_config(
        page_title="Resume Screening System",
        page_icon="📄",
        layout="wide"
    )

    st.title("📄 Resume Screening System")
    st.markdown("Upload a job description and multiple resumes to get automated screening results.")

    # Sidebar
    st.sidebar.header("🛠️ Configuration")
    st.sidebar.markdown("### Scoring Weights")
    st.sidebar.info("Hard Score Weight: 70%\nSemantic Score Weight: 30%")
    
    st.sidebar.markdown("### Score Categories")
    st.sidebar.success("🟢 High Fit: ≥70")
    st.sidebar.warning("🟡 Medium Fit: 50-69")
    st.sidebar.warning("🟠 Low Fit: 30-49")
    st.sidebar.error("🔴 Poor Fit: <30")

    # Main content
    col1, col2 = st.columns([1, 2])

    with col1:
        st.header("📋 Upload Files")
        
        # Job Description Upload
        st.subheader("Job Description")
        jd_file = st.file_uploader(
            "Upload Job Description", 
            type=['pdf', 'docx'],
            help="Upload the job description in PDF or DOCX format"
        )
        
        # Resume Upload
        st.subheader("Resumes")
        resume_files = st.file_uploader(
            "Upload Resumes", 
            type=['pdf', 'docx'],
            accept_multiple_files=True,
            help="Upload multiple resumes in PDF or DOCX format"
        )

        # Process Button
        if st.button("🔄 Process Resumes", type="primary", use_container_width=True):
            if jd_file and resume_files:
                with st.spinner("Processing resumes..."):
                    # Save files temporarily
                    jd_path = save_uploaded_file(jd_file)
                    resume_paths = [(rf, save_uploaded_file(rf)) for rf in resume_files]
                    
                    # Process resumes
                    results = process_resumes(jd_path, resume_paths)
                    
                    # Clean up temporary files
                    os.unlink(jd_path)
                    for _, path in resume_paths:
                        os.unlink(path)
                    
                    # Store results in session state
                    st.session_state.results = results
                    st.success(f"✅ Processed {len(results)} resumes successfully!")
            else:
                st.error("Please upload both job description and at least one resume.")

    with col2:
        st.header("📊 Results")
        
        if 'results' in st.session_state and st.session_state.results:
            results = st.session_state.results
            
            # Summary metrics
            col_a, col_b, col_c, col_d = st.columns(4)
            
            high_fit = len([r for r in results if r['final_score'] >= 70])
            medium_fit = len([r for r in results if 50 <= r['final_score'] < 70])
            low_fit = len([r for r in results if 30 <= r['final_score'] < 50])
            poor_fit = len([r for r in results if r['final_score'] < 30])
            
            col_a.metric("🟢 High Fit", high_fit)
            col_b.metric("🟡 Medium Fit", medium_fit)
            col_c.metric("🟠 Low Fit", low_fit)
            col_d.metric("🔴 Poor Fit", poor_fit)
            
            # Results table
            st.subheader("📋 Detailed Results")
            
            # Convert to DataFrame for better display
            df = pd.DataFrame(results)
            df = df[['name', 'email', 'phone', 'hard_score', 'semantic_score', 'final_score', 'verdict']]
            df.columns = ['Name', 'Email', 'Phone', 'Hard Score', 'Semantic Score', 'Final Score', 'Verdict']
            
            # Sort by final score descending
            df = df.sort_values('Final Score', ascending=False)
            
            st.dataframe(
                df,
                use_container_width=True,
                height=400
            )
            
            # Individual candidate details
            st.subheader("👤 Candidate Details")
            
            candidate_names = [r['name'] for r in results]
            selected_candidate = st.selectbox("Select a candidate to view details:", candidate_names)
            
            if selected_candidate:
                candidate_data = next(r for r in results if r['name'] == selected_candidate)
                
                col_x, col_y = st.columns(2)
                
                with col_x:
                    st.markdown(f"**📄 Resume:** {candidate_data['resume_file']}")
                    st.markdown(f"**📧 Email:** {candidate_data['email']}")
                    st.markdown(f"**📱 Phone:** {candidate_data['phone']}")
                    st.markdown(f"**🎯 Verdict:** {candidate_data['verdict']}")
                
                with col_y:
                    st.markdown(f"**📊 Hard Score:** {candidate_data['hard_score']}/100")
                    st.markdown(f"**🧠 Semantic Score:** {candidate_data['semantic_score']}/100")
                    st.markdown(f"**⭐ Final Score:** {candidate_data['final_score']}/100")
                
                if candidate_data['missing_skills']:
                    st.markdown("**🔧 Missing Skills:**")
                    st.code(', '.join(candidate_data['missing_skills']))
                
                st.markdown("**💬 AI Feedback:**")
                st.info(candidate_data['feedback'])
        
        else:
            st.info("Upload files and click 'Process Resumes' to see results here.")

    # Database viewer
    st.header("🗄️ Database Records")
    if st.button("📊 View All Records"):
        db = SessionLocal()
        records = db.query(ResumeResult).order_by(ResumeResult.created_at.desc()).all()
        db.close()
        
        if records:
            db_data = []
            for record in records:
                db_data.append({
                    'ID': record.id,
                    'Name': record.name,
                    'Resume File': record.resume_file,
                    'Email': record.email,
                    'Phone': record.phone,
                    'Final Score': record.final_score,
                    'Verdict': record.verdict,
                    'Created At': record.created_at.strftime('%Y-%m-%d %H:%M:%S')
                })
            
            df_db = pd.DataFrame(db_data)
            st.dataframe(df_db, use_container_width=True)
        else:
            st.info("No records found in database.")

if __name__ == "__main__":
    main()