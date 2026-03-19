# Setup Guide for New PC

Follow these steps to run the AI Intruder Alert System on a new computer.

## 1. Install Software
1.  **Instal Python**: Download and install Python 3.10 or 3.11 from [python.org](https://www.python.org/downloads/).
    *   **IMPORTANT**: Check the box "Add Python to PATH" during installation.
2.  **Install Git** (Optional): If you want to use git commands.

## 2. Setup the Project
1.  Unzip the project folder to a location (e.g., `Desktop\IntruderSystem`).
2.  Open a terminal (Command Prompt or PowerShell) in that folder.

## 3. Install Dependencies
Run this command to install all required libraries:
```bash
pip install -r requirements.txt
```
*This may take a few minutes as it downloads TensorFlow and other heavy libraries.*

## 4. Run the Server
1.  Find your new PC's IP address:
    *   Run `ipconfig` in the terminal.
    *   Look for "IPv4 Address" (e.g., `192.168.1.XX`).
2.  Start the server:
    ```bash
    python app.py
    ```
3.  Allow access if Windows Firewall asks.

## 5. Connect the App
1.  **Crucial Step**: Since your IP address changed, the mobile app needs to know.
    *   You will need to reinstall the app with the new IP, OR...
    *   (If you added an IP settings screen, simply update it there).
    *   *If the app is hardcoded*: You must open the `mobile_app` folder in VS Code, update `lib/main.dart` with the new IP, and run `flutter run --release` with your phone connected.

## Troubleshooting
*   **"No module named..."**: Run `pip install [missing_module_name]`.
*   **Camera not working**: Ensure no other app is using the webcam.
