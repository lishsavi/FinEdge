import streamlit as st
import mysql.connector
import re
import bcrypt
import os
import pandas as pd
from datetime import date, timedelta
from datetime import datetime, timedelta
from mysql.connector import Error

# NOTE: The original code had 'from fledge_db import customer_dashboard'.
# Since the full customer_dashboard logic is present below, this import
# is removed to create a single, self-contained, working file.

# --- 1. Database Configuration (UPDATE THESE CREDENTIALS FOR YOUR XAMPP SETUP) ---
# IMPORTANT: These must match your MySQL server running on XAMPP.
DB_CONFIG = {
    "host": "localhost",
    "user": "root",  # Default XAMPP MySQL user
    "password": "",  # Default XAMPP MySQL password (often empty)
    "database": "finedge_db"  # Must match the database name you created
}


# --- Database Connection and Security Utilities ---

@st.cache_resource(ttl=3600)
def get_db_connection():
    """Establishes and returns a reusable database connection."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        if conn.is_connected():
            return conn
        else:
            # st.error("Database Connection Failed: Could not connect to MySQL. Ensure XAMPP is running.")
            # st.stop() # Uncomment for production
            return None # Allow app to run in mock mode if DB is down
    except Error as err:
        # st.error(f"Database Error: {err}. Check your DB_CONFIG settings and XAMPP status.")
        # st.stop() # Uncomment for production
        return None # Allow app to run in mock mode if DB is down

def hash_password(password):
    """Hashes the password using bcrypt for secure storage."""
    # Salt is automatically generated and included in the hash
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def check_password(password, hashed_password):
    """Checks a plain password against a hashed one."""
    try:
        # bcrypt handles the salt extraction and comparison
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    except ValueError:
        return False  # Handles cases of bad hash format


# --- 2. Validation Functions ---

def validate_nic(nic):
    """Validates the NIC number format (Old: 9 digits + V/X, New: 12 digits)."""
    nic = nic.upper().strip()
    # Old format: 9 digits followed by 'V' or 'X'
    if len(nic) == 10 and nic[9] in ('V', 'X'):
        return nic[:9].isdigit()
    # New format: 12 digits
    elif len(nic) == 12 and nic.isdigit():
        return True
    return False


def validate_account_number(acc_no):
    """Validates a bank account number (fixed length of 12 digits)."""
    return len(acc_no) == 12 and acc_no.isdigit()


def validate_password(password):
    """Validates password length (8 to 14 characters)."""
    return 8 <= len(password) <= 14


def validate_email(email):
    """Basic email format validation."""
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)


# --- 3. Registration Logic ---

def register_customer(data):
    """Inserts new customer data into the database after hashing the password."""
    conn = get_db_connection()
    if not conn:
        st.warning("Registration simulated. Database is not connected.")
        return True # Simulate success if DB is down

    hashed_pw = hash_password(data['password'])

    query = """
    INSERT INTO customers (full_name, address, mobile_no, email_address, bank_name, branch_name, nic, acc_no, username, password_hash)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    try:
        cursor = conn.cursor()
        cursor.execute(query, (
            data['full_name'], data['address'], data['mobile_no'], data['email_address'],
            data['bank_name'], data['branch_name'], data['nic'], data['acc_no'],
            data['username'], hashed_pw
        ))
        conn.commit()
        st.success("✅ Customer registration complete! You can now log in from the Login Section.")
        return True
    except Error as err:
        if err.errno == 1062:
            st.error("Registration failed: Username, NIC, Account, or Email is already registered.")
        else:
            st.error(f"Database error during customer registration: {err}")
        return False


def register_bank_user(data):
    """Inserts new bank user data into the database after hashing the password."""
    conn = get_db_connection()
    if not conn:
        st.warning("Registration simulated. Database is not connected.")
        return True # Simulate success if DB is down

    hashed_pw = hash_password(data['admin_password'])

    query = """
    INSERT INTO bank_users (country, bank_name, branch_name, branch_code, reg_no, bank_address, 
                            contact_person_name, contact_email, contact_phone, admin_username, admin_password_hash)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    try:
        cursor = conn.cursor()
        cursor.execute(query, (
            data['country'], data['bank_name'], data['branch_name'], data['branch_code'], data['reg_no'],
            data['bank_address'],
            data['contact_person_name'], data['contact_email'], data['contact_phone'],
            data['admin_username'], hashed_pw
        ))
        conn.commit()
        st.success("✅ Bank registration complete. You can now log in as a Bank User.")
        return True
    except Error as err:
        if err.errno == 1062:
            st.error("Registration failed: Username or Registration No. is already in use.")
        else:
            st.error(f"Database error during bank registration: {err}")
        return False


# --- 4. Authentication Logic ---

def authenticate_user(username, password, user_type):
    """Authenticates a user against the database."""
    conn = get_db_connection()
    if not conn:
        # MOCK LOGIN for testing when DB is down. REMOVE THIS FOR PRODUCTION.
        if username == "test" and password == "test" and user_type == 'customer':
            st.warning("MOCK LOGIN SUCCESSFUL (DB DISCONNECTED).")
            return 100
        elif username == "bank" and password == "bank" and user_type == 'bank':
            st.warning("MOCK LOGIN SUCCESSFUL (DB DISCONNECTED).")
            return 200
        st.error("Database connection failed. Cannot authenticate.")
        return None

    # Determine the table and column names based on user type
    table = "customers" if user_type == 'customer' else "bank_users"
    username_col = "username" if user_type == 'customer' else "admin_username"
    password_col = "password_hash"
    id_col = "id"

    query = f"SELECT {id_col}, {password_col} FROM {table} WHERE {username_col} = %s"

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, (username,))
        user_record = cursor.fetchone()

        if user_record and check_password(password, user_record[password_col]):
            return user_record[id_col]  # Return the user's ID
        else:
            return None
    except Error as err:
        st.error(f"Database error during login: {err}")
        return None


# --- 5. Dashboard Logic and UI Components ---

def log_customer_request(customer_id, req_type, details, fee, is_urgent, time_estimate, status="Pending Review"):
    """Helper function to log any customer service request to the DB."""
    conn = get_db_connection()
    if not conn:
        st.warning("Request logged locally. Database is not connected.")
        return True # Simulate success if DB is down

    query = """
    INSERT INTO requests (customer_id, request_type, details, is_urgent, service_fee, status, estimated_time)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    try:
        cursor = conn.cursor()
        cursor.execute(query, (
            customer_id, req_type, details, is_urgent, fee, status, time_estimate
        ))
        conn.commit()
        return True
    except Error as err:
        st.error(f"Failed to submit request to database: {err}")
        return False


# --- Customer Dashboard Implementations ---


def render_request_document(customer_id):
    """Handles the 'Request a Document' form submission."""
    st.subheader("📝 Request a Document")

    service_charges = {
        'Balance Confirmation Letter': 500.00,
        'Tax Certificate': 750.00,
        'Cheque Book (50 leaves)': 1500.00,
        'Pay Order': 1000.00,
        'Bank Draft': 350.00
    }

    STANDARD_TIME = "48 hours (Standard)"
    URGENT_TIME = "24 hours (Next Business Day)"

    # --- Fee Selection and Calculation (MUST BE OUTSIDE THE FORM FOR REACTIVITY) ---

    # 1. Selection Box for Document Type
    doc_type = st.selectbox(
        "Select Document Type *",
        list(service_charges.keys()),
        key="doc_type_select"  # Added key for better session state management
    )

    # 2. Urgency Checkbox
    col_urgency, col_fee = st.columns(2)
    with col_urgency:
        is_urgent = st.checkbox("Urgent Processing", help="50% surcharge applies for urgent requests.",
                                key="is_urgent_check")

    # 3. Fee Calculation Logic
    base_fee = service_charges.get(doc_type, 0.0)

    # Apply the conditional fee change immediately based on the checkbox state
    if is_urgent:
        fee = base_fee * 1.5  # 50% increase for urgent
        time_estimate = URGENT_TIME
        # Display the new message for urgent fee
        st.warning("⚠ *50% Service Charge Added* for urgent processing.")
    else:
        fee = base_fee
        time_estimate = STANDARD_TIME

    # 4. Fee Display (st.metric)
    with col_fee:
        st.metric(label="Calculated Service Fee", value=f"LKR {fee:.2f}")

    # --- Request Submission Form (Only input fields that don't affect fee/time) ---
    with st.form("document_request_form"):
        # The form now contains the data that needs to be submitted

        st.info(f"Estimated Collection Time: *{time_estimate}*.")
        details = st.text_area("Additional Requirements/Details (Optional):", height=100)
        st.warning("🚨 Please ensure sufficient funds are available. "
                   "The Calculated Service Fee will be automatically deducted from your account after you submit the request.")

        # Hidden fields to pass the calculated values into the form submission logic
        st.session_state['current_doc_type'] = doc_type
        st.session_state['current_fee'] = fee
        st.session_state['current_is_urgent'] = is_urgent
        st.session_state['current_time_estimate'] = time_estimate
        st.session_state['current_details'] = details

        submitted = st.form_submit_button("Submit Request and Deduct Fee", type="primary")

        if submitted:
            # Use the calculated values stored in session state
            submit_doc_type = st.session_state['current_doc_type']
            submit_fee = st.session_state['current_fee']
            submit_is_urgent = st.session_state['current_is_urgent']
            submit_time_estimate = st.session_state['current_time_estimate']
            submit_details = st.session_state['current_details']

            # Simulation of Fee Deduction and OTP verification (as requested in original documents)
            st.toast("✅ Fee deduction simulated and approved from your account.")

            if log_customer_request(customer_id, submit_doc_type, submit_details, submit_fee, submit_is_urgent,
                                    submit_time_estimate):
                st.success(
                    f"Request for *{submit_doc_type}* submitted successfully! You can track the status in the 'Check Request Status' section.")


def render_check_status(customer_id):
    """Displays the status of the customer's requests."""
    st.subheader("🕒 Check Request Status")
    conn = get_db_connection()

    if conn:
        query = """
        SELECT request_type, status, estimated_time, service_fee, created_at, is_urgent
        FROM requests 
        WHERE customer_id = %s
        ORDER BY created_at DESC
        """
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, (customer_id,))
            requests = cursor.fetchall()

            if requests:
                for req in requests:
                    # Determine styling based on status
                    status_color_map = {
                        'Pending Review': '#1f77b4',  # blue
                        'In Progress': '#ff7f0e',  # orange
                        'Ready for Collection': '#2ca02c',  # green
                        'Completed': '#9467bd'  # purple
                    }
                    status_color = status_color_map.get(req['status'], 'gray')

                    st.markdown(f"""
                    <div style="padding: 15px; border-radius: 8px; margin-bottom: 15px; border: 1px solid #ddd; background-color: #000000;">
                        Request: {req['request_type']} {'<span style="color:red; font-weight:bold;">(URGENT)</span>' if req['is_urgent'] else ''} <br>
                        Status: <span style="font-weight: bold; color: {status_color};">{req['status']}</span> <br>
                        Fee Paid: LKR {req['service_fee']:.2f} <br>
                        Estimated Time: {req['estimated_time']} <br>
                        <small>Submitted: {req['created_at'].strftime('%Y-%m-%d %H:%M')}</small>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("You have no active or completed service requests.")
        except Error as err:
            st.error(f"Failed to fetch request status: {err}")
    else:
        st.warning("Cannot fetch request status. Database is not connected.")
        st.info("Example status: **Debit Card Replacement** (Status: **Ready for Collection**)")


def render_kyc_form(customer_id):
    """Handles the KYC Update Form request, actual PDF download, and simulated upload."""
    st.subheader("📄 Get KYC Update Form")

    # Mock KYC expiry check (Keep existing logic)
    MOCK_DAYS_LEFT = 180
    kyc_expiry = date.today() + timedelta(days=MOCK_DAYS_LEFT)

    if MOCK_DAYS_LEFT <= 365:
        st.error(
            f"⚠ *Compliance Alert:* Your KYC is due to expire on *{kyc_expiry.strftime('%Y-%m-%d')}* (in {MOCK_DAYS_LEFT} days). Please update your details promptly.")
    else:
        st.info(f"Your current KYC is valid until *{kyc_expiry.strftime('%Y-%m-%d')}*.")

    st.markdown("""
    To update your details, *download the official KYC form* below. You must print, fill out, sign, and submit the physical copy at your nearest branch for mandatory verification.
    """)

    # --- Attempt to download the ACTUAL PDF file ---
    pdf_filename = "KYC Form.pdf"

    try:
        # 1. Read the PDF file's binary data from the same directory
        with open(pdf_filename, "rb") as pdf_file:
            PDF_DATA = pdf_file.read()

        st.download_button(
            label="Download Official KYC Update Form (PDF)",
            data=PDF_DATA,
            file_name=f"KYC_Update_Form_{customer_id}.pdf",
            # Set the correct MIME type for a PDF file
            mime="application/pdf"
        )
    except FileNotFoundError:
        st.error(
            f"⚠ Error: *'{pdf_filename}'* not found. Please ensure the file is in the same directory as your Python script.")

        # --- FALLBACK: Provide the text simulation if the PDF is missing ---
        KYC_FORM_CONTENT = "KYC Profile Form (Individual/Joint)... [Full text content goes here as a fallback]"

        st.download_button(
            label="Download KYC Reference Form (TXT - Fallback)",
            data=KYC_FORM_CONTENT.strip().encode('utf-8'),
            file_name=f"KYC_Update_Form_FALLBACK_{customer_id}.txt",
            mime="text/plain"
        )
    # --- End PDF Download Logic ---

    st.markdown("---")
    st.markdown("### Secure Form Submission (Pre-Processing)")
    uploaded_file = st.file_uploader("Upload your filled/scanned form (PDF/JPG)", type=["pdf", "jpg", "jpeg"])

    if uploaded_file and st.button("Submit Uploaded Form for Bank Pre-Review", key="kyc_submit_btn"):
        # Log this as a request to notify the bank
        if log_customer_request(customer_id, "KYC Update Form Upload",
                                f"File uploaded for KYC Pre-Review: {uploaded_file.name}", fee=0.00,
                                is_urgent=False, time_estimate="N/A (Requires Physical Verification)",
                                status="Pending Review"):
            st.success(
                f"File *{uploaded_file.name}* uploaded successfully. Bank staff have been notified for pre-processing."
            )
            st.info(
                "You must still visit your branch with the original documents and signed form for *mandatory physical verification* to complete the KYC update.")
            st.toast("🚨 New KYC Review Request sent to Bank Dashboard!")
            st.experimental_rerun()


def display_kyc_notifications(conn):
    """Fetches and displays pending KYC Update Form Upload requests as prominent notifications."""

    st.markdown("---")
    st.markdown("## 🔔 *URGENT KYC NOTIFICATIONS*")

    # SQL query to fetch ONLY pending KYC uploads
    kyc_query = """
    SELECT 
        r.request_id, c.full_name, r.created_at
    FROM requests r
    JOIN customers c ON r.customer_id = c.id
    WHERE r.request_type = 'KYC Update Form Upload' AND r.status = 'Pending Review'
    ORDER BY r.created_at ASC
    """

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(kyc_query)
        kyc_alerts = cursor.fetchall()

        if kyc_alerts:
            count = len(kyc_alerts)
            st.warning(
                f"🚨 *Action Required:* {count} New KYC Forms have been uploaded and require immediate review and physical verification scheduling.")

            st.markdown("### Pending Uploads List")

            for alert in kyc_alerts:
                # Calculate time difference
                # NOTE: Ensure created_at is a datetime object. If it comes as a string, you need to parse it.
                # Assuming it is a datetime object from the database for this calculation:
                time_diff = datetime.now() - alert['created_at']
                minutes_ago = int(time_diff.total_seconds() / 60)

                # Display the notification card with bold text and a distinct background
                st.markdown(f"""
                    <div style="padding: 10px; border: 1px solid #ff4b4b; border-radius: 5px; margin-bottom: 8px; background-color: #FF6666;">
                        <strong>KYC Alert (ID: {alert['request_id']})</strong>: Customer 
                        <strong>{alert['full_name']}</strong> submitted a KYC Form for pre-review.
                        <br>
                        <small>Submitted approx. {minutes_ago} minutes ago.</small>
                    </div>
                """, unsafe_allow_html=True)

            st.markdown("---")

        else:
            st.success("✅ No urgent KYC form submissions are currently pending review.")

    except Exception as err:
        st.error(f"Failed to fetch KYC notifications: {err}")


def render_debit_card_replacement(customer_id):
    """Handles the Debit Card Replacement request."""
    st.subheader("💳 Request Debit Card Replacement")

    st.markdown("""
    Request a replacement for a lost, damaged, or expired debit card. A **LKR 750.00 fee** will be automatically deducted upon successful submission.
    """)

    REPLACEMENT_FEE = 750.00

    with st.form("debit_card_replacement_form"):
        reason = st.selectbox("Reason for Replacement *",
                              ["Card Lost/Stolen (URGENT)", "Card Damaged", "Card Expired", "Other"])

        details = st.text_area("Provide specific details (e.g., last transaction date if lost):")

        is_urgent = "URGENT" in reason
        time_estimate = "5 business days (Urgent)" if is_urgent else "7 business days (Standard)"

        st.warning(f"Replacement Fee: **LKR {REPLACEMENT_FEE:.2f}**. Estimated time: **{time_estimate}**.")

        submitted = st.form_submit_button("Submit Card Replacement Request and Deduct Fee", type="primary")

    if submitted:
            # Simulate Fee Deduction
        st.toast("✅ Fee deduction simulated and approved from your account.")

        if log_customer_request(customer_id, "Debit Card Replacement", f"Reason: {reason}. Details: {details}",
                                    fee=REPLACEMENT_FEE, is_urgent=is_urgent, time_estimate=time_estimate):
            st.success(f"Replacement request submitted (Reason: {reason}). New card processing initiated.")

            st.download_button(
                label="Download Replacement Reference Form",
                data=f"Reference Form for Debit Card Replacement (Reason: {reason}).",
                file_name="Debit_Card_Replacement_Reference.txt",
                mime="text/plain"
            )


def customer_dashboard():
    """Customer Dashboard UI and navigation."""
    st.title("👤 Customer Dashboard")
    st.info("Welcome, User.")
    # user_id is set during successful login in main_app()
    customer_id = st.session_state.user_id

    st.sidebar.title("Customer Services")
    dashboard_choice = st.sidebar.radio(
        "Select an Action",
        ['Request a Document', 'Check Request Status', 'Get KYC Update Form', 'Request Debit Card Replacement'],
        key="customer_nav"
    )

    # Render selected functionality
    if dashboard_choice == 'Request a Document':
        render_request_document(customer_id)
    elif dashboard_choice == 'Check Request Status':
        render_check_status(customer_id)
    elif dashboard_choice == 'Get KYC Update Form':
        render_kyc_form(customer_id)
    elif dashboard_choice == 'Request Debit Card Replacement':
        render_debit_card_replacement(customer_id)

    if st.sidebar.button("Log Out", type="secondary"):
        reset_session_state()
        st.experimental_rerun()


# --- Bank Dashboard Implementation ---

def update_request_status(request_id, new_status, conn):
    """Updates the status of a request in the database."""
    update_query = "UPDATE requests SET status = %s WHERE request_id = %s"
    try:
        cursor = conn.cursor()
        cursor.execute(update_query, (new_status, request_id))
        conn.commit()
        return True
    except Error as err:
        st.error(f"Failed to update status for request {request_id}: {err}")
        return False


def bank_dashboard():
    """Bank User Dashboard UI for request management, now with a separate KYC notification section."""
    st.title("🏦 Bank User Dashboard")
    st.info("Welcome, Bank User. Manage incoming customer service requests here.")

    if st.button("Log Out", type="secondary"):
        reset_session_state()
        st.experimental_rerun()
        return

    conn = get_db_connection()

    if not conn:
        st.error("Cannot connect to the database. Dashboard data cannot be fetched.")
        return

    # ----------------------------------------------------
    # NEW SECTION: Display the dedicated KYC Notifications
    # ----------------------------------------------------
    display_kyc_notifications(conn)
    # ----------------------------------------------------

    st.header("General Service Request Queue")

    # Fetch all requests, ordered by status (Pending first) and urgency
    query = """
    SELECT 
        r.request_id, c.full_name, r.request_type, r.is_urgent, r.service_fee, r.status, r.estimated_time, r.created_at
    FROM requests r
    JOIN customers c ON r.customer_id = c.id
    ORDER BY FIELD(r.status, 'Pending Review', 'In Progress', 'Ready for Collection', 'Completed'), r.is_urgent DESC, r.created_at ASC
    """
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query)
        all_requests = cursor.fetchall()

        if all_requests:

            col_info, col_filter = st.columns([1, 1])
            with col_info:
                st.write(f"*Total Requests in System: {len(all_requests)}*")

            # Filter UI
            with col_filter:
                status_filter = st.selectbox("Filter by Status",
                                             ['All', 'Pending Review', 'In Progress', 'Ready for Collection',
                                              'Completed'], key="bank_status_filter")

            filtered_requests = [req for req in all_requests if
                                 status_filter == 'All' or req['status'] == status_filter]

            if filtered_requests:
                for req in filtered_requests:
                    # Highlighting KYC uploads in the general list is still useful
                    is_kyc_upload = req['request_type'] == 'KYC Update Form Upload' and req[
                        'status'] == 'Pending Review'

                    status_color_map = {
                        'Pending Review': 'red' if req['is_urgent'] or is_kyc_upload else '#1f77b4',
                        'In Progress': '#ff7f0e',
                        'Ready for Collection': '#2ca02c',
                        'Completed': '#9467bd'
                    }
                    status_color = status_color_map.get(req['status'], 'gray')

                    st.markdown("---")

                    # Use columns for a structured view
                    col1, col2, col3, col4 = st.columns([1, 2, 2, 2])

                    with col1:
                        st.markdown(f"*ID:* {req['request_id']}")
                    with col2:
                        st.markdown(f"*Customer:* {req['full_name']}")
                        st.markdown(
                            f"*Type:* {req['request_type']} {'<span style=\"color:red; font-weight:bold;\">(URGENT)</span>' if req['is_urgent'] else ''}",
                            unsafe_allow_html=True)
                    with col3:
                        st.markdown(
                            f"*Status:* <span style='font-weight: bold; color: {status_color};'>{req['status']}</span>",
                            unsafe_allow_html=True)
                        st.markdown(f"*Submitted:* {req['created_at'].strftime('%Y-%m-%d %H:%M')}")

                    with col4:
                        # Dropdown to update the status
                        current_status_index = ['Pending Review', 'In Progress', 'Ready for Collection',
                                                'Completed'].index(req['status'])
                        new_status = st.selectbox(
                            "Update Status",
                            ['Pending Review', 'In Progress', 'Ready for Collection', 'Completed'],
                            index=current_status_index,
                            key=f"status_select_{req['request_id']}"
                        )
                        if st.button("Apply Status Update", key=f"btn_update_{req['request_id']}", type="primary"):
                            if update_request_status(req['request_id'], new_status, conn):
                                st.success(f"Request {req['request_id']} updated to '{new_status}'. Refreshing...")
                                st.experimental_rerun()
            else:
                st.info(f"No requests found with status: *{status_filter}*.")
        else:
            st.info("No customer requests currently in the system.")

    except Error as err:
        st.error(f"Failed to fetch general requests: {err}")



# --- 6. Main Application Flow (Entry Point) ---

def reset_session_state():
    """Clears session state for logging out."""
    st.session_state.logged_in = False
    st.session_state.user_type = None
    st.session_state.user_id = None


def main_app():
    """The main Streamlit application logic."""
    st.set_page_config(page_title="FinEdge Banking App", layout="wide")
    st.markdown("<h1 style='text-align: center; color: #1e88e5;'>FinEdge: Modernizing Financial Services</h1>",
                unsafe_allow_html=True)

    # Initialize session state for login management
    if 'logged_in' not in st.session_state:
        reset_session_state()

    # --- Logged In User Flow ---
    if st.session_state.logged_in:
        if st.session_state.user_type == 'customer':
            customer_dashboard() # Calls the defined customer dashboard
        elif st.session_state.user_type == 'bank':
            bank_dashboard() # Calls the defined bank dashboard
        return

    # --- Unauthenticated User Flow (Home/Login/Register) ---

    st.sidebar.title("App Navigation")
    menu_options = {1: 'Registration', 2: 'Login', 3: 'Forgot Password (Mock)', 4: 'Forgot Username (Mock)'}

    st.header("Welcome to FinEdge")

    # Use the same menu choices as the original console code
    choice = st.sidebar.selectbox(
        "Select your action:",
        options=list(menu_options.keys()),
        format_func=lambda x: menu_options[x]
    )

    if choice == 1:
        render_registration()
    elif choice == 2:
        render_login()
    elif choice in [3, 4]:
        st.subheader(menu_options[choice])
        st.warning("This is a mock recovery feature. A recovery link would be sent to your registered email.")
        st.text_input("Enter your registered email address")
        st.button("Simulate Recovery Request", type="primary")


def render_registration():
    """Renders the top-level registration form to select user type."""
    st.header("New User Registration")
    user_type = st.radio("Select account type:", ('customer', 'bank'), horizontal=True, key="reg_type_radio")

    if user_type == 'customer':
        render_customer_registration_form()
    elif user_type == 'bank':
        render_bank_registration_form()


def render_customer_registration_form():
    """Renders the Customer Registration Form."""
    st.subheader("Customer Registration")

    branches = {
        '139':'2nd Branch Batticaloa - 139',
         '111': 'Akkaraipattu - 111',
         '179': 'Akuressa - 179',
         '53': 'Alawwa PBC - 53',
         '79': 'Aluthgama - 79',
         '104': 'Ambalantota - 104',
         '72': 'Ambalongoda - 72',
         '62': 'Ampara - 62',
         '143': 'Anamabuwa - 143',
         '168': 'Anuradhapura New Town - 168',
         '21': 'Anuradhapura Super Branch - 21',
         '154': 'Aralangawila - 154',
         '67': 'Athurugiriya PBC - 67',
         '89': 'Attidiya - 89',
         '22': 'Avissawella - 22',
         '118': 'Baddegama - 118',
         '93': 'Badulla - 93',
         '97': 'Balangoda - 97',
         '11': 'Bambalapitiya - 11',
         '59': 'Bandaragama - 59',
         '46': 'Bandarawela - 46',
         '61': 'Battaramulla - 61',
         '107': 'Batticaloa - 107',
         '180': 'Beliatta - 180',
         '161': 'Bibile - 161',
         '142': 'Boralesgamuwa - 142',
         '4': 'Borella - 4',
         '218': 'Borella Super - 218',
         '145': 'Buttala - 145',
         '996': 'Card Centre - 996',
         '993': 'Central Clearing Department - 993',
         '164': 'Chankanai - 164',
         '169': 'Chavakachcheri - 169',
         '121': 'Chenkalady - 121',
         '108': 'Chilaw - 108',
         '128': 'Chunnakam - 128',
         '1': 'City Office - 1',
         '175': 'Colombo Super - 175',
         '90': 'Dambulla - 90',
         '196': 'Dankotuwa - 196',
         '167': 'Dehiattakandiya - 167',
         '17': 'Dehiwala - 17',
         '202': 'Delgoda - 202',
         '14': 'Deniyaya - 14',
         '49': 'Deraniyagala PBC - 49',
         '216': 'Dickwella - 216',
         '85': 'Digana PBC - 85',
         '198': 'Divulapitiya - 198',
         '20': 'Eheliyagoda - 20',
         '204': 'Elpitiya - 204',
         '43': 'Embilipitiya - 43',
         '114': 'Embuldeniya - 114',
         '12': 'Fort - 12',
         '190': 'Galewela - 190',
         '35': 'Galle - 35',
         '159': 'Galle Bazaar - 159',
         '16': 'Gampaha - 16',
         '212': 'Gampaha Super - 212',
         '101': 'Gampola - 101',
         '78': 'Ganemulla PBC - 78',
         '135': 'Gangodawila - 135',
         '95': 'Giriulla - 95',
         '225': 'Godakawela - 225',
         '173': 'Gothatuwa New Town - 173',
         '127': 'Grandpass - 127',
         '70': 'Gregorys Road PBC - 70',
         '181': 'Habaraduwa - 181',
         '137': 'Hanwella - 137',
         '58': 'Harbour-View PBC - 58',
         '80': 'Hatton - 80',
         '999': 'Head Office - 999',
         '29': 'Headquarters - 29',
         '220': 'Heerassagala - 220',
         '96': 'Hendala - 96',
         '187': 'Hettipola - 187',
         '229': 'Hikkaduwa - 229',
         '110': 'Hingurakgoda - 110',
         '69': 'Homagama - 69',
         '57': 'Horana - 57',
         '140': 'Ingiriya - 140',
         '98': 'Ja-Ela - 98',
         '120': 'Jaffna - 120',
         '206': 'Kaburupitiya - 206',
         '60': 'Kadawatha - 60',
         '38': 'Kaduruwela - 38',
         '162': 'Kaduwela - 162',
         '203': 'Kahatagasdigiliya - 203',
         '41': 'Kalawana - 41',
         '112': 'Kalmunai - 112',
         '50': 'Kalutara - 50',
         '125': 'Kaluwanchikudy - 125',
         '76': 'Kandana - 76',
         '123': 'Kandy City Centre - 123',
         '100': 'Kandy Metro - 100',
         '7': 'Kandy Super - 7',
         '172': 'Kantale - 172',
         '210': 'Karagampitiya - 210',
         '141': 'Karapitiya - 141',
         '115': 'Kattankudy - 115',
         '32': 'Katugastota - 32',
         '171': 'Kayts - 171',
         '64': 'Kegall - 64',
         '149': 'Kekirawa - 149',
         '227': 'Kelaniya - 227',
         '224': 'Kesbewa - 224',
         '151': 'Keselwatta - 151',
         '148': 'Kilinochchi - 148',
         '177': 'Kinniya - 177',
         '5': 'Kiribathgoda - 5',
         '200': 'Kiribathgoda - 200',
         '83': 'Kirindiwela PBC - 83',
         '117': 'Kirulapone - 117',
         '165': 'Kochchikade - 165',
         '94': 'Kohuwela - 94',
         '134': 'Kollupitiya - 134',
         '37': 'Kotahena - 37',
         '52': 'Kottawa - 52',
         '23': 'Kuliyapitiya - 23',
         '133': 'Kundasale - 133',
         '6': 'Kurunegala - 6',
         '215': 'Kurunegala Metro - 215',
         '189': 'Madampe - 189',
         '13': 'Maharagama - 13',
         '92': 'Maharagama Super - 92',
         '56': 'Mahiyanganaya - 56',
         '197': 'Maho - 197',
         '42': 'Main Street - 42',
         '207': 'Makola - 207',
         '39': 'Malabe - 39',
         '174': 'Mallavi - 174',
         '147': 'Manipay - 147',
         '119': 'Mannar - 119',
         '144': 'Maradana - 144',
         '183': 'Marandagahamula - 183',
         '194': 'Marawila - 194',
         '25': 'Matale - 25',
         '10': 'Matara - 10',
         '153': 'Matara Bazaar - 153',
         '176': 'Mattegoda - 176',
         '106': 'Matugama - 106',
         '160': 'Mawanella - 160',
         '109': 'Mawathagama - 109',
         '184': 'Menikhinna - 184',
         '158': 'Middeniya - 158',
         '65': 'Minuwangoda - 65',
         '86': 'Mirigama - 86',
         '74': 'Monaragala - 74',
         '155': 'Moratumulla - 155',
         '31': 'Moratuwa - 31',
         '15': 'Morawaka - 15',
         '199': 'Mount Lavinia - 199',
         '208': 'Muttur - 208',
         '193': 'Mutwal - 193',
         '40': 'Narahenpita - 40',
         '99': 'Narammala - 99',
         '132': 'Nattandiya - 132',
         '82': 'Nawala - 82',
         '223': 'Nawala Koswatta - 223',
         '195': 'Nawalapitiya - 195',
         '9': 'Nawam Mawatha - 9',
         '24': 'Negombo - 24',
         '88': 'Negombo 2nd - 88',
         '129': 'Nelliady - 129',
         '54': 'Neluwa PBC - 54',
         '102': 'Nikaweratiya - 102',
         '185': 'Ninthavur - 185',
         '71': 'Nittambuwa - 71',
         '138': 'Nochchiyagama - 138',
         '3': 'Nugegoda - 3',
         '84': 'Nuwara Eliya - 84',
         '124': 'Oddamavady - 124',
         '27': 'Old Moor Street - 27',
         '214': 'Orugodawatte - 214',
         '192': 'Padukka - 192',
         '26': 'Panadura - 26',
         '47': 'Panadura Wekada - 47',
         '191': 'Panchikawatte - 191',
         '166': 'Pannala - 166',
         '87': 'Pannipitiya - 87',
         '146': 'Passara - 146',
         '63': 'Pelawatte PBC - 63',
         '136': 'Peliyagoda - 136',
         '103': 'Pelmadulla - 103',
         '51': 'Peradeniya PBC - 51',
         '2': 'Pettah - 2',
         '150': 'Pilimatalawa - 150',
         '19': 'Piliyandala - 19',
         '91': 'Pitakotte - 91',
         '131': 'Platinum Plus - 131',
         '228': 'Polgahawela - 228',
         '221': 'Poojapitiya - 221',
         '130': 'Pottuvil - 130',
         '217': 'Prince Street - 217',
         '152': 'Pussellawa - 152',
         '156': 'Puttalam - 156',
         '73': 'Ragama PBC - 73',
         '122': 'Rajagiriya - 122',
         '188': 'Rambukkana - 188',
         '33': 'Rathnapura - 33',
         '18': 'Ratmalana - 18',
         '226': 'Ratnapura - 226',
         '163': 'Rikillagaskada - 163',
         '201': 'Ruwanwella - 201',
         '126': 'Sainthamaruthu - 126',
         '929': 'Sampath Viswa - 929',
         '213': 'Seeduwa - 213',
         '157': 'Sooriyawewa - 157',
         '211': 'Talahena - 211',
         '116': 'Tangalle - 116',
         '222': 'Thalawakele - 222',
         '178': 'Thalawathugoda - 178',
         '48': 'Thambuttegama (PBC) - 48',
         '34': 'Thimbirigasyaya - 34',
         '186': 'Thirunelvely - 186',
         '28': 'Tissamaharama - 28',
         '66': 'Trincomalee - 66',
         '55': 'Vavunia - 55',
         '170': 'Vavuniya Metro - 170',
         '77': 'veyangoda PBC - 77',
         '75': 'Wadduwa PBC - 75',
         '205': 'Warakapola - 205',
         '44': 'Wariyapola (PBC) - 44',
         '8': 'Wattala - 8',
         '105': 'Wattegama - 105',
         '209': 'Weligama - 209',
         '81': 'Welimada - 81',
         '45': 'Wellampitiya (PBC) - 45',
         '36': 'Wellawatte Super - 36',
         '113': 'Wellawaya - 113',
         '30': 'Wennappuwa - 30',
         '219': 'World Trade Center - 219',
         '68': 'Yakkala PBC - 68'
         }

    bnames = {'SB': 'Sampath Bank', }

    with st.form("customer_reg_form"):
        st.markdown("### Personal Details")
        full_name = st.text_input("Full Name *")
        address = st.text_area("Full Residential Address *")
        mobile_no = st.text_input("Mobile Number *")
        email_address = st.text_input("Email Address *")

        st.markdown("### Bank Account & Verification")
        bank_name= st.selectbox("Select your Bank Name*",list(bnames.keys()), format_func=lambda x: bnames[x])



        branch_name = st.selectbox("Select your Bank Branch's Name *", list(branches.keys()), format_func=lambda x: branches[x])

        #submitted = st.form_submit_button("Login", type="primary")

        nic = st.text_input("NIC Number (Old: XXXXXXXXXV/X, New: 12 digits) *").upper().strip()
        acc_no = st.text_input("Bank Account Number (12 digits) *")

        st.markdown("### Create Credentials")
        username = st.text_input("Create a Username *")
        password = st.text_input("Create a Password/PIN (8-14 characters) *", type="password")

        submitted = st.form_submit_button("Complete Customer Registration", type="primary")

        if submitted:
            data = {
                'full_name': full_name, 'address': address, 'mobile_no': mobile_no, 'email_address': email_address,
                'bank_name': bnames['SB'],'branch_name': branches[branch_name], 'nic': nic, 'acc_no': acc_no,
                'username': username, 'password': password
            }

            is_valid = True
            if not all(data.values()):
                st.error("Please fill in all mandatory fields (*).")
                is_valid = False
            if is_valid and not validate_nic(nic):
                st.error("Invalid NIC format. Must be 9-digit + V/X or 12-digit number.")
                is_valid = False
            if is_valid and not validate_account_number(acc_no):
                st.error("Invalid account number. Must be 12 digits.")
                is_valid = False
            if is_valid and not validate_password(password):
                st.error("Invalid password. Must be between 8 and 14 characters.")
                is_valid = False
            if is_valid and not validate_email(email_address):
                st.error("Invalid email address format.")
                is_valid = False

            if is_valid:
                register_customer(data)


def render_bank_registration_form():
    """Renders the Bank User (Admin) Registration Form."""
    st.subheader("Bank User (Admin) Registration")

    countries = {'SL': 'Sri Lanka',}# 'IN': 'India', 'UK': 'United Kingdom'
    bnames={'SB': 'Sampath Bank',}

    with st.form("bank_reg_form"):
        st.markdown("### Bank Details")
        country_code = st.selectbox("Select your country *", list(countries.keys()), format_func=lambda x: countries[x])
        #bank_name = st.text_input("Bank's Name *")
        bank_name= st.selectbox("Select your Bank Name*",list(bnames.keys()), format_func=lambda x: bnames[x])
        branch_name = st.text_input("Branch's Name *")
        branch_code = st.text_input("Branch Code *")
        reg_no = st.text_input("Bank's Registration Number *")
        bank_address = st.text_area("Bank's Physical Address *")

        st.markdown("### Contact Person Details")
        contact_person_name = st.text_input("Contact Person's Full Name *")
        contact_email = st.text_input("Contact Person's Email Address *")
        contact_phone = st.text_input("Contact Person's Phone Number *")

        st.markdown("### Create Admin Credentials")
        admin_username = st.text_input("Create a Bank Admin Username *")
        admin_password = st.text_input("Create a Password (8-14 characters) *", type="password")

        submitted = st.form_submit_button("Complete Bank Registration", type="primary")

        if submitted:
            data = {
                'country': countries[country_code], 'bank_name': bnames['SB'], 'branch_name': branch_name,
                'branch_code': branch_code, 'reg_no': reg_no, 'bank_address': bank_address,
                'contact_person_name': contact_person_name, 'contact_email': contact_email,
                'contact_phone': contact_phone, 'admin_username': admin_username, 'admin_password': admin_password
            }

            is_valid = True
            if not all(data.values()):
                st.error("Please fill in all mandatory fields (*).")
                is_valid = False
            if is_valid and not validate_password(admin_password):  # Reusing the password validation for admin
                st.error("Invalid password. Must be between 8 and 14 characters.")
                is_valid = False

            if is_valid:
                register_bank_user(data)


def render_login():
    """Renders the Login Form."""
    st.header("Login")

    with st.form("login_form"):
        user_type = st.radio("Are you a:", ('customer', 'bank'), horizontal=True, key="login_type")
        username = st.text_input("Username")
        password = st.text_input("Password (Only 3 attempts left)", type="password")

        submitted = st.form_submit_button("Login", type="primary")

        if submitted:
            if not username or not password:
                st.error("Please enter both username and password.")
            else:
                with st.spinner(f"Verifying {user_type} credentials..."):
                    # user_id will be the primary key ID from the DB
                    user_id = authenticate_user(username, password, user_type)

                    if user_id is not None:
                        st.session_state.logged_in = True
                        st.session_state.user_type = user_type
                        st.session_state.user_id = user_id
                        st.success("Login successful! Redirecting...")
                        # Use RERUN to force refresh and change view to the dashboard
                        st.experimental_rerun()
                    else:
                        st.error("Login failed. Invalid username or password.")


# Run the application
if __name__ == "__main__":
    main_app()
