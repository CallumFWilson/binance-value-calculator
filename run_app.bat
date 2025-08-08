@echo off
CALL C:\Users\YOURUSERNAME\anaconda3\Scripts\activate.bat
CALL conda activate streamlit-env
streamlit run streamlit_app.py
pause
