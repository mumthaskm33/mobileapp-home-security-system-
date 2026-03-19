# Intruder Alert System - Setup & Run Guide

This guide details how to set up and run the AI-Based Intruder Alert System. You can run it using **SQLite (Default, No Install)** or **MySQL**.

## Prerequisites

Ensure you have the following installed:
1.  **Python** (3.8 or higher)
2.  **Flutter SDK** (for the mobile app)
3.  **Android Studio** or **VS Code** (with Flutter extensions)
4.  *(Optional)* **MySQL Server** (only if you want to use MySQL)

## 1. Database Setup

### Option A: SQLite (Recommended for Testing)
**No action required.** The application will automatically create a local `face_security.db` file when you run it.

### Option B: MySQL (Advanced)
If you prefer MySQL:
1.  Open `database.py`.
2.  Change `DB_TYPE` to `'MYSQL'`.
3.  Update the `password` field in `get_connection()` with your MySQL password.
4.  Initialize the database:
    ```sql
    source setup_database.sql;
    ```

## 2. Backend Setup (Flask)

1.  Open a terminal in the project root folder (where `app.py` is).
2.  Install the required Python dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Start the Flask server:
    ```bash
    python app.py
    ```
    - You should see output indicating the server is running on `http://0.0.0.0:5000` (or `127.0.0.1:5000`).
    - Note your computer's local IP address (e.g., `192.168.1.X`) for the mobile app connection.

## 3. Mobile App Setup (Flutter)

1.  Navigate to the mobile app directory:
    ```bash
    cd mobile_app
    ```
2.  Install Flutter dependencies:
    ```bash
    flutter pub get
    ```
3.  **Configure API URL**:
    - Open `lib/main.dart` (or wherever the API calls are made).
    - Find the variable storing the backend URL (usually `http://10.0.2.2:5000` for Android emulator or `http://<YOUR_PC_IP>:5000` for physical devices).
    - Update it to match your Flask server's address.

4.  Run the app:
    - **Emulator**:
        ```bash
        flutter run
        ```
    - **Physical Device**: Connect via USB, enable debugging, and run:
        ```bash
        flutter run
        ```

## Troubleshooting

-   **Database Errors**:
    -   **SQLite**: Ensure folder permissions allow creating files.
    -   **MySQL**: Ensure MySQL service is running and credentials in `database.py` are correct.
-   **Connection Refused (Mobile)**:
    -   If using Emulator: Use `http://10.0.2.2:5000`.
    -   If using Physical Device: Ensure phone and PC are on the *same Wi-Fi*. Use PC's IP address (e.g., `192.168.x.x`). Check firewall settings.
-   **Mediapipe Errors**: Ensure your Python version is compatible with Mediapipe (Python 3.8-3.11 recommended).
