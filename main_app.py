import streamlit as st
import pandas as pd
import datetime

# --- PRODUCTION CONFIGURATION ---
st.set_page_config(page_title="TASK ASSIGNER", layout="wide", initial_sidebar_state="expanded")

# --- REVOLVING STATE ENGINE ---
# Preserves data dynamically for active users across mobile devices
if "cloud_users" not in st.session_state:
    st.session_state.cloud_users = {
        "master_admin": {"password": "admin123", "role": "Master User"},
        "local_head1": {"password": "head123", "role": "Local Head"},
        "junior_staff1": {"password": "staff123", "role": "Junior Staff"},
    }

if "cloud_tasks" not in st.session_state:
    st.session_state.cloud_tasks = [
        {
            "id": 1, 
            "task_name": "Income Tax Audit - Client X", 
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

# --- INTERNAL CONTROL 1: ROLE CREATION ENGINE (MASTER ONLY) ---
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
                else:
                    st.sidebar.error("System Error: ID exists.")
            else:
                st.sidebar.error("Input missing metrics.")

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

if user_role in ["Master User", "Local Head"]:
    c1, c2 = st.columns(2)
    c1.metric("Gross Active Deployments", len(df_tasks))
    c2.metric("System Managed Operational Identities", len(st.session_state.cloud_users))
    
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

# Deployment Logic Framework (Master and Local Head Only)
if user_role in ["Master User", "Local Head"]:
    with st.expander("➕ Authorize & Deploy a New Allocation Assignment"):
        t_name = st.text_input("Assignment Title / Client Name")
        all_juniors = [u for u, data in st.session_state.cloud_users.items() if data["role"] == "Junior Staff"]
        t_alloc = st.selectbox("Assign Primary Accountability To", all_juniors if all_juniors else ["No Resources Registered"])
        t_due = st.date_input("Target Legal/Statutory Maturity Due Date", min_value=today)
        t_status = st.selectbox("System Prioritization Level Status", ["In Progress", "Urgent"])
        t_desc = st.text_area("Initial Operational Scope Description Data")
        
        if st.button("Commit Allocation to Log"):
            if t_name and t_alloc != "No Resources Registered":
                new_id = max([t["id"] for t in st.session_state.cloud_tasks]) + 1 if st.session_state.cloud_tasks else 1
                st.session_state.cloud_tasks.append({
                    "id": new_id, "task_name": t_name, "allocated_to": t_alloc,
                    "allocation_date": today, "due_date": t_due, "status": t_status, "description": t_desc
                })
                st.success("Allocation updated!")
                st.rerun()

# Processing Log Updates Matrix
if st.session_state.cloud_tasks:
    with st.expander("📝 Process Modification Audits & Track Updates"):
        if user_role in ["Master User", "Local Head"]:
            eligible_options = {f"ID {t['id']}: {t['task_name']} (Responsible: {t['allocated_to']})": t for t in st.session_state.cloud_tasks}
        else:
            eligible_options = {f"ID {t['id']}: {t['task_name']}": t for t in st.session_state.cloud_tasks if t['allocated_to'] == current_user}
            
        if eligible_options:
            selected_node = st.selectbox("Select Target Registry Object to Modify", list(eligible_options.keys()))
            target_object = eligible_options[selected_node]
            idx_map = next(i for i, t in enumerate(st.session_state.cloud_tasks) if t["id"] == target_object["id"])
            
            # Master User & Local Head configuration changes
            if user_role in ["Master User", "Local Head"]:
                m_name = st.text_input("Modify Operational Title Description", value=target_object["task_name"])
                all_juniors = [u for u, data in st.session_state.cloud_users.items() if data["role"] == "Junior Staff"]
                m_alloc = st.selectbox("Re-allocate Core Responsibility Node", all_juniors, index=all_juniors.index(target_object["allocated_to"]) if target_object["allocated_to"] in all_juniors else 0)
                m_due = st.date_input("Alter Allocation Target Timeline Due Date", value=target_object["due_date"])
                m_status = st.selectbox("Update State Vector Flag", ["In Progress", "Urgent", "Completed"])
                m_desc = st.text_area("Audit Log Tracking Block Description Area", value=target_object["description"])
                
                if st.button("Publish Modifications"):
                    st.session_state.cloud_tasks[idx_map].update({
                        "task_name": m_name, "allocated_to": m_alloc,
                        "due_date": m_due, "status": m_status, "description": m_desc
                    })
                    st.success("Changes saved successfully.")
                    st.rerun()

            # Junior Staff: Description update access only
            elif user_role == "Junior Staff":
                st.markdown(f"**Task Classification:** {target_object['task_name']}")
                m_desc = st.text_area("Update Stage Description (Description Progress Box Only)", value=target_object["description"])
                
                if st.button("Publish Log Progress Update"):
                    st.session_state.cloud_tasks[idx_map]["description"] = m_desc
                    st.success("Audit narrative progress updated.")
                    st.rerun()
      
