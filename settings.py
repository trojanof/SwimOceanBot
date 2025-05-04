import os
import ast
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('TOKEN')
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
WORKSHEET_NAME = os.getenv('WORKSHEET_NAME')
user_column_map = ast.literal_eval(os.getenv('USER_COLUMN_MAP'))  # magic преобразование строки в словарь
SCOPE = ast.literal_eval(os.getenv('SCOPE'))  # Google Sheets API credentials
