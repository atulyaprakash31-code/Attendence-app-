"""
Attendance Management System
============================
A cross-platform, offline, CLI-based attendance management application.
Works on Windows and macOS.

Data is stored in an "AttendanceData" folder in the SAME directory as:
  - The .exe / binary  (when running as a packaged application)
  - This .py script    (when running from Python directly)

This means the app + data can be moved together as one folder,
and data can be shared or withheld simply by including/excluding
the AttendanceData/ folder.

No third-party dependencies — uses Python standard library only.
"""

import csv
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# SECTION 1: Path helpers
# ---------------------------------------------------------------------------

def get_app_directory() -> Path:
    """
    Return the directory where the application is located.

    - When packaged as .exe or binary (PyInstaller):
        Returns the folder that contains the .exe / binary file.
        sys.frozen is set to True by PyInstaller in this case.

    - When run as a plain Python script:
        Returns the folder that contains attendance_system.py.

    This ensures AttendanceData/ always lives next to the program,
    making the entire app portable — move the folder, data moves with it.
    """
    if getattr(sys, "frozen", False):
        # Running as a PyInstaller bundle (.exe or binary)
        # sys.executable is the path to the actual .exe file
        return Path(sys.executable).parent
    else:
        # Running as a Python script
        return Path(__file__).resolve().parent


def get_data_directory() -> Path:
    """
    Return <app_directory>/AttendanceData/

    Example paths:
      Windows exe:   C:\\MyApp\\AttendanceSystem\\AttendanceData\\
      macOS binary:  /Applications/AttendanceSystem/AttendanceData/
      Python script: /path/to/attendance-system/AttendanceData/
    """
    return get_app_directory() / "AttendanceData"


def get_classes_directory() -> Path:
    """Return .../AttendanceData/Classes/"""
    return get_data_directory() / "Classes"


def get_class_directory(class_name: str) -> Path:
    """Return .../Classes/<class_name>/"""
    return get_classes_directory() / class_name


def get_attendance_directory(class_name: str) -> Path:
    """Return .../Classes/<class_name>/Attendance/"""
    return get_class_directory(class_name) / "Attendance"


def get_class_info_path(class_name: str) -> Path:
    return get_class_directory(class_name) / "ClassInfo.json"


def get_students_path(class_name: str) -> Path:
    return get_class_directory(class_name) / "Students.csv"


def get_attendance_file_path(class_name: str, date_str: str) -> Path:
    """date_str is DDMMYY e.g. '120926'"""
    return get_attendance_directory(class_name) / f"{date_str}.csv"


# ---------------------------------------------------------------------------
# SECTION 2: OS-specific helpers (isolated for cross-platform cleanliness)
# ---------------------------------------------------------------------------

def open_file(path: Path) -> None:
    """Open a file with the OS default application."""
    try:
        if sys.platform == "win32":
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=True)
        else:
            subprocess.run(["xdg-open", str(path)], check=True)
    except Exception as e:
        print(f"  [!] Could not open file: {e}")


def open_directory(path: Path) -> None:
    """Open a directory in the OS file manager."""
    try:
        if sys.platform == "win32":
            subprocess.run(["explorer", str(path)], check=False)
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=True)
        else:
            subprocess.run(["xdg-open", str(path)], check=True)
    except Exception as e:
        print(f"  [!] Could not open directory: {e}")


# ---------------------------------------------------------------------------
# SECTION 3: Class info helpers
# ---------------------------------------------------------------------------

def list_classes() -> list:
    """
    Return a sorted list of valid class names found in the Classes directory.
    A valid class must have both ClassInfo.json and Students.csv.
    """
    classes_dir = get_classes_directory()
    if not classes_dir.exists():
        return []

    result = []
    for entry in sorted(classes_dir.iterdir()):
        if entry.is_dir():
            if (entry / "ClassInfo.json").exists() and (entry / "Students.csv").exists():
                result.append(entry.name)
    return result


def load_class_info(class_name: str) -> dict:
    """
    Load ClassInfo.json for a class.
    Returns dict with keys: class_name, room_no, strength.
    Returns None on failure.
    """
    info_path = get_class_info_path(class_name)
    if not info_path.exists():
        print(f"  [!] ClassInfo.json not found for '{class_name}'.")
        return None
    try:
        with open(info_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        required = {"class_name", "room_no", "strength"}
        if not required.issubset(data.keys()):
            print(f"  [!] ClassInfo.json for '{class_name}' is missing required fields.")
            return None
        return data
    except json.JSONDecodeError as e:
        print(f"  [!] ClassInfo.json for '{class_name}' is malformed: {e}")
        return None
    except OSError as e:
        print(f"  [!] Could not read ClassInfo.json: {e}")
        return None


def load_students(class_name: str) -> list:
    """
    Load Students.csv.
    Returns list of dicts: [{'Roll No': '1', 'Name': 'Rahul Kumar'}, ...]
    Returns None on failure.
    """
    students_path = get_students_path(class_name)
    if not students_path.exists():
        print(f"  [!] Students.csv not found for '{class_name}'.")
        return None
    try:
        students = []
        with open(students_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                students.append({
                    "Roll No": row["Roll No"].strip(),
                    "Name": row["Name"].strip()
                })
        return students
    except (KeyError, csv.Error, OSError) as e:
        print(f"  [!] Could not read Students.csv for '{class_name}': {e}")
        return None


def save_students(class_name: str, students: list) -> bool:
    """Write students list to Students.csv. Returns True on success."""
    students_path = get_students_path(class_name)
    try:
        with open(students_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["Roll No", "Name"])
            writer.writeheader()
            writer.writerows(students)
        return True
    except OSError as e:
        print(f"  [!] Could not save Students.csv: {e}")
        return False


# ---------------------------------------------------------------------------
# SECTION 4: Attendance file helpers
# ---------------------------------------------------------------------------

def validate_date(date_str: str) -> tuple:
    """
    Validate a date string in DDMMYY format.
    Returns (True, datetime_object) on success, (False, error_message) on failure.
    """
    date_str = date_str.strip()
    if len(date_str) != 6 or not date_str.isdigit():
        return False, "Date must be exactly 6 digits in DDMMYY format (e.g., 120926)."
    try:
        dt = datetime.strptime(date_str, "%d%m%y")
        return True, dt
    except ValueError:
        return False, f"'{date_str}' is not a valid date. Use DDMMYY format (e.g., 120926)."


def format_date_display(date_str: str) -> str:
    """Convert DDMMYY to DD/MM/YYYY for display."""
    ok, result = validate_date(date_str)
    if ok:
        return result.strftime("%d/%m/%Y")
    return date_str


def create_attendance_file(class_name: str, date_str: str, class_info: dict, students: list) -> bool:
    """
    Create a new attendance CSV with all students marked Present.
    Returns True on success, False on failure.
    """
    att_dir = get_attendance_directory(class_name)
    att_dir.mkdir(parents=True, exist_ok=True)

    att_path = get_attendance_file_path(class_name, date_str)
    display_date = format_date_display(date_str)

    try:
        with open(att_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            # Header block (metadata)
            writer.writerow(["Class", class_info["class_name"]])
            writer.writerow(["Room", class_info["room_no"]])
            writer.writerow(["Date", display_date])
            writer.writerow(["Strength", class_info["strength"]])
            writer.writerow([])  # Blank separator row
            # Attendance table
            writer.writerow(["Roll No", "Name", "Attendance"])
            for s in students:
                writer.writerow([s["Roll No"], s["Name"], "Present"])
        return True
    except OSError as e:
        print(f"  [!] Could not create attendance file: {e}")
        return False


def load_attendance(class_name: str, date_str: str) -> tuple:
    """
    Load an existing attendance CSV.
    Returns (meta_dict, students_list) or (None, None) on failure.
    """
    att_path = get_attendance_file_path(class_name, date_str)
    if not att_path.exists():
        return None, None

    try:
        with open(att_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)
    except (OSError, csv.Error) as e:
        print(f"  [!] Could not read attendance file: {e}")
        return None, None

    # Parse header block
    meta = {}
    data_start = 0
    for i, row in enumerate(rows):
        if len(row) >= 2:
            key = row[0].strip()
            val = row[1].strip()
            if key in ("Class", "Room", "Date", "Strength"):
                meta[key] = val
        if len(row) >= 3 and row[0].strip() == "Roll No":
            data_start = i + 1
            break

    if not meta or data_start == 0:
        print("  [!] Attendance file appears malformed.")
        return None, None

    students = []
    for row in rows[data_start:]:
        if len(row) >= 3:
            students.append({
                "Roll No": row[0].strip(),
                "Name": row[1].strip(),
                "Attendance": row[2].strip()
            })

    return meta, students


def save_attendance(class_name: str, date_str: str, meta: dict, students: list) -> bool:
    """
    Overwrite an existing attendance CSV with updated data.
    Returns True on success.
    """
    att_path = get_attendance_file_path(class_name, date_str)
    try:
        with open(att_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Class", meta.get("Class", "")])
            writer.writerow(["Room", meta.get("Room", "")])
            writer.writerow(["Date", meta.get("Date", "")])
            writer.writerow(["Strength", meta.get("Strength", "")])
            writer.writerow([])
            writer.writerow(["Roll No", "Name", "Attendance"])
            for s in students:
                writer.writerow([s["Roll No"], s["Name"], s["Attendance"]])
        return True
    except OSError as e:
        print(f"  [!] Could not save attendance: {e}")
        return False


# ---------------------------------------------------------------------------
# SECTION 5: UI helpers
# ---------------------------------------------------------------------------

def print_separator(char="=", width=42):
    print(char * width)


def print_header(title: str):
    print_separator()
    print(title)
    print_separator("-")


def pause():
    input("\n  Press Enter to continue...")


def select_class() -> str:
    """
    Display numbered list of classes and let user pick one.
    Returns the selected class name or None if cancelled / no classes.
    """
    classes = list_classes()
    if not classes:
        print("\n  No classes found.")
        print(f"  Data directory: {get_classes_directory()}")
        print("  Use option 4 to add a new class first.")
        return None

    print("\n  Select Class:\n")
    for i, name in enumerate(classes, 1):
        print(f"  {i}. {name}")
    print()

    while True:
        choice = input("  Enter choice: ").strip()
        if not choice:
            print("  [!] Please enter a number.")
            continue
        if not choice.isdigit():
            print("  [!] Invalid input. Please enter a number.")
            continue
        idx = int(choice) - 1
        if 0 <= idx < len(classes):
            return classes[idx]
        print(f"  [!] Please enter a number between 1 and {len(classes)}.")


def get_date_input(prompt: str = "  Enter date (DDMMYY): ") -> str:
    """Prompt for a validated DDMMYY date. Returns date_str or None if user types 'back'."""
    while True:
        date_str = input(prompt).strip()
        if date_str.lower() == "back":
            return None
        ok, result = validate_date(date_str)
        if ok:
            return date_str
        print(f"  [!] {result}")
        print("  (Type 'back' to cancel)")


# ---------------------------------------------------------------------------
# SECTION 6: Attendance taking session
# ---------------------------------------------------------------------------

def run_attendance_session(class_name: str, date_str: str, meta: dict, students: list) -> None:
    """
    Core attendance-taking loop.
    Modifies students in-place and saves to disk on 'done'.
    """
    # Build a fast lookup: roll_no_str -> index in students list
    roll_index = {s["Roll No"]: i for i, s in enumerate(students)}

    print_separator()
    print(f"  Class    : {meta.get('Class', class_name)}")
    print(f"  Room     : {meta.get('Room', '')}")
    print(f"  Date     : {meta.get('Date', '')}")
    print(f"  Strength : {meta.get('Strength', '')}")
    print_separator("-")
    print("  Attendance started.")
    print("  Enter roll number to toggle Present/Absent.")
    print("  Type 'done' when finished.\n")

    while True:
        entry = input("  Enter Roll No: ").strip()

        if entry.lower() == "done":
            if save_attendance(class_name, date_str, meta, students):
                print("\n  [✓] Attendance saved.")
            break

        if not entry:
            continue

        if not entry.isdigit():
            print(f"  [!] Invalid input '{entry}'. Enter a roll number or 'done'.")
            continue

        if entry not in roll_index:
            print(f"  [!] Roll No {entry} not found in this class.")
            continue

        # Toggle attendance
        idx = roll_index[entry]
        student = students[idx]
        if student["Attendance"] == "Present":
            student["Attendance"] = "Absent"
        else:
            student["Attendance"] = "Present"

        status_display = student["Attendance"].upper()
        print(f"  {student['Roll No']} - {student['Name']} : {status_display}")


# ---------------------------------------------------------------------------
# SECTION 7: Main menu option handlers
# ---------------------------------------------------------------------------

def add_class() -> None:
    """Menu option 4: Add a new class."""
    print_header("ADD NEW CLASS")

    # --- Class name ---
    while True:
        class_name = input("  Class name: ").strip()
        if not class_name:
            print("  [!] Class name cannot be empty.")
            continue
        existing = list_classes()
        if class_name in existing:
            print(f"  [!] A class named '{class_name}' already exists.")
            pause()
            return
        break

    # --- Room number ---
    while True:
        room_no = input("  Room number: ").strip()
        if not room_no:
            print("  [!] Room number cannot be empty.")
            continue
        break

    # --- Strength ---
    while True:
        strength_str = input("  Strength: ").strip()
        if not strength_str.isdigit() or int(strength_str) <= 0:
            print("  [!] Strength must be a positive integer.")
            continue
        strength = int(strength_str)
        break

    print(f"\n  Enter details for {strength} students.\n")

    # --- Student entry ---
    students = []
    used_rolls = set()

    for i in range(1, strength + 1):
        print(f"  Student {i} of {strength}")

        # Roll number
        while True:
            roll_str = input("    Roll No: ").strip()
            if not roll_str.isdigit() or int(roll_str) <= 0:
                print("    [!] Roll number must be a positive integer.")
                continue
            if roll_str in used_rolls:
                print(f"    [!] Roll No {roll_str} is already assigned.")
                continue
            break

        # Name
        while True:
            name = input("    Name: ").strip()
            if not name:
                print("    [!] Name cannot be empty.")
                continue
            break

        students.append({"Roll No": roll_str, "Name": name})
        used_rolls.add(roll_str)
        print()

    # --- Confirm and save ---
    print_separator("-")
    print(f"  Class    : {class_name}")
    print(f"  Room     : {room_no}")
    print(f"  Strength : {strength}")
    print(f"  Students : {len(students)}")
    print_separator("-")
    confirm = input("  Save this class? (Y/N): ").strip().lower()
    if confirm != "y":
        print("  [!] Class creation cancelled.")
        return

    # Create directories
    class_dir = get_class_directory(class_name)
    att_dir = get_attendance_directory(class_name)
    try:
        class_dir.mkdir(parents=True, exist_ok=True)
        att_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"  [!] Could not create directories: {e}")
        return

    # Save ClassInfo.json
    class_info = {
        "class_name": class_name,
        "room_no": room_no,
        "strength": strength
    }
    info_path = get_class_info_path(class_name)
    try:
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(class_info, f, indent=2)
    except OSError as e:
        print(f"  [!] Could not save ClassInfo.json: {e}")
        return

    # Save Students.csv
    if not save_students(class_name, students):
        return

    print(f"\n  [✓] Class '{class_name}' created successfully.")
    print(f"  Data stored in: {class_dir}")
    pause()


def take_attendance() -> None:
    """Menu option 1: Take attendance for a class."""
    print_header("TAKE ATTENDANCE")

    class_name = select_class()
    if not class_name:
        pause()
        return

    class_info = load_class_info(class_name)
    if not class_info:
        pause()
        return

    students_base = load_students(class_name)
    if not students_base:
        pause()
        return

    print(f"\n  Class    : {class_info['class_name']}")
    print(f"  Room     : {class_info['room_no']}")
    print(f"  Strength : {class_info['strength']}\n")

    date_str = get_date_input()
    if not date_str:
        return

    att_path = get_attendance_file_path(class_name, date_str)

    if att_path.exists():
        # Attendance file already exists — do NOT overwrite silently
        print(f"\n  Attendance file already exists.")
        print(f"  Path: {att_path}\n")
        print("  1. Resume / Edit")
        print("  2. Cancel")
        while True:
            choice = input("\n  Enter choice: ").strip()
            if choice == "1":
                meta, students = load_attendance(class_name, date_str)
                if meta is None or students is None:
                    print("  [!] Could not load existing attendance file.")
                    pause()
                    return
                print("\n  Resuming existing attendance...")
                run_attendance_session(class_name, date_str, meta, students)
                pause()
                return
            elif choice == "2":
                print("  Cancelled.")
                return
            else:
                print("  [!] Enter 1 or 2.")
    else:
        # New attendance file
        display_date = format_date_display(date_str)
        meta = {
            "Class": class_info["class_name"],
            "Room": class_info["room_no"],
            "Date": display_date,
            "Strength": str(class_info["strength"])
        }
        students = [
            {"Roll No": s["Roll No"], "Name": s["Name"], "Attendance": "Present"}
            for s in students_base
        ]
        if not create_attendance_file(class_name, date_str, class_info, students_base):
            pause()
            return
        run_attendance_session(class_name, date_str, meta, students)
        pause()


def show_attendance() -> None:
    """Menu option 2: Display attendance for a class and date."""
    print_header("SHOW ATTENDANCE")

    class_name = select_class()
    if not class_name:
        pause()
        return

    date_str = get_date_input()
    if not date_str:
        return

    att_path = get_attendance_file_path(class_name, date_str)

    if not att_path.exists():
        print(f"\n  No attendance file found for '{date_str}' in class '{class_name}'.")
        print(f"  Expected path: {att_path}")
        pause()
        return

    meta, students = load_attendance(class_name, date_str)
    if meta is None or students is None:
        pause()
        return

    # Display header
    print_separator()
    print(f"  Class    : {meta.get('Class', class_name)}")
    print(f"  Room     : {meta.get('Room', '')}")
    print(f"  Date     : {meta.get('Date', '')}")
    print(f"  Strength : {meta.get('Strength', '')}")
    print_separator("-")

    # Column widths
    col_roll = 8
    col_name = 24
    col_att  = 12

    header  = f"  {'Roll No':<{col_roll}} {'Name':<{col_name}} {'Attendance':<{col_att}}"
    divider = f"  {'-'*col_roll} {'-'*col_name} {'-'*col_att}"
    print(header)
    print(divider)

    present_count = 0
    absent_count  = 0

    for s in students:
        roll = s["Roll No"]
        name = s["Name"]
        att  = s["Attendance"]
        print(f"  {roll:<{col_roll}} {name:<{col_name}} {att:<{col_att}}")
        if att == "Present":
            present_count += 1
        else:
            absent_count += 1

    print_separator("-")
    print(f"  Present  : {present_count}")
    print(f"  Absent   : {absent_count}")
    print_separator()
    print(f"  File: {att_path}")
    pause()


def calculate_student_percentage() -> None:
    """Menu option 3: Show attendance percentage for a student."""
    print_header("STUDENT ATTENDANCE PERCENTAGE")

    class_name = select_class()
    if not class_name:
        pause()
        return

    students_base = load_students(class_name)
    if not students_base:
        pause()
        return

    # Build lookup: roll_no_str -> name
    roll_to_name = {s["Roll No"]: s["Name"] for s in students_base}
    valid_rolls  = set(roll_to_name.keys())

    # Get roll number from user
    while True:
        roll_input = input("\n  Enter Roll No: ").strip()
        if not roll_input:
            continue
        if roll_input in valid_rolls:
            break
        if roll_input.isdigit():
            matched = None
            for r in valid_rolls:
                if r.isdigit() and int(r) == int(roll_input):
                    matched = r
                    break
            if matched:
                roll_input = matched
                break
        sorted_rolls = sorted(valid_rolls, key=lambda x: int(x) if x.isdigit() else x)
        print(f"  [!] Roll No '{roll_input}' not found in class '{class_name}'.")
        print("  (Valid roll numbers: " + ", ".join(sorted_rolls) + ")")

    student_name = roll_to_name[roll_input]

    # Scan all attendance files
    att_dir = get_attendance_directory(class_name)
    if not att_dir.exists():
        print(f"\n  No attendance records found for class '{class_name}'.")
        print("  Attendance percentage cannot be calculated yet.")
        pause()
        return

    att_files = sorted(att_dir.glob("*.csv"))
    if not att_files:
        print(f"\n  No attendance files found in:\n  {att_dir}")
        print("  Attendance percentage cannot be calculated yet.")
        pause()
        return

    total_classes = 0
    present_count = 0
    absent_count  = 0

    for att_file in att_files:
        date_key = att_file.stem
        ok, _ = validate_date(date_key)
        if not ok:
            continue  # Skip unrelated/malformed filenames

        meta, file_students = load_attendance(class_name, date_key)
        if meta is None or file_students is None:
            continue  # Skip malformed files

        for s in file_students:
            s_roll = s["Roll No"]
            if s_roll == roll_input or (
                s_roll.isdigit() and roll_input.isdigit() and
                int(s_roll) == int(roll_input)
            ):
                total_classes += 1
                if s["Attendance"] == "Present":
                    present_count += 1
                else:
                    absent_count += 1
                break

    if total_classes == 0:
        print(f"\n  No valid attendance records found for Roll No {roll_input}.")
        print("  Attendance percentage cannot be calculated yet.")
        pause()
        return

    percentage  = (present_count / total_classes) * 100
    eligibility = "ELIGIBLE" if percentage >= 75.0 else "NOT ELIGIBLE"

    print_separator()
    print(f"  Roll No  : {roll_input}")
    print(f"  Name     : {student_name}")
    print(f"  Class    : {class_name}")
    print_separator("-")
    print(f"  Total Classes : {total_classes}")
    print(f"  Present       : {present_count}")
    print(f"  Absent        : {absent_count}")
    print_separator("-")
    print(f"  Attendance %  : {percentage:.2f}%")
    print(f"  Status        : {eligibility}")
    print_separator()
    pause()


def find_attendance_path() -> None:
    """Menu option 5: Find and optionally open attendance files."""
    print_header("FIND ATTENDANCE PATH")

    class_name = select_class()
    if not class_name:
        pause()
        return

    print(f"\n  Class: {class_name}\n")
    print("  1. Show Class Attendance Directory")
    print("  2. Show Attendance File Path for a Specific Date")
    print("  3. Back")

    while True:
        choice = input("\n  Enter choice: ").strip()
        if choice == "1":
            _show_class_attendance_directory(class_name)
            break
        elif choice == "2":
            _show_attendance_file_path(class_name)
            break
        elif choice == "3":
            break
        else:
            print("  [!] Enter 1, 2, or 3.")


def _show_class_attendance_directory(class_name: str) -> None:
    """Show and optionally open the Attendance directory for a class."""
    att_dir = get_attendance_directory(class_name)
    print_separator("-")
    print(f"  {class_name} Attendance Directory:\n")
    print(f"  {att_dir}")
    print_separator("-")

    if not att_dir.exists():
        print("  (Directory does not exist yet — take attendance first.)")
        pause()
        return

    open_choice = input("\n  Open this directory? (Y/N): ").strip().lower()
    if open_choice == "y":
        open_directory(att_dir)


def _show_attendance_file_path(class_name: str) -> None:
    """Show and optionally open a specific attendance file by date."""
    date_str = get_date_input()
    if not date_str:
        return

    att_path = get_attendance_file_path(class_name, date_str)

    if att_path.exists():
        print(f"\n  Attendance file found.\n")
        print(f"  {att_path}\n")
        print("  1. Open File")
        print("  2. Open Containing Directory")
        print("  3. Back")
        while True:
            choice = input("\n  Enter choice: ").strip()
            if choice == "1":
                open_file(att_path)
                break
            elif choice == "2":
                open_directory(att_path.parent)
                break
            elif choice == "3":
                break
            else:
                print("  [!] Enter 1, 2, or 3.")
    else:
        print(f"\n  No attendance file exists for date '{date_str}' in class '{class_name}'.")
        print(f"  Expected path:\n  {att_path}")
    pause()


# ---------------------------------------------------------------------------
# SECTION 8: Main menu loop
# ---------------------------------------------------------------------------

def main_menu() -> None:
    """Main application loop."""
    # Ensure base directories exist silently on startup
    try:
        get_classes_directory().mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    while True:
        print()
        print_separator()
        print("ATTENDANCE SYSTEM")
        print_separator("=", 17)
        print()
        print("  1. Take Attendance")
        print("  2. Show Attendance")
        print("  3. Student Attendance Percentage")
        print("  4. Add New Class")
        print("  5. Find Attendance Path")
        print("  6. Exit")
        print()

        choice = input("  Enter choice: ").strip()

        if choice == "1":
            take_attendance()
        elif choice == "2":
            show_attendance()
        elif choice == "3":
            calculate_student_percentage()
        elif choice == "4":
            add_class()
        elif choice == "5":
            find_attendance_path()
        elif choice == "6":
            print("\n  Goodbye!\n")
            break
        else:
            print("  [!] Invalid choice. Please enter 1-6.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\n  [!] Interrupted. Goodbye!\n")
        sys.exit(0)
