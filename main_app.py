import streamlit as st
import pandas as pd
import datetime

# --- PRODUCTION CONFIGURATION ---
st.set_page_config(page_title="TASK ASSIGNER", layout="wide", initial_sidebar_state="expanded")

# --- REVOLVING STATE ENGINE (PURE IN-MEMORY STORAGE) ---
if "cloud_users" not in st.session_state:
    st.session_state.cloud_users = {
        "master_admin": {"password": "admin123", "role": "Master User"},
        "local_head1": {"password": "head123", "role": "Local Head"},
        "local_head2": {"password": "head456", "role": "Local Head"},
        "junior_staff1": {"password": "staff123", "role": "Junior Staff"},
        "junior_staff2": {"password": "staff456", "role": "Junior Staff"},
    }

if "cloud_tasks" not in st.session_state:
    st.session_state.cloud_tasks = [
        {
            "id": 1, 
            "task_name": "Income Tax Audit - Client X", 
            "local_head_assigned": "local_head1",
            "allocated_to": "junior_staff1", 
            "allocation_date": datetime.date.today(),
            "due_date": datetime.date.today() + datetime.timedelta(days=4),
            "status": "In Progress",
            "description": "Initial data compilation started by Junior." 
        }
    ]

# --- LOGIN GATEWAY ---
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None

if st.session_state.auth_user is None:
    st.title("🔒 Professional CA Firm Management Portal")
    st.subheader("Secure Firm Authentication Gateway")
    
    username = st.text_input("User ID Key", placeholder="Enter assigned user id...")
    password = st.text_input("Password Security Key", type="password", placeholder="Enter password...")
    
    if st.button("Authenticate Connection", use_container_width=True):
        if username in st.session_state.cloud_users and st.session_state.cloud_users[username]["password"] == password:
            st.session_state.auth_user = username
            st.session_state.auth_role = st.session_state.cloud_users[username]["role"]
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
                if new_uid not in st.session_state.cloud_users:
                    st.session_state.cloud_users[new_uid] = {"password": new_pwd, "role": role_selection}
                    st.sidebar.success(f"System clearance issued to '{new_uid}'!")
                    st.rerun()
                else:
                    st.sidebar.error("System Error: ID exists.")
            else:
                st.sidebar.error("Input missing metrics.")

    with st.sidebar.expander("❌ De-provision System Users"):
        removable_users = [u for u in st.session_state.cloud_users.keys() if u != "master_admin"]
        
        if removable_users:
            user_to_delete = st.selectbox("Select Profile to Remove", removable_users)
            if st.button("Revoke Account Access", type="primary"):
                if user_to_delete in st.session_state.cloud_users:
                    del st.session_state.cloud_users[user_to_delete]
                    st.sidebar.warning(f"User account '{user_to_delete}' has been purged.")
                    st.rerun()
        else:
            st.sidebar.text("No external accounts available.")

# Dynamic identification lists that read directly from current memory logs
all_registered_identities = sorted(list(st.session_state.cloud_users.keys()))

# --- INTERNAL CONTROL 2: VISIBILITY & DATA ISOLATION ENGINE ---
st.title("📊 Chartered Accountant Operational Oversight Panel")
df_tasks = pd.DataFrame(st.session_state.cloud_tasks)
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
        base_df = df_tasks[df_tasks["local_head_assigned"] == current_user] if not df_tasks.empty else df_tasks

    # --- ADVANCED VIEW FILTERS CORE ---
    st.subheader("🔍 Operational Filter Console")
    f_col1, f_col2 = st.columns(2)
    
    with f_col1:
        if user_role == "Master User":
            filter_head = st.selectbox("Filter by Local Head Overseer", ["All Personnel"] + all_registered_identities)
        else:
            filter_head = current_user
            st.info(f"Filtering tracking scoped to your profile: **{current_user}**")
            
    with f_col2:
        filter_worker = st.selectbox("Filter by Assigned Worker Account", ["All Personnel"] + all_registered_identities)

    # Process filters dynamically on the view DataFrame
    visible_df = base_df.copy() if not base_df.empty else pd.DataFrame()
    
    if not visible_df.empty:
        if user_role == "Master User" and filter_head != "All Personnel":
            visible_df = visible_df[visible_df["local_head_assigned"] == filter_head]
        if filter_worker != "All Personnel":
            visible_df = visible_df[visible_df["allocated_to"] == filter_worker]

    # Metrics rendering block
    c1, c2 = st.columns(2)
    c1.metric("Filtered Active Deployments", len(visible_df) if not visible_df.empty else 0)
    c2.metric("System Managed Operational Identities", len(st.session_state.cloud_users))
    
    st.subheader("📋 Comprehensive Assignment Log Matrix")
    if not visible_df.empty:
        st.dataframe(visible_df[["id", "task_name", "local_head_assigned", "allocated_to", "allocation_date", "due_date", "Deadline Status Tracker", "status", "description"]], use_container_width=True)
    else:
        st.info("No matching task assignments recorded within this filter query.")
    
    # Master Audit Dashboard Credentials Viewer Panel
    if user_role == "Master User":
        st.markdown("---")
        st.subheader("👥 Active Database User Credentials Registry")
        df_db_users = pd.DataFrame([
            {"User ID Key": u, "Password Security Key": d["password"], "System Access Level Rights": d["role"]}
            for u, d in st.session_state.cloud_users.items()
        ])
        st.dataframe(df_db_users, use_container_width=True)
else:
    # Junior Staff Isolation Stream
    st.subheader("📥 Personal Duty Isolation Stream")
    if not df_tasks.empty:
        my_isolated_tasks = df_tasks[df_tasks["allocated_to"] == current_user]
        if not my_isolated_tasks.empty:
            st.dataframe(my_isolated_tasks[["id", "task_name", "local_head_assigned", "allocation_date", "due_date", "Deadline Status Tracker", "status", "description"]], use_container_width=True)
        else:
            st.info("No tasks allocated to your profile.")

# --- INTERNAL CONTROL 3: CONSTRAINED MODIFICATION CORE ---
st.markdown("---")
st.subheader("⚙️ Authorized Processing Action Panel")

if user_role in ["Master User", "Local Head"]:
    with st.expander("➕ Authorize & Deploy a New Allocation Assignment"):
        t_name = st.text_input("Assignment Title / Client Name")
        
        # Operational flexibility dropdown configurations (Loads ALL users dynamically)
        if user_role == "Master User":
            t_head = st.selectbox("Designate Overseeing Local Head", all_registered_identities if all_registered_identities else ["No Resources"])
            t_alloc = st.selectbox("Assign Primary Accountability To (Worker)", all_registered_identities if all_registered_identities else ["No Resources"])
        else:
            st.text(f"Designate Overseeing Local Head: {current_user} (Auto-Locked)")
            t_head = current_user
            t_alloc = st.selectbox("Assign Primary Accountability To (Worker)", all_registered_identities if all_registered_identities else ["No Resources"])
            
        t_due = st.date_input("Target Legal/Statutory Maturity Due Date", min_value=today)
        t_status = st.selectbox("System Prioritization Level Status", ["In Progress", "Urgent"])
        t_desc = st.text_area("Initial Operational Scope Description Data")
        
        if st.button("Commit Allocation to Log"):
            if t_name and t_alloc != "No Resources" and t_head != "No Resources":
                # Fixed ID safety fallback logic to prevent crash if log array is completely empty
                new_id = max([t["id"] for t in st.session_state.cloud_tasks]) + 1 if st.session_state.cloud_tasks else 1
                
                st.session_state.cloud_tasks.append({
                    "id": new_id, 
                    "task_name": t_name, 
