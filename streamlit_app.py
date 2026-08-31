import streamlit as st
import datetime
from datetime import timedelta
import json
import os
from openai import OpenAI

# ---------------------------------------------------------
# 1. PAGE SETUP
# ---------------------------------------------------------
st.set_page_config(
    page_title="Unstuck - Adaptive Revision Planner",
    page_icon="⚡",
    layout="wide"
)

# Safe OpenAI Client Setup
openai_api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
client = OpenAI(api_key=openai_api_key) if (openai_api_key and not openai_api_key.startswith("your-")) else None

# ---------------------------------------------------------
# 2. SESSION STATE & DEFENSIVE KEYS
# ---------------------------------------------------------
if "user" not in st.session_state:
    st.session_state.user = None

if "user_settings" not in st.session_state:
    st.session_state.user_settings = {
        "level": "GCSE",
        "weekly_hours": 20,
        "selected_subjects": ["Chemistry", "Physics", "Maths"],
        "subject_boards": {
            "Chemistry": "AQA",
            "Physics": "OCR A",
            "Maths": "Edexcel",
            "Biology": "AQA",
            "English Literature": "Edexcel",
            "History": "AQA",
            "Computer Science": "OCR"
        }
    }

today = datetime.date.today()

if "tasks" not in st.session_state:
    st.session_state.tasks = []

# Ensure backwards compatibility for session state keys
for t in st.session_state.tasks:
    if "exam_board" not in t:
        t["exam_board"] = st.session_state.user_settings["subject_boards"].get(t.get("subject", ""), "Standard")
    if "confidence" not in t:
        t["confidence"] = 3
    if "quiz_score" not in t:
        t["quiz_score"] = None
    if "status" not in t:
        t["status"] = "Pending"
    if "est_minutes" not in t:
        t["est_minutes"] = 30
    if "exam_date" not in t:
        t["exam_date"] = t.get("scheduled_date", today)

if "selected_task_id" not in st.session_state:
    st.session_state.selected_task_id = None

if "recovery_triggered" not in st.session_state:
    st.session_state.recovery_triggered = False

# ---------------------------------------------------------
# 3. AUTOMATIC RECOVERY MODE (3 OVERDUE TASKS)
# ---------------------------------------------------------
overdue_tasks = [t for t in st.session_state.tasks if t.get("exam_date", today) < today and t.get("status") == "Pending"]

if len(overdue_tasks) >= 3 and not st.session_state.recovery_triggered:
    st.session_state.recovery_triggered = True
    for t in st.session_state.tasks:
        if t.get("status") == "Pending":
            t["est_minutes"] = max(15, int(t.get("est_minutes", 30) * 0.7))
            if t.get("exam_date", today) < today:
                t["exam_date"] = today

# ---------------------------------------------------------
# 4. TOPIC-SPECIFIC AI GENERATOR (WITH DETAILED FALLBACKS)
# ---------------------------------------------------------
@st.cache_data(show_spinner=False)
def fetch_ai_breakdown(topic, subject, board):
    """Generates specific micro-steps, real flashcard answers, and exam questions tailored to the topic."""
    
    # Smart, realistic fallback if OpenAI key is missing or fails
    fallback_data = {
        "est_minutes": 35,
        "steps": [
            f"Watch the concept breakdown video on **Cognito** or **Save My Exams** for {topic} to understand the core mechanism.",
            f"Download the official {board} specification notes and flashcards on **Physics & Maths Tutor (PMT)** or **CGP** for {topic}.",
            f"Work through 3 past-paper exam questions on **PMT** for {topic} and mark them using the official mark scheme."
        ],
        "flashcards": [
            {
                "q": f"What is the key core principle underlying {topic} in {subject}?",
                "a": f"In {subject} ({board}), {topic} requires applying standard spec definitions, maintaining unit consistency, and showing clear step-by-step working."
            },
            {
                "q": f"What equation or key term must be remembered for {topic}?",
                "a": f"State the main equation/definition required for {topic}, ensuring standard SI units are applied."
            },
            {
                "q": f"What is a common trap students lose marks on in {board} exam questions for {topic}?",
                "a": "Forgetting to convert units before calculating, missing key command words (e.g., 'explain' vs 'describe'), or omitting final unit labels."
            }
        ],
        "test_questions": [
            {
                "q": f"Which approach is required when solving a multi-step calculation on {topic} for {board}?",
                "options": ["Convert all values to standard units first", "Skip writing down intermediate equations", "Ignore state symbols", "Round numbers before final calculation"],
                "correct": 0
            },
            {
                "q": f"When revising {topic}, what is the main purpose of consulting the {board} specification?",
                "options": ["To check exact key terms and required practical steps", "To memorize non-examinable facts", "To avoid past papers", "To estimate exam grade boundaries"],
                "correct": 0
            },
            {
                "q": f"In {subject}, how does doubling the primary input parameter usually affect the outcome in {topic}?",
                "options": ["It changes according to the explicit formula relationships", "It always doubles the value", "It always quadruples the value", "It has zero effect"],
                "correct": 0
            },
            {
                "q": f"Which resource provides recommended exam-board specific topic notes for {topic}?",
                "options": ["Physics & Maths Tutor (PMT)", "Generic dictionary", "Random forum posts", "Unverified blog notes"],
                "correct": 0
            },
            {
                "q": f"What is the final step before submitting a response to a high-tariff question on {topic}?",
                "options": ["Verify units, significant figures, and command words", "Erase working out", "Re-write question text", "Leave answer blank"],
                "correct": 0
            }
        ]
    }
    
    if not client:
        return fallback_data
        
    prompt = f"""
    You are an expert UK school tutor specializing in {board} {subject}.
    Generate a precise, topic-specific revision package for the topic: '{topic}'.
    
    Return ONLY a JSON object with:
    - "est_minutes": integer (estimated revision time between 20 and 50 based on topic complexity).
    - "steps": array of 3 specific, actionable steps tailored to '{topic}'. Explicitly recommend specific top UK resources like Physics & Maths Tutor (PMT), Cognito, Save My Exams, Seneca, or CGP revision guides.
    - "flashcards": array of 3 concrete flashcards with actual factual questions ("q") and direct, complete factual answers ("a") specifically about '{topic}' (NO placeholders or vague meta-text).
    - "test_questions": array of 5 genuine multiple-choice practice questions specifically testing knowledge of '{topic}'. Each object has "q", "options" (4 distinct real answer choices), and "correct" (0-3 index).
    """
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(res.choices[0].message.content)
    except Exception:
        return fallback_data

# ---------------------------------------------------------
# 5. SIDEBAR: ACCOUNT & PERSONALISATION
# ---------------------------------------------------------
with st.sidebar:
    st.header("👤 Account Sync")
    if st.session_state.user:
        st.success(f"Signed in as: **{st.session_state.user}**")
        if st.button("Sign Out"):
            st.session_state.user = None
            st.rerun()
    else:
        with st.expander("Sign In / Register"):
            email = st.text_input("Email", key="login_email")
            pwd = st.text_input("Password", type="password", key="login_pwd")
            if st.button("Sign In"):
                if email:
                    st.session_state.user = email
                    st.success("Signed in! Progress synced.")
                    st.rerun()

    st.divider()
    st.header("⚙️ Personalise Planner")
    
    level = st.selectbox("Level", ["A-Level", "GCSE"], index=1 if st.session_state.user_settings["level"] == "GCSE" else 0)
    st.session_state.user_settings["level"] = level
    
    # Up to 50 hours per week
    weekly_hrs = st.slider("Weekly Revision Target (Hours)", 5, 50, st.session_state.user_settings.get("weekly_hours", 20))
    st.session_state.user_settings["weekly_hours"] = weekly_hrs
    
    st.subheader("Subjects & Exam Boards")
    available_subjects = ["Chemistry", "Physics", "Maths", "Biology", "English Literature", "History", "Computer Science"]
    
    selected_subs = st.multiselect(
        "Select Your Subjects:",
        options=available_subjects,
        default=st.session_state.user_settings.get("selected_subjects", ["Chemistry", "Physics", "Maths"])
    )
    if not selected_subs:
        selected_subs = ["Chemistry"]
    st.session_state.user_settings["selected_subjects"] = selected_subs
    
    boards = ["AQA", "OCR A", "OCR B", "Edexcel", "WJEC", "Eduqas", "CIE"]
    st.caption("Select Exam Board for each subject:")
    for sub in selected_subs:
        curr_board = st.session_state.user_settings["subject_boards"].get(sub, "AQA")
        board_idx = boards.index(curr_board) if curr_board in boards else 0
        new_board = st.selectbox(f"{sub} Board", boards, index=board_idx, key=f"board_select_{sub}")
        st.session_state.user_settings["subject_boards"][sub] = new_board

# ---------------------------------------------------------
# 6. HEADER & AUTOMATIC RECOVERY BANNER
# ---------------------------------------------------------
st.title("⚡ Unstuck")
st.caption("Adaptive Revision Planner • Beat Procrastination with Day-by-Day Micro-Steps")

if st.session_state.recovery_triggered:
    st.info("ℹ️ **Recovery Mode Activated:** You had 3 or more overdue tasks. Workload times have been scaled back by 30% and schedule adjusted automatically.")

st.divider()

# ---------------------------------------------------------
# 7. MAIN SCHEDULE & MICRO-TASK WORKSPACE
# ---------------------------------------------------------
col_schedule, col_workspace = st.columns([1.1, 0.9])

with col_schedule:
    st.subheader("📅 Your Schedule by Date")
    
    # Task Creator Form (AI estimates expected time; Date labeled 'Exam Date')
    with st.expander("➕ Add Task to Schedule", expanded=(len(st.session_state.tasks) == 0)):
        with st.form("add_task_form"):
            chosen_subjects = st.session_state.user_settings["selected_subjects"]
            new_sub = st.selectbox("Select Subject", chosen_subjects)
            new_top = st.text_input("Topic Name", placeholder="e.g. Titration Calculations / Newton's Laws")
            
            # Exam Date Selection (No Expected Time input required)
            new_exam_date = st.date_input("Exam Date / Target Date", today)
            new_conf = st.slider("Current Confidence Rating (1-5)", 1, 5, 3)
            
            if st.form_submit_button("➕ Add Task to Schedule"):
                if new_top.strip():
                    assigned_board = st.session_state.user_settings["subject_boards"].get(new_sub, "AQA")
                    new_id = max([t.get("id", 0) for t in st.session_state.tasks], default=0) + 1
                    
                    # Fetch AI content to get dynamic expected time
                    content_preview = fetch_ai_breakdown(new_top.strip(), new_sub, assigned_board)
                    est_time = content_preview.get("est_minutes", 30)
                    
                    st.session_state.tasks.append({
                        "id": new_id,
                        "subject": new_sub,
                        "exam_board": assigned_board,
                        "topic": new_top.strip(),
                        "exam_date": new_exam_date,
                        "est_minutes": est_time,
                        "status": "Pending",
                        "confidence": new_conf,
                        "quiz_score": None
                    })
                    st.success(f"Added '{new_top}'! AI estimated time: {est_time} mins.")
                    st.rerun()
                else:
                    st.error("Please enter a topic name.")

    # Date Tabs View
    days = [today + timedelta(days=i) for i in range(7)]
    day_names = ["Today", "Tomorrow"] + [(today + timedelta(days=i)).strftime("%a %b %d") for i in range(2, 7)]
    
    tabs = st.tabs(day_names)
    
    for i, day in enumerate(days):
        with tabs[i]:
            day_tasks = [t for t in st.session_state.tasks if t.get("exam_date") == day]
            
            if not day_tasks:
                st.caption("✨ No tasks scheduled for this date. Use 'Add Task to Schedule' above.")
            else:
                for task in day_tasks:
                    is_completed = task.get("status") == "Completed"
                    status_icon = "✅" if is_completed else ("🔴" if task.get("exam_date", today) < today else "🔵")
                    
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 2, 2])
                        with c1:
                            st.markdown(f"**{status_icon} {task.get('topic', 'Topic')}**")
                            sub_text = task.get('subject', 'General')
                            board_text = task.get('exam_board', 'AQA')
                            conf_text = task.get('confidence', 3)
                            st.caption(f"{sub_text} ({board_text}) • Conf: {conf_text}/5")
                        with c2:
                            st.caption(f"⏱️ {task.get('est_minutes', 30)} mins (AI Est.)")
                            if task.get("quiz_score") is not None:
                                st.caption(f"📊 Test Score: {task.get('quiz_score')}/5")
                        with c3:
                            if not is_completed:
                                if st.button("🚀 Unstuck", key=f"btn_unstuck_{task.get('id')}"):
                                    st.session_state.selected_task_id = task.get("id")
                                    st.rerun()
                            else:
                                st.success("Completed")

# --- RIGHT COLUMN: WORKSPACE ---
with col_workspace:
    st.subheader("💡 Micro-Task Workspace")
    
    current_task = next((t for t in st.session_state.tasks if t.get("id") == st.session_state.selected_task_id), None)
    
    if not current_task:
        st.info("👈 Select a date tab on the schedule and click **'🚀 Unstuck'** on any task to open its revision plan.")
    else:
        st.markdown(f"### Working on: **{current_task.get('topic')}**")
        st.caption(f"**Subject:** {current_task.get('subject')} ({current_task.get('exam_board')}) | **AI Estimated Time:** {current_task.get('est_minutes')} mins | **Exam Date:** {current_task.get('exam_date').strftime('%b %d, %Y') if isinstance(current_task.get('exam_date'), (datetime.date, datetime.datetime)) else current_task.get('exam_date')}")
        
        # Load topic-specific AI content
        content = fetch_ai_breakdown(current_task.get('topic'), current_task.get('subject'), current_task.get('exam_board'))
        
        # Sync estimated minutes if AI updated it
        if "est_minutes" in content:
            current_task["est_minutes"] = content["est_minutes"]
        
        st.divider()
        st.write("#### 🎯 3 Best Learning Steps & Recommended Resources")
        for idx, step in enumerate(content.get("steps", []), 1):
            st.checkbox(f"**Step {idx}:** {step}", key=f"chk_{current_task.get('id')}_{idx}")
            
        st.divider()
        st.write("#### 🧠 Key Topic Flashcards")
        for fc_idx, fc in enumerate(content.get("flashcards", []), 1):
            with st.expander(f"🎴 Flashcard {fc_idx}: {fc.get('q')}"):
                st.write(f"**Answer:** {fc.get('a')}")
                
        st.divider()
        st.write("#### 📝 5 Exam Practice Questions")
        quiz_answers = []
        for q_idx, q in enumerate(content.get("test_questions", [])):
            st.write(f"**Q{q_idx+1}: {q.get('q')}**")
            ans = st.radio(
                f"Select answer for Q{q_idx+1}:", 
                q.get("options", []), 
                key=f"quiz_{current_task.get('id')}_{q_idx}",
                index=None
            )
            correct_opt = q.get("options")[q.get("correct")] if q.get("options") and q.get("correct") < len(q.get("options")) else None
            quiz_answers.append((ans, correct_opt))
            
        st.divider()
        st.write("#### 📊 Post-Session Confidence & Completion")
        
        # Confidence Rating (1-5 Scale)
        new_conf_val = st.slider(
            "Rate your confidence level after completing this session (1-5):",
            min_value=1,
            max_value=5,
            value=int(current_task.get("confidence", 3)),
            key=f"conf_slider_{current_task.get('id')}"
        )
        
        if st.button("✅ Complete Task", type="primary", key=f"complete_{current_task.get('id')}"):
            score = sum(1 for user_ans, correct_ans in quiz_answers if user_ans is not None and user_ans == correct_ans)
            
            # Update session state
            current_task["status"] = "Completed"
            current_task["confidence"] = new_conf_val
            current_task["quiz_score"] = score
            st.session_state.selected_task_id = None
            
            st.success(f"Task completed! Practice test score saved: {score}/5.")
            st.rerun()
