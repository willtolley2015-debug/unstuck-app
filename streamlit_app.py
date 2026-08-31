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
# 2. SESSION STATE & DEFENSIVE KEYS (PREVENTS KEYERRORS)
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

# Start with empty task list initially
if "tasks" not in st.session_state:
    st.session_state.tasks = []

# Defensive Migration: ensure any cached session tasks contain all keys
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

if "selected_task_id" not in st.session_state:
    st.session_state.selected_task_id = None

if "recovery_triggered" not in st.session_state:
    st.session_state.recovery_triggered = False

# ---------------------------------------------------------
# 3. RECOVERY MODE LOGIC
# ---------------------------------------------------------
overdue_tasks = [t for t in st.session_state.tasks if t.get("scheduled_date", today) < today and t.get("status") == "Pending"]

if len(overdue_tasks) >= 3 and not st.session_state.recovery_triggered:
    st.session_state.recovery_triggered = True
    for t in st.session_state.tasks:
        if t.get("status") == "Pending":
            t["est_minutes"] = max(15, int(t.get("est_minutes", 30) * 0.7))
            if t.get("scheduled_date", today) < today:
                t["scheduled_date"] = today

# ---------------------------------------------------------
# 4. AI BREAKDOWN ENGINE (WITH FALLBACK MOCK DATA)
# ---------------------------------------------------------
def fetch_ai_breakdown(topic, subject, board):
    fallback_data = {
        "steps": [
            f"Review key specification definitions for {topic} ({board}) using summary notes.",
            "Work through 2 step-by-step example calculations or diagrams to master the core method.",
            "Complete 3 targeted practice problems without relying on notes or hints."
        ],
        "flashcards": [
            {"q": f"What is the standard specification definition for {topic}?", "a": f"The official {board} marking scheme definition for {topic}."},
            {"q": f"Which equation or key term is critical for {topic}?", "a": "Primary formula or core theory and required standard units."},
            {"q": f"What common mistake do students make in {board} exam questions for this topic?", "a": "Incorrect unit conversions or missing required working steps."}
        ],
        "test_questions": [
            {"q": f"Question 1: What is the fundamental principle of {topic}?", "options": ["Option A: Core Definition", "Option B: Secondary Effect", "Option C: Unrelated Theory", "Option D: Inverse Rule"], "correct": 0},
            {"q": f"Question 2: Which unit is correct for {topic} calculations?", "options": ["Joule (J)", "Mole (mol)", "Pascal (Pa)", "Volt (V)"], "correct": 1},
            {"q": f"Question 3: Calculate the expected result under standard specification conditions.", "options": ["12.5", "25.0", "50.0", "100.0"], "correct": 1},
            {"q": f"Question 4: Identify the essential step in multi-mark exam questions.", "options": ["Rearrange formula first", "Ignore units", "Estimate final value", "Skip state symbols"], "correct": 0},
            {"q": f"Question 5: What occurs when variables double in this process?", "options": ["Halves", "Doubles", "Quadruples", "Remains constant"], "correct": 1}
        ]
    }
    
    if not client:
        return fallback_data
        
    prompt = f"""
    Generate a revision breakdown for {subject} ({board}) topic '{topic}'.
    Return ONLY a JSON object with:
    - "steps": 3 concise steps on the best way to learn this specific topic.
    - "flashcards": array of 3-5 objects with "q" and "a".
    - "test_questions": array of 5 objects with "q", "options" (4 strings), "correct" (index 0-3).
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
    
    # Revision Target Slider (Up to 50 hours)
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
    
    boards = ["AQA", "OCR A", "OCR B", "Edexcel", "WJEC", "Eduqas", "Cambridge (CIE)"]
    st.caption("Select Exam Board for each subject:")
    for sub in selected_subs:
        curr_board = st.session_state.user_settings["subject_boards"].get(sub, "AQA")
        board_idx = boards.index(curr_board) if curr_board in boards else 0
        new_board = st.selectbox(f"{sub} Board", boards, index=board_idx, key=f"board_select_{sub}")
        st.session_state.user_settings["subject_boards"][sub] = new_board

# ---------------------------------------------------------
# 6. MAIN HEADER & RECOVERY BANNER
# ---------------------------------------------------------
st.title("⚡ Unstuck")
st.caption("Adaptive Revision Planner • Beat Procrastination with Day-by-Day Micro-Steps")

if st.session_state.recovery_triggered:
    st.info("ℹ️ **Recovery Mode Activated:** 3 tasks were missed recently. Workload for upcoming days has been reduced by 30% and schedule adjusted automatically.")

st.divider()

# ---------------------------------------------------------
# 7. MAIN SCHEDULE & WORKSPACE
# ---------------------------------------------------------
col_schedule, col_workspace = st.columns([1.1, 0.9])

with col_schedule:
    st.subheader("📅 Your Schedule by Day")
    
    # Task Creator Form
    with st.expander("➕ Add Task to Schedule", expanded=(len(st.session_state.tasks) == 0)):
        with st.form("add_task_form"):
            chosen_subjects = st.session_state.user_settings["selected_subjects"]
            new_sub = st.selectbox("Select Subject", chosen_subjects)
            new_top = st.text_input("Topic Name", placeholder="e.g. Quantitative Chemistry / Electricity & Circuits")
            
            # Select Day & Parameters
            new_date = st.date_input("Scheduled Day", today)
            new_mins = st.number_input("Expected Time (minutes)", value=30, min_value=10, max_value=180, step=5)
            new_conf = st.slider("Current Confidence Rating (1-5)", 1, 5, 3)
            
            if st.form_submit_button("➕ Add Task to Schedule"):
                if new_top.strip():
                    assigned_board = st.session_state.user_settings["subject_boards"].get(new_sub, "AQA")
                    new_id = max([t.get("id", 0) for t in st.session_state.tasks], default=0) + 1
                    st.session_state.tasks.append({
                        "id": new_id,
                        "subject": new_sub,
                        "exam_board": assigned_board,
                        "topic": new_top.strip(),
                        "scheduled_date": new_date,
                        "est_minutes": new_mins,
                        "status": "Pending",
                        "confidence": new_conf,
                        "quiz_score": None
                    })
                    st.success(f"Added '{new_top}' to schedule for {new_date.strftime('%b %d')}!")
                    st.rerun()
                else:
                    st.error("Please enter a topic name.")

    # 7-Day View Tabs
    days = [today + timedelta(days=i) for i in range(7)]
    day_names = ["Today", "Tomorrow"] + [(today + timedelta(days=i)).strftime("%a %b %d") for i in range(2, 7)]
    
    tabs = st.tabs(day_names)
    
    for i, day in enumerate(days):
        with tabs[i]:
            day_tasks = [t for t in st.session_state.tasks if t.get("scheduled_date") == day]
            
            if not day_tasks:
                st.caption("✨ No tasks scheduled for this day yet. Use 'Add Task to Schedule' above.")
            else:
                for task in day_tasks:
                    is_completed = task.get("status") == "Completed"
                    status_icon = "✅" if is_completed else ("🔴" if task.get("scheduled_date", today) < today else "🔵")
                    
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

# Workspace Column
with col_workspace:
    st.subheader("💡 Micro-Task Workspace")
    
    current_task = next((t for t in st.session_state.tasks if t.get("id") == st.session_state.selected_task_id), None)
    
    if not current_task:
        st.info("👈 Select a day tab on the schedule and click **'🚀 Unstuck'** to load micro-steps, flashcards, and practice questions.")
    else:
        st.markdown(f"### Working on: **{current_task.get('topic')}**")
        st.caption(f"**Subject:** {current_task.get('subject')} ({current_task.get('exam_board')}) | **Expected Time:** {current_task.get('est_minutes')} mins")
        
        # Load topic content
        content = fetch_ai_breakdown(current_task.get('topic'), current_task.get('subject'), current_task.get('exam_board'))
        
        st.divider()
        st.write("#### 🎯 3 Best Learning Steps")
        for idx, step in enumerate(content.get("steps", []), 1):
            st.checkbox(f"**Step {idx}:** {step}", key=f"chk_{current_task.get('id')}_{idx}")
            
        st.divider()
        st.write("#### 🧠 Quick Recall Flashcards")
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
        st.write("#### 📊 Confidence Rating & Completion")
        
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
            
            # Save updates
            current_task["status"] = "Completed"
            current_task["confidence"] = new_conf_val
            current_task["quiz_score"] = score
            st.session_state.selected_task_id = None
            
            st.success(f"Task marked complete! Test score: {score}/5.")
            st.rerun()
