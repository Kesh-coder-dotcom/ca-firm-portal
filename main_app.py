"""
CA FIRM TASK DASHBOARD
Single file - paste entirely into main_app.py
"""

from __future__ import annotations
import os
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from supabase import create_client, Client

# SUPABASE CLIENT

_supabase_client = None

def get_client():
    global _supabase_client
    if _supabase_client is None:
        try:
            url = st.secrets["SUPABASE_URL"]
            key = st.secrets["SUPABASE_KEY"]
        except Exception:
            url = os.environ.get("SUPABASE_URL", "")
            key = os.environ.get("SUPABASE_KEY", "")
        if not url or not key:
            st.error("SUPABASE_URL and SUPABASE_KEY are not set.")
            st.stop()
        _supabase_client = create_client(url, key)
    return _supabase_client

# AUTH

def login(email, password):
    sb = get_client()
    try:
        resp = sb.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
    except Exception as e:
        st.error("Login error: " + str(e))
        return False
    if resp.user is None:
        st.error("Invalid credentials.")
        return False
    profile = (
        sb.table("users")
        .select("*")
        .eq("id", resp.user.id)
        .single()
        .execute()
    )
    if not profile.data:
        st.error("User profile not found. Contact your administrator.")
        return False
    if not profile.data.get("is_active", True):
        st.error("Your account has been deactivated.")
        return False
    st.session_state["auth_user"] = resp.user
    st.session_state["profile"] = profile.data
    st.session_state["token"] = resp.session.access_token
    return True


def logout():
    get_client().auth.sign_out()
    for key in ["auth_user", "profile", "token"]:
        st.session_state.pop(key, None)
    st.rerun()


def current_user():
    return st.session_state.get("profile")


def require_login():
    if not current_user():
        st.warning("Please log in to access this page.")
        st.stop()


def has_role(*roles):
    u = current_user()
    return bool(u and u.get("role") in roles)

# DATABASE

def get_all_users():
    return (
        get_client()
        .table("users")
        .select("*")
        .order("full_name")
        .execute()
        .data or []
    )


def get_users_by_role(role):
    return (
        get_client()
        .table("users")
        .select("*")
        .eq("role", role)
        .eq("is_active", True)
        .order("full_name")
        .execute()
        .data or []
    )


def create_user_profile(uid, email, full_name, role):
    actor = current_user()
    row = {
        "id": uid,
        "email": email,
        "full_name": full_name,
        "role": role,
        "created_by": actor["id"] if actor else None,
    }
    resp = get_client().table("users").insert(row).execute()
    _audit("user_created", "user", uid, {"email": email, "role": role})
    return resp.data[0] if resp.data else None


def update_user(uid, **fields):
    get_client().table("users").update(fields).eq("id", uid).execute()
    _audit("user_updated", "user", uid, fields)
    return True


def deactivate_user(uid):
    get_client().table("users").update(
        {"is_active": False}
    ).eq("id", uid).execute()
    _audit("user_deactivated", "user", uid, {})
    return True


def get_tasks(filters=None):
    cols = (
        "id, title, description, status, priority, category,"
        "due_date, created_at, updated_at,"
        "assigned_hod, assigned_staff, created_by"
    )
    q = (
        get_client()
        .table("tasks")
        .select(cols)
        .order("created_at", desc=True)
    )
    if filters:
        if filters.get("status"):
            q = q.eq("status", filters["status"])
        if filters.get("priority"):
            q = q.eq("priority", filters["priority"])
        if filters.get("category"):
            q = q.eq("category", filters["category"])
        if filters.get("assigned_hod"):
            q = q.eq("assigned_hod", filters["assigned_hod"])
        if filters.get("assigned_staff"):
            q = q.eq("assigned_staff", filters["assigned_staff"])
        if filters.get("due_date_from"):
            q = q.gte("due_date", str(filters["due_date_from"]))
        if filters.get("due_date_to"):
            q = q.lte("due_date", str(filters["due_date_to"]))
    rows = q.execute().data or []
    users = {u["id"]: u for u in get_all_users()}
    for r in rows:
        r["hod_name"] = (
            users.get(r["assigned_hod"], {}).get("full_name", "-")
        )
        r["staff_name"] = (
            users.get(r["assigned_staff"], {}).get("full_name", "-")
        )
        r["creator_name"] = (
            users.get(r["created_by"], {}).get("full_name", "-")
        )
    return rows


def create_task(data):
    actor = current_user()
    data["created_by"] = actor["id"] if actor else None
    resp = get_client().table("tasks").insert(data).execute()
    if resp.data:
        _audit("task_created", "task", resp.data[0]["id"], data)
        return resp.data[0]
    return None


def update_task(task_id, **fields):
    get_client().table("tasks").update(fields).eq("id", task_id).execute()
    _audit("task_updated", "task", task_id, fields)
    return True


def delete_task(task_id):
    get_client().table("tasks").delete().eq("id", task_id).execute()
    _audit("task_deleted", "task", task_id, {})
    return True


def get_comments(task_id):
    rows = (
        get_client()
        .table("task_comments")
        .select("*")
        .eq("task_id", task_id)
        .order("created_at")
        .execute()
        .data or []
    )
    users = {u["id"]: u for u in get_all_users()}
    for r in rows:
        r["author_name"] = (
            users.get(r["author_id"], {}).get("full_name", "Unknown")
        )
    return rows


def add_comment(task_id, content):
    actor = current_user()
    if not actor:
        return False
    get_client().table("task_comments").insert(
        {
            "task_id": task_id,
            "author_id": actor["id"],
            "content": content,
        }
    ).execute()
    return True


def _audit(action, target_type, target_id, details):
    actor = current_user()
    try:
        get_client().table("audit_log").insert(
            {
                "actor_id": actor["id"] if actor else None,
                "action": action,
                "target_type": target_type,
                "target_id": target_id,
                "details": details,
            }
        ).execute()
    except Exception:
        pass

# CONSTANTS

STATUSES = [
    "pending",
    "in_progress",
    "review",
    "completed",
    "on_hold",
]
PRIORITIES = ["low", "medium", "high", "urgent"]
CATEGORIES = [
    "Audit", "Tax", "GST", "MCA",
    "ROC", "Payroll", "Advisory", "Other",
]
STATUS_COLORS = {
    "pending": "#f59e0b",
    "in_progress": "#3b82f6",
    "review": "#8b5cf6",
    "completed": "#10b981",
    "on_hold": "#ef4444",
}
PRIORITY_COLORS = {
    "low": "#6ee7b7",
    "medium": "#fcd34d",
    "high": "#fb923c",
    "urgent": "#f87171",
}

# UI COMPONENTS

def render_filters(show_hod=True, show_staff=True):
    hods = get_users_by_role("hod")
    staff = get_users_by_role("staff")
    cols = st.columns([2, 2, 2, 2, 2, 2, 2])
    filters = {}
    with cols[0]:
        s = st.selectbox("Status", ["All"] + STATUSES, key="f_status")
        if s != "All":
            filters["status"] = s
    with cols[1]:
        p = st.selectbox(
            "Priority", ["All"] + PRIORITIES, key="f_priority"
        )
        if p != "All":
            filters["priority"] = p
    with cols[2]:
        c = st.selectbox(
            "Category", ["All"] + CATEGORIES, key="f_cat"
        )
        if c != "All":
            filters["category"] = c
    if show_hod:
        with cols[3]:
            hod_opts = {"All": None}
            for h in hods:
                hod_opts[h["full_name"]] = h["id"]
            hod_sel = st.selectbox(
                "HOD", list(hod_opts.keys()), key="f_hod"
            )
            if hod_opts[hod_sel]:
                filters["assigned_hod"] = hod_opts[hod_sel]
    if show_staff:
        with cols[4]:
            st_opts = {"All": None}
            for s in staff:
                st_opts[s["full_name"]] = s["id"]
            st_sel = st.selectbox(
                "Staff", list(st_opts.keys()), key="f_staff"
            )
            if st_opts[st_sel]:
                filters["assigned_staff"] = st_opts[st_sel]
    with cols[5]:
        df = st.date_input("Due From", value=None, key="f_df")
        if df:
            filters["due_date_from"] = df
    with cols[6]:
        dt = st.date_input("Due To", value=None, key="f_dt")
        if dt:
            filters["due_date_to"] = dt
    return filters


def render_task_card(task):
    sc = STATUS_COLORS.get(task["status"], "#888")
    pc = PRIORITY_COLORS.get(task["priority"], "#888")
    with st.expander(task["title"], expanded=False):
        status_label = task["status"].replace("_", " ").title()
        priority_label = task["priority"].upper()
        badge_html = (
            "<span style='background:" + sc + ";"
            "color:#fff;padding:2px 10px;"
            "border-radius:99px;font-size:0.75rem;"
            "margin-right:6px'>" + status_label + "</span>"
            "<span style='background:" + pc + ";"
            "color:#000;padding:2px 10px;"
            "border-radius:99px;font-size:0.75rem'>"
            + priority_label + "</span>"
        )
        st.markdown(badge_html, unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("HOD", task.get("hod_name", "-"))
        c2.metric("Staff", task.get("staff_name", "-"))
        c3.metric("Due Date", str(task.get("due_date") or "-"))
        cat = str(task.get("category", "-"))
        creator = str(task.get("creator_name", "-"))
        st.markdown("**Category:** " + cat + " | **Created by:** " + creator)
        if task.get("description"):
            st.markdown("---")
            st.markdown("**Task Description:**")
            st.write(task["description"])
        st.markdown("---")
        render_inline_edit(task)
        st.markdown("---")
        render_comments(task["id"])


def render_inline_edit(task):
    role = current_user().get("role", "")
    uid = current_user().get("id", "")
    can_edit_core = (role == "master")
    can_edit_staff = (
        role == "master"
        or (role == "hod" and task.get("assigned_hod") == uid)
    )
    can_edit_status = (
        can_edit_staff
        or (role == "staff" and task.get("assigned_staff") == uid)
    )
    if not (can_edit_core or can_edit_staff or can_edit_status):
        return

    with st.form(key="edit_" + task["id"]):
        st.markdown("##### Edit Task")
        cols = st.columns(3)
        cur_status_idx = (
            STATUSES.index(task["status"])
            if task["status"] in STATUSES else 0
        )
        new_status = cols[0].selectbox(
            "Status",
            STATUSES,
            index=cur_status_idx,
            disabled=not can_edit_status,
        )
        staff_list = get_users_by_role("staff")
        staff_names = [s["full_name"] for s in staff_list]
        staff_ids = [s["id"] for s in staff_list]
        cur_s = 0
        if task.get("assigned_staff") in staff_ids:
            cur_s = staff_ids.index(task["assigned_staff"])
        new_staff_name = cols[1].selectbox(
            "Staff",
            staff_names if staff_names else ["-"],
            index=cur_s,
            disabled=not can_edit_staff,
        )
        new_staff_id = None
        if staff_names and new_staff_name in staff_names:
            new_staff_id = staff_ids[staff_names.index(new_staff_name)]

        if can_edit_core:
            hod_list = get_users_by_role("hod")
            hod_names = [h["full_name"] for h in hod_list]
            hod_ids = [h["id"] for h in hod_list]
            cur_h = 0
            if task.get("assigned_hod") in hod_ids:
                cur_h = hod_ids.index(task["assigned_hod"])
            new_hod_name = cols[2].selectbox(
                "HOD",
                hod_names if hod_names else ["-"],
                index=cur_h,
            )
            new_hod_id = None
            if hod_names and new_hod_name in hod_names:
                new_hod_id = hod_ids[hod_names.index(new_hod_name)]
        else:
            new_hod_id = task.get("assigned_hod")

        if can_edit_core:
            new_title = st.text_input("Title", value=task["title"])
            col_p, col_c = st.columns(2)
            pri_idx = (
                PRIORITIES.index(task["priority"])
                if task["priority"] in PRIORITIES else 1
            )
            new_priority = col_p.selectbox(
                "Priority", PRIORITIES, index=pri_idx
            )
            cat_idx = (
                CATEGORIES.index(task["category"])
                if task.get("category") in CATEGORIES else 0
            )
            new_category = col_c.selectbox(
                "Category", CATEGORIES, index=cat_idx
            )
            due_val = None
            if task.get("due_date"):
                try:
                    due_val = date.fromisoformat(task["due_date"])
                except Exception:
                    due_val = None
            new_due = st.date_input("Due Date", value=due_val)
            new_desc = st.text_area(
                "Description", value=task.get("description") or ""
            )
        else:
            new_title = task["title"]
            new_priority = task["priority"]
            new_category = task.get("category")
            new_due = task.get("due_date")
            new_desc = task.get("description")

        if st.form_submit_button("Save Changes", use_container_width=True):
            update_task(
                task["id"],
                status=new_status,
                assigned_hod=new_hod_id,
                assigned_staff=new_staff_id,
                title=new_title,
                priority=new_priority,
                category=new_category,
                due_date=str(new_due) if new_due else None,
                description=new_desc,
            )
            st.success("Task updated!")
            st.rerun()

    if can_edit_core:
        if st.button("Delete Task", key="del_" + task["id"]):
            delete_task(task["id"])
            st.warning("Task deleted.")
            st.rerun()


def render_comments(task_id):
    st.markdown("##### Discussion / Comments")
    comments = get_comments(task_id)
    if comments:
        for c in comments:
            ts = c["created_at"][:16].replace("T", " ")
            author = c["author_name"]
            content = c["content"]
            box = (
                "<div style='background:#1e293b;"
                "border-radius:8px;padding:8px 14px;"
                "margin-bottom:6px;"
                "border-left:3px solid #0ea5e9'>"
                "<small style='color:#94a3b8'>"
                "<b>" + author + "</b> - " + ts + "</small>"
                "<p style='margin:4px 0 0;color:#e2e8f0'>"
                + content + "</p></div>"
            )
            st.markdown(box, unsafe_allow_html=True)
    else:
        st.caption("No comments yet.")
    with st.form(key="comment_" + task_id):
        msg = st.text_area(
            "Add comment",
            height=75,
            label_visibility="collapsed",
            placeholder="Type your update or note here...",
        )
        if st.form_submit_button("Send"):
            if msg.strip():
                add_comment(task_id, msg.strip())
                st.rerun()

# PAGES

def page_dashboard():
    require_login()
    user = current_user()
    role = user["role"]
    st.markdown("## Task Dashboard")
    base = {}
    if role == "hod":
        base["assigned_hod"] = user["id"]
    elif role == "staff":
        base["assigned_staff"] = user["id"]
    with st.expander("Filters", expanded=True):
        extra = render_filters(
            show_hod=has_role("master"),
            show_staff=has_role("master", "hod"),
        )
    tasks = get_tasks({**base, **extra})
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total", len(tasks))
    k2.metric("Pending", sum(
        1 for t in tasks if t["status"] == "pending"
    ))
    k3.metric("In Progress", sum(
        1 for t in tasks if t["status"] == "in_progress"
    ))
    k4.metric("Completed", sum(
        1 for t in tasks if t["status"] == "completed"
    ))
    k5.metric("Urgent", sum(
        1 for t in tasks if t["priority"] == "urgent"
    ))
    st.divider()
    if not tasks:
        st.info("No tasks match the selected filters.")
        return
    df = pd.DataFrame(tasks)
    col1, col2 = st.columns(2)
    with col1:
        s_df = df.groupby("status").size().reset_index(name="count")
        fig = px.pie(
            s_df,
            values="count",
            names="status",
            title="Tasks by Status",
            color="status",
            color_discrete_map=STATUS_COLORS,
            hole=0.5,
        )
        fig.update_layout(
            paper_bgcolor="#0f172a",
            plot_bgcolor="#0f172a",
            font_color="#e2e8f0",
            legend_font_color="#e2e8f0",
        )
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        c_df = df.groupby("category").size().reset_index(name="count")
        fig2 = px.bar(
            c_df,
            x="category",
            y="count",
            title="Tasks by Category",
            color="count",
            color_continuous_scale="Blues",
        )
        fig2.update_layout(
            paper_bgcolor="#0f172a",
            plot_bgcolor="#0f172a",
            font_color="#e2e8f0",
            showlegend=False,
        )
        st.plotly_chart(fig2, use_container_width=True)
    st.markdown("### Task List")
    for task in tasks:
        render_task_card(task)


def page_my_tasks():
    require_login()
    user = current_user()
    role = user["role"]
    st.markdown("## My Tasks")
    base = {}
    if role == "hod":
        base["assigned_hod"] = user["id"]
    elif role == "staff":
        base["assigned_staff"] = user["id"]
    with st.expander("Filters", expanded=False):
        extra = render_filters(
            show_hod=False,
            show_staff=(role == "master"),
        )
    tasks = get_tasks({**base, **extra})
    if not tasks:
        st.info("No tasks found for your account.")
        return
    st.caption(str(len(tasks)) + " task(s) found")
    for task in tasks:
        render_task_card(task)


def page_new_task():
    require_login()
    if not has_role("master"):
        st.error("Access denied. Only Master users can create tasks.")
        return
    st.markdown("## Create New Task")
    hods = get_users_by_role("hod")
    staff = get_users_by_role("staff")
    if not hods:
        st.warning("No HOD users found. Add HOD users first.")
    if not staff:
        st.warning("No Staff users found. Add Staff users first.")
    with st.form("new_task_form", clear_on_submit=True):
        title = st.text_input(
            "Task Title",
            placeholder="e.g. Q4 GST Return - Client ABC",
        )
        c1, c2, c3 = st.columns(3)
        priority = c1.selectbox("Priority", PRIORITIES, index=1)
        category = c2.selectbox("Category", CATEGORIES)
        due_date = c3.date_input(
            "Due Date", value=None, min_value=date.today()
        )
        c4, c5 = st.columns(2)
        hod_names = [h["full_name"] for h in hods]
        hod_ids = [h["id"] for h in hods]
        st_names = [s["full_name"] for s in staff]
        st_ids = [s["id"] for s in staff]
        sel_hod = c4.selectbox(
            "Assign HOD", hod_names if hod_names else ["-"]
        )
        sel_staff = c5.selectbox(
            "Assign Staff", st_names if st_names else ["-
