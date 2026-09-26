import os

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

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


# ---------------- API HELPERS ----------------

def api_request(method, endpoint, **kwargs):
    """Send authenticated requests to FastAPI."""

    headers = kwargs.pop("headers", {})

    if st.session_state.token:
        headers["Authorization"] = (
            f"Bearer {st.session_state.token}"
        )

    try:
        response = requests.request(
            method=method,
            url=f"{API_BASE_URL}{endpoint}",
            headers=headers,
            timeout=20,
            **kwargs,
        )

        if response.status_code == 401:
            st.session_state.token = None
            st.session_state.user = None
            st.error("Session expired. Please log in again.")
            st.rerun()

        response.raise_for_status()

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

                # Adapt this to your actual login response.
                st.session_state.user = result.get("user", {})

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
    st.title("👥 Employee Management")

    tab1, tab2 = st.tabs(
        ["Employee List", "Add Employee"]
    )

    with tab1:
        if st.button("🔄 Refresh Employees"):
            st.rerun()

        employees = api_request(
            "GET",
            "/employees/",
        )

        if employees is not None:
            if isinstance(employees, dict):
                employees = employees.get(
                    "data", employees.get("items", [])
                )

            if employees:
                st.dataframe(
                    pd.DataFrame(employees),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No employees found.")

    with tab2:
        with st.form("add_employee_form"):
            first_name = st.text_input("First Name")
            last_name = st.text_input("Last Name")
            email = st.text_input("Email")
            employee_code = st.text_input("Employee Code")
            phone = st.text_input("Phone")
            department_id = st.number_input(
                "Department ID", min_value=1, step=1
            )
            role_id = st.number_input(
                "Role ID", min_value=1, step=1
            )

            submitted = st.form_submit_button(
                "Create Employee",
                type="primary",
            )

        if submitted:
            payload = {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "employee_code": employee_code,
                "phone": phone,
                "department_id": int(department_id),
                "role_id": int(role_id),
            }

            result = api_request(
                "POST",
                "/employees/",
                json=payload,
            )

            if result is not None:
                st.success("Employee created successfully.")
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
            employee = api_request(
                "GET",
                f"/employees/{int(employee_id)}",
            )

            if employee is not None:
                balance = employee.get("leave_balance", 0)
                st.metric("Available Leave Balance", balance)

    with tab2:
        st.subheader("Submit Leave Request")

        with st.form("leave_request_form"):
            employee_id = st.number_input(
                "Employee ID",
                min_value=1,
                step=1,
                key="request_employee_id",
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

    with st.sidebar:
        st.title("🏢 EMS")

        user = st.session_state.user or {}
        st.write(
            f"Welcome, {user.get('first_name', 'User')}"
        )

        page = st.radio(
            "Navigation",
            [
                "Dashboard",
                "Employees",
                "Attendance",
                "Leave Management",
                "AI Assistant",
            ],
        )

        st.divider()

        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.token = None
            st.session_state.user = None
            st.session_state.chat_history = []
            st.rerun()

    if page == "Dashboard":
        dashboard_page()
    elif page == "Employees":
        employees_page()
    elif page == "Attendance":
        attendance_page()
    elif page == "Leave Management":
        leave_page()
    elif page == "AI Assistant":
        ai_assistant_page()


if __name__ == "__main__":
    main()