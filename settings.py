import json
import streamlit as st

TOKEN = st.secrets['TOKEN']
SPREADSHEET_ID = st.secrets['SPREADSHEET_ID']
user_column_map = json.loads(st.secrets['user_column_map'])
WORKSHEET_NAME = 'МетрыV2'
SCOPE = ['https://www.googleapis.com/auth/spreadsheets']