import json
import os
from datetime import date, datetime, time

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

from employee_management import render_employee_management

load_dotenv()

API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://127.0.0.1:8000"
)

st.set_page_config(
    page_title="EMS | Employee Management",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------- SESSION STATE ----------------

if "token" not in st.session_state:
    st.session_state.token = None

if "user" not in st.session_state:
    st.session_state.user = None

if "permissions" not in st.session_state:
    st.session_state.permissions = None


# ---------------- API HELPERS ----------------

def api_request(method, endpoint, **kwargs):
    """Send authenticated requests to FastAPI."""

    headers = kwargs.pop("headers", {})
    return_response = kwargs.pop("return_response", False)
    handle_unauthorized = kwargs.pop("handle_unauthorized", True)

    if st.session_state.token:
        headers["Authorization"] = (
            f"Bearer {st.session_state.token}"
        )

    try:
        response = requests.request(
            method=method,
            url=f"{API_BASE_URL}{endpoint}",
            headers=headers,
            timeout=180,
            **kwargs,
        )

        if response.status_code == 401 and handle_unauthorized:
            st.session_state.token = None
            st.session_state.user = None
            st.session_state.permissions = []
            st.error("Session expired. Please log in again.")
            st.rerun()

        response.raise_for_status()

        if return_response:
            return response

        if response.status_code == 204:
            return None

        if not response.content:
            return None

        return response.json()

    except requests.exceptions.ConnectionError:
        st.error("Unable to connect to the FastAPI backend.")
    except requests.exceptions.Timeout:
        st.error("Request timed out. Please try again.")
    except requests.exceptions.HTTPError as exc:
        try:
            detail = exc.response.json().get(
                "detail", str(exc)
            )
        except Exception:
            detail = str(exc)

        st.error(f"API error: {detail}")

    return None


# ---------------- LOGIN PAGE ----------------

def login_page():
    st.title("🏢 Employee Management System")
    st.caption("Sign in to access your employee dashboard.")
    if st.session_state.get("auth_message"):
        st.success(st.session_state.pop("auth_message"))

    _, center, _ = st.columns([1, 1.2, 1])

    with center:
        with st.form("login_form"):
            email = st.text_input(
                "Email",
                placeholder="Enter your email",
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
            )

            submitted = st.form_submit_button(
                "Login",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            if not email or not password:
                st.warning("Please enter email and password.")
                return

            result = api_request(
                "POST",
                "/auth/login",
                json={
                    "email": email,
                    "password": password,
                },
            )

            if result and result.get("access_token"):
                st.session_state.token = result["access_token"]
                st.session_state.user = api_request("GET", "/auth/me") or {}
                st.session_state.permissions = (
                    api_request("GET", "/auth/me/permissions") or []
                )

                st.rerun()

    st.caption(
        "Password changes require signing in. If you cannot access your "
        "account, contact an administrator."
    )


def change_password_page():
    st.title("Change password")
    st.caption("Confirm your current password before choosing a new one.")

    with st.form("change_password_form"):
        current_password = st.text_input("Current password", type="password")
        new_password = st.text_input("New password", type="password")
        confirm_password = st.text_input("Confirm new password", type="password")
        submitted = st.form_submit_button(
            "Update password",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return
    if len(new_password) < 6:
        st.warning("Password must be at least 6 characters.")
        return
    if new_password != confirm_password:
        st.warning("Passwords do not match.")
        return

    result = api_request(
        "PUT",
        "/auth/change-password",
        json={
            "current_password": current_password,
            "new_password": new_password,
            "confirm_password": confirm_password,
        },
    )
    if result:
        st.session_state.token = None
        st.session_state.user = None
        st.session_state.permissions = []
        st.session_state.auth_message = (
            "Password updated. Please sign in with your new password."
        )
        st.rerun()


# ---------------- DASHBOARD ----------------

def dashboard_page():
    st.title("📊 Dashboard")
    st.caption("Employee Management System overview")

    col1, col2, col3, col4 = st.columns(4)

    # Replace these with your actual summary API endpoints.
    col1.metric("Employees", "—")
    col2.metric("Present Today", "—")
    col3.metric("Pending Leaves", "—")
    col4.metric("Departments", "—")

    st.info(
        "Connect your dashboard summary API to display "
        "live employee statistics."
    )


# ---------------- EMPLOYEES ----------------

def employees_page():
    render_employee_management(api_request)


# ---------------- PERMISSION MANAGEMENT ----------------

def permission_management_page():
    st.title("Permission management")
    st.caption(
        "Manage permission definitions and assign permissions to roles. "
        "The API enforces the required permissions for each action."
    )

    permissions_for_user = set(st.session_state.permissions)
    can_manage_permissions = (
        "*" in permissions_for_user
        or "permission:manage" in permissions_for_user
    )
    can_assign_permissions = (
        "*" in permissions_for_user
        or "role:assign" in permissions_for_user
    )
    if not can_manage_permissions and not can_assign_permissions:
        st.error("Your role does not have permission to manage role permissions.")
        return

    permissions = api_request("GET", "/permissions/")
    if permissions is None:
        return

    tab_names = []
    if can_manage_permissions:
        tab_names.append("Permission catalog")
    if can_assign_permissions:
        tab_names.append("Role assignments")
    tabs = iter(st.tabs(tab_names))

    if can_manage_permissions:
        with next(tabs):
            st.subheader("Permission catalog")
            if permissions:
                st.dataframe(
                    pd.DataFrame(permissions),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No permissions are defined yet.")

            with st.expander("Create permission"):
                with st.form("create_permission_form"):
                    new_name = st.text_input(
                        "Permission name",
                        placeholder="employee:read:all",
                    )
                    new_description = st.text_area("Description")
                    create_submitted = st.form_submit_button(
                        "Create permission",
                        type="primary",
                    )

                if create_submitted:
                    if not new_name.strip():
                        st.warning("Enter a permission name.")
                    else:
                        created = api_request(
                            "POST",
                            "/permissions/",
                            json={
                                "name": new_name,
                                "description": new_description.strip() or None,
                            },
                        )
                        if created is not None:
                            st.success(f"Created permission: {created['name']}")
                            st.rerun()

            if permissions:
                labels = {
                    f"{item['name']} (ID: {item['id']})": item
                    for item in permissions
                }
                selected_label = st.selectbox(
                    "Select a permission to edit or delete",
                    options=list(labels),
                    key="permission_catalog_selection",
                )
                selected_permission = labels[selected_label]

                with st.expander("Edit selected permission"):
                    with st.form("edit_permission_form"):
                        edited_name = st.text_input(
                            "Permission name",
                            value=selected_permission["name"],
                        )
                        edited_description = st.text_area(
                            "Description",
                            value=selected_permission.get("description") or "",
                        )
                        edit_submitted = st.form_submit_button(
                            "Save changes",
                            type="primary",
                        )

                    if edit_submitted:
                        if not edited_name.strip():
                            st.warning("Enter a permission name.")
                        else:
                            updated = api_request(
                                "PATCH",
                                f"/permissions/{selected_permission['id']}",
                                json={
                                    "name": edited_name,
                                    "description": (
                                        edited_description.strip() or None
                                    ),
                                },
                            )
                            if updated is not None:
                                st.success(f"Updated permission: {updated['name']}")
                                st.rerun()

                confirm_delete = st.checkbox(
                    f"Confirm deletion of {selected_permission['name']}",
                    key=f"confirm_delete_permission_{selected_permission['id']}",
                )
                if st.button(
                    "Delete selected permission",
                    disabled=not confirm_delete,
                    key="delete_permission_button",
                ):
                    response = api_request(
                        "DELETE",
                        f"/permissions/{selected_permission['id']}",
                        return_response=True,
                    )
                    if response is not None:
                        st.success("Permission deleted.")
                        st.rerun()

    if can_assign_permissions:
        with next(tabs):
            st.subheader("Assign permissions to a role")
            roles = api_request("GET", "/roles/")
            if roles is None:
                return
            assignable_roles = [
                role for role in roles if role["name"] != "Super Admin"
            ]
            if not assignable_roles:
                st.info("No editable roles are available.")
                return

            role_labels = {
                f"{role['name']} (ID: {role['id']})": role
                for role in assignable_roles
            }
            selected_role_label = st.selectbox(
                "Role",
                options=list(role_labels),
                key="permission_assignment_role",
            )
            selected_role = role_labels[selected_role_label]
            assigned_permissions = api_request(
                "GET",
                f"/permissions/roles/{selected_role['id']}/permissions",
            )
            if assigned_permissions is None:
                return

            permission_labels = {
                f"{permission['name']} (ID: {permission['id']})": permission
                for permission in permissions
            }
            current_ids = {
                permission["id"] for permission in assigned_permissions
            }
            current_labels = [
                label
                for label, permission in permission_labels.items()
                if permission["id"] in current_ids
            ]

            with st.form("role_permissions_form"):
                chosen_labels = st.multiselect(
                    "Permissions",
                    options=list(permission_labels),
                    default=current_labels,
                    help="This replaces the role's complete permission set.",
                )
                assignment_submitted = st.form_submit_button(
                    "Save role permissions",
                    type="primary",
                )

            if assignment_submitted:
                permission_ids = [
                    permission_labels[label]["id"] for label in chosen_labels
                ]
                updated_permissions = api_request(
                    "PUT",
                    f"/permissions/roles/{selected_role['id']}/permissions",
                    json={"permission_ids": permission_ids},
                )
                if updated_permissions is not None:
                    st.success(
                        f"Updated permissions for the {selected_role['name']} role."
                    )
                    st.rerun()


# ---------------- AUDIT LOGS ----------------

def audit_logs_page():
    st.title("Audit logs")
    st.caption(
        "Review recorded changes to employee, role, permission, and attendance data."
    )

    filter_columns = st.columns(4)
    action_filter = filter_columns[0].text_input(
        "Action contains",
        key="audit_action_filter",
    )
    resource_filter = filter_columns[1].text_input(
        "Resource type",
        key="audit_resource_filter",
    )
    actor_filter = filter_columns[2].text_input(
        "Actor ID",
        key="audit_actor_filter",
    )
    resource_id_filter = filter_columns[3].text_input(
        "Resource ID",
        key="audit_resource_id_filter",
    )

    date_columns = st.columns(2)
    use_from_date = date_columns[0].checkbox(
        "Filter from date",
        key="audit_use_from_date",
    )
    use_to_date = date_columns[1].checkbox(
        "Filter through date",
        key="audit_use_to_date",
    )
    query = {
        "page": st.session_state.get("audit_page", 1),
        "page_size": 50,
    }
    if action_filter.strip():
        query["action"] = action_filter.strip()
    if resource_filter.strip():
        query["resource_type"] = resource_filter.strip()
    for field, raw_value in (
        ("actor_id", actor_filter),
        ("resource_id", resource_id_filter),
    ):
        if raw_value.strip():
            if not raw_value.strip().isdecimal() or int(raw_value) < 1:
                st.warning(f"{field.replace('_', ' ').capitalize()} must be a positive integer.")
                return
            query[field] = int(raw_value)
    if use_from_date:
        query["from"] = date_columns[0].date_input(
            "From",
            key="audit_from_date",
        ).isoformat()
    if use_to_date:
        query["to"] = date_columns[1].date_input(
            "Through",
            key="audit_to_date",
        ).isoformat()
    filter_signature = tuple(
        sorted(
            (key, str(value))
            for key, value in query.items()
            if key not in {"page", "page_size"}
        )
    )
    if st.session_state.get("audit_filter_signature") != filter_signature:
        st.session_state.audit_filter_signature = filter_signature
        st.session_state.audit_page = 1
        query["page"] = 1

    response = api_request(
        "GET",
        "/audit-logs/",
        params=query,
        return_response=True,
    )
    if response is None:
        return

    logs = response.json()
    total = int(response.headers.get("X-Total-Count", len(logs)))
    st.caption(f"{total} matching audit event(s)")
    if not logs:
        st.info("No audit events match these filters.")
        return

    st.dataframe(
        [
            {
                "ID": item["id"],
                "Created at": item["created_at"],
                "Actor ID": item["actor_id"],
                "Action": item["action"],
                "Resource": item["resource_type"],
                "Resource ID": item["resource_id"],
            }
            for item in logs
        ],
        use_container_width=True,
        hide_index=True,
    )
    selected_log_id = st.selectbox(
        "Event details",
        options=[item["id"] for item in logs],
        format_func=lambda log_id: (
            f"#{log_id} "
            f"{next(item['action'] for item in logs if item['id'] == log_id)}"
        ),
    )
    selected_log = next(
        item for item in logs if item["id"] == selected_log_id
    )
    detail_columns = st.columns(2)
    with detail_columns[0]:
        st.subheader("Before")
        st.json(json.loads(selected_log["before_json"]) if selected_log["before_json"] else {})
    with detail_columns[1]:
        st.subheader("After")
        st.json(json.loads(selected_log["after_json"]) if selected_log["after_json"] else {})

    page = query["page"]
    page_count = max((total + query["page_size"] - 1) // query["page_size"], 1)
    previous_column, page_column, next_column = st.columns([1, 2, 1])
    if previous_column.button("Previous", disabled=page <= 1):
        st.session_state.audit_page = page - 1
        st.rerun()
    page_column.caption(f"Page {page} of {page_count}")
    if next_column.button("Next", disabled=page >= page_count):
        st.session_state.audit_page = page + 1
        st.rerun()


# ---------------- ATTENDANCE ----------------

def attendance_page():
    st.title("🕒 Attendance Management")
    user = st.session_state.user or {}
    employee_id = user.get("id")
    permissions = set(st.session_state.permissions or [])
    has_all_permissions = "*" in permissions
    can_read_attendance = (
        has_all_permissions or "attendance:read" in permissions
    )
    can_create_attendance = (
        has_all_permissions or "attendance:create" in permissions
    )
    can_review_wfh = has_all_permissions or "attendance:wfh" in permissions
    can_review_corrections = (
        has_all_permissions or "attendance:correct" in permissions
    )
    can_view_reports = has_all_permissions or "report:read" in permissions

    tabs = ["My attendance", "WFH and corrections"]
    if can_view_reports:
        tabs.append("Attendance reports")
    attendance_tab, requests_tab, *report_tabs = st.tabs(tabs)

    with attendance_tab:
        st.subheader("Today's attendance")
        if not isinstance(employee_id, int):
            st.error("Your employee profile could not be loaded. Sign in again.")
            return

        today_record = (
            api_request("GET", "/attendance/today")
            if can_read_attendance
            else None
        )
        if can_read_attendance and today_record is None:
            st.info("You have not checked in today.")
        elif today_record:
            metric_columns = st.columns(4)
            metric_columns[0].metric("Status", today_record["status"])
            metric_columns[1].metric(
                "Check-in",
                today_record["check_in"].replace("T", " ")[:16],
            )
            metric_columns[2].metric(
                "Check-out",
                (
                    today_record["check_out"].replace("T", " ")[:16]
                    if today_record.get("check_out")
                    else "Not checked out"
                ),
            )
            metric_columns[3].metric(
                "Working hours",
                f"{today_record.get('working_hours', 0):.2f}",
            )
            st.caption(
                f"Late by {today_record.get('late_minutes', 0)} minute(s); "
                f"left early by {today_record.get('early_leave_minutes', 0)} "
                "minute(s). "
                f"Work mode: {today_record.get('work_mode', 'office')}."
            )

        if can_create_attendance:
            if not today_record:
                with st.form("attendance_check_in_form"):
                    work_mode = st.selectbox(
                        "Work mode",
                        ["office", "wfh"],
                        format_func=lambda value: value.upper(),
                    )
                    check_in_notes = st.text_area(
                        "Check-in notes (optional)",
                        key="check_in_notes",
                    )
                    check_in_submitted = st.form_submit_button(
                        "Check in",
                        type="primary",
                    )
                if check_in_submitted:
                    result = api_request(
                        "POST",
                        "/attendance/check-in",
                        json={
                            "work_mode": work_mode,
                            "source": "streamlit",
                            "notes": check_in_notes.strip() or None,
                        },
                    )
                    if result is not None:
                        st.success("Checked in successfully.")
                        st.rerun()
            elif not today_record.get("check_out"):
                with st.form("attendance_check_out_form"):
                    check_out_notes = st.text_area(
                        "Check-out notes (optional)",
                        key="check_out_notes",
                    )
                    check_out_submitted = st.form_submit_button(
                        "Check out",
                        type="primary",
                    )
                if check_out_submitted:
                    result = api_request(
                        "POST",
                        "/attendance/check-out",
                        json={"notes": check_out_notes.strip() or None},
                    )
                    if result is not None:
                        st.success("Checked out successfully.")
                        st.rerun()

        records = (
            api_request("GET", f"/attendance/employee/{employee_id}")
            if can_read_attendance
            else []
        )
        if records is None:
            return
        st.subheader("Attendance history")
        if records:
            st.dataframe(
                [
                    {
                        "Date": record["attendance_date"],
                        "Check-in": record["check_in"],
                        "Check-out": record["check_out"],
                        "Hours": record["working_hours"],
                        "Overtime": record["overtime_hours"],
                        "Late minutes": record["late_minutes"],
                        "Early departure minutes": record["early_leave_minutes"],
                        "Status": record["status"],
                        "Work mode": record["work_mode"],
                    }
                    for record in records
                ],
                use_container_width=True,
                hide_index=True,
            )
        elif can_read_attendance:
            st.info("No attendance records found.")

    with requests_tab:
        st.subheader("Work From Home")
        if can_create_attendance:
            with st.form("wfh_request_form"):
                request_date = st.date_input(
                    "Requested work-from-home date",
                    min_value=date.today(),
                )
                wfh_reason = st.text_area("Reason for WFH")
                wfh_submitted = st.form_submit_button("Request WFH")
            if wfh_submitted:
                if len(wfh_reason.strip()) < 3:
                    st.warning("Enter a reason with at least 3 characters.")
                else:
                    result = api_request(
                        "POST",
                        "/attendance/wfh-requests",
                        json={
                            "request_date": request_date.isoformat(),
                            "reason": wfh_reason.strip(),
                        },
                    )
                    if result is not None:
                        st.success("WFH request submitted.")
                        st.rerun()

        if can_read_attendance:
            wfh_requests = api_request("GET", "/attendance/wfh-requests")
            if wfh_requests is None:
                return
            if wfh_requests:
                st.dataframe(
                    [
                        {
                            "ID": item["id"],
                            "Date": item["request_date"],
                            "Employee ID": item["employee_id"],
                            "Reason": item["reason"],
                            "Status": item["status"],
                            "Review comment": item.get("review_comment"),
                        }
                        for item in wfh_requests
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
                pending_wfh = [
                    item for item in wfh_requests if item["status"] == "Pending"
                ]
                if can_review_wfh and pending_wfh:
                    selected_wfh = st.selectbox(
                        "Pending WFH request",
                        pending_wfh,
                        format_func=lambda item: (
                            f"#{item['id']} - Employee {item['employee_id']} - "
                            f"{item['request_date']}"
                        ),
                        key="pending_wfh_selection",
                    )
                    wfh_comment = st.text_input(
                        "Review comment",
                        key="wfh_review_comment",
                    )
                    approve_column, reject_column = st.columns(2)
                    for column, action, label in (
                        (approve_column, "approve", "Approve WFH"),
                        (reject_column, "reject", "Reject WFH"),
                    ):
                        if column.button(label, key=f"wfh_{action}"):
                            result = api_request(
                                "POST",
                                f"/attendance/wfh-requests/{selected_wfh['id']}/{action}",
                                json={"comment": wfh_comment.strip() or None},
                            )
                            if result is not None:
                                st.success(f"WFH request {action}d.")
                                st.rerun()
            else:
                st.info("No WFH requests found.")

        st.divider()
        st.subheader("Attendance corrections")
        attendance_records = (
            api_request("GET", f"/attendance/employee/{employee_id}")
            if can_read_attendance and isinstance(employee_id, int)
            else []
        )
        if attendance_records is None:
            return

        if can_create_attendance and attendance_records:
            attendance_options = {
                f"{item['attendance_date']} (record #{item['id']})": item
                for item in attendance_records
            }
            with st.form("attendance_correction_form"):
                selected_record_label = st.selectbox(
                    "Attendance record",
                    list(attendance_options),
                )
                selected_record = attendance_options[selected_record_label]
                change_check_in = st.checkbox("Request check-in correction")
                requested_check_in = None
                if change_check_in:
                    check_in_date = st.date_input(
                        "Correct check-in date",
                        value=date.fromisoformat(
                            selected_record["attendance_date"][:10]
                        ),
                    )
                    check_in_time = st.time_input(
                        "Correct check-in time",
                        value=datetime.fromisoformat(
                            selected_record["check_in"]
                        ).time(),
                    )
                    requested_check_in = datetime.combine(
                        check_in_date,
                        check_in_time,
                    ).isoformat()

                change_check_out = st.checkbox("Request check-out correction")
                requested_check_out = None
                if change_check_out:
                    default_checkout = (
                        datetime.fromisoformat(selected_record["check_out"]).time()
                        if selected_record.get("check_out")
                        else time(17, 0)
                    )
                    check_out_date = st.date_input(
                        "Correct check-out date",
                        value=date.fromisoformat(
                            selected_record["attendance_date"][:10]
                        ),
                    )
                    check_out_time = st.time_input(
                        "Correct check-out time",
                        value=default_checkout,
                    )
                    requested_check_out = datetime.combine(
                        check_out_date,
                        check_out_time,
                    ).isoformat()

                requested_work_mode = st.selectbox(
                    "Correct work mode (optional)",
                    ["Keep current", "office", "wfh"],
                )
                correction_reason = st.text_area("Correction reason")
                correction_submitted = st.form_submit_button(
                    "Submit correction request",
                )
            if correction_submitted:
                if not (
                    requested_check_in
                    or requested_check_out
                    or requested_work_mode != "Keep current"
                ):
                    st.warning("Select at least one attendance field to correct.")
                elif len(correction_reason.strip()) < 3:
                    st.warning("Enter a reason with at least 3 characters.")
                else:
                    result = api_request(
                        "POST",
                        "/attendance/corrections",
                        json={
                            "original_attendance_id": selected_record["id"],
                            "requested_check_in": requested_check_in,
                            "requested_check_out": requested_check_out,
                            "requested_work_mode": (
                                None
                                if requested_work_mode == "Keep current"
                                else requested_work_mode
                            ),
                            "reason": correction_reason.strip(),
                        },
                    )
                    if result is not None:
                        st.success("Correction request submitted.")
                        st.rerun()
        elif can_create_attendance:
            st.info("Check in before requesting an attendance correction.")

        if can_read_attendance:
            corrections = api_request("GET", "/attendance/corrections")
            if corrections is None:
                return
            if corrections:
                st.dataframe(
                    [
                        {
                            "ID": item["id"],
                            "Employee ID": item["employee_id"],
                            "Attendance ID": item["original_attendance_id"],
                            "Reason": item["reason"],
                            "Status": item["status"],
                            "Review comment": item.get("review_comment"),
                        }
                        for item in corrections
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
                pending_corrections = [
                    item for item in corrections if item["status"] == "Pending"
                ]
                if can_review_corrections and pending_corrections:
                    selected_correction = st.selectbox(
                        "Pending correction",
                        pending_corrections,
                        format_func=lambda item: (
                            f"#{item['id']} - Employee {item['employee_id']} - "
                            f"Attendance #{item['original_attendance_id']}"
                        ),
                        key="pending_correction_selection",
                    )
                    correction_comment = st.text_input(
                        "Correction review comment",
                        key="correction_review_comment",
                    )
                    approve_column, reject_column = st.columns(2)
                    for column, action, label in (
                        (approve_column, "approve", "Approve correction"),
                        (reject_column, "reject", "Reject correction"),
                    ):
                        if column.button(
                            label,
                            key=f"correction_{action}",
                        ):
                            result = api_request(
                                "POST",
                                f"/attendance/corrections/{selected_correction['id']}/{action}",
                                json={"comment": correction_comment.strip() or None},
                            )
                            if result is not None:
                                st.success(f"Correction {action}d.")
                                st.rerun()
            else:
                st.info("No attendance corrections found.")

    if can_view_reports:
        with report_tabs[0]:
            st.subheader("Attendance report")
            report_columns = st.columns(3)
            report_from = report_columns[0].date_input(
                "From",
                value=date.today().replace(day=1),
                key="attendance_report_from",
            )
            report_to = report_columns[1].date_input(
                "To",
                value=date.today(),
                key="attendance_report_to",
            )
            department_id_filter = report_columns[2].number_input(
                "Department ID (0 for all)",
                min_value=0,
                step=1,
                value=0,
                key="attendance_report_department",
            )
            if report_from > report_to:
                st.warning("The report start date must be on or before its end date.")
            else:
                params = {
                    "from": report_from.isoformat(),
                    "to": report_to.isoformat(),
                }
                if department_id_filter:
                    params["department_id"] = int(department_id_filter)
                report = api_request(
                    "GET",
                    "/reports/attendance",
                    params=params,
                )
                if report is not None:
                    st.subheader("Totals")
                    st.json(report["totals"])
                    st.subheader("Employees")
                    if report["employees"]:
                        st.dataframe(
                            pd.DataFrame(report["employees"]),
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.info("No employees were found for the selected scope.")


# ---------------- LEAVE MANAGEMENT ----------------

def leave_page():
    st.title("🌴 Leave Management")

    tab1, tab2 = st.tabs(
        ["Leave Balance", "Leave Requests"]
    )

    with tab1:
        employee_id = st.number_input(
            "Employee ID",
            min_value=1,
            step=1,
            key="leave_employee_id",
        )

        if st.button("Fetch Leave Balance"):
            leaves = api_request(
                "GET",
                f"/leaves/employee/{int(employee_id)}",
            )

            if leaves is not None:
                if leaves:
                    st.dataframe(
                        pd.DataFrame(leaves),
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("No leave records found.")

    with tab2:
        st.subheader("Submit Leave Request")

        with st.form("leave_request_form"):
            employee_id = st.number_input(
                "Employee ID",
                min_value=1,
                step=1,
                key="request_employee_id",
            )

            leave_type = st.selectbox(
                "Leave Type",
                [
                    "Casual",
                    "Sick",
                    "Earned",
                    "Maternity",
                    "Paternity",
                ],
                index=None,
                placeholder="Select leave type",
            )
            start_date = st.date_input("Start Date")
            end_date = st.date_input("End Date")
            reason = st.text_area("Reason")

            submitted = st.form_submit_button(
                "Submit Leave Request",
                type="primary",
            )

        if submitted:
            if end_date < start_date:
                st.error("End date cannot be before start date.")
            else:
                payload = {
                    "employee_id": int(employee_id),
                    "leave_type": leave_type,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "reason": reason,
                }

                result = api_request(
                    "POST",
                    "/leaves/",
                    json=payload,
                )

                if result is not None:
                    st.success("Leave request submitted.")


# -----------------Salary Page -----------------

def salary_page():
    st.title("$ Salary Management")

    tab1, tab2 = st.tabs(
        ["Salary List", "Create Salary"]
    )

    with tab1:
        employee_id = st.number_input(
            "Employee ID",
            min_value=1,
            step=1,
            key="salary_employee_id",
        )

        if st.button("Fetch Salary List"):
            salaries = api_request(
                "GET",
                f"/salaries/employee/{int(employee_id)}",
            )

            if salaries is not None:
                if salaries:
                    st.dataframe(
                        pd.DataFrame(salaries),
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("No Salary records found.")

    with tab2:
        st.subheader("Submit Leave Request")

        with st.form("leave_request_form"):
            employee_id = st.number_input(
                "Employee ID",
                min_value=1,
                step=1,
                key="request_employee_id",
            )

            leave_type = st.selectbox(
                "Leave Type",
                [
                    "Casual",
                    "Sick",
                    "Earned",
                    "Maternity",
                    "Paternity",
                ],
                index=None,
                placeholder="Select leave type",
            )
            start_date = st.date_input("Start Date")
            end_date = st.date_input("End Date")
            reason = st.text_area("Reason")

            submitted = st.form_submit_button(
                "Submit Leave Request",
                type="primary",
            )

        if submitted:
            if end_date < start_date:
                st.error("End date cannot be before start date.")
            else:
                payload = {
                    "employee_id": int(employee_id),
                    "leave_type": leave_type,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "reason": reason,
                }

                result = api_request(
                    "POST",
                    "/leaves/",
                    json=payload,
                )

                if result is not None:
                    st.success("Leave request submitted.")

# ---------------- AI ASSISTANT ----------------

def ai_assistant_page():
    st.title("🤖 AI Employee Assistant")

    st.caption(
        "Ask questions about your attendance, leave balance, "
        "or employee information."
    )

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Ask your question...")

    if prompt:
        st.session_state.chat_history.append({
            "role": "user",
            "content": prompt,
        })

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                result = api_request(
                    "POST",
                    "/api/v1/ai/chat",
                    json={"message": prompt},
                )

                if result is not None:
                    answer = result.get(
                        "response",
                        result.get("answer", "No response received."),
                    )
                else:
                    answer = "Unable to get a response from the AI assistant."

                st.markdown(answer)

        st.session_state.chat_history.append({
            "role": "assistant",
            "content": answer,
        })


# ---------------- MAIN APP ----------------

def main():
    if not st.session_state.token:
        login_page()
        return

    if st.session_state.permissions is None:
        permissions = api_request("GET", "/auth/me/permissions")
        if permissions is None:
            return
        st.session_state.permissions = permissions

    with st.sidebar:
        st.title("🏢 EMS")

        user = st.session_state.user or {}
        st.write(
            f"Welcome, {user.get('first_name', 'User')}"
        )

        current_permissions = set(st.session_state.permissions)
        page_options = [
            "Dashboard",
            "Employees",
            "Leave Management",
            "Salary Management",
            "AI Assistant",
            "Change password",
        ]
        if current_permissions.intersection(
            {
                "*",
                "attendance:create",
                "attendance:read",
                "attendance:update",
                "attendance:manage",
                "attendance:correct",
                "attendance:wfh",
                "report:read",
            }
        ):
            page_options.insert(2, "Attendance")
        if (
            "*" in current_permissions
            or "permission:manage" in current_permissions
            or "role:assign" in current_permissions
        ):
            page_options.insert(2, "Permission management")
        if "*" in current_permissions or "audit:read" in current_permissions:
            page_options.insert(3, "Audit logs")

        page = st.radio("Navigation", page_options)

        st.divider()

        if st.button("🚪 Logout", use_container_width=True):
            api_request(
                "POST",
                "/auth/logout",
                handle_unauthorized=False,
            )
            st.session_state.token = None
            st.session_state.user = None
            st.session_state.permissions = []
            st.session_state.chat_history = []
            st.rerun()

    if page == "Dashboard":
        dashboard_page()
    elif page == "Employees":
        employees_page()
    elif page == "Permission management":
        permission_management_page()
    elif page == "Audit logs":
        audit_logs_page()
    elif page == "Attendance":
        attendance_page()
    elif page == "Leave Management":
        leave_page()
    elif page == "Salary Management":
        salary_page()
    elif page == "AI Assistant":
        ai_assistant_page()
    elif page == "Change password":
        change_password_page()


if __name__ == "__main__":
    main()