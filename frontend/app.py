import os

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


# ---------------- ATTENDANCE ----------------

def attendance_page():
    st.title("🕒 Attendance Management")

    employee_id = st.number_input(
        "Employee ID",
        min_value=1,
        step=1,
    )

    if st.button("Fetch Attendance", type="primary"):
        records = api_request(
            "GET",
            f"/attendences/employee/{int(employee_id)}",
        )

        if records is not None:
            if records:
                st.dataframe(
                    pd.DataFrame(records),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No attendance records found.")


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
            "Attendance",
            "Leave Management",
            "Salary Management",
            "AI Assistant",
            "Change password",
        ]
        if (
            "*" in current_permissions
            or "permission:manage" in current_permissions
            or "role:assign" in current_permissions
        ):
            page_options.insert(2, "Permission management")

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