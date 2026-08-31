import streamlit as st
import datetime
from datetime import timedelta
import os
import json
from openai import OpenAI

# ---------------------------------------------------------
# 1. SETUP & CONFIGURATION
# ---------------------------------------------------------
st.set_page_config(
    page_title="Unstuck - Adaptive Revision Planner",
    page_icon="⚡",
    layout="wide"
)

# Initialize OpenAI Client (Uses Streamlit Secrets or Environment Variable)
openai_api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
client = OpenAI(api_key=openai_api_key) if openai_api_key else None

# ---------------------------------------------------------
# 2. STATE MANAGEMENT (Mocking Supabase for Prototyping)
# ---------------------------------------------------------
if "tasks" not in st.session_state:
    st.session_state.tasks = [
        {
            "id": 1,
            "subject": "Chemistry",
            "topic": "Quantitative Chemistry & Moles",
            "exam_date": datetime.date.today() + timedelta(days=14),
            "confidence": "Low",
            "status": "Overdue",
            "scheduled_date": datetime.date.today() - timedelta(days=1),
            "est_minutes": 60,
        },
        {
            "id": 2,
            "subject": "Physics",
            "topic": "Electricity & Circuits",
            "exam_date": datetime.date.today() + timedelta(days=20),
            "confidence": "Medium",
            "status": "Overdue",
            "scheduled_date": datetime.date.today() - timedelta(days=2),
            "est_minutes": 45,
        },
        {
            "id": 3,
            "subject": "Biology",
            "topic": "Cell Structure & Transport",
            "exam_date": datetime.date.today() + timedelta(days=10),
            "confidence": "Low",
            "status": "Overdue",
            "scheduled_date": datetime.date.today() - timedelta(days=3),
            "est_minutes": 60,
        },
        {
            "id": 4,
            "subject": "Maths",
            "topic": "Calculus & Integration",
            "exam_date": datetime.date.today() + timedelta(days=5),
            "confidence": "High",
            "status": "Pending",
            "scheduled_date": datetime.date.today(),
            "est_minutes": 30,
        }
    ]

if "consecutive_misses" not in st.session_state:
    st.session_state.consecutive_misses = 3  # Pre-set for demonstration

if "recovery_mode" not in st.session_state:
    st.session_state.recovery_mode = False

if "selected_task" not in st.session_state:
    st.session_state.selected_task = None

# ---------------------------------------------------------
# 3. HELPER FUNCTIONS & LOGIC
# ---------------------------------------------------------
def activate_recovery_mode():
    """Reduces the next 48 hours of workload by 30% and pushes dates."""
    st.session_state.recovery_mode = True
    today = datetime.date.today()
    next_48h = today + timedelta(days=2)
    
    for task in st.session_state.tasks:
        if task["scheduled_date"] <= next_48h and task["status"] != "Completed":
            # Scale down estimated work time by 30%
            task["est_minutes"] = int(task["est_minutes"] * 0.7)
            # Push overdue items forward to today/tomorrow
            if task["scheduled_date"] < today:
                task["scheduled_date"] = today + timedelta(days=1)
                task["status"] = "Pending"
                
    st.session_state.consecutive_misses = 0

def generate_ai_breakdown(topic, subject):
    """Calls OpenAI API to break a topic into micro-steps, flashcards, and practice questions."""
    if not client:
        # Fallback Mock Data if no API key is set up yet
        return {
            "micro_steps": [
                f"Read the summary notes for {topic} on Physics & Maths Tutor.",
                "Define key formulas/terms and write them on a single index card.",
                "Complete 3 foundation-level practice questions."
            ],
            "flashcards": [
                {"q": f"What is the core definition in {topic}?", "a": "Standard exam board definition goes here."},
                {"q": "What is the key equation?", "a": "Primary formula and units required."},
                {"q": "What common mistake do students make?", "a": "Forgetting unit conversions."}
            ],
            "practice_questions": [
                "Define the main term.",
                "Calculate a standard problem given basic values.",
                "Explain the mechanism/process in 3 steps.",
                "Compare this process with a related topic.",
                "Solve an extended multi-step exam question."
            ]
        }
    
    prompt = f"""
    You are an expert tutor for UK secondary students (GCSE/A-Level). 
    Break down the revision topic '{topic}' in '{subject}' to help an overwhelmed student who is procrastinating.
    
    Return ONLY a valid JSON object matching this structure:
    {{
      "micro_steps": ["step 1", "step 2", "step 3"],
      "flashcards": [
        {{"q": "question 1", "a": "answer 1"}},
        {{"q": "question 2", "a": "answer 2"}},
        {{"q": "question 3", "a": "answer 3"}}
      ],
      "practice_questions": ["q1", "q2", "q3", "q4", "q5"]
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"Error calling OpenAI API: {e}")
        return None

# Check consecutive misses on initial load
overdue_count = sum(1 for t in st.session_state.tasks if t["status"] == "Overdue")
if overdue_count >= 3 and not st.session_state.recovery_mode:
    st.session_state.consecutive_misses = overdue_count

# ---------------------------------------------------------
# 4. UI HEADER & RECOVERY BANNER
# ---------------------------------------------------------
st.title("⚡ Unstuck")
st.caption("Adaptive Revision Planner • Beat Procrastination with Micro-Steps")

# Auto-Trigger Recovery Banner
if st.session_state.consecutive_misses >= 3 or st.session_state.recovery_mode:
    st.warning("⚠️ **Overwhelm Detected!** You have missed 3 or more tasks recently. Don't worry—revision plans should adapt to you, not the other way around.")
    col_rec1, col_rec2 = st.columns([3, 1])
    with col_rec1:
        st.write("Activate **Recovery Mode** to cut your workload for the next 48 hours by 30% and reschedule overdue tasks automatically.")
    with col_rec2:
        if st.button("🛡️ Activate Recovery Mode", type="primary"):
            activate_recovery_mode()
            st.rerun()

st.divider()

# ---------------------------------------------------------
# 5. DASHBOARD LAYOUT (2 COLUMNS)
# ---------------------------------------------------------
col_dash, col_workspace = st.columns([1, 1])

# --- LEFT COLUMN: Schedule & Tasks ---
with col_dash:
    st.subheader("📋 Your Adaptive Schedule")
    
    # Quick Add Form
    with st.expander("➕ Add New Topic / Subject"):
        with st.form("new_task"):
            new_sub = st.selectbox("Subject", ["Chemistry", "Physics", "Biology", "Maths", "English", "History"])
            new_topic = st.text_input("Topic Name", placeholder="e.g. Quantitative Chemistry")
            new_exam = st.date_input("Exam Date", datetime.date.today() + timedelta(days=30))
            new_conf = st.select_slider("Current Confidence", options=["Low", "Medium", "High"])
            submit = st.form_submit_button("Add to Schedule")
            
            if submit and new_topic:
                st.session_state.tasks.append({
                    "id": len(st.session_state.tasks) + 1,
                    "subject": new_sub,
                    "topic": new_topic,
                    "exam_date": new_exam,
                    "confidence": new_conf,
                    "status": "Pending",
                    "scheduled_date": datetime.date.today(),
                    "est_minutes": 60 if new_conf == "Low" else 30
                })
                st.success(f"Added {new_topic}!")
                st.rerun()

    # Task List Display
    st.write("### Tasks")
    for task in st.session_state.tasks:
        card_color = "🔴" if task["status"] == "Overdue" else ("🟢" if task["status"] == "Completed" else "🔵")
        
        with st.container(border=True):
            tc1, tc2, tc3 = st.columns([3, 2, 2])
            with tc1:
                st.markdown(f"**{card_color} {task['topic']}**")
                st.caption(f"{task['subject']} • Confidence: {task['confidence']}")
            with tc2:
                st.caption(f"⏱️ {task['est_minutes']} mins")
                st.caption(f"📅 Due: {task['scheduled_date'].strftime('%b %d')}")
            with tc3:
                if st.button("🚀 Unstuck", key=f"btn_{task['id']}"):
                    st.session_state.selected_task = task
                    st.rerun()

# --- RIGHT COLUMN: Micro-Task Workspace ---
with col_workspace:
    st.subheader("💡 Micro-Task Workspace")
    
    task = st.session_state.selected_task
    if not task:
        st.info("👈 Select any task from your schedule and click **'Unstuck'** to generate a step-by-step micro-plan.")
    else:
        st.success(f"### Working on: {task['topic']}")
        st.write(f"**Goal:** Complete 3 tiny actions to break through starting resistance.")
        
        # Trigger OpenAI Generation
        with st.spinner("AI is breaking down this topic into micro-steps..."):
            breakdown = generate_ai_breakdown(task["topic"], task["subject"])
            
        if breakdown:
            st.markdown("---")
            st.write("#### 🎯 Step-by-Step Action Plan")
            for i, step in enumerate(breakdown["micro_steps"], 1):
                st.checkbox(f"**Step {i}:** {step}", key=f"step_{task['id']}_{i}")
                
            st.markdown("---")
            st.write("#### 🧠 Quick Recall Flashcards")
            for card in breakdown["flashcards"]:
                with st.expander(f"❓ {card['q']}"):
                    st.write(f"Answer:")
                    
            st.markdown("---")
            st.write("#### 📝 5 Optional Practice Questions")
            for q in breakdown["practice_questions"]:
                st.markdown(f"- {q}")
                
            st.markdown("---")
            st.write("#### Finish Task & Rate Confidence")
            conf_rating = st.select_slider(
                "How do you feel after this revision session?",
                options=["Low", "Medium", "High"],
                value=task["confidence"],
                key=f"post_conf_{task['id']}"
            )
            
            if st.button("✅ Mark Task Complete", type="primary"):
                task["status"] = "Completed"
                task["confidence"] = conf_rating
                st.session_state.selected_task = None
                st.success("Great job! Schedule updated.")
                st.rerun()
