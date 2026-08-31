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
    page_title="Unstuck - Adaptive Revision",
    page_icon="⚡",
    layout="wide"
)

# Safe OpenAI Client Setup (Uses Fallback Data if Key is Missing or Invalid)
openai_api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
client = OpenAI(api_key=openai_api_key) if (openai_api_key and not openai_api_key.startswith("your-")) else None

# ---------------------------------------------------------
# 2. SESSION STATE & USER ACCOUNTS
# ---------------------------------------------------------
if "user" not in st.session_state:
    st.session_state.user = None

if "user_settings" not in st.session_state:
    st.session_state.user_settings = {
        "level": "A-Level",
        "weekly_hours": 15,
        "subjects": {
            "Chemistry": "AQA",
            "Physics": "OCR A",
            "Maths": "Edexcel"
        }
    }

today = datetime.date.today()

# Initial Demo Schedule Organized by Days
if "tasks" not in st.session_state:
    st.session_state.tasks = [
        {
            "id": 1,
            "subject": "Chemistry",
            "exam_board": "AQA",
            "topic": "Quantitative Chemistry & Moles",
            "scheduled_date": today - timedelta(days=2),
            "est_minutes": 45,
            "status": "Pending",
            "confidence": 2,
            "quiz_score": None
        },
        {
            "id": 2,
            "subject": "Physics",
            "exam_board": "OCR A",
            "topic": "Electricity & Circuits",
            "scheduled_date": today - timedelta(days=1),
            "est_minutes": 40,
            "status": "Pending",
            "confidence": 3,
            "quiz_score": None
        },
        {
            "id": 3,
            "subject": "Maths",
            "exam_board": "Edexcel",
            "topic": "Calculus & Integration",
            "scheduled_date": today - timedelta(days=1),
            "est_minutes": 50,
            "status": "Pending",
            "confidence": 1,
            "quiz_score": None
        },
        {
            "id": 4,
            "subject": "Chemistry",
            "exam_board": "AQA",
            "topic": "Organic Reactions",
            "scheduled_date": today,
            "est_minutes": 30,
            "status": "Pending",
            "confidence": 3,
            "quiz_score": None
        },
        {
            "id": 5,
            "subject": "Physics",
            "exam_board": "OCR A",
            "topic": "Waves & Quantum Physics",
            "scheduled_date": today + timedelta(days=1),
            "est_minutes": 45,
            "status": "Pending",
            "confidence": 4,
            "quiz_score": None
        }
    ]

if "selected_task_id" not in st.session_state:
    st.session_state.selected_task_id = None

if "recovery_triggered" not in st.session_state:
    st.session_state.recovery_triggered = False

# ---------------------------------------------------------
# 3. FUNCTIONAL RECOVERY MODE (AUTOMATIC ON 3 MISSED TASKS)
# ---------------------------------------------------------
overdue_tasks = [t for t in st.session_state.tasks if t["scheduled_date"] < today and t["status"] == "Pending"]

if len(overdue_tasks) >= 3 and not st.session_state.recovery_triggered:
    st.session_state.recovery_triggered = True
    for t in st.session_state.tasks:
        if t["status"] == "Pending":
            # Scale down remaining workload time by 30%
            t["est_minutes"] = max(15, int(t["est_minutes"] * 0.7))
            # Reschedule overdue tasks to today
            if t["scheduled_date"] < today:
                t["scheduled_date"] = today

# ---------------------------------------------------------
# 4. AI TASK BREAKDOWN GENERATOR (WITH SAFE FALLBACK)
# ---------------------------------------------------------
def fetch_ai_breakdown(topic, subject, board):
    fallback_data = {
        "steps": [
            f"Review key specification definitions for {topic} ({board}) using summary notes.",
            "Work through 2 step-by-step example calculations or diagrams to master the core method.",
            "Complete 3 targeted practice problems without relying on notes or hints."
        ],
        "flashcards": [
            {"q": f"What is the standard specification definition for {topic}?", "a": "The official exam board marking scheme definition."},
            {"q": f"Which equation/formula is critical for {topic}?", "a": "Primary formula and required standard SI units."},
            {"q": "What common mistake do students make in exam questions for this topic?", "a": "Incorrect unit conversions or missing working out steps."}
        ],
        "test_questions": [
            {"q": f"Question 1: What is the fundamental principle of {topic}?", "options": ["Option A", "Option B", "Option C", "Option D"], "correct": 0},
            {"q": f"Question 2: Which unit is correct for {topic} calculations?", "options": ["Joule", "Mole", "Pascal", "Volt"], "correct": 1},
            {"q": f"Question 3: Calculate expected value under standard conditions.", "options": ["12.5", "25.0", "50.0", "100.0"], "correct": 1},
            {"q": f"Question 4: Identify the essential step in multi-mark questions.", "options": ["Rearrange formula", "Ignore units", "Estimate value", "Skip state symbols"], "correct": 0},
            {"q": f"Question 5: What occurs when variables double in this process?", "options": ["Halves", "Doubles", "Quadruples", "Remains constant"], "correct": 1}
        ]
    }
    
    if not client:
        return fallback_data
        
    prompt = f"""
    Generate a revision breakdown for {subject} ({board}) topic '{topic}'.
    Return ONLY a JSON object with:
    - "steps": 3 concise steps on the best way to learn this specific topic.
    - "flashcards": array of 3 objects with "q" and "a".
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
    
    level = st.selectbox("Level", ["A-Level", "GCSE"], index=0 if st.session_state.user_settings["level"] == "A-Level" else 1)
    st.session_state.user_settings["level"] = level
    
    weekly_hrs = st.slider("Weekly Revision Target (Hours)", 5, 40, st.session_state.user_settings["weekly_hours"])
    st.session_state.user_settings["weekly_hours"] = weekly_hrs
    
    st.subheader("Subjects & Exam Boards")
    boards = ["AQA", "OCR A", "OCR B", "Edexcel", "WJEC"]
    
    chem_board = st.selectbox("Chemistry Board", boards, index=0)
    phys_board = st.selectbox("Physics Board", boards, index=1)
    math_board = st.selectbox("Maths Board", boards, index=3)
    
    st.session_state.user_settings["subjects"] = {
        "Chemistry": chem_board,
        "Physics": phys_board,
        "Maths": math_board
    }

# ---------------------------------------------------------
# 6. HEADER & AUTOMATIC RECOVERY BANNER
# ---------------------------------------------------------
st.title("⚡ Unstuck")
st.caption("Adaptive Revision Planner • Beat Procrastination with Day-by-Day Micro-Steps")

if st.session_state.recovery_triggered:
    st.info("ℹ️ **Recovery Mode Activated:** You missed 3 tasks recently. Your workload for the next 48 hours has been reduced by 30% and schedule adjusted automatically.")

st.divider()

# ---------------------------------------------------------
# 7. MAIN LAYOUT (DAY-BY-DAY SCHEDULE & WORKSPACE)
# ---------------------------------------------------------
col_schedule, col_workspace = st.columns([1.1, 0.9])

with col_schedule:
    st.subheader("📅 Your Schedule by Day")
    
    # Organize schedule into 5 daily tabs
    days = [today + timedelta(days=i) for i in range(5)]
    day_names = ["Today", "Tomorrow"] + [(today + timedelta(days=i)).strftime("%A (%b %d)") for i in range(2, 5)]
    
    tabs = st.tabs(day_names)
    
    for i, day in enumerate(days):
        with tabs[i]:
            day_tasks = [t for t in st.session_state.tasks if t["scheduled_date"] == day]
            
            if not day_tasks:
                st.caption("🎉 No tasks scheduled for this day.")
            else:
                for task in day_tasks:
                    is_completed = task["status"] == "Completed"
                    status_icon = "✅" if is_completed else ("🔴" if task["scheduled_date"] < today else "🔵")
                    
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 2, 2])
                        with c1:
                            st.markdown(f"**{status_icon} {task['topic']}**")
                            st.caption(f"{task['subject']} ({task['exam_board']}) • Conf: {task['confidence']}/5")
                        with c2:
                            st.caption(f"⏱️ {task['est_minutes']} mins")
                            if task["quiz_score"] is not None:
                                st.caption(f"📊 Test Score: {task['quiz_score']}/5")
                        with c3:
                            if not is_completed:
                                if st.button("🚀 Unstuck", key=f"btn_unstuck_{task['id']}"):
                                    st.session_state.selected_task_id = task["id"]
                                    st.rerun()
                            else:
                                st.success("Completed")

    # Add Task Option
    with st.expander("➕ Add Task"):
        with st.form("add_task_form"):
            new_sub = st.selectbox("Subject", list(st.session_state.user_settings["subjects"].keys()))
            new_top = st.text_input("Topic Name", placeholder="e.g. Redox Reactions")
            new_date = st.date_input("Schedule Date", today)
            new_mins = st.number_input("Expected Time (minutes)", value=30, step=5)
            new_conf = st.slider("Current Confidence Rating (1-5)", 1, 5, 3)
            
            if st.form_submit_button("Add Task") and new_top:
                new_id = max([t["id"] for t in st.session_state.tasks], default=0) + 1
                st.session_state.tasks.append({
                    "id": new_id,
                    "subject": new_sub,
                    "exam_board": st.session_state.user_settings["subjects"].get(new_sub, "AQA"),
                    "topic": new_top,
                    "scheduled_date": new_date,
                    "est_minutes": new_mins,
                    "status": "Pending",
                    "confidence": new_conf,
                    "quiz_score": None
                })
                st.success("Task added!")
                st.rerun()

# --- RIGHT COLUMN: MICRO-TASK WORKSPACE ---
with col_workspace:
    st.subheader("💡 Micro-Task Workspace")
    
    current_task = next((t for t in st.session_state.tasks if t["id"] == st.session_state.selected_task_id), None)
    
    if not current_task:
        st.info("👈 Select a day on the left schedule and click **'🚀 Unstuck'** on any task to open its learning plan.")
    else:
        st.markdown(f"### Working on: **{current_task['topic']}**")
        st.caption(f"**Subject:** {current_task['subject']} ({current_task['exam_board']}) | **Expected Time:** {current_task['est_minutes']} mins")
        
        # Load topic content safely
        content = fetch_ai_breakdown(current_task["topic"], current_task["subject"], current_task["exam_board"])
        
        st.divider()
        st.write("#### 🎯 3 Best Learning Steps")
        for idx, step in enumerate(content["steps"], 1):
            st.checkbox(f"**Step {idx}:** {step}", key=f"chk_{current_task['id']}_{idx}")
            
        st.divider()
        st.write("#### 🧠 Quick Recall Flashcards")
        for fc_idx, fc in enumerate(content["flashcards"], 1):
            with st.expander(f"🎴 Flashcard {fc_idx}: {fc['q']}"):
                st.write(f"**Answer:** {fc['a']}")
                
        st.divider()
        st.write("#### 📝 5 Exam Practice Questions")
        quiz_answers = []
        for q_idx, q in enumerate(content["test_questions"]):
            st.write(f"**Q{q_idx+1}: {q['q']}**")
            ans = st.radio(
                f"Select answer for Q{q_idx+1}:", 
                q["options"], 
                key=f"quiz_{current_task['id']}_{q_idx}",
                index=None
            )
            quiz_answers.append((ans, q["options"][q["correct"]]))
            
        st.divider()
        st.write("#### 📊 Confidence & Completion")
        
        # Confidence Rating (1-5 Scale)
        new_conf_val = st.slider(
            "Rate your confidence after this session (1 = Low, 5 = High):",
            min_value=1,
            max_value=5,
            value=int(current_task["confidence"]),
            key=f"conf_slider_{current_task['id']}"
        )
        
        if st.button("✅ Complete Task", type="primary", key=f"complete_{current_task['id']}"):
            score = sum(1 for user_ans, correct_ans in quiz_answers if user_ans == correct_ans)
            
            # Save updates to session state
            current_task["status"] = "Completed"
            current_task["confidence"] = new_conf_val
            current_task["quiz_score"] = score
            st.session_state.selected_task_id = None
            
            st.success(f"Task completed! Exam test score saved: {score}/5.")
            st.rerun()
