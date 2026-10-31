import csv
import io

from pydantic import ValidationError
from sqlalchemy.orm import Session

from models.department import Department
from models.designation import Designation
from models.employee import Employee
from models.employee_document import EmployeeDocument  # noqa: F401
from models.leave import Leave  # noqa: F401
from models.role import Role
from models.shift import Shift
from schemas.employee_csv import EmployeeImportPreview, EmployeeImportRow, EmployeeImportRowResult

MAX_IMPORT_SIZE = 5 * 1024 * 1024
MAX_IMPORT_ROWS = 10_000
REQUIRED_IMPORT_COLUMNS = {"employee_code", "first_name", "last_name", "email"}
IMPORT_COLUMNS = set(EmployeeImportRow.model_fields)
EXPORT_COLUMNS = [
    "employee_code",
    "first_name",
    "last_name",
    "email",
    "phone",
    "gender",
    "joining_date",
    "department_id",
    "designation_id",
    "role_id",
    "reporting_manager_id",
    "shift_id",
    "address",
    "status",
    "is_active",
    "exit_date",
    "exit_reason",
]


def _validation_errors(error: ValidationError) -> list[str]:
    return [
        f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
        for item in error.errors()
    ]


def preview_employee_csv(db: Session, content: bytes) -> EmployeeImportPreview:
    if len(content) > MAX_IMPORT_SIZE:
        raise ValueError("CSV file exceeds the 5 MB upload limit.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("CSV file must use UTF-8 encoding.") from error

    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames is None:
        raise ValueError("CSV file must include a header row.")
    headers = [header.strip() for header in reader.fieldnames if header]
    if len(headers) != len(reader.fieldnames) or len(headers) != len(set(headers)):
        raise ValueError("CSV header names must be non-empty and unique.")
    missing_columns = sorted(REQUIRED_IMPORT_COLUMNS - set(headers))
    if missing_columns:
        raise ValueError(
            "CSV is missing required columns: " + ", ".join(missing_columns)
        )
    unsupported_columns = sorted(set(headers) - IMPORT_COLUMNS)
    if unsupported_columns:
        raise ValueError(
            "CSV contains unsupported columns: " + ", ".join(unsupported_columns)
        )

    employees = db.query(Employee.employee_code, Employee.email).all()
    existing_codes = {code.casefold() for code, _ in employees}
    existing_emails = {email.casefold() for _, email in employees}
    department_ids = {row_id for (row_id,) in db.query(Department.id).all()}
    designation_ids = {
        row_id
        for (row_id,) in db.query(Designation.id)
        .filter(Designation.is_active.is_(True))
        .all()
    }
    role_ids = {row_id for (row_id,) in db.query(Role.id).all()}
    shift_ids = {row_id for (row_id,) in db.query(Shift.id).all()}
    active_employee_ids = {
        row_id
        for (row_id,) in db.query(Employee.id)
        .filter(Employee.is_active.is_(True))
        .all()
    }

    results: list[EmployeeImportRowResult] = []
    seen_codes: dict[str, int] = {}
    seen_emails: dict[str, int] = {}
    duplicate_first_rows: dict[int, set[str]] = {}
    for row_number, raw_row in enumerate(reader, start=2):
        if row_number > MAX_IMPORT_ROWS + 1:
            raise ValueError(f"CSV file may not exceed {MAX_IMPORT_ROWS} data rows.")
        if raw_row is None:
            continue
        if None in raw_row:
            results.append(
                EmployeeImportRowResult(
                    row=row_number,
                    employee_code=raw_row.get("employee_code"),
                    email=raw_row.get("email"),
                    valid=False,
                    errors=["Row contains more values than the header columns."],
                )
            )
            continue
        if all(
            not value or not value.strip() for value in raw_row.values()
        ):
            continue

        row_data = {
            (key.strip() if key else ""): (
                value.strip() if value and value.strip() else None
            )
            for key, value in raw_row.items()
        }
        errors: list[str] = []
        parsed: EmployeeImportRow | None = None
        try:
            parsed = EmployeeImportRow.model_validate(row_data)
        except ValidationError as error:
            errors.extend(_validation_errors(error))

        if parsed is not None:
            code_key = parsed.employee_code.casefold()
            email_key = parsed.email.casefold()
            if code_key in existing_codes:
                errors.append("employee_code already exists.")
            if email_key in existing_emails:
                errors.append("email already exists.")
            if code_key in seen_codes:
                errors.append(f"employee_code duplicates CSV row {seen_codes[code_key]}.")
                duplicate_first_rows.setdefault(seen_codes[code_key], set()).add(
                    "employee_code"
                )
            else:
                seen_codes[code_key] = row_number
            if email_key in seen_emails:
                errors.append(f"email duplicates CSV row {seen_emails[email_key]}.")
                duplicate_first_rows.setdefault(seen_emails[email_key], set()).add(
                    "email"
                )
            else:
                seen_emails[email_key] = row_number

            references = (
                ("department_id", parsed.department_id, department_ids),
                ("designation_id", parsed.designation_id, designation_ids),
                ("role_id", parsed.role_id, role_ids),
                ("shift_id", parsed.shift_id, shift_ids),
                ("reporting_manager_id", parsed.reporting_manager_id, active_employee_ids),
            )
            for field_name, value, valid_ids in references:
                if value is not None and value not in valid_ids:
                    errors.append(f"{field_name} does not reference an eligible record.")

        results.append(
            EmployeeImportRowResult(
                row=row_number,
                employee_code=parsed.employee_code if parsed else row_data.get("employee_code"),
                email=parsed.email if parsed else row_data.get("email"),
                valid=not errors,
                errors=errors,
            )
        )

    results_by_row = {result.row: result for result in results}
    for row_number, duplicate_fields in duplicate_first_rows.items():
        result = results_by_row[row_number]
        result.valid = False
        result.errors.extend(
            f"{field_name} duplicates another CSV row."
            for field_name in sorted(duplicate_fields)
        )

    valid_rows = sum(result.valid for result in results)
    return EmployeeImportPreview(
        total_rows=len(results),
        valid_rows=valid_rows,
        invalid_rows=len(results) - valid_rows,
        rows=results,
    )


def export_employees_csv(employees: list[Employee]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(EXPORT_COLUMNS)

    for employee in employees:
        values = [getattr(employee, column) for column in EXPORT_COLUMNS]
        writer.writerow(
            [
                _spreadsheet_safe(value.isoformat() if hasattr(value, "isoformat") else value)
                for value in values
            ]
        )
    return output.getvalue()


def _spreadsheet_safe(value: object) -> object:
    if isinstance(value, str):
        first_character = value.lstrip(" \t\r\n")[:1]
        if first_character in {"=", "+", "-", "@"}:
            return "'" + value
    return value
