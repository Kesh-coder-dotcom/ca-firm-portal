import streamlit as st
import pandas as pd
import datetime
from supabase import create_client, Client

# --- PRODUCTION CONFIGURATION ---
st.set_page_config(page_title="TASK ASSIGNER", layout="wide", initial_sidebar_state="expanded")

# --- DATABASE CONNECTION ENGINE ---
@st.cache_resource
def init_supabase() -> Client:
    """Establishes a single cached client using standard clean secrets strings."""
    url = st.secrets["supabase"]["url"].strip().rstrip("/")
    key = st.secrets["supabase"]["key"].strip()
    return create_client(url, key)

try:
    supabase = init_supabase()
except Exception as e:
    st.error("🔒 Infrastructure Alert: Failed to establish secure connection to Supabase database clusters.")
    st.stop()

# --- DATABASE UTILITY WRAPPERS ---
def fetch_all_users() -> dict:
    """Retrieves all operational credentials from the cloud."""
    response = supabase.table("cloud_users").select("*").execute()
    user_dict = {}
    for user in response.data:
        user_dict[user["username"]] = {"password": user["password"], "role": user["role"]}
    return user_dict

def fetch_all_tasks() -> list:
    """Retrieves all active task items from the cloud database."""
    response = supabase.table("cloud_tasks").select("*").execute()
    return response.data

# Fetch a dynamic baseline for application operations
try:
    current_db_users = fetch_all_users()
    current_db_tasks = fetch_all_tasks()
except Exception as e:
    st.error(f"⚠️ Query Failure: Failed to synchronize live logs. Ensure tables exist in Supabase and secrets match. Error: {e}")
    st.stop()

# --- LOGIN GATEWAY ---
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None

if st.session_state.auth_user is None:
    st.title("🔒 Professional Portal")
    st.subheader("Secure Firm Authentication Gateway")
    
    username_input = st.text_input("User ID Key", placeholder="Enter assigned user id...").strip()
    password_input = st.text_input("Password Security Key", type="password", placeholder="Enter password...").strip()
    
    if st.button("Authenticate Connection", use_container_width=True):
        if username_input in current_db_users and current_db_users[username_input]["password"] == password_input:
            st.session_state.auth_user = username_input
            st.session_state.auth_role = current_db_users[username_input]["role"]
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

# --- INTERNAL CONTROL 1: ROLE PROVISIONING ENGINE (MASTER ONLY) ---
if user_role == "Master User":
    st.sidebar.markdown("---")
    st.sidebar.subheader("🛠️ Master Provisioning Engine")
    
    with st.sidebar.expander("Generate New System Credentials"):
        new_uid = st.text_input("Target User ID", key="prov_uid").strip()
        new_pwd = st.text_input("Security Access Password", type="password", key="prov_pwd").strip()
        role_selection = st.radio("System Access Level Rights:", ["Junior Staff", "Local Head"], key="prov_role")
        
        if st.button("Deploy User Credentials"):
            if new_uid and new_pwd:
                if new_uid not in current_db_users:
                    supabase.table("cloud_users").insert({
                        "username": new_uid, 
                        "password": new_pwd, 
                        "role": role_selection
                    }).execute()
                    st.sidebar.success(f"System clearance issued to '{new_uid}'!")
                    st.rerun()
                else:
                    st.sidebar.error("System Error: ID exists.")
            else:
                st.sidebar.error("Input missing metrics.")

    with st.sidebar.expander("❌ De-provision System Users"):
        removable_users = [u for u in current_db_users.keys() if u != "master_admin"]
        
        if removable_users:
            user_to_delete = st.selectbox("Select Profile to Remove", removable_users, key="del_user_select")
            if st.button("Revoke Account Access", type="primary"):
                supabase.table("cloud_users").delete().eq("username", user_to_delete).execute()
                st.sidebar.warning(f"User account '{user_to_delete}' has been purged.")
                st.rerun()
        else:
            st.sidebar.text("No external accounts available.")

# Dynamic identification lists parsing structural layout models
all_registered_identities = sorted(list(current_db_users.keys()))
all_local_heads = [u for u, d in current_db_users.items() if d["role"] == "Local Head"]
all_junior_staff = [u for u, d in current_db_users.items() if d["role"] == "Junior Staff"]

# --- INTERNAL CONTROL 2: VISIBILITY & DATA ISOLATION ENGINE ---
st.title("📊 Chartered Accountant Operational Oversight Panel")
df_tasks = pd.DataFrame(current_db_tasks)
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
    
    # --- TASK PROVISIONING ENGINE (CREATION FORM) ---
    st.subheader("➕ Deploy New Task Assignment")
    with st.expander("Configure New Task Deployment Parameters", expanded=False):
        t_col1, t_col2 = st.columns(2)
        
        with t_col1:
            new_task_name = st.text_input("Task Assignment Name", placeholder="e.g., Statutory Audit - Client ABC", key="task_add_name")
            if user_role == "Master User":
                assigned_head = st.selectbox("Assign Supervising Local Head", all_local_heads if all_local_heads else ["No Local Heads Available"], key="task_add_head")
            else:
                assigned_head = current_user
                st.text_input("Supervising Local Head (Locked)", value=current_user, disabled=True)
                
        with t_col2:
            assigned_worker = st.selectbox("Allocate to Worker (Junior Staff)", all_junior_staff if all_junior_staff else ["No Junior Staff Available"], key="task_add_staff")
            new_due_date = st.date_input("Target Completion Date (Due Date)", today + datetime.timedelta(days=7), key="task_add_date")
            
        new_task_desc = st.text_area("Initial Directives & Operational Scope", key="task_add_desc")
        
        if st.button("Initialize & Deploy Task", type="primary", use_container_width=True):
            if not new_task_name:
                st.error("Deployment Refused: Task Assignment Name cannot be blank.")
            elif assigned_head == "No Local Heads Available" or assigned_worker == "No Junior Staff Available":
                st.error("Deployment Refused: Valid firm operators must be selected.")
            else:
                supabase.table("cloud_tasks").insert({
                    "task_name": new_task_name,
                    "local_head_assigned": assigned_head,
                    "allocated_to": assigned_worker,
                    "allocation_date": str(today),
                    "due_date": str(new_due_date),
                    "status": "In Progress",
                    "description": new_task_desc if new_task_desc else "No custom guidelines attached."
                }).execute()
                st.success("Success! New task successfully deployed into cloud workflow chain.")
                st.rerun()

    # --- ADVANCED VIEW FILTERS CORE ---
    st.subheader("🔍 Operational Filter Console")
    f_col1, f_col2 = st.columns(2)
    
    # Isolate initial view dataframe rows based on system clearance
    base_df = df_tasks if user_role == "Master User" else (df_tasks[df_tasks["local_head_assigned"] == current_user] if not df_tasks.empty else df_tasks)
    
    with f_col1:
        if user_role == "Master User":
            filter_head = st.selectbox("Filter by Local Head Overseer", ["All Personnel"] + all_local_heads, key="f_head_select")
        else:
            filter_head = current_user
            st.info(f"Filtering tracking scoped to your profile: **{current_user}**")
            
    with f_col2:
        filter_worker = st.selectbox("Filter by Assigned Worker Account", ["All Personnel"] + all_junior_staff, key="f_staff_select")

    # Process metrics and display logs dynamically
    visible_df = base_df.copy() if not base_df.empty else pd.DataFrame()
    
    if not visible_df.empty:
        if user_role == "Master User" and filter_head != "All Personnel":
            visible_df = visible_df[visible_df["local_head_assigned"] == filter_head]
        if filter_worker != "All Personnel":
            visible_df = visible_df[visible_df["allocated_to"] == filter_worker]

    # Metrics rendering block
    c1, c2 = st.columns(2)
    c1.metric("Filtered Active Deployments", len(visible_df) if not visible_df.empty else 0)
    c2.metric("System Managed Operational Identities", len(current_db_users))
    
    st.subheader("📋 Comprehensive Assignment Log Matrix")
    if not visible_df.empty:
        # Columns mapped safely against database layouts
    
