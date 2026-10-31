from datetime import date
from typing import Any, Callable

import pandas as pd
import streamlit as st

ApiRequest = Callable[..., Any]


def _option_map(records: list[dict], include_none: bool = True) -> dict[str, int | None]:
    options = {"None": None} if include_none else {}
    options.update(
        {
            f"{record['name']} (#{record['id']})": record["id"]
            for record in records
        }
    )
    return options


def _query_value(value: Any) -> Any:
    if value is None or value == "Any":
        return None
    if isinstance(value, date):
        return value.isoformat()
    return value


def _render_employee_directory(api_request: ApiRequest) -> None:
    st.subheader("Employee directory")

    with st.form("employee_directory_filters"):
        search_col, department_col, designation_col = st.columns(3)
        q = search_col.text_input("Search", placeholder="Name, email, employee code")
        department_id = department_col.number_input(
            "Department ID", min_value=0, step=1, value=0
        )
        designation_id = designation_col.number_input(
            "Designation ID", min_value=0, step=1, value=0
        )

        manager_col, status_col, active_col, page_size_col = st.columns(4)
        manager_id = manager_col.number_input(
            "Reporting manager ID", min_value=0, step=1, value=0
        )
        employee_status = status_col.text_input("Status")
        active_filter = active_col.selectbox(
            "Active status", ["Any", "Active", "Inactive"]
        )
        page_size = page_size_col.selectbox("Rows per page", [10, 25, 50, 100], index=1)

        start_col, end_col, sort_col, direction_col = st.columns(4)
        joining_date_from = start_col.date_input(
            "Joined from", value=None, format="YYYY-MM-DD"
        )
        joining_date_to = end_col.date_input(
            "Joined to", value=None, format="YYYY-MM-DD"
        )
        sort_by = sort_col.selectbox(
            "Sort by",
            [
                "employee_code",
                "first_name",
                "last_name",
                "email",
                "joining_date",
                "status",
                "is_active",
                "department_id",
                "designation_id",
                "reporting_manager_id",
                "created_at",
            ],
        )
        sort_order = direction_col.selectbox("Direction", ["asc", "desc"])
        submitted = st.form_submit_button("Apply filters", type="primary")

    if submitted or "employee_list_filters" not in st.session_state:
        st.session_state.employee_list_page = 1
        st.session_state.employee_list_filters = {
            "q": _query_value(q.strip() or None),
            "department_id": _query_value(int(department_id) or None),
            "designation_id": _query_value(int(designation_id) or None),
            "reporting_manager_id": _query_value(int(manager_id) or None),
            "status": _query_value(employee_status.strip() or None),
            "is_active": (
                True if active_filter == "Active"
                else False if active_filter == "Inactive"
                else None
            ),
            "joining_date_from": _query_value(joining_date_from),
            "joining_date_to": _query_value(joining_date_to),
            "sort_by": sort_by,
            "sort_order": sort_order,
            "page_size": page_size,
        }

    filters = st.session_state.employee_list_filters
    params = {
        key: value
        for key, value in filters.items()
        if value is not None
    }
    params.update(
        {
            "page": st.session_state.employee_list_page,
            "page_size": filters["page_size"],
        }
    )
    response = api_request(
        "GET",
        "/employees/",
        params=params,
        return_response=True,
    )
    if response is None:
        return

    employees = response.json()
    total = int(response.headers.get("X-Total-Count", len(employees)))
    page = int(response.headers.get("X-Page", params["page"]))
    pages = max(1, (total + filters["page_size"] - 1) // filters["page_size"])
    st.caption(f"{total} employees · Page {page} of {pages}")

    if employees:
        display_columns = [
            "id",
            "employee_code",
            "first_name",
            "last_name",
            "email",
            "department_id",
            "designation_id",
            "reporting_manager_id",
            "joining_date",
            "status",
            "is_active",
            "exit_date",
        ]
        st.dataframe(
            pd.DataFrame(employees).reindex(columns=display_columns),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No employees match the current filters.")

    previous_col, page_col, next_col = st.columns([1, 2, 1])
    if previous_col.button(
        "← Previous",
        disabled=page <= 1,
        key="employee_previous_page",
    ):
        st.session_state.employee_list_page = page - 1
        st.rerun()
    page_col.markdown(f"<div style='text-align:center'>Page {page} of {pages}</div>", unsafe_allow_html=True)
    if next_col.button(
        "Next →",
        disabled=page >= pages,
        key="employee_next_page",
    ):
        st.session_state.employee_list_page = page + 1
        st.rerun()

    if st.button("Prepare filtered CSV export", key="prepare_employee_export"):
        export_params = {
            key: value
            for key, value in filters.items()
            if key != "page_size" and value is not None
        }
        export_response = api_request(
            "GET",
            "/employees/export",
            params=export_params,
            return_response=True,
        )
        if export_response is not None:
            st.session_state.employee_export_csv = export_response.content

    export_csv = st.session_state.get("employee_export_csv")
    if export_csv is not None:
        st.download_button(
            "Download filtered employee CSV",
            data=export_csv,
            file_name="employees.csv",
            mime="text/csv",
            type="primary",
        )


def _render_hire_employee(api_request: ApiRequest) -> None:
    st.subheader("Hire employee")
    designations = api_request("GET", "/designations/") or []
    designation_options = _option_map(designations)

    with st.form("phase_one_hire_employee"):
        code_col, first_col, last_col = st.columns(3)
        employee_code = code_col.text_input("Employee code")
        first_name = first_col.text_input("First name")
        last_name = last_col.text_input("Last name")

        email_col, phone_col, password_col = st.columns(3)
        email = email_col.text_input("Email")
        phone = phone_col.text_input("Phone")
        password = password_col.text_input("Temporary password", type="password")

        department_col, role_col, manager_col = st.columns(3)
        department_id = department_col.number_input(
            "Department ID (optional)", min_value=0, step=1, value=0
        )
        role_id = role_col.number_input(
            "Role ID (optional)", min_value=0, step=1, value=0
        )
        manager_id = manager_col.number_input(
            "Reporting manager ID (optional)", min_value=0, step=1, value=0
        )
        designation_label = st.selectbox(
            "Designation",
            list(designation_options),
        )
        joining_date = st.date_input("Joining date", value=date.today())

        submitted = st.form_submit_button("Create employee", type="primary")

    if submitted:
        payload = {
            "employee_code": employee_code.strip(),
            "first_name": first_name.strip(),
            "last_name": last_name.strip(),
            "email": email.strip(),
            "password": password,
            "phone": phone.strip() or None,
            "department_id": int(department_id) or None,
            "role_id": int(role_id) or None,
            "reporting_manager_id": int(manager_id) or None,
            "designation_id": designation_options[designation_label],
            "joining_date": joining_date.isoformat(),
        }
        created = api_request("POST", "/employees/", json=payload)
        if created is not None:
            st.success(
                f"Created {created['first_name']} {created['last_name']} "
                f"({created['employee_code']})."
            )


def _render_employee_documents(api_request: ApiRequest) -> None:
    st.subheader("Employee documents")
    employee_id = st.number_input(
        "Employee ID",
        min_value=1,
        step=1,
        key="document_employee_id",
    )
    upload_col, list_col = st.columns([1, 1])

    with upload_col:
        uploaded_file = st.file_uploader(
            "Upload PDF, PNG, or JPEG (maximum 10 MB)",
            type=["pdf", "png", "jpg", "jpeg"],
            key="employee_document_upload",
        )
        if st.button("Upload document", type="primary", disabled=uploaded_file is None):
            upload_response = api_request(
                "POST",
                f"/employees/{int(employee_id)}/documents",
                files={
                    "file": (
                        uploaded_file.name,
                        uploaded_file.getvalue(),
                        uploaded_file.type or "application/octet-stream",
                    )
                },
            )
            if upload_response is not None:
                st.success(f"Uploaded {upload_response['file_name']}.")
                st.rerun()

    with list_col:
        if st.button("Load documents", key="load_employee_documents"):
            st.session_state.loaded_documents_employee_id = int(employee_id)

        if st.session_state.get("loaded_documents_employee_id") == int(employee_id):
            documents = api_request(
                "GET",
                f"/employees/{int(employee_id)}/documents",
            )
            if documents:
                for document in documents:
                    download_key = f"employee_document_content_{document['id']}"
                    if st.button(
                        f"Prepare {document['file_name']}",
                        key=f"prepare_document_{document['id']}",
                    ):
                        download = api_request(
                            "GET",
                            f"/employees/documents/{document['id']}/download",
                            return_response=True,
                        )
                        if download is not None:
                            st.session_state[download_key] = download.content
                    content = st.session_state.get(download_key)
                    if content is not None:
                        st.download_button(
                            f"Download {document['file_name']}",
                            data=content,
                            file_name=document["file_name"],
                            mime=document["content_type"],
                            key=f"download_employee_document_{document['id']}",
                        )
            elif documents is not None:
                st.info("No documents uploaded for this employee.")


def _render_csv_import(api_request: ApiRequest) -> None:
    st.subheader("CSV import preview")
    st.caption(
        "Preview checks required fields, duplicate identifiers, and reference IDs. "
        "It does not create employees."
    )
    st.download_button(
        "Download CSV template",
        data=(
            "employee_code,first_name,last_name,email,phone,gender,dob,joining_date,"
            "department_id,designation_id,role_id,reporting_manager_id,shift_id,"
            "address,salary,status\n"
        ),
        file_name="employee_import_template.csv",
        mime="text/csv",
    )
    uploaded_file = st.file_uploader(
        "Choose employee CSV",
        type=["csv"],
        key="employee_csv_preview_upload",
    )
    if uploaded_file is None:
        return

    if st.button("Validate CSV (dry run)", type="primary"):
        result = api_request(
            "POST",
            "/employees/import/preview",
            files={
                "file": (
                    uploaded_file.name,
                    uploaded_file.getvalue(),
                    "text/csv",
                )
            },
        )
        if result is not None:
            st.session_state.employee_csv_preview = result

    preview = st.session_state.get("employee_csv_preview")
    if preview:
        valid_col, invalid_col, total_col = st.columns(3)
        valid_col.metric("Valid rows", preview["valid_rows"])
        invalid_col.metric("Invalid rows", preview["invalid_rows"])
        total_col.metric("Total rows", preview["total_rows"])
        st.dataframe(
            pd.DataFrame(preview["rows"]),
            use_container_width=True,
            hide_index=True,
        )
        if preview["invalid_rows"]:
            st.warning("Fix the listed CSV errors and preview again.")
        else:
            st.success("All rows pass validation. This preview has not imported them.")


def _render_designations(api_request: ApiRequest) -> None:
    st.subheader("Designations")
    records = api_request("GET", "/designations/")
    if records:
        st.dataframe(
            pd.DataFrame(records),
            use_container_width=True,
            hide_index=True,
        )
    elif records is not None:
        st.info("No active designations yet.")

    with st.expander("Add designation"):
        with st.form("create_designation_form"):
            name = st.text_input("Designation name")
            description = st.text_area("Description")
            submitted = st.form_submit_button("Create designation")
        if submitted:
            created = api_request(
                "POST",
                "/designations/",
                json={
                    "name": name.strip(),
                    "description": description.strip() or None,
                },
            )
            if created is not None:
                st.success(f"Created designation: {created['name']}.")
                st.rerun()

    if records:
        designation_options = _option_map(records, include_none=False)
        with st.expander("Deactivate designation"):
            selected = st.selectbox(
                "Designation",
                list(designation_options),
                key="deactivate_designation_selection",
            )
            if st.button("Deactivate", key="deactivate_designation_button"):
                updated = api_request(
                    "PATCH",
                    f"/designations/{designation_options[selected]}",
                    json={"is_active": False},
                )
                if updated is not None:
                    st.success(f"Deactivated {updated['name']}.")
                    st.rerun()


def _render_employee_exit(api_request: ApiRequest) -> None:
    st.subheader("Record employee exit")
    st.warning(
        "This deactivates the employee and records the exit details; it does not "
        "delete their employee record."
    )
    with st.form("record_employee_exit"):
        employee_id = st.number_input("Employee ID", min_value=1, step=1)
        exit_date = st.date_input("Final date of employment")
        exit_reason = st.text_area("Exit reason")
        submitted = st.form_submit_button("Record exit", type="primary")
    if submitted:
        exited = api_request(
            "POST",
            f"/employees/{int(employee_id)}/exit",
            json={
                "exit_date": exit_date.isoformat(),
                "exit_reason": exit_reason.strip(),
            },
        )
        if exited is not None:
            st.success(
                f"Recorded exit for {exited['employee_code']} on "
                f"{exited['exit_date']}."
            )


def render_employee_management(api_request: ApiRequest) -> None:
    st.title("Employee management")
    st.caption(
        "Hire employees, assign reporting lines and designations, manage documents, "
        "and export a filtered workforce list."
    )

    tabs = st.tabs(
        [
            "Directory & export",
            "Hire employee",
            "Documents",
            "CSV preview",
            "Designations",
            "Employee exit",
        ]
    )
    with tabs[0]:
        _render_employee_directory(api_request)
    with tabs[1]:
        _render_hire_employee(api_request)
    with tabs[2]:
        _render_employee_documents(api_request)
    with tabs[3]:
        _render_csv_import(api_request)
    with tabs[4]:
        _render_designations(api_request)
    with tabs[5]:
        _render_employee_exit(api_request)
