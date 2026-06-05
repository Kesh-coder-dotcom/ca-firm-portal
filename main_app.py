import streamlit as st
import pandas as pd
import datetime
import sqlite3

# --- PRODUCTION CONFIGURATION ---
st.set_page_config(page_title="TASK ASSIGNER", layout="wide", initial_sidebar_state="expanded")

# --- PERSISTENT SQLITE DATABASE ENGINE ---
DB_FILE = "database.db"

def init_db():
    """Initializes database schema and scales structures to accommodate multi-manager nodes."""
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
        
        # Create/Upgrade Tasks table with direct Local Head tracking support
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_name TEXT NOT NULL,
                local_head_assigned TEXT NOT NULL DEFAULT 'local_head1',
                allocated_to TEXT NOT NULL,
                allocation_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                status TEXT NOT NULL,
                description TEXT
            )
        ''')
        
        # Safe migration check: Add column if an older database file exists without it
        cursor.execute("PRAGMA table_info(tasks)")
        columns = [col[1] for col in cursor.fetchall()]
        if "local_head_assigned" not in columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN local_head_assigned TEXT NOT NULL DEFAULT 'Unassigned Head'")
        
        # Seed initial default system nodes if table is blank
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            cursor.executemany("INSERT INTO users VALUES (?, ?, ?)", [
                ("master_admin", "admin123", "Master User"),
                ("local_head1", "head123", "Local Head"),
                ("local_head2", "head456", "Local Head"),
                ("junior_staff1", "staff123", "Junior Staff"),
                ("junior_staff2", "staff456", "Junior Staff")
            ])
            # Seed initial task containing cross-referenced role vectors
            cursor.execute(
                "INSERT INTO tasks (task_name, local_head_assigned, allocated_to, allocation_date, due_date, status, description) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("Income Tax Audit - Client X", "local_head1", "junior_staff1", str(datetime.date.today()), str(datetime.date.today() + datetime.timedelta(days=4)), "In Progress", "Initial data compilation started by Junior.")
            )
        conn.commit()

# Trigger active structural database sync
init_db()

# High-utility database operational helper wrappers
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
    rows = run_query("SELECT id, task_name, local_head_assigned, allocated_to, allocation_date, due_date, status, description FROM tasks")
    tasks = []
    for row in rows:
        tasks.append({
            "id": row[0], "task_name": row[1], "local_head_assigned": row[2], "allocated_to": row[3],
            "allocation_date": datetime.datetime.strptime(row[4], "%Y-%m-%d").date(),
            "due_date": datetime.datetime.strptime(row[5], "%Y-%m-%d").date(),
            "status": row[6], "description": row[7]
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

# Dynamic identification lists for database population controls (Shows ALL users created)
all_registered_identities = sorted(list(current_users_dict.keys()))

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

# High-Tier Visibility & Interactive Multi-User Filters
if user_role in ["Master User", "Local Head"]:
    
    # Base isolation filtering rules
    if user_role == "Master User":
        base_df = df_tasks
    else:
        # Local Head defaults to seeing rows where they are marked as the overseer
        base_df = df_tasks[df_tasks["local_head_assigned"] == current_user] if not df_tasks.empty else df_tasks

    # --- ADVANCED VIEW FILTERS CORE ---
    st.subheader("🔍 Operational Filter Console")
    f_col1, f_col2 = st.columns(2)
    
    with f_col1:
        # Show all choices for Master; Keep fixed to self for Local Head
        if user_role == "Master User":
            filter_head = st.selectbox("Filter by Local Head Overseer", ["All Personnel"] + all_registered_identities)
        else:
            filter_head = current_user
            st.info(f"Filtering tracking scoped to your profile: **{current_user}**")
            
    with f_col2:
        filter_worker = st.selectbox("Filter by Assigned Worker Account", ["All Personnel"] + all_registered_identities)

    # Process filters on dataframe
    visible_df = base_df.copy() if not base_df.empty else pd.DataFrame()
    
    if not visible_df.empty:
        if user_role == "Master User" and filter_head != "All Personnel":
            visible_df = visible_df[visible_df["local_head_assigned"] == filter_head]
        if filter_worker != "All Personnel":
            visible_df = visible_df[visible_df["allocated_to"] == filter_worker]

    # Metrics rendering block
    c1, c2 = st.columns(2)
    c1.metric("Filtered Active Deployments", len(visible_df) if not visible_df.empty else 0)
    c2.metric("System Managed Operational Identities", len(current_users_dict))
    
    st.subheader("📋 Comprehensive Assignment Log Matrix")
    if not visible_df.empty:
        st.dataframe(visible_df[["id", "task_name", "local_head_assigned", "allocated_to", "allocation_date", "due_date", "Deadline Status Tracker", "status", "description"]], use_container_width=True)
    else:
        st.info("No matching task assignments recorded within this filter query.")
        # --- SECURE CREDENTIALS AUDIT CORE PANEL (PASTE ANYWHERE) ---
if user_role == "Master User":
    st.markdown("---")
    st.subheader("👥 Active Database User Credentials Registry")
    
    # Query all users, passwords, and roles directly from the persistent SQLite database
    user_rows = run_query("SELECT username AS 'User ID Key', password AS 'Password Security Key', role AS 'System Access Level' FROM users")
    
    if user_rows:
        # Convert raw database rows into a clear, viewable screen table
        df_db_users = pd.DataFrame(user_rows, columns=["User ID Key", "Password Security Key", "System Access Level"])
        st.dataframe(df_db_users, use_container_width=True)
    else:
        st.info("No active users found in the system registry.")
        

    
