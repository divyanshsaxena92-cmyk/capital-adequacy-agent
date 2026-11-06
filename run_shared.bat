@echo off
REM Share the app with colleagues on the same office network / VPN.
REM They open:  http://<this-computer's-IP>:8501   (run "ipconfig" to see the IPv4 address)
REM The app stays available only while this window is open.
cd /d "%~dp0"
python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true
pause
