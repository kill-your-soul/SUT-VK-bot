import os
import logging
import re
import pymysql
from collections import defaultdict
from datetime import time, datetime, timedelta
from typing import Optional

from dateutil.relativedelta import relativedelta
from vkbottle import Callback, GroupEventType, Keyboard, Text, BaseStateGroup, KeyboardButtonColor
from vkbottle.bot import Bot, Message, MessageEvent, rules

bot = Bot(os.environ.get('token'))

logging.basicConfig(level=logging.INFO)
bot.labeler.message_view.replace_mention = True


class User:
    def __init__(self, surname="", name="", patronymic="", group="", vk_id="", is_admin=False, black_list=False):
        self.surname = surname
        self.name = name
        self.patronymic = patronymic
        self.group = group
        self.vk_id = vk_id
        self.is_admin = is_admin
        self.black_list = black_list

    def __eq__(self, other):
        if isinstance(other, User):
            return (self.surname, self.name, self.patronymic, self.group, self.vk_id, self.is_admin, self.black_list) == (
            other.surname, other.name, other.patronymic, other.group, other.vk_id, other.is_admin, other.black_list)
        return False

    def __hash__(self):
        return hash((self.surname, self.name, self.patronymic, self.group, self.vk_id, self.is_admin, self.black_list))

    def __ne__(self, other):
        return not (self == other)

    def __str__(self):
        fio = self.surname + " " + self.name + " " + self.patronymic
        if (self.is_admin):
            return f"Администратор:\nФИО: {fio}\nГруппа: \"{self.group}\"\nВК id: \"{self.vk_id}\""
        return f"Пользователь:\nФИО: {fio}\nГруппа: \"{self.group}\"\nВК id: \"{self.vk_id}\""


class Lecture:
    def __init__(self, date=datetime.now(), name="", descr=""):
        self.date = date
        self.name = name
        self.descr = descr

    def __eq__(self, other):
        if isinstance(other, Lecture):
            return (self.date, self.name, self.descr) == (other.date, other.name, other.descr)
        return False

    def __hash__(self):
        return hash((self.date, self.name, self.descr))

    def __ne__(self, other):
        return not (self == other)

    def __str__(self):
        return f"\nДата: {self.date}\nНазвание: \"{self.name}\"\nОписание: \"{self.descr}\""


LECTIONS_DRAFTS = defaultdict(Lecture)
USER_DRAFTS = defaultdict(User)


class States(BaseStateGroup):
    LECTIONS_REGISTRATION_DATE = "lections_registration_date"
    LECTIONS_REGISTRATION_TIME = "lections_registration_time"
    LECTIONS_REGISTRATION_NAME = "lections_registration_name"
    LECTIONS_REGISTRATION_DESCR = "lections_registration_descr"
    LECTIONS_BOOKING = "lections_registration_booking"
    LECTIONS_APPROVING = "lections_admin_approving"
    USER_REGISTRATION_F = "user_registration_f"
    USER_REGISTRATION_I = "user_registration_i"
    USER_REGISTRATION_O = "user_registration_o"
    USER_REGISTRATION_GROUP = "user_registration_group"
    COWORKING = "coworking"
    COMMON = "common"


TIME_SLOTS = [(9, 11), (11, 13), (13, 15), (15, 17), (17, 19)]
LECTION_TIMES = [time(9), time(11), time(13), time(15), time(17)]

DEFAULT_USER_KEYBOARD = (
    Keyboard(one_time=False, inline=False)
    .add(Text("Лекториум", {"btn": "lections"}))
    .row()
    .add(Text("Коворкинг", {"btn": "coworking"}))
    .row()
    .add(Text("Мои записи", {"btn": "statuses"}))
    .get_json()
)
DEFAULT_ADMIN_KEYBOARD = (
    Keyboard(one_time=False, inline=False)
    .add(Text("Лекториум", {"btn": "lections"}))
    .row()
    .add(Text("Коворкинг", {"btn": "coworking"}))
    .row()
    .add(Text("Мои записи", {"btn": "statuses"}))
    .row()
    .add(Text("Заявки на лекции", {"btn": "lections_waiting_approval"}), color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Text("Статус коворкинга", {"btn": "admin_coworking"}), color=KeyboardButtonColor.PRIMARY)
    # .row()
    # .add(Text("Добавить пользователя в черный список", {"btn": "black_list"}), color=KeyboardButtonColor.PRIMARY)
    .get_json()
)

conn = pymysql.connect(
    host='localhost',
    user='root',
    password="1q2w!Q@W",
    db='test',
)

def sendUserDraftToDatabase(from_id):
    user = USER_DRAFTS.pop(from_id)
    if user.is_admin:
        is_admin = 1
    else:
        is_admin = 0
    conn.cursor().execute(
    f"INSERT INTO user (`surname`, `name`, `patrynomic`, `group`, `vk_id`, `is_admin`) "
    f"VALUES ('{user.surname}', '{user.name}', '{user.patronymic}', '{user.group}', '{from_id}', '{is_admin}')")
    conn.commit()


def sendLectionDraftToDatabase(from_id):
    lection = LECTIONS_DRAFTS.pop(from_id)
    conn.cursor().execute(
        f"INSERT INTO lections (`vk_id`, `date`, `name`, `description`) "
        f"VALUES ('{from_id}', '{lection.date.isoformat(sep=' ', timespec='microseconds')}', '{lection.name}', '{lection.descr}')")
    conn.commit()

def getStatuses(from_id):
    date = datetime.now()
    timeMinus29min = date - timedelta(hours=0, minutes=29)
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT * FROM lections "
        f"WHERE date >= '{timeMinus29min}' and find_in_set('{from_id}', students)")
    output = cursor.fetchall()
    formatted_output = ""
    for lection in output:
        formatted_output += f"ID лекции: {lection[0]}\n" + lection[2][:-10] + " " + lection[3] + " " + lection[4] + "\n"
    cursor.execute(
        f"SELECT * FROM coworking "
        f"WHERE date >= '{timeMinus29min}' and find_in_set('{from_id}', students)")
    output = cursor.fetchall()
    for coworking in output:
        formatted_output += "Коворкинг: " + coworking[1][:-10] + "\n"
    return formatted_output

def getLections():
    date = datetime.now()
    timeMinus29min = date - timedelta(hours=0, minutes=29)
    timePlus1month = date + relativedelta(months=1)
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT * FROM lections "
        f"WHERE date >= '{timeMinus29min}' and date <= '{timePlus1month}' and isApproved = '1'")
    output = cursor.fetchall()
    filtered_output = {}
    for i in output:
        if i[5] is None or len(i[5].split(',')) < 30:
            filtered_output[str(i[0])] = i
    return filtered_output

def getLectionsWaitingApproval():
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT * FROM lections "
        f"WHERE isApproved = '0'")
    output = cursor.fetchall()
    formatted_output = {}
    for i in output:
        formatted_output[str(i[0])] = i
    return formatted_output

def getClosestAvailableDatesForLections():
    cursor = conn.cursor()
    date = datetime.now()

    cursor.execute(
        f"SELECT * FROM lections "
        f"WHERE date >= '{date}'")
    output = cursor.fetchall()
    lection_dates = defaultdict(int)
    lection_dates[date.date()] = sum(i < date.time() for i in LECTION_TIMES)
    for i in output:
        lection_dates[datetime.strptime(i[2], "%Y-%m-%d %H:%M:%S.%f").date()] += 1
    from_db_not_available = {key: val for key, val in lection_dates.items() if val >= 5}

    i = 0
    while True:
        closest_day = (date + timedelta(days=i)).date()
        if closest_day not in from_db_not_available:
            return closest_day
        i += 1

def getTimesIfAvailableForLection(date):
    temp_lection_times = LECTION_TIMES.copy()
    cursor = conn.cursor()
    timePlus1day = date + timedelta(days=1)

    cursor.execute(
        f"SELECT * FROM lections "
        f"WHERE date >= '{date}' and date <= '{timePlus1day}' and isApproved = '1'")
    output = cursor.fetchall()
    for i in output:
        temp_lection_times.remove(datetime.strptime(i[2], "%Y-%m-%d %H:%M:%S.%f").time())
    return temp_lection_times

def getAvailableForCoworking(accepted_times):
    date = datetime.now()
    timeMinus29min = date - timedelta(hours=0, minutes=29)
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT * FROM coworking "
        f"WHERE date >= '{timeMinus29min}' LIMIT 3")
    output = cursor.fetchall()
    for i in output:
        if i[2] is not None and len(i[2].split(',')) >= 35:
            accepted_times.pop(datetime.strptime(i[2], "%Y-%m-%d %H:%M:%S.%f").hour)
    return accepted_times

def getAvailableForAdminCoworking(time):
    cursor = conn.cursor()
    date = datetime.now()
    timeMinus29min = date - timedelta(hours=0, minutes=29)
    slotStartTime = datetime.now().replace(hour=time, minute=0, second=0, microsecond=0)
    if timeMinus29min.hour > time:
        slotStartTime = slotStartTime + timedelta(days=1)
    cursor.execute(
        f"SELECT * FROM coworking "
        f"WHERE date = '{slotStartTime.isoformat(sep=' ', timespec='microseconds')}'")
    output = cursor.fetchall()
    if len(output) == 0 or output[0][2] is None:
        return None
    else:
        return output[0][2].split(',')

def sendCoworkingToDatabase(from_id, time):
    cursor = conn.cursor()
    date = datetime.now()
    timeMinus29min = date - timedelta(hours=0, minutes=29)
    slotStartTime = datetime.now().replace(hour=time, minute=0, second=0, microsecond=0)
    if timeMinus29min.hour > time:
        slotStartTime = slotStartTime + timedelta(days=1)
    cursor.execute(
        f"SELECT * FROM coworking "
        f"WHERE date = '{slotStartTime.isoformat(sep=' ', timespec='microseconds')}'")
    output = cursor.fetchall()
    if len(output) == 0:
        conn.cursor().execute(
            f"INSERT INTO `coworking` (`date`, `students`) VALUES ('{slotStartTime.isoformat(sep=' ', timespec='microseconds')}', '{from_id}')")
        conn.commit()
        return True
    else:
        if output[0][2] is None:
            currentStudents = []
        else:
            currentStudents = output[0][2].split(',')
        if str(from_id) in currentStudents:
            return False
        else:
            currentStudents.append(str(from_id))
            newStudents = ','.join(currentStudents)
            conn.cursor().execute(
                f"UPDATE `coworking` SET `students` = '{newStudents}' WHERE (`id` = '{output[0][0]}')")
            conn.commit()
            return True

def sendCoworkingCancelToDatabase(from_id, time):
    cursor = conn.cursor()
    date = datetime.now()
    timeMinus29min = date - timedelta(hours=0, minutes=29)
    slotStartTime = datetime.now().replace(hour=time, minute=0, second=0, microsecond=0)
    if timeMinus29min.hour > time:
        slotStartTime = slotStartTime + timedelta(days=1)
    cursor.execute(
        f"SELECT * FROM coworking "
        f"WHERE date = '{slotStartTime.isoformat(sep=' ', timespec='microseconds')}'")
    output = cursor.fetchall()
    currentStudents = output[0][2].split(',')
    currentStudents.remove(str(from_id))
    if len(currentStudents) == 0:
        conn.cursor().execute(f"DELETE FROM `coworking` WHERE (`id` = '{output[0][0]}')")
    else:
        newStudents = ','.join(currentStudents)
        conn.cursor().execute(f"UPDATE `coworking` SET `students` = '{newStudents}' WHERE (`id` = '{output[0][0]}')")
    conn.commit()
    return True

def sendLectionBookingToDatabase(from_id, item):
    lections = getLections()
    if item in lections.keys():
        if lections[item][5] is None:
            currentStudents = []
        else:
            currentStudents = lections[item][5].split(',')
        if str(from_id) in currentStudents:
            return False
        else:
            currentStudents.append(str(from_id))
            newStudents = ','.join(currentStudents)
            conn.cursor().execute(
                f"UPDATE `lections` SET `students` = '{newStudents}' WHERE (`id` = '{item}')")
            conn.commit()
            return True
    else:
        return False


def sendLectionApproveToDatabase(item):
    lections = getLectionsWaitingApproval()
    if item in lections.keys():
        conn.cursor().execute(
            f"UPDATE `lections` SET `isApproved` = '1' WHERE (`id` = '{item}')")
        conn.commit()
        return True
    else:
        return False


def isAdmin(from_id):
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT is_admin FROM user WHERE vk_id=\"{from_id}\"")
    output = cursor.fetchall()
    print(type(output[0][0]))

    if output[0][0] == 1:
        return True
    return False

def isExists(from_id):
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT EXISTS(SELECT 1 FROM user WHERE vk_id=\"{from_id}\")")
    output = cursor.fetchall()
    if output[0][0] == 1:
        return True
    return False

@bot.on.private_message(state=States.USER_REGISTRATION_F, text="<item>")
async def user_registration_f(message: Message, item: Optional[str] = None):
    if item is None:
        await start_handler(message)
        await bot.state_dispenser.set(message.peer_id, States.COMMON)
    elif item == "elephant":
        await message.answer(f"Пароль принят, теперь Вам дарована власть админа!")
        await message.answer(f"А теперь давайте все-таки познакомимся. Ваша фамилия:")
        USER_DRAFTS[message.from_id].is_admin = True
    else:
        USER_DRAFTS[message.from_id].surname = item
        await message.answer(f"Введите ваше имя:")
        await bot.state_dispenser.set(message.peer_id, States.USER_REGISTRATION_I)


@bot.on.private_message(state=States.USER_REGISTRATION_I, text="<item>")
async def user_registration_i(message: Message, item: Optional[str] = None):
    if item is None:
        await start_handler(message)
        await bot.state_dispenser.set(message.peer_id, States.COMMON)
    else:
        USER_DRAFTS[message.from_id].name = item
        await message.answer(f"Введите ваше отчество:")
        await bot.state_dispenser.set(message.peer_id, States.USER_REGISTRATION_O)


@bot.on.private_message(state=States.USER_REGISTRATION_O, text="<item>")
async def user_registration_o(message: Message, item: Optional[str] = None):
    if item is None:
        await start_handler(message)
        await bot.state_dispenser.set(message.peer_id, States.COMMON)
    else:
        USER_DRAFTS[message.from_id].patronymic = item
        await message.answer(f"Введите номер группы: \nНапример - ИКПИ-05")
        await bot.state_dispenser.set(message.peer_id, States.USER_REGISTRATION_GROUP)


@bot.on.private_message(state=States.USER_REGISTRATION_GROUP, text="<item>")
async def user_registration_group(message: Message, item: Optional[str] = None):
    if item is None:
        await start_handler(message)
        await bot.state_dispenser.set(message.peer_id, States.COMMON)
    else:
        if re.match('\w{1,4}-\d{2}\w?', item):
            USER_DRAFTS[message.from_id].group = item
            USER_DRAFTS[message.from_id].vk_id = message.from_id
            await message.answer(f"Вы успешно зарегистрировались в системе!")
            await message.answer(str(USER_DRAFTS[message.from_id]))
            sendUserDraftToDatabase(message.from_id)
            await start_handler(message)
            await bot.state_dispenser.set(message.peer_id, States.COMMON)
        else:
            await message.answer(f"Некорректный номер группы. Попробуйте еще раз.\nЕсли не получается подобрать формат, уточните информацию у администратора")

@bot.on.private_message(payload={"btn": "statuses"})
async def statuses(message: Message):
    await message.answer("Ваши текущие записи:\n" + getStatuses(message.from_id))


@bot.on.private_message(payload={"btn": "lections"})
async def lections(message: Message):
    KEYBOARD = Keyboard(inline=True)
    KEYBOARD.add(Text("Записаться на посещение", {"cmd": "lections_available_list"})).row()
    KEYBOARD.add(Text("Подать заявку на проведение", {"cmd": "lections_registration"}))
    await message.answer("Вы вошли в раздел \"Лекториум\":", keyboard=KEYBOARD.get_json())


@bot.on.private_message(payload={"cmd": "lections_available_list"})
async def lections_available_list(message: Message):
    lections_available_list = getLections().values()
    if len(lections_available_list) != 0:
        await message.answer(f"На текущий момент доступные лекции:")
        lectionsStr = ""
        for lection in lections_available_list:
            lectionsStr += f"ID лекции: {lection[0]}\n" + lection[2][:-10] + " " + lection[3] + " " + lection[4] + "\n"
        await message.answer(lectionsStr)
        await message.answer(f"Для того чтобы записаться на лекцию - напишите её ID")
        await bot.state_dispenser.set(message.peer_id, States.LECTIONS_BOOKING)
    else:
        await message.answer(f"На текущий момент доступных лекций нет")

@bot.on.private_message(state=States.LECTIONS_BOOKING, text="<item>")
async def lections_booking(message: Message, item: Optional[str] = None):
    if item is None:
        await start_handler(message)
        await bot.state_dispenser.set(message.peer_id, States.COMMON)
    else:
        if (sendLectionBookingToDatabase(message.from_id, item)):
            await message.answer(f"Вы зарегистрированы на лекцию: {item}")
        else:
            await message.answer(
                "Невозможно записаться на лекцию, так как нет свободных мест, либо Вы уже проходили регистрацию")
        await start_handler(message)
        await bot.state_dispenser.set(message.peer_id, States.COMMON)


@bot.on.private_message(payload={"btn": "lections_waiting_approval"})
async def lections_waiting_approval(message: Message):
    lections_available_list = getLectionsWaitingApproval().values()
    if len(lections_available_list) != 0:
        await message.answer(f"На текущий момент лекции, ожидающие подтверждения:")
        lectionsStr = ""
        for lection in lections_available_list:
            lectionsStr += f"ID лекции: {lection[0]}\n" + lection[2][:-10] + " " + lection[3] + " " + lection[4] + "\n"
        await message.answer(lectionsStr)
        await message.answer(f"Для того чтобы заапрувить лекцию - напишите её ID")
        await bot.state_dispenser.set(message.peer_id, States.LECTIONS_APPROVING)
    else:
        await message.answer(f"На текущий момент лекций, ожидающих подтверждения нет")


@bot.on.private_message(state=States.LECTIONS_APPROVING, text="<item>")
async def lections_admin_approving(message: Message, item: Optional[str] = None):
    if item is None:
        await start_handler(message)
        await bot.state_dispenser.set(message.peer_id, States.COMMON)
    else:
        if (sendLectionApproveToDatabase(item)):
            await message.answer(f"Вы подтвердили лекцию: {item}")
        else:
            await message.answer(
                "Внутренняя ошибка. ПАНИКА! (Но скорее всего, что-то не то введено)")
        await start_handler(message)
        await bot.state_dispenser.set(message.peer_id, States.COMMON)

@bot.on.private_message(payload={"cmd": "lections_registration"})
async def lections_registration(message: Message):
    await message.answer(f"Введите дату лекции в формате \"дд.мм.гггг\"\nБлижайшая дата с доступными слотами - " + getClosestAvailableDatesForLections().strftime("%d.%m.%Y"))
    await bot.state_dispenser.set(message.peer_id, States.LECTIONS_REGISTRATION_DATE)


@bot.on.private_message(state=States.LECTIONS_REGISTRATION_DATE, text="<item>")
async def lections_registration2(message: Message, item: Optional[str] = None):
    if item is None:
        await start_handler(message)
        await bot.state_dispenser.set(message.peer_id, States.COMMON)
    else:
        try:
            if re.match('\d{2}\.\d{2}\.\d{4}', item):
                raw_date = item.split(".")
                date = datetime(day=int(raw_date[0]), month=int(raw_date[1]), year=int(raw_date[2]))
                available_times = getTimesIfAvailableForLection(date)
                if len(available_times) > 0:
                    LECTIONS_DRAFTS[message.from_id].date = date
                    times_str = ""
                    for time in available_times:
                        times_str += "\n"
                        times_str += time.strftime("%H:%M")
                    await message.answer(
                        f"Доступные слоты для проведения лекции: " + times_str + "\nВведите в формате \"чч:мм\"")
                    await bot.state_dispenser.set(message.peer_id, States.LECTIONS_REGISTRATION_TIME)
                else:
                    await message.answer(
                        f"В выбранную дату отсутствуют. Попробуйте еще раз.\nЕсли не получается подобрать формат, уточните информацию у администратора")
            else:
                await message.answer(
                    f"Некорректный формат даты. Попробуйте еще раз.\nЕсли не получается подобрать формат, уточните информацию у администратора")
        except ValueError:
            await message.answer(
                f"Некорректный формат даты. Попробуйте еще раз.\nЕсли не получается подобрать формат, уточните информацию у администратора")

@bot.on.private_message(state=States.LECTIONS_REGISTRATION_TIME, text="<item>")
async def lections_registration3(message: Message, item: Optional[str] = None):
    if item is None:
        await start_handler(message)
        await bot.state_dispenser.set(message.peer_id, States.COMMON)
    else:
        if re.match('\d{2}:00', item):
            hour = int(item.split(":")[0])
            available_times = getTimesIfAvailableForLection(LECTIONS_DRAFTS[message.from_id].date)
            if time(hour) in available_times:
                LECTIONS_DRAFTS[message.from_id].date = LECTIONS_DRAFTS[message.from_id].date.replace(hour=hour)
                await message.answer(f"Введите название лекции: ")
                await bot.state_dispenser.set(message.peer_id, States.LECTIONS_REGISTRATION_NAME)
            else:
                await message.answer(
                    f"Выбранное время отсутствует. Попробуйте еще раз.\nЕсли не получается подобрать формат, уточните информацию у администратора")
        else:
            await message.answer(
                f"Некорректный формат времени. Попробуйте еще раз.\nЕсли не получается подобрать формат, уточните информацию у администратора")


@bot.on.private_message(state=States.LECTIONS_REGISTRATION_NAME, text="<item>")
async def lections_registration4(message: Message, item: Optional[str] = None):
    if item is None:
        await start_handler(message)
        await bot.state_dispenser.set(message.peer_id, States.COMMON)
    else:
        if len(item) <= 45:
            LECTIONS_DRAFTS[message.from_id].name = item
            await message.answer(f"Введите описание лекции: ")
            await bot.state_dispenser.set(message.peer_id, States.LECTIONS_REGISTRATION_DESCR)
        else:
            await message.answer(
                f"Слишком много символов. Ограничение - 45 \nЕсли не получается подобрать формат, уточните информацию у администратора")


@bot.on.private_message(state=States.LECTIONS_REGISTRATION_DESCR, text="<item>")
async def lections_registration5(message: Message, item: Optional[str] = None):
    if item is None:
        await start_handler(message)
        await bot.state_dispenser.set(message.peer_id, States.COMMON)
    else:
        if len(item) <= 1000:
            LECTIONS_DRAFTS[message.from_id].descr = item
            await message.answer("Ваша заявка успешно зарегистрирована и отправлена администратору на рассмотрение:\n" + str(LECTIONS_DRAFTS[message.from_id]))
            sendLectionDraftToDatabase(message.from_id)
            await start_handler(message)
            await bot.state_dispenser.set(message.peer_id, States.COMMON)
        else:
            await message.answer(
                f"Слишком много символов. Ограничение - 1000 \nЕсли не получается подобрать формат, уточните информацию у администратора")


def getAcceptedTimes():
    now = datetime.now()
    timeMinus29min = now - timedelta(hours=0, minutes=29)
    for i in range(0, len(TIME_SLOTS)):
        slotStartTime = now.replace(hour=TIME_SLOTS[i][0], minute=0, second=0, microsecond=0)
        if timeMinus29min < slotStartTime:
            return {i: TIME_SLOTS[i],
                    (i + 1) % len(TIME_SLOTS): TIME_SLOTS[(i + 1) % len(TIME_SLOTS)],
                    (i + 2) % len(TIME_SLOTS): TIME_SLOTS[(i + 2) % len(TIME_SLOTS)]}
    return {0: TIME_SLOTS[0], 1: TIME_SLOTS[1], 2: TIME_SLOTS[2]}


def getAcceptedTimesKeyboard():
    ACCEPTED_TIMES = getAcceptedTimes()
    KEYBOARD = Keyboard(one_time=False, inline=True)
    for time in getAvailableForCoworking(ACCEPTED_TIMES):
        timeStr = str(ACCEPTED_TIMES[time][0]) + " - " + str(ACCEPTED_TIMES[time][1])
        KEYBOARD.add(Callback(timeStr, payload={"cmd": "coworking_booking", "timeSlot": time}))
    return KEYBOARD.get_json()


@bot.on.private_message(payload={"btn": "coworking"})
async def coworking(message: Message):
    acceptedTimesKeyboard = getAcceptedTimesKeyboard()
    if acceptedTimesKeyboard is not None:
        await message.answer(f"На текущий момент доступные слоты для записи:", keyboard=acceptedTimesKeyboard)
    else:
        await message.answer(f"На текущий момент все доступные слоты времени заняты. Попробуйте снова после окончания ближайшей сессии")


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, rules.PayloadContainsRule({"cmd": "coworking_booking"}))
async def coworking_booking(event: MessageEvent):
    timeStr = str(TIME_SLOTS[event.payload["timeSlot"]][0]) + " - " + str(TIME_SLOTS[event.payload["timeSlot"]][1])
    if sendCoworkingToDatabase(event.user_id, TIME_SLOTS[event.payload["timeSlot"]][0]):
        await event.send_message("Вы записаны на временной слот: " + timeStr, keyboard=getDefaultKeyboard(event.user_id))
        await event.show_snackbar("Успешно")
    else:
        KEYBOARD = Keyboard(one_time=False, inline=True)
        KEYBOARD.add(Callback("Отменить бронь", payload={"cmd": "coworking_booking_cancel", "timeSlot": event.payload["timeSlot"]}))
        KEYBOARD.add(Callback("Отмена", payload={"cmd": "coworking_booking_back", "timeSlot": event.payload["timeSlot"]}))
        await event.send_message("Вы уже записаны на временной слот: " + timeStr, keyboard=KEYBOARD.get_json())
        await event.show_snackbar("Бронь уже имеется")

@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, rules.PayloadContainsRule({"cmd": "coworking_booking_cancel"}))
async def coworking_booking_cancel(event: MessageEvent):
    timeStr = str(TIME_SLOTS[event.payload["timeSlot"]][0]) + " - " + str(TIME_SLOTS[event.payload["timeSlot"]][1])
    if sendCoworkingCancelToDatabase(event.user_id, TIME_SLOTS[event.payload["timeSlot"]][0]):
        await event.send_message("Вы удалили запись на временной слот: " + timeStr, keyboard=getDefaultKeyboard(event.user_id))
        await event.show_snackbar("Успешно")


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, rules.PayloadContainsRule({"cmd": "coworking_booking_back"}))
async def coworking_booking_back(event: MessageEvent):
    await event.send_message("Вы вернулись в главное меню", keyboard=getDefaultKeyboard(event.user_id))
    await event.show_snackbar("Успешно")


@bot.on.private_message(payload={"btn": "admin_coworking"})
async def admin_coworking(message: Message):
    ACCEPTED_TIMES = getAcceptedTimes()
    KEYBOARD = Keyboard(one_time=False, inline=True)
    for time in getAvailableForCoworking(ACCEPTED_TIMES):
        timeStr = str(ACCEPTED_TIMES[time][0]) + " - " + str(ACCEPTED_TIMES[time][1])
        KEYBOARD.add(Callback(timeStr, payload={"cmd": "admin_coworking_statuses", "timeSlot": time}))
    await message.answer(f"На текущий момент доступные слоты для участников:", keyboard=KEYBOARD.get_json())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, rules.PayloadContainsRule({"cmd": "admin_coworking_statuses"}))
async def admin_coworking_statuses(event: MessageEvent):
    timeStr = str(TIME_SLOTS[event.payload["timeSlot"]][0]) + " - " + str(TIME_SLOTS[event.payload["timeSlot"]][1])
    result = getAvailableForAdminCoworking(TIME_SLOTS[event.payload["timeSlot"]][0])
    if result is None:
        await event.send_message("Список участников на временной слот " + timeStr + f"\n(0/35)\n",
                                 keyboard=getDefaultKeyboard(event.user_id))
        await event.show_snackbar("Успешно")
    else:
        await event.send_message("Список участников на временной слот " + timeStr + f"\n({len(result)}/35)\n" + ','.join(result), keyboard=getDefaultKeyboard(event.user_id))
        await event.show_snackbar("Успешно")

def getLectionRequests():
    pass

def getLectionRequestsKeyboard():
    pass

@bot.on.private_message(payload={"btn": "lections_requests"})
async def lections_requests(message: Message):
    await message.answer(f"Текущие заявки:", keyboard=getLectionRequestsKeyboard())


def getDefaultKeyboard(id):
    if isAdmin(id):
        return DEFAULT_ADMIN_KEYBOARD
    return DEFAULT_USER_KEYBOARD

@bot.on.private_message(state=None)
async def start_handler(message: Message):
    if not isExists(message.from_id):
        await message.answer(f"Добро пожаловать в коворкинг СПбГУТ! Пожалуйста, зарегистрируйтесь!\nВведите вашу фамилию:")
        await bot.state_dispenser.set(message.peer_id, States.USER_REGISTRATION_F)
    # Main menu handlers payload
    else:
        await message.answer(f"Приветствую!\n"
                             f"Для работы с разделом Лекториум, выберите пункт меню \"Лекториум\"\n"
                             f"Для работы с разделом Коворкинг, выберите пункт меню \"Коворкинг\"", keyboard=getDefaultKeyboard(message.from_id))
        await bot.state_dispenser.set(message.peer_id, States.COMMON)


if __name__ == '__main__':
    bot.run_forever()
    