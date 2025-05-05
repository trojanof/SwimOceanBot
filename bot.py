import json
from tempfile import TemporaryDirectory
from pathlib import Path
import streamlit as st
import telebot
from telebot.types import ReactionTypeEmoji
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from settings import TOKEN, SPREADSHEET_ID, WORKSHEET_NAME, user_column_map, SCOPE
from datetime import datetime

# Инициализация бота
bot = telebot.TeleBot(TOKEN)


# /todo добавить логгирование бота


# Функция для подключения к Google Sheets
def get_gsheet_client():
    cred_str = st.secrets['CREDS']
    creds_obj = json.loads(cred_str)
    tmp_dir = TemporaryDirectory()
    tmp_dir_path = Path(tmp_dir.name)
    json_path = tmp_dir_path / 'creds.json'
    with open(json_path, 'w') as f:
        f.write(json.dumps(creds_obj, indent=2))
    creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, SCOPE)
    client = gspread.authorize(creds)
    tmp_dir.cleanup()
    return client


# Функция для записи данных в Google Sheets
def write_to_sheet(value, usr_id, date):
    """Берем текущую дату"""
    if date == "":
        date = datetime.now().strftime("%d.%m.%Y")  # -> "13.04.2025"

    try:
        client = get_gsheet_client()
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
        """Ищем строку с указанной датой"""
        dates = sheet.col_values(1)  # Получаем все даты из столбца A (он с датами)
        if user_column_map[usr_id]:
            usr_name = user_column_map[usr_id]  # вытаскиваем из словаря Имя пользователя по его tg-id
            col_names = sheet.row_values(1)  # список всех имен пользователей
            col_index = col_names.index(usr_name) + 1
            row_num = dates.index(date) + 1  # +1 т.к. нумерация с 1
            sheet.update_cell(row_num, col_index, value)  # добавляем в последнюю ячейку определенного столбца данные
            print(f'Value "{value}" appended to sheet')

    except Exception as e:
        print(f'An error occurred: {e}')


def plus_message_handling(message):
    return message.text.startswith('+') and message.text[1:].isdigit()


# Обработчик сообщений, начинающихся с "+" и числа
# /todo проверять формат метров
@bot.message_handler(func=plus_message_handling)
def handle_number_message(message):
    number = message.text[1:]
    if plus_message_handling(message):
        user_id = str(message.from_user.id)
        date = ""
        print(f'ID пользователя, который ввел данные: {user_id}')
        write_to_sheet(number, user_id, date)  # записываем число в таблицу

        bot.set_message_reaction(chat_id=message.chat.id,
                                 message_id=message.id,
                                 reaction=[ReactionTypeEmoji("✍")]
                                 )
    else:
        bot.set_message_reaction(chat_id=message.chat.id,
                                 message_id=message.id,
                                 reaction=[ReactionTypeEmoji("❌")])
        bot.reply_to(message, 'Данные введены неверно, ознакомьтесь с инструкцией в /help')


def plus_data_message_handing(message):
    return message.text.startswith('+') and message.text.split()[0][1:].isdigit() and len(message.text.split()) == 2


# Обработчик сообщений вида: +метры дата_куда_нужно_записать_метры
@bot.message_handler(func=plus_data_message_handing)
def handle_number_with_data_message(message):
    number = message.text.split()[0][1:]
    date = str(message.text.split()[1])  # ToDo проверять формат даты
    user_id = str(message.from_user.id)
    print(f'ID пользователя, который ввел данные: {user_id}')
    write_to_sheet(number, user_id, date)  # записываем число в таблицу
    # list_of_data.append(number)  # добавляем число в список
    # count_of_dist += int(number)  # увеличиваем общий счетчик
    bot.reply_to(message, f'Number {number} has been recorded on the date {date}')
    bot.set_message_reaction(chat_id=message.chat.id,
                             message_id=message.id,
                             reaction=[ReactionTypeEmoji("✍")]
                             )


# Обработчик команды /start
@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.reply_to(message, "Привет! Я бот, который записывает метры, которые вы проплыли, в таблицу."
                          "Чтобы увидеть список команд, которые я понимаю, и формат, "
                          "в котором нужно записывать метры, введите команду /help")


# /todo Доделать обработчик команды help, докидать команд
# Обработчик команды /help
@bot.message_handler(commands=['help'])
def handle_help(message):
    bot.reply_to(message, "Расстояние нужно писать исключительно в виде метров\n"
                          "Список команд и правил записи:\n"
                          "+<кол-во_метров> - записать метры (пример: +1000)\n"
                          "+<кол-во_метров дата> - записать в конкретную дату (пример: +100 19.04.2025)\n"
                          "")


# Запуск бота
if __name__ == '__main__':
    st.write('Bot is running...')
    bot.polling(none_stop=True)
    st.stop()
