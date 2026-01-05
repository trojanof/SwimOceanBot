import json
import pytz
from io import BytesIO
from tempfile import TemporaryDirectory
from pathlib import Path
import streamlit as st
from streamlit_folium import folium_static
import pandas as pd
import matplotlib.pyplot as plt
import telebot
from telebot.types import ReactionTypeEmoji
from telebot.types import (InlineKeyboardMarkup, InlineKeyboardButton,
                           WebAppInfo, ReplyKeyboardMarkup, KeyboardButton)
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from map import prepare_map
from settings import (
    TOKEN, SPREADSHEET_ID, WORKSHEET_NAME, user_column_map, SCOPE, START_DATE,
    LOCATIONS_SHEET_NAME, DEFAULT_START_CAPTION, DEFAULT_FINISH_CAPTION
)
from datetime import datetime, timezone, timedelta

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


def get_df_from_google_sheet(sheet_name):
    client = get_gsheet_client()
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(sheet_name)
    data = sheet.get_all_values()
    df = pd.DataFrame(data, columns=data[0])[1:]
    return df


def get_distance_at_day(day):
    '''
    Get distance value from table on requested day
    Distance in meters
    '''
    df = get_df_from_google_sheet(WORKSHEET_NAME)
    df['Date'] = pd.to_datetime(df['Date'], dayfirst=True)
    df['Cumulative_sum'] = df['Cumulative_sum'].replace('', None)
    df['Cumulative_sum'] = df['Cumulative_sum'].ffill()
    df['Cumulative_sum'] = df['Cumulative_sum'].astype(int)
    dist = df[df['Date'] == day]['Cumulative_sum'].values[0]
    return dist


def get_location(dist):
    '''
    Get location table and an index corresponding to the
    next destination location, i.e. returns df, ind, such that
    df[ind] is a row describing next destination
    '''
    df = get_df_from_google_sheet(LOCATIONS_SHEET_NAME)
    df['Cumul_dist'] = df['Cumul_dist'].replace('', 0)
    df['Cumul_dist'] = df['Cumul_dist'].astype(int)
    next_df = df[df['Cumul_dist'] > dist]
    ind = next_df[next_df['Cumul_dist'] == next_df['Cumul_dist'].min()].index
    return df, ind


def get_statistics_for_period(start_date: str, end_date: str):
    """
    Возвращает статистики за выбранный период
    """
    df = get_df_from_google_sheet(WORKSHEET_NAME)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.set_index('Date')

    for col in df.columns:
        df[col] = df[col].replace('', 0)
        df[col] = df[col].fillna(0)
        df[col] = df[col].astype(float)

    df = df.reset_index()
    start_date = pd.to_datetime(start_date, dayfirst=True)
    end_date = pd.to_datetime(end_date, dayfirst=True)
    period_df = df[df['Date'].between(start_date, end_date)]
    period_df = period_df.set_index('Date')
    period_df = period_df.drop(['Day_distance', 'Cumulative_sum'], axis=1)
    return period_df


def get_sum_for_period(df):
    sum_df = df.sum().to_frame().reset_index()
    sum_df = sum_df.rename(columns={0: 'sum', 'index': 'people'})
    sum_df = sum_df.sort_values(by='sum', ascending=False)
    sum_df = sum_df[sum_df['sum'] > 0]

    min_date = df.index.min().strftime("%d.%m.%Y")
    max_date = df.index.max().strftime("%d.%m.%Y")

    sum_df = sum_df[sum_df['sum'] > 0]
    fig, ax = plt.subplots(figsize=(12, 6))
    fig.subplots_adjust()
    bar_container = ax.bar(x=sum_df['people'],
                           height=sum_df['sum'],
                           width=0.6,
                           color='green'
                           )
    ax.bar_label(bar_container)
    ax.set(ylabel='Метраж',
           title=f'Метры за период {min_date} - {max_date}'
           )
    ax.tick_params(axis='x', labelrotation=90)

    tmp_dir = TemporaryDirectory()
    tmp_dir_path = Path(tmp_dir.name)
    img_path = tmp_dir_path / 'sum.png'
    fig.savefig(img_path, bbox_inches='tight')

    with open(img_path, 'rb') as file:
        img_data = file.read()

    # Создаем BytesIO объект
    img = BytesIO(img_data)
    tmp_dir.cleanup()
    return img


# Функция для записи данных в Google Sheets
def write_to_sheet(value, usr_name, date):
    try:
        client = get_gsheet_client()
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
        """Ищем строку с указанной датой"""
        # Получаем все даты из столбца A (он с датами):
        dates = sheet.col_values(1)

        # вытаскиваем из словаря Имя пользователя по его tg-id:
        usr_name = user_column_map[usr_name]
        col_names = sheet.row_values(1)  # список всех имен пользователей
        col_index = col_names.index(usr_name) + 1
        row_num = dates.index(date) + 1  # +1 т.к. нумерация с 1

        # добавляем в последнюю ячейку определенного столбца данные:
        sheet.update_cell(row_num, col_index, value)
        print(f'Value "{value}" appended to sheet')

    except Exception as e:
        print(f'An error occurred: {e}')


# Проверка есть ли ID пользователя в общей базе
def get_user_key(message):
    if message.from_user.id:
        user_id = str(message.from_user.id)
        if user_id in user_column_map.keys():
            return user_id
    if message.from_user.username:
        username = message.from_user.username
        if username in user_column_map.keys():
            return username
    else:
        user_frst_name = message.from_user.first_name
        if user_frst_name in user_column_map.keys():
            return user_frst_name
        else:
            return None


def is_date_valid(input_date_str):
    user_date = datetime.strptime(input_date_str, "%d.%m.%Y").date()
    now_utc = datetime.now(timezone.utc)
    # Добавляем смещение +5 часов и округляем до дня
    today = (now_utc + timedelta(hours=5)).date()
    return user_date <= today


def plus_message_handling(message):
    return message.text.startswith('+')


def plus_data_message_handing(message):
    result = (plus_message_handling(message) and
              message.text.split()[0][1:].isdigit() and
              len(message.text.split()) == 2)
    return result


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
    if isValid and is_date_valid(date):
        user_key = get_user_key(message)
        if user_key:
            print(f'ID пользователя, который ввел данные: {user_key}')
            # записываем число в таблицу:
            write_to_sheet(number, user_key, date) 
            bot.reply_to(message,
                         f'Число {number} было записано в дату: {date}')
            bot.set_message_reaction(chat_id=message.chat.id,
                                     message_id=message.id,
                                     reaction=[ReactionTypeEmoji("✍")]
                                     )
        else:
            bot.reply_to(message,
                         "Вас нет в таблице или вашего ID нет в общей базе")
    else:
        bot.set_message_reaction(chat_id=message.chat.id,
                                 message_id=message.id,
                                 reaction=[ReactionTypeEmoji("👎")])
        msg = 'Дата введена неверно, ознакомьтесь с инструкцией в /help'
        bot.reply_to(message, msg)


# Обработчик сообщений, начинающихся с "+" и числа
@bot.message_handler(func=plus_message_handling)
def handle_number_message(message):
    number = message.text[1:]
    if plus_message_handling(message) and message.text[1:].isdigit():
        """
        Извлекаем дату сообщения. Дата в формате unix timestamp.
        Прибавляем 18000 = 5 часов т.к. дата хранится в GMT+0
        """
        # Преобразовываем дату из unix timestamp в datetime obj:
        date_obj = datetime.fromtimestamp(message.date + 18000)

        # преобразуем в нормальный формат -> "13.04.2025":
        date = date_obj.strftime("%d.%m.%Y")
        user_key = get_user_key(message)
        if user_key:
            print(f'ID пользователя, который ввел данные: {user_key}')
            # записываем число в таблицу:
            write_to_sheet(number, user_key, date)

            bot.set_message_reaction(chat_id=message.chat.id,
                                     message_id=message.id,
                                     reaction=[ReactionTypeEmoji("✍")]
                                     )
        else:
            msg = ("Вас нет в таблице или вашего ID нет в общей базе. "
                   "Обратитесь к администратору бота")
            bot.reply_to(message, msg)
    else:
        bot.set_message_reaction(chat_id=message.chat.id,
                                 message_id=message.id,
                                 reaction=[ReactionTypeEmoji("👎")])
        msg = 'Команда введена неверно, ознакомьтесь с инструкцией в /help'
        bot.reply_to(message, msg)


# Обработчик команды /start
@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.reply_to(message, "Привет! Я бот клуба SwimOcean, который следит, чтобы все проплытые метры были учтены в "
                          "наших заплывах! "
                          "Чтобы увидеть список команд, которые я понимаю, и формат, "
                          "в котором нужно записывать метры, введите команду /help")


# Обработчик команды /help
@bot.message_handler(commands=['help'])
def handle_help(message):
    bot.reply_to(message, "Расстояние нужно писать исключительно в виде метров.\n"
                          "Запись в даты в будущем невозможна.\n"
                          "Список команд и правил записи:\n\n"
                          "+<кол-во_метров> - записать метры (пример: +1000)\n"
                          "+<кол-во_метров дата> - записать в прошедшую дату\n (пример: +100 19.04.2025)\n\n"
                          "Существующие команды:\n"
                          "/start - вызов стартового сообщения\n"
                          "/help - вызов справки\n"
                          "/stat_my - вывод персональной статистики за весь период по месяцам\n"
                          "/stat_all - показ общей статистики")


def get_month_name(month_number):
    months = ['', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
              'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
    return months[month_number]


def create_mobile_table(data, title):
    # Используем компактную горизонтальную таблицу
    lines = [title, ""]
    for row in data:
        line = " │ ".join(f"{str(cell):^8}" for cell in row)
        lines.append(line)
        if row == data[0]:  # После заголовка
            lines.append("─" * (len(line) - 1))
    return f"<pre>{chr(10).join(lines)}</pre>"


# Персональная статистика
@bot.message_handler(commands=['stat_my'])
def handle_pstat(message):
    user_key = get_user_key(message)
    if user_key:
        user_name = user_column_map[user_key]
        start_date = pd.to_datetime(START_DATE, dayfirst=True)
        today = datetime.now().date().strftime("%d.%m.%Y")
        today = pd.to_datetime(today, dayfirst=True)

        period_df = get_statistics_for_period(start_date=start_date,
                                              end_date=today)

        sum_by_month = period_df[[user_name]].copy()
        sum_by_month = sum_by_month.groupby(pd.Grouper(axis=0, freq='m')).sum()
        count_by_month = period_df[[user_name]].copy()
        count_by_month = count_by_month.replace(0, None).groupby(pd.Grouper(
            axis=0, freq='m'
            )).count()

        merged_df = pd.merge(left=sum_by_month, right=count_by_month, on='Date')
        merged_df = merged_df.reset_index()
        merged_df['Date'] = merged_df['Date'].apply(
            lambda x: get_month_name(x.month)
            )

        data = [['Месяц', 'Объём, м', 'Кол-во']]
        data.extend(merged_df.values.tolist())

        # table = f"```\n{create_table(data, user_name)}\n```"
        result = create_mobile_table(data, user_name)
        bot.send_message(message.chat.id, result, parse_mode='HTML')
    else:
        msg = ("Вас нет в таблице или вашего ID нет в общей базе. "
               "Обратитесь к администратору бота")
        bot.reply_to(message, msg)


# Общая статистика
@bot.message_handler(commands=['stat_all'])
def handle_all_stat(message):
    start_date = pd.to_datetime(START_DATE, dayfirst=True)
    today = datetime.now().date().strftime("%d.%m.%Y")
    today = pd.to_datetime(today, dayfirst=True)
    period_df = get_statistics_for_period(start_date=start_date,
                                          end_date=today)
    img = get_sum_for_period(period_df)
    bot.send_photo(chat_id=message.chat.id,
                   photo=img,
                   caption='Общая статистика')


@bot.message_handler(commands=['map2'])
def open_web_app(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton(
        "Посмотреть где мы плывём",
        web_app=WebAppInfo(url="https://swimocean.streamlit.app/")
    ))
    bot.send_message(message.chat.id,
                     "Чтобы посмотреть где мы плывем воспользуйтесь кнопкой из меню",
                     reply_markup=markup)


def map_only():
    tz = pytz.timezone('Asia/Yekaterinburg')
    today = datetime.now(tz).date().strftime("%d.%m.%Y")
    today = pd.to_datetime(today, dayfirst=True)
    # st.session_state.map = None

    overall_distance = get_distance_at_day(today)
    df, ind = get_location(overall_distance)
    if ind == df.index.min():
        current_dist = overall_distance
    else:
        current_dist = overall_distance - df.loc[ind-1, 'Cumul_dist'].values[0]

    start_coord = df.loc[ind, 'Start_point'].values[0].split(',')
    finish_coord = df.loc[ind, 'Finish_point'].values[0].split(',')
    start_coord = [float(i) for i in start_coord]
    finish_coord = [float(i) for i in finish_coord]

    dist = int(df.loc[ind, 'Distance'].values[0])

    start_caption = df.loc[ind, 'Start_caption'].values[0]
    finish_caption = df.loc[ind, 'Finish_caption'].values[0]
    if start_caption:
        start_caption = DEFAULT_START_CAPTION + ': ' + start_caption
    else:
        start_caption = DEFAULT_START_CAPTION
    if finish_caption:
        finish_caption = DEFAULT_FINISH_CAPTION + ': ' + finish_caption
    else:
        finish_caption = DEFAULT_FINISH_CAPTION
    description = df.loc[ind, 'Description'].values[0]
    st.write(description)
    map = prepare_map(start_coord,
                      finish_coord,
                      start_caption,
                      finish_caption,
                      dist,
                      distance_travelled=current_dist)
    folium_static(map, width=600)
    return map


# Запуск бота
if __name__ == '__main__':
    st.write('Bot is running...')
    map_only()
    st.write('text')
    bot.polling(none_stop=True)
    st.stop()
