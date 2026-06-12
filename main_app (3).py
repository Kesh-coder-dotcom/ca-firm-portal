"""
CA FIRM TASK DASHBOARD - Single file main_app.py
Features: Tasks, Real-time Messaging, File Attachments
HOD can create tasks assigned to themselves.
"""

from __future__ import annotations
import os
import base64
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from supabase import create_client

_sb = None

def get_client():
    global _sb
    if _sb is None:
        try:
            url = st.secrets["SUPABASE_URL"]
            key = st.secrets["SUPABASE_KEY"]
        except Exception:
            url = os.environ.get("SUPABASE_URL", "")
            key = os.environ.get("SUPABASE_KEY", "")
        if not url or not key:
            st.error("SUPABASE_URL and SUPABASE_KEY are not set.")
            st.stop()
        _sb = create_client(url, key)
    return _sb

# ── AUTH ─────────────────────────────────────────────────────────

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
    for k in ["auth_user", "profile", "token"]:
        st.session_state.pop(k, None)
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

# ── USERS ────────────────────────────────────────────────────────

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

# ── TASKS ────────────────────────────────────────────────────────

def get_tasks(filters=None):
    cols = (
        "id, title, description, status, priority,"
        "category, due_date, created_at, updated_at,"
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
    get_client().table("tasks").update(fields).eq(
        "id", task_id
    ).execute()
    _audit("task_updated", "task", task_id, fields)
    return True


def delete_task(task_id):
    get_client().table("tasks").delete().eq("id", task_id).execute()
    _audit("task_deleted", "task", task_id, {})
    return True

# ── COMMENTS ─────────────────────────────────────────────────────

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

# ── MESSAGES ─────────────────────────────────────────────────────

def get_messages(since_id=None, limit=100):
    q = (
        get_client()
        .table("messages")
        .select("id, sender_id, content, created_at")
        .order("created_at", desc=False)
        .limit(limit)
    )
    if since_id:
        q = q.gt("id", since_id)
    rows = q.execute().data or []
    users = {u["id"]: u for u in get_all_users()}
    for r in rows:
        r["sender_name"] = (
            users.get(r["sender_id"], {}).get("full_name", "Unknown")
        )
        r["sender_role"] = (
            users.get(r["sender_id"], {}).get("role", "")
        )
    return rows


def send_message(content):
    actor = current_user()
    if not actor:
        return False
    get_client().table("messages").insert(
        {"sender_id": actor["id"], "content": content}
    ).execute()
    return True

# ── ATTACHMENTS ──────────────────────────────────────────────────

MAX_FILE_BYTES = 1 * 1024 * 1024


def upload_attachment(task_id, uploaded_file):
    actor = current_user()
    if not actor:
        return False, "Not logged in."
    if uploaded_file.size > MAX_FILE_BYTES:
        return False, "File exceeds 1 MB limit."
    raw = uploaded_file.read()
    b64 = base64.b64encode(raw).decode("utf-8")
    row = {
        "task_id": task_id,
        "uploader_id": actor["id"],
        "file_name": uploaded_file.name,
        "file_type": uploaded_file.type or "application/octet-stream",
        "file_size": uploaded_file.size,
        "file_data": b64,
    }
    try:
        get_client().table("task_attachments").insert(row).execute()
        _audit(
            "file_uploaded", "task", task_id,
            {"file_name": uploaded_file.name},
        )
        return True, "File uploaded successfully."
    except Exception as e:
        return False, "Upload failed: " + str(e)


def get_attachments(task_id):
    rows = (
        get_client()
        .table("task_attachments")
        .select(
            "id, task_id, uploader_id, file_name,"
            "file_type, file_size, file_data, created_at"
        )
        .eq("task_id", task_id)
        .order("created_at")
        .execute()
        .data or []
    )
    users = {u["id"]: u for u in get_all_users()}
    for r in rows:
        r["uploader_name"] = (
            users.get(r["uploader_id"], {}).get("full_name", "Unknown")
        )
    return rows


def delete_attachment(att_id):
    get_client().table("task_attachments").delete().eq(
        "id", att_id
    ).execute()

# ── AUDIT ────────────────────────────────────────────────────────

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

# ── CONSTANTS ────────────────────────────────────────────────────

STATUSES = [
    "pending", "in_progress", "review", "completed", "on_hold"
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
ROLE_COLORS = {
    "master": "#f59e0b",
    "hod": "#3b82f6",
    "staff": "#10b981",
}

# ── SHARED UI ────────────────────────────────────────────────────

def render_filters(show_hod=True, show_staff=True):
    hods = get_users_by_role("hod")
    staff = get_users_by_role("staff")
    cols = st.columns([2, 2, 2, 2, 2, 2, 2])
    filters = {}
    with cols[0]:
        s = st.selectbox(
            "Status", ["All"] + STATUSES, key="f_status"
        )
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


def render_attachments(task_id):
    st.markdown("##### Attachments")
    atts = get_attachments(task_id)
    if atts:
        for att in atts:
            ts = att["created_at"][:16].replace("T", " ")
            kb = round(att["file_size"] / 1024, 1)
            ca, cb = st.columns([4, 1])
            with ca:
                st.markdown(
                    "**" + att["file_name"] + "** | "
                    + str(kb) + " KB | "
                    + att["uploader_name"] + " | " + ts
                )
                if att.get("file_data"):
                    try:
                        raw = base64.b64decode(att["file_data"])
                        st.download_button(
                            label="Download",
                            data=raw,
                            file_name=att["file_name"],
                            mime=att["file_type"],
                            key="dl_" + att["id"],
                        )
                    except Exception:
                        st.caption("Cannot preview.")
            with cb:
                me = current_user()
                can_del = (
                    me.get("role") == "master"
                    or me.get("id") == att["uploader_id"]
                )
                if can_del:
                    if st.button("Remove", key="rm_" + att["id"]):
                        delete_attachment(att["id"])
                        st.rerun()
    else:
        st.caption("No files attached yet.")
    with st.form(key="upload_" + task_id):
        st.markdown("**Attach a File (max 1 MB)**")
        upl = st.file_uploader(
            "Choose file",
            key="fu_" + task_id,
            label_visibility="collapsed",
        )
        if st.form_submit_button("Upload File"):
            if upl is None:
                st.warning("Please select a file first.")
            else:
                ok, msg = upload_attachment(task_id, upl)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)


def render_task_card(task):
    sc = STATUS_COLORS.get(task["status"], "#888")
    pc = PRIORITY_COLORS.get(task["priority"], "#888")
    with st.expander(task["title"], expanded=False):
        slabel = task["status"].replace("_", " ").title()
        plabel = task["priority"].upper()
        html = (
            "<span style='background:" + sc + ";color:#fff;"
            "padding:2px 10px;border-radius:99px;"
            "font-size:0.75rem;margin-right:6px'>"
            + slabel + "</span>"
            "<span style='background:" + pc + ";color:#000;"
            "padding:2px 10px;border-radius:99px;"
            "font-size:0.75rem'>" + plabel + "</span>"
        )
        st.markdown(html, unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("HOD", task.get("hod_name", "-"))
        c2.metric("Staff", task.get("staff_name", "-"))
        c3.metric("Due Date", str(task.get("due_date") or "-"))
        cat = str(task.get("category", "-"))
        creator = str(task.get("creator_name", "-"))
        st.markdown(
            "**Category:** " + cat
            + " | **Created by:** " + creator
        )
        if task.get("description"):
            st.markdown("---")
            st.markdown("**Task Description:**")
            st.write(task["description"])
        st.markdown("---")
        render_inline_edit(task)
        st.markdown("---")
        render_attachments(task["id"])
        st.markdown("---")
        render_comments(task["id"])


def render_inline_edit(task):
    role = current_user().get("role", "")
    uid = current_user().get("id", "")
    can_core = (role == "master")
    can_staff = (
        role == "master"
        or (role == "hod" and task.get("assigned_hod") == uid)
    )
    can_status = (
        can_staff
        or (role == "staff" and task.get("assigned_staff") == uid)
    )
    if not (can_core or can_staff or can_status):
        return
    with st.form(key="edit_" + task["id"]):
        st.markdown("##### Edit Task")
        cols = st.columns(3)
        cur_si = (
            STATUSES.index(task["status"])
            if task["status"] in STATUSES else 0
        )
        new_status = cols[0].selectbox(
            "Status", STATUSES, index=cur_si,
            disabled=not can_status,
        )
        sl = get_users_by_role("staff")
        snames = [x["full_name"] for x in sl]
        sids = [x["id"] for x in sl]
        cur_s = 0
        if task.get("assigned_staff") in sids:
            cur_s = sids.index(task["assigned_staff"])
        new_sname = cols[1].selectbox(
            "Staff",
            snames if snames else ["-"],
            index=cur_s,
            disabled=not can_staff,
        )
        new_sid = None
        if snames and new_sname in snames:
            new_sid = sids[snames.index(new_sname)]
        if can_core:
            hl = get_users_by_role("hod")
            hnames = [x["full_name"] for x in hl]
            hids = [x["id"] for x in hl]
            cur_h = 0
            if task.get("assigned_hod") in hids:
                cur_h = hids.index(task["assigned_hod"])
            new_hname = cols[2].selectbox(
                "HOD",
                hnames if hnames else ["-"],
                index=cur_h,
            )
            new_hid = None
            if hnames and new_hname in hnames:
                new_hid = hids[hnames.index(new_hname)]
        else:
            new_hid = task.get("assigned_hod")
        if can_core:
            new_title = st.text_input("Title", value=task["title"])
            cp, cc = st.columns(2)
            pri_i = (
                PRIORITIES.index(task["priority"])
                if task["priority"] in PRIORITIES else 1
            )
            new_priority = cp.selectbox(
                "Priority", PRIORITIES, index=pri_i
            )
            cat_i = (
                CATEGORIES.index(task["category"])
                if task.get("category") in CATEGORIES else 0
            )
            new_category = cc.selectbox(
                "Category", CATEGORIES, index=cat_i
            )
            due_val = None
            if task.get("due_date"):
                try:
                    due_val = date.fromisoformat(task["due_date"])
                except Exception:
                    due_val = None
            new_due = st.date_input("Due Date", value=due_val)
            new_desc = st.text_area(
                "Description",
                value=task.get("description") or "",
            )
        else:
            new_title = task["title"]
            new_priority = task["priority"]
            new_category = task.get("category")
            new_due = task.get("due_date")
            new_desc = task.get("description")
        if st.form_submit_button(
            "Save Changes", use_container_width=True
        ):
            update_task(
                task["id"],
                status=new_status,
                assigned_hod=new_hid,
                assigned_staff=new_sid,
                title=new_title,
                priority=new_priority,
                category=new_category,
                due_date=str(new_due) if new_due else None,
                description=new_desc,
            )
            st.success("Task updated!")
            st.rerun()
    if can_core:
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

# ── PAGE: DASHBOARD ──────────────────────────────────────────────

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
            s_df, values="count", names="status",
            title="Tasks by Status",
            color="status",
            color_discrete_map=STATUS_COLORS,
            hole=0.5,
        )
        fig.update_layout(
            paper_bgcolor="#0f172a", plot_bgcolor="#0f172a",
            font_color="#e2e8f0", legend_font_color="#e2e8f0",
        )
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        c_df = (
            df.groupby("category").size().reset_index(name="count")
        )
        fig2 = px.bar(
            c_df, x="category", y="count",
            title="Tasks by Category",
            color="count",
            color_continuous_scale="Blues",
        )
        fig2.update_layout(
            paper_bgcolor="#0f172a", plot_bgcolor="#0f172a",
            font_color="#e2e8f0", showlegend=False,
        )
        st.plotly_chart(fig2, use_container_width=True)
    st.markdown("### Task List")
    for task in tasks:
        render_task_card(task)

# ── PAGE: MY TASKS ───────────────────────────────────────────────

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

# ── PAGE: NEW TASK (master + HOD) ────────────────────────────────

def page_new_task():
    require_login()
    user = current_user()
    role = user["role"]

    if role not in ("master", "hod"):
        st.error("Access denied.")
        return

    st.markdown("## Create New Task")
    staff_list = get_users_by_role("staff")

    if role == "master":
        hods = get_users_by_role("hod")
        if not hods:
            st.warning("No HOD users found. Add HOD users first.")
        if not staff_list:
            st.warning("No Staff users found. Add Staff users first.")
    else:
        # HOD creates task — they are the HOD
        if not staff_list:
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

        if role == "master":
            hods = get_users_by_role("hod")
            hod_names = [h["full_name"] for h in hods]
            hod_ids = [h["id"] for h in hods]
            c4, c5 = st.columns(2)
            sel_hod = c4.selectbox(
                "Assign HOD",
                hod_names if hod_names else ["-"],
            )
            st_names = [s["full_name"] for s in staff_list]
            st_ids = [s["id"] for s in staff_list]
            sel_staff = c5.selectbox(
                "Assign Staff",
                st_names if st_names else ["-"],
            )
        else:
            # HOD: they are the HOD, only pick staff
            hod_names = [user["full_name"]]
            hod_ids = [user["id"]]
            sel_hod = user["full_name"]
            st.info(
                "You are creating this task as HOD: "
                + user["full_name"]
            )
            st_names = [s["full_name"] for s in staff_list]
            st_ids = [s["id"] for s in staff_list]
            sel_staff = st.selectbox(
                "Assign Staff",
                st_names if st_names else ["-"],
            )

        description = st.text_area(
            "Task Description and Notes",
            height=160,
            placeholder="Client name, documents, instructions...",
        )

        if st.form_submit_button(
            "Create Task", use_container_width=True
        ):
            if not title.strip():
                st.error("Task title is required.")
            elif not st_ids:
                st.error("Add at least one Staff member first.")
            elif not hod_ids:
                st.error("No HOD available.")
            else:
                hod_id = hod_ids[hod_names.index(sel_hod)]
                staff_id = st_ids[st_names.index(sel_staff)]
                result = create_task({
                    "title": title.strip(),
                    "priority": priority,
                    "category": category,
                    "due_date": str(due_date) if due_date else None,
                    "assigned_hod": hod_id,
                    "assigned_staff": staff_id,
                    "description": description.strip() or None,
                    "status": "pending",
                })
                if result:
                    st.success("Task created successfully!")
                else:
                    st.error("Failed. Check your Supabase connection.")

# ── PAGE: MESSAGING (real-time poll) ────────────────────────────

def page_messaging():
    require_login()
    user = current_user()
    st.markdown("## Team Messaging")
    st.caption(
        "Group chat for all team members. "
        "Click Refresh to load new messages."
    )

    # Init session state
    if "messages" not in st.session_state:
        st.session_state["messages"] = get_messages(limit=100)
    if "last_msg_id" not in st.session_state:
        msgs = st.session_state["messages"]
        st.session_state["last_msg_id"] = (
            msgs[-1]["id"] if msgs else None
        )

    # Auto-refresh every 4 seconds using meta refresh trick
    st.markdown(
        "<meta http-equiv='refresh' content='4'>",
        unsafe_allow_html=True,
    )

    # Fetch any new messages since last known id
    last_id = st.session_state.get("last_msg_id")
    if last_id:
        new_msgs = get_messages(since_id=last_id, limit=50)
        if new_msgs:
            st.session_state["messages"].extend(new_msgs)
            st.session_state["last_msg_id"] = new_msgs[-1]["id"]
    else:
        st.session_state["messages"] = get_messages(limit=100)
        msgs = st.session_state["messages"]
        if msgs:
            st.session_state["last_msg_id"] = msgs[-1]["id"]

    messages = st.session_state["messages"]
    me = user["id"]

    # Build chat window
    chat = (
        "<div style='height:460px;overflow-y:auto;"
        "background:#0f172a;border:1px solid #334155;"
        "border-radius:12px;padding:16px;"
        "display:flex;flex-direction:column;gap:8px'>"
    )
    for msg in messages:
        is_me = (msg["sender_id"] == me)
        rc = ROLE_COLORS.get(msg.get("sender_role", ""), "#888")
        ts = msg["created_at"][:16].replace("T", " ")
        name = msg["sender_name"]
        content = msg["content"]
        if is_me:
            bubble = (
                "<div style='display:flex;"
                "justify-content:flex-end;margin-bottom:4px'>"
                "<div style='max-width:70%;background:#0ea5e9;"
                "border-radius:12px 12px 2px 12px;"
                "padding:8px 12px'>"
                "<div style='font-size:0.7rem;color:#bae6fd;"
                "margin-bottom:2px'>" + ts + "</div>"
                "<div style='color:#fff'>" + content + "</div>"
                "</div></div>"
            )
        else:
            bubble = (
                "<div style='display:flex;"
                "justify-content:flex-start;margin-bottom:4px'>"
                "<div style='max-width:70%;background:#1e293b;"
                "border:1px solid #334155;"
                "border-radius:12px 12px 12px 2px;"
                "padding:8px 12px'>"
                "<div style='font-size:0.7rem;margin-bottom:2px'>"
                "<b style='color:" + rc + "'>" + name + "</b>"
                "<span style='color:#64748b'> - " + ts + "</span>"
                "</div>"
                "<div style='color:#e2e8f0'>" + content + "</div>"
                "</div></div>"
            )
        chat += bubble
    chat += "</div>"
    st.markdown(chat, unsafe_allow_html=True)

    st.markdown("")
    with st.form("msg_form", clear_on_submit=True):
        ci, cb = st.columns([5, 1])
        new_msg = ci.text_input(
            "msg",
            placeholder="Type a message...",
            label_visibility="collapsed",
        )
        if cb.form_submit_button("Send", use_container_width=True):
            if new_msg.strip():
                send_message(new_msg.strip())
                # Reload all messages after sending
                st.session_state["messages"] = get_messages(
                    limit=100
                )
                msgs = st.session_state["messages"]
                if msgs:
                    st.session_state["last_msg_id"] = msgs[-1]["id"]
                st.rerun()

    if st.button("Refresh Messages"):
        last_id = st.session_state.get("last_msg_id")
        if last_id:
            new_msgs = get_messages(since_id=last_id, limit=50)
            if new_msgs:
                st.session_state["messages"].extend(new_msgs)
                st.session_state["last_msg_id"] = (
                    new_msgs[-1]["id"]
                )
        else:
            st.session_state["messages"] = get_messages(limit=100)
        st.rerun()

# ── PAGE: USERS ──────────────────────────────────────────────────

def page_users():
    require_login()
    if not has_role("master"):
        st.error("Access denied.")
        return
    st.markdown("## User Management")
    BADGE = {
        "master": ("#f59e0b"),
        "hod": ("#3b82f6"),
        "staff": ("#10b981"),
    }
    tab_list, tab_add = st.tabs(["All Users", "Add New User"])
    with tab_list:
        users = get_all_users()
        rf = st.radio(
            "Filter by role",
            ["All", "master", "hod", "staff"],
            horizontal=True,
        )
        filtered = (
            users if rf == "All"
            else [u for u in users if u["role"] == rf]
        )
        if not filtered:
            st.info("No users found.")
        for u in filtered:
            color = BADGE.get(u["role"], "#888")
            is_active = u.get("is_active", True)
            atxt = "Active" if is_active else "Inactive"
            acol = "#10b981" if is_active else "#ef4444"
            with st.expander(u["full_name"] + " - " + u["email"]):
                st.markdown(
                    "<b>Role:</b> "
                    "<span style='color:" + color + "'>"
                    + u["role"].upper() + "</span>"
                    "&nbsp;&nbsp;"
                    "<span style='color:" + acol + "'>- "
                    + atxt + "</span>",
                    unsafe_allow_html=True,
                )
                c1, c2, c3 = st.columns(3)
                new_role = c1.selectbox(
                    "Change Role",
                    ["master", "hod", "staff"],
                    index=["master", "hod", "staff"].index(
                        u["role"]
                    ),
                    key="role_" + u["id"],
                )
                if c2.button("Update Role", key="upd_" + u["id"]):
                    update_user(u["id"], role=new_role)
                    st.success("Role updated.")
                    st.rerun()
                me = current_user()
                if u["id"] != me["id"]:
                    if is_active:
                        if c3.button(
                            "Deactivate", key="deact_" + u["id"]
                        ):
                            deactivate_user(u["id"])
                            st.warning(
                                u["full_name"] + " deactivated."
                            )
                            st.rerun()
                    else:
                        if c3.button(
                            "Reactivate", key="react_" + u["id"]
                        ):
                            update_user(u["id"], is_active=True)
                            st.success(
                                u["full_name"] + " reactivated."
                            )
                            st.rerun()
    with tab_add:
        st.markdown("### Create New User")
        st.info(
            "Creates a Supabase Auth account and profile row. "
            "User can log in immediately."
        )
        with st.form("add_user_form", clear_on_submit=True):
            full_name = st.text_input("Full Name")
            email = st.text_input("Email Address")
            role = st.selectbox("Role", ["staff", "hod", "master"])
            temp_pass = st.text_input(
                "Temporary Password",
                type="password",
                help="User should change this on first login.",
            )
            if st.form_submit_button(
                "Create User", use_container_width=True
            ):
                if not all([
                    full_name.strip(),
                    email.strip(),
                    temp_pass.strip(),
                ]):
                    st.error("All fields are required.")
                else:
                    try:
                        ar = get_client().auth.admin.create_user(
                            {
                                "email": email.strip(),
                                "password": temp_pass.strip(),
                                "email_confirm": True,
                            }
                        )
                        create_user_profile(
                            ar.user.id,
                            email.strip(),
                            full_name.strip(),
                            role,
                        )
                        st.success(
                            "User " + full_name
                            + " created as " + role.upper() + "."
                        )
                    except Exception as e:
                        st.error("Error: " + str(e))

# ── PAGE: REPORTS ────────────────────────────────────────────────

def page_reports():
    require_login()
    if not has_role("master"):
        st.error("Access denied.")
        return
    st.markdown("## Reports and Analytics")
    tasks = get_tasks()
    if not tasks:
        st.info("No task data available yet.")
        return
    df = pd.DataFrame(tasks)
    df["due_date"] = pd.to_datetime(df["due_date"], errors="coerce")
    df["created_at"] = pd.to_datetime(
        df["created_at"], errors="coerce"
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Tasks", len(df))
    c2.metric("Completed", len(df[df["status"] == "completed"]))
    overdue = df[
        (df["due_date"] < pd.Timestamp.now())
        & (df["status"] != "completed")
    ]
    c3.metric("Overdue", len(overdue))
    hc = max(df["hod_name"].nunique(), 1)
    c4.metric("Avg per HOD", round(len(df) / hc, 1))
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        s_df = df.groupby("status").size().reset_index(name="count")
        fig = px.pie(
            s_df, values="count", names="status",
            title="Status Distribution",
            color="status",
            color_discrete_map=STATUS_COLORS,
            hole=0.45,
        )
        fig.update_layout(
            paper_bgcolor="#0f172a", plot_bgcolor="#0f172a",
            font_color="#e2e8f0",
        )
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        p_df = (
            df.groupby("priority").size().reset_index(name="count")
        )
        fig2 = px.bar(
            p_df, x="priority", y="count",
            title="Priority Breakdown",
            color="priority",
            color_discrete_map=PRIORITY_COLORS,
        )
        fig2.update_layout(
            paper_bgcolor="#0f172a", plot_bgcolor="#0f172a",
            font_color="#e2e8f0", showlegend=False,
        )
        st.plotly_chart(fig2, use_container_width=True)
    hod_df = (
        df.groupby("hod_name").size().reset_index(name="tasks")
    )
    fig3 = px.bar(
        hod_df.sort_values("tasks", ascending=False),
        x="hod_name", y="tasks",
        title="Task Load per HOD",
        color="tasks",
        color_continuous_scale="Blues",
    )
    fig3.update_layout(
        paper_bgcolor="#0f172a", plot_bgcolor="#0f172a",
        font_color="#e2e8f0",
    )
    st.plotly_chart(fig3, use_container_width=True)
    if df["created_at"].notna().any():
        tl = (
            df.set_index("created_at")
            .resample("W")["id"]
            .count()
            .reset_index()
            .rename(columns={
                "id": "tasks_created",
                "created_at": "week",
            })
        )
        fig4 = px.line(
            tl, x="week", y="tasks_created",
            title="Tasks Created Weekly",
            line_shape="spline", markers=True,
        )
        fig4.update_traces(line_color="#0ea5e9")
        fig4.update_layout(
            paper_bgcolor="#0f172a", plot_bgcolor="#0f172a",
            font_color="#e2e8f0",
        )
        st.plotly_chart(fig4, use_container_width=True)
    st.divider()
    st.markdown("### Full Task Data")
    scols = [
        "title", "status", "priority", "category",
        "hod_name", "staff_name", "due_date", "created_at",
    ]
    st.dataframe(
        df[[c for c in scols if c in df.columns]],
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        "Download CSV",
        df.to_csv(index=False).encode("utf-8"),
        "tasks_export.csv",
        "text/csv",
    )

# ── APP SHELL ────────────────────────────────────────────────────

st.set_page_config(
    page_title="CA Firm | Task Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
html, body, [class*="css"] {
    font-family: sans-serif;
    background-color: #0f172a !important;
    color: #e2e8f0 !important;
}
h1, h2, h3 { color: #f8fafc; }
section[data-testid="stSidebar"] {
    background: #1e293b !important;
    border-right: 1px solid #334155;
}
div[data-testid="stMetric"] {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 12px 16px;
}
.stButton > button {
    background: #0ea5e9;
    color: #fff;
    border: none;
    border-radius: 8px;
    font-weight: 600;
}
.stButton > button:hover { background: #0284c7; }
.streamlit-expanderHeader {
    background: #1e293b !important;
    border-radius: 8px !important;
    border: 1px solid #334155 !important;
    margin-bottom: 4px;
}
div[data-testid="stForm"] {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 16px;
}
.block-container { padding-top: 1.5rem; }
</style>
""",
    unsafe_allow_html=True,
)


def render_login():
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown(
            "<h1 style='text-align:center;margin-bottom:4px'>"
            "CA Task Dashboard</h1>"
            "<p style='text-align:center;color:#94a3b8;"
            "margin-bottom:2rem'>"
            "Chartered Accountants - Task Management</p>",
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            email = st.text_input(
                "Email", placeholder="you@firm.com"
            )
            password = st.text_input("Password", type="password")
            if st.form_submit_button(
                "Sign In", use_container_width=True
            ):
                with st.spinner("Authenticating..."):
                    if login(email, password):
                        st.rerun()


def render_sidebar(user):
    with st.sidebar:
        name = user["full_name"]
        role = user["role"]
        rc = ROLE_COLORS.get(role, "#888")
        st.markdown(
            "<div style='padding:12px 0 8px'>"
            "<b style='font-size:1.05rem'>" + name + "</b><br>"
            "<span style='color:" + rc
            + ";text-transform:capitalize'>"
            + role + "</span></div>",
            unsafe_allow_html=True,
        )
        st.divider()
        pages = {
            "Dashboard": "dashboard",
            "My Tasks": "my_tasks",
            "Team Messaging": "messaging",
        }
        if has_role("master", "hod"):
            pages["New Task"] = "new_task"
        if has_role("master"):
            pages["Manage Users"] = "users"
            pages["Reports"] = "reports"
        selected = st.radio(
            "Navigation",
            list(pages.keys()),
            label_visibility="collapsed",
        )
        st.divider()
        if st.button("Sign Out", use_container_width=True):
            logout()
    return pages[selected]


def main():
    user = current_user()
    if not user:
        render_login()
        return
    page = render_sidebar(user)
    page_map = {
        "dashboard": page_dashboard,
        "my_tasks": page_my_tasks,
        "new_task": page_new_task,
        "messaging": page_messaging,
        "users": page_users,
        "reports": page_reports,
    }
    page_map[page]()


main()
