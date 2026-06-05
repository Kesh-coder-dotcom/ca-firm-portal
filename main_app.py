import streamlit as st
import pandas as pd
import datetime
import sqlite3

# --- PRODUCTION CONFIGURATION ---
st.set_page_config(page_title="TASK ASSIGNER", layout="wide", initial_sidebar_state="expanded")

# --- PERSISTENT SQLITE DATABASE ENGINE ---
DB_FILE = "database.db"

def init_db():
    """Initializes the database tables and inserts default system users if empty."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        # Create Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                role TEXT NOT NULL
            )
        ''')
        # Create Tasks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_name TEXT NOT NULL,
                allocated_to TEXT NOT NULL,
                allocation_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                status TEXT NOT NULL,
                description TEXT
            )
        ''')
        
        # Seed initial default users if table is blank
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            cursor.executemany("INSERT INTO users VALUES (?, ?, ?)", [
                ("master_admin", "admin123", "Master User"),
                ("local_head1", "head123", "Local Head"),
                ("junior_staff1", "staff123", "Junior Staff")
            ])
            # Seed initial task
            cursor.execute(
                "INSERT INTO tasks (task_name, allocated_to, allocation_date, due_date, status, description) VALUES (?, ?, ?, ?, ?, ?)",
                ("Income Tax Audit - Client X", "junior_staff1", str(datetime.date.today()), str(datetime.date.today() + datetime.timedelta(days=4)), "In Progress", "Initial data compilation started by Junior.")
            )
        conn.commit()

# Trigger database build
init_db()

# Helper database utility functions
def run_query(query, params=(), is_select=True):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        if is_select:
            return cursor.fetchall()
        conn.commit()

def get_users_dict():
    rows = run_query("SELECT username, password, role FROM users")
    return {row[0]: {"password": row[1], "role": row[2]} for row in rows}

def get_tasks_list():
    rows = run_query("SELECT id, task_name, allocated_to, allocation_date, due_date, status, description FROM tasks")
    tasks = []
    for row in rows:
        tasks.append({
            "id": row[0], "task_name": row[1], "allocated_to": row[2],
            "allocation_date": datetime.datetime.strptime(row[3], "%Y-%m-%d").date(),
            "due_date": datetime.datetime.strptime(row[4], "%Y-%m-%d").date(),
            "status": row[5], "description": row[6]
        })
    return tasks

# --- LOGIN GATEWAY ---
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None

if st.session_state.auth_user is None:
    st.title("🔒 Professional CA Firm Management Portal")
    st.subheader("Secure Firm Authentication Gateway")
    
    username = st.text_input("User ID Key", placeholder="Enter assigned user id...")
    password = st.text_input("Password Security Key", type="password", placeholder="Enter password...")
    
    if st.button("Authenticate Connection", use_container_width=True):
        cloud_users = get_users_dict()
        if username in cloud_users and cloud_users[username]["password"] == password:
            st.session_state.auth_user = username
            st.session_state.auth_role = cloud_users[username]["role"]
            st.rerun()
        else: 
            st.error("🔒 Security Exception: Access Denied. Invalid User ID or Password.")
    st.stop()

current_user = st.session_state.auth_user
user_role = st.session_state.auth_role

# --- SIDEBAR INTERFACE ---
st.sidebar.title("🏢 Firm Operations")
st.sidebar.info(f"Active Operator: **{current_user}**\n\nSecurity Clearance: **{user_role}**")

if st.sidebar.button("Secure Terminate (Logout)", use_container_width=True):
    st.session_state.auth_user = None
    st.session_state.auth_role = None
    st.rerun()

# --- INTERNAL CONTROL 1: ROLE PROVISIONING & DELETION ENGINE (MASTER ONLY) ---
if user_role == "Master User":
    st.sidebar.markdown("---")
    st.sidebar.subheader("🛠️ Master Provisioning Engine")
    
    with st.sidebar.expander("Generate New System Credentials"):
        new_uid = st.text_input("Target User ID")
        new_pwd = st.text_input("Security Access Password", type="password")
        role_selection = st.radio("System Access Level Rights:", ["Junior Staff", "Local Head"])
        
        if st.button("Deploy User Credentials"):
            if new_uid and new_pwd:
                cloud_users = get_users_dict()
                if new_uid not in cloud_users:
                    run_query("INSERT INTO users VALUES (?, ?, ?)", (new_uid, new_pwd, role_selection), is_select=False)
                    st.sidebar.success(f"System clearance issued to '{new_uid}'!")
                    st.rerun()
                else:
                    st.sidebar.error("System Error: ID exists.")
            else:
                st.sidebar.error("Input missing metrics.")

    with st.sidebar.expander("❌ De-provision System Users"):
        cloud_users = get_users_dict()
        # Prevent master admin from deleting themselves accidentally
        removable_users = [u for u in cloud_users.keys() if u != "master_admin"]
        
        if removable_users:
            user_to_delete = st.selectbox("Select Profile to Remove", removable_users)
            if st.button("Revoke Account Access", type="primary"):
                run_query("DELETE FROM users WHERE username = ?", (user_to_delete,), is_select=False)
                st.sidebar.warning(f"User account '{user_to_delete}' has been purged.")
                st.rerun()
        else:
            st.sidebar.text("No external accounts available.")

# --- DATA RETRIEVAL FOR VIEWS ---
current_tasks = get_tasks_list()
current_users_dict = get_users_dict()

# --- INTERNAL CONTROL 2: VISIBILITY & DATA ISOLATION ENGINE ---
st.title("📊 Chartered Accountant Operational Oversight Panel")
df_tasks = pd.DataFrame(current_tasks)
today = datetime.date.today()

def compute_deadline_metrics(due_date):
    if isinstance(due_date, str):
        due_date = datetime.datetime.strptime(due_date, "%Y-%m-%d").date()
    delta = (due_date - today).days
    if delta < 0: return f"🔴 Overdue by {abs(delta)} Days"
    elif delta <= 2: return f"⚠️ Critical Risk ({delta} Days Remaining)"
    else: return f"🟢 Stabilized ({delta} Days)"

if not df_tasks.empty:
    df_tasks["Deadline Status Tracker"] = df_tasks["due_date"].apply(compute_deadline_metrics)

if user_role in ["Master User", "Local Head"]:
    c1, c2 = st.columns(2)
    c1.metric("Gross Active Deployments", len(df_tasks))
    c2.metric("System Managed Operational Identities", len(current_users_dict))
    
    st.subheader("📋 Comprehensive Assignment Log Matrix")
    if not df_tasks.empty:
        st.dataframe(df_tasks[["id", "task_name", "allocated_to", "allocation_date", "due_date", "Deadline Status Tracker", "status", "description"]], use_container_width=True)
else:
    st.subheader("📥 Personal Duty Isolation Stream")
    if not df_tasks.empty:
        my_isolated_tasks = df_tasks[df_tasks["allocated_to"] == current_user]
        if not my_isolated_tasks.empty:
            st.dataframe(my_isolated_tasks[["id", "task_name", "allocation_date", "due_date", "Deadline Status Tracker", "status", "description"]], use_container_width=True)
        else:
            st.info("No tasks allocated to your profile.")

# --- INTERNAL CONTROL 3: CONSTRAINED MODIFICATION CORE ---
st.markdown("---")
st.subheader("⚙️ Authorized Processing Action Panel")

if user_role in ["Master User", "Local Head"]:
    with st.expander("➕ Authorize & Deploy a New Allocation Assignment"):
        t_name = st.text_input("Assignment Title / Client Name")
        all_juniors = [u for u, data in current_users_dict.items() if data["role"] == "Junior Staff"]
        t_alloc = st.selectbox("Assign Primary Accountability To", all_juniors if all_juniors else ["No Resources Registered"])
        t_due = st.date_input("Target Legal/Statutory Maturity Due Date", min_value=today)
        t_status = st.selectbox("System Prioritization Level Status", ["In Progress", "Urgent"])
        t_desc = st.text_area("Initial Operational Scope Description Data")
        
        if st.button("Commit Allocation to Log"):
            if t_name and t_alloc != "No Resources Registered":
                run_query(
                    "INSERT INTO tasks (task_name, allocated_to, allocation_date, due_date, status, description) VALUES (?, ?, ?, ?, ?, ?)",
                    (t_name, t_alloc, str(today), str(t_due), t_status, t_desc),
                    is_select=False
                )
                st.success("Allocation updated!")
                st.rerun()

# Processing Log Updates & Task Deletion Matrix
if current_tasks:
    with st.expander("📝 Process Modification Audits & Task Actions"):
        if user_role in ["Master User", "Local Head"]:
            eligible_options = {f"ID {t['id']}: {t['task_name']} (Responsible: {t['allocated_to']})": t for t in current_tasks}
        else:
            eligible_options = {f"ID {t['id']}: {t['task_name']}": t for t in current_tasks if t['allocated_to'] == current_user}
            
        if eligible_options:
            selected_node = st.selectbox("Select Target Registry Object to Modify/Delete", list(eligible_options.keys()))
            target_object = eligible_options[selected_node]
            
            # Form Layout split for Edit vs Delete Actions
    
