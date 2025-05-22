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
def write_to_sheet(value, usr_name, date):
    try:
        client = get_gsheet_client()
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
        """Ищем строку с указанной датой"""
        dates = sheet.col_values(1)  # Получаем все даты из столбца A (он с датами)

        usr_name = user_column_map[usr_name]  # вытаскиваем из словаря Имя пользователя по его tg-id
        col_names = sheet.row_values(1)  # список всех имен пользователей
        col_index = col_names.index(usr_name) + 1
        row_num = dates.index(date) + 1  # +1 т.к. нумерация с 1
        sheet.update_cell(row_num, col_index, value)  # добавляем в последнюю ячейку определенного столбца данные
        print(f'Value "{value}" appended to sheet')

    except Exception as e:
        print(f'An error occurred: {e}')


# Проверка есть ли ID пользователя в общей базе
def get_user_key(message):
    if message.from_user.username:
        username = message.from_user.username
        if username in user_column_map.keys():
            return username
        else:
            return None
    elif message.from_user.id:
        user_id = message.from_user_id
        if user_id in user_column_map.keys():
            return user_id
        else:
            return None
    else:
        user_frst_name = message.from_user.first_name
        if user_frst_name in user_column_map.keys():
            return user_frst_name
        else:
            return None


def plus_message_handling(message):
    return message.text.startswith('+')


def plus_data_message_handing(message):
    return plus_message_handling(message) and message.text.split()[0][1:].isdigit() and len(message.text.split()) == 2


# Обработчик сообщений вида: +метры дата_куда_нужно_записать_метры
@bot.message_handler(func=plus_data_message_handing)
def handle_number_with_data_message(message):
    number = message.text.split()[0][1:]
    date = str(message.text.split()[1])
    # Блок проверки валидности вводимой даты
    pattern_of_date = "%d.%m.%Y"  # паттерн правильной даты
    isValid = True
    try:
        isValid = bool(datetime.strptime(date, pattern_of_date))
    except ValueError:
        isValid = False
    if isValid:
        user_key = get_user_key(message)
        if user_key:
            print(f'ID пользователя, который ввел данные: {user_key}')
            write_to_sheet(number, user_key, date)  # записываем число в таблицу
            bot.reply_to(message, f'Число {number} было записано в дату: {date}')
            bot.set_message_reaction(chat_id=message.chat.id,
                                     message_id=message.id,
                                     reaction=[ReactionTypeEmoji("✍")]
                                     )
        else:
            bot.reply_to(message, "Вас нет в таблице или вашего ID нет в общей базе")
    else:
        bot.set_message_reaction(chat_id=message.chat.id,
                                 message_id=message.id,
                                 reaction=[ReactionTypeEmoji("👎")])
        bot.reply_to(message, 'Дата введена неверно, ознакомьтесь с инструкцией в /help')


# Обработчик сообщений, начинающихся с "+" и числа
@bot.message_handler(func=plus_message_handling)
def handle_number_message(message):
    number = message.text[1:]
    if plus_message_handling(message) and message.text[1:].isdigit():
        """
        Извлекаем дату сообщения. Дата в формате unix timestamp. Прибавляем 18000 = 5 часов т.к. дата хранится в GMT+0
        """
        date_obj = datetime.fromtimestamp(message.date + 18000)  # Преобразовываем дату из unix timestamp в datetime obj
        date = date_obj.strftime("%d.%m.%Y")  # преобразуем в нормальный формат -> "13.04.2025"
        user_key = get_user_key(message)
        if user_key:
            print(f'ID пользователя, который ввел данные: {user_key}')
            write_to_sheet(number, user_key, date)  # записываем число в таблицу

            bot.set_message_reaction(chat_id=message.chat.id,
                                     message_id=message.id,
                                     reaction=[ReactionTypeEmoji("✍")]
                                     )
        else:
            bot.reply_to(message, "Вас нет в таблице или вашего ID нет в общей базе")
    else:
        bot.set_message_reaction(chat_id=message.chat.id,
                                 message_id=message.id,
                                 reaction=[ReactionTypeEmoji("👎")])
        bot.reply_to(message, 'Команда введена неверно, ознакомьтесь с инструкцией в /help')


# Обработчик команды /start
@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.reply_to(message, "Привет! Я бот, который следит, чтобы все проплытые метры были учтены в наших заплывах! "
                          "Чтобы увидеть список команд, которые я понимаю, и формат, "
                          "в котором нужно записывать метры, введите команду /help")


# Обработчик команды /help
@bot.message_handler(commands=['help'])
def handle_help(message):
    bot.reply_to(message, "Расстояние нужно писать исключительно в виде метров.\n"
                          "Список команд и правил записи:\n\n"
                          "+<кол-во_метров> - записать метры (пример: +1000)\n"
                          "+<кол-во_метров дата> - записать в конкретную дату\n (пример: +100 19.04.2025)\n"
                          "")


# Запуск бота
if __name__ == '__main__':
    st.write('Bot is running...')
    bot.polling(none_stop=True)
    st.stop()
