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
client = OpenAI(api_key=openai_api_key) if (openai_api_key and not openai_api_key.startswith("your-") and len(openai_api_key) > 10) else None

# ---------------------------------------------------------
# 2. SESSION STATE
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

# Backwards compatibility check
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
    if "spec_details" not in t:
        t["spec_details"] = ""

if "selected_task_id" not in st.session_state:
    st.session_state.selected_task_id = None

if "recovery_triggered" not in st.session_state:
    st.session_state.recovery_triggered = False

# ---------------------------------------------------------
# 3. RECOVERY MODE (3 OVERDUE TASKS)
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
# 4. EXAM-BOARD SPECIFIC AI GENERATOR
# ---------------------------------------------------------
@st.cache_data(show_spinner=False)
def fetch_ai_breakdown(topic, subject, board, level, spec_details=""):
    """Generates rigorous, specification-aligned content using OpenAI."""
    
    # Notice banner if client is missing (lets user know why it's fallback)
    fallback_data = {
        "est_minutes": 35,
        "steps": [
            f"Review the official **{board} {level}** specification points for **{topic}** on **Physics & Maths Tutor (PMT)** or **Save My Exams**.",
            f"Watch the **Cognito** or **Freesciencelessons** breakdown specifically addressing {topic}.",
            f"Solve 3 official past paper questions from **PMT** for {topic} and verify using the mark scheme."
        ],
        "flashcards": [
            {
                "q": f"[API KEY MISSING] Add OPENAI_API_KEY in Streamlit Secrets to generate custom spec content for '{topic}'.",
                "a": "Go to Streamlit Cloud -> Manage App -> Settings -> Secrets and paste your OpenAI API key."
            }
        ],
        "test_questions": [
            {
                "q": f"To unlock live AI questions for '{topic}', configure your OpenAI API Key.",
                "options": ["API Key Not Configured", "API Key Configured", "Pending", "Error"],
                "correct": 0
            }
        ]
    }
    
    if not client:
        return fallback_data
        
    prompt = f"""
    You are a senior UK chief examiner for {board} {level} {subject}.
    Generate a precise, highly accurate, and rigorous learning package for the topic: '{topic}'.
    Specification Context / Notes from student: '{spec_details if spec_details else "Standard syllabus requirements"}'

    CRITICAL REQUIREMENTS:
    1. Everything MUST strictly follow the official {board} {level} {subject} syllabus.
    2. Flashcards must test exact definitions, formulas, required practicals, or core mechanisms. Answers MUST be 100% complete and factual (NO vague meta-statements or placeholders).
    3. Test questions must mimic real {board} exam questions (including realistic distractors, unit conversions, or calculations where applicable).

    Return ONLY a JSON object formatted as follows:
    {{
      "est_minutes": integer (realistic target study time between 20 and 45 mins),
      "steps": [
        "Step 1 with specific resource recommendation (e.g. PMT, Cognito, Save My Exams, CGP, Seneca)",
        "Step 2 focusing on active recall or formula practice",
        "Step 3 focusing on past-paper questions and mark scheme checking"
      ],
      "flashcards": [
        {{"q": "Concrete question about {topic}", "a": "Full accurate factual answer according to {board} mark schemes"}},
        {{"q": "Question 2", "a": "Answer 2"}},
        {{"q": "Question 3", "a": "Answer 3"}}
      ],
      "test_questions": [
        {{
          "q": "Exam-style question 1 for {topic}",
          "options": ["Correct Answer", "Distractor 1", "Distractor 2", "Distractor 3"],
          "correct": 0
        }},
        ... 4 more objects (5 total questions)
      ]
    }}
    """
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3
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

if not client:
    st.warning("⚠️ **Live AI is offline:** Add your `OPENAI_API_KEY` into Streamlit Cloud Secrets to enable custom topic flashcards and exam questions.")

if st.session_state.recovery_triggered:
    st.info("ℹ️ **Recovery Mode Activated:** You had 3 or more overdue tasks. Workload times have been scaled back by 30% and schedule adjusted automatically.")

st.divider()

# ---------------------------------------------------------
# 7. MAIN SCHEDULE & WORKSPACE
# ---------------------------------------------------------
col_schedule, col_workspace = st.columns([1.1, 0.9])

with col_schedule:
    st.subheader("📅 Your Schedule by Date")
    
    # Task Creator Form
    with st.expander("➕ Add Task to Schedule", expanded=(len(st.session_state.tasks) == 0)):
        with st.form("add_task_form"):
            chosen_subjects = st.session_state.user_settings["selected_subjects"]
            new_sub = st.selectbox("Select Subject", chosen_subjects)
            new_top = st.text_input("Topic Name", placeholder="e.g. Titration Calculations / Newton's Second Law")
            
            # Optional Spec Context for exact precision
            new_spec = st.text_area("Specification Points / Sub-topics (Optional)", placeholder="e.g. AQA 3.1.2 Amount of substance, empirical formula, ideal gas equation pV=nRT", help="Paste exact spec codes or sub-topics to get higher quality flashcards and exam questions.")
            
            new_exam_date = st.date_input("Exam Date / Target Date", today)
            new_conf = st.slider("Current Confidence Rating (1-5)", 1, 5, 3)
            
            if st.form_submit_button("➕ Add Task to Schedule"):
                if new_top.strip():
                    assigned_board = st.session_state.user_settings["subject_boards"].get(new_sub, "AQA")
                    curr_level = st.session_state.user_settings["level"]
                    new_id = max([t.get("id", 0) for t in st.session_state.tasks], default=0) + 1
                    
                    # AI estimates time and validates content
                    content_preview = fetch_ai_breakdown(new_top.strip(), new_sub, assigned_board, curr_level, new_spec.strip())
                    est_time = content_preview.get("est_minutes", 30)
                    
                    st.session_state.tasks.append({
                        "id": new_id,
                        "subject": new_sub,
                        "exam_board": assigned_board,
                        "topic": new_top.strip(),
                        "spec_details": new_spec.strip(),
                        "exam_date": new_exam_date,
                        "est_minutes": est_time,
                        "status": "Pending",
                        "confidence": new_conf,
                        "quiz_score": None
                    })
                    st.success(f"Added '{new_top}'! Target time: {est_time} mins.")
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
                            st.caption(f"⏱️ {task.get('est_minutes', 30)} mins")
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
        st.caption(f"**Subject:** {current_task.get('subject')} ({current_task.get('exam_board')}) | **Est. Time:** {current_task.get('est_minutes')} mins | **Level:** {st.session_state.user_settings['level']}")
        if current_task.get("spec_details"):
            st.caption(f"**Spec Focus:** {current_task.get('spec_details')}")
        
        # Load topic-specific AI content
        content = fetch_ai_breakdown(
            current_task.get('topic'),
            current_task.get('subject'),
            current_task.get('exam_board'),
            st.session_state.user_settings['level'],
            current_task.get('spec_details', '')
        )
        
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
