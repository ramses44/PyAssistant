"""Голосовой помощник для школьника"""

# Импорт модулей
import sys
import os
import speech_recognition as sr
from fuzzywuzzy import fuzz
import pyttsx3
import sqlite3
import winsound
from random import choice
from PyQt5.QtWidgets import QMainWindow, QAction, QApplication
from PyQt5.QtWidgets import QListWidgetItem, QTableWidget, QTableWidgetItem
from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
from PyQt5.QtGui import QFont
from PyQt5 import uic
from my_web import *
from time import sleep
import datetime
from datetime import timedelta


def del_extra_words(text, ex_words):
    """Функция для удаления из текста потенциально бесполезных для логики программы слов.
    На вход подаётся исходный текст и список слов, которые нужно исключить"""

    text = text.split()

    # Удаляем точно совпадающие фрагменты
    text = set(filter(lambda x: x not in ex_words, text))

    # Создаём множество для слов, которые нужно убрать
    blacklist = set()

    # Заносим в черный список соответствующие слова
    for ex_w in ex_words:
        for word in text:

            # Используем FuzzyWuzzy
            if 100 > fuzz.partial_ratio(ex_w, word) > 80:
                # Если совпадение не полное (иначе будет ошибка например с однобуквенными словами),
                # но больше 80%, то добавляем слово в ЧС
                blacklist.add(word)

    # В результирующее множество добавляем только те слова, что не в ЧС
    res = text - blacklist

    # Возвращаем итоговый вариант текста
    return ' '.join(res)


def callback(recognizer, audio):
    """Функция распознавания речи"""

    try:
        # Переведение текста в речь с использованием Google
        lan = "ru-RU"
        voice = recognizer.recognize_google(audio, language=lan)
        voice = voice.lower()

        # Вывод в графическом интерфейсе пользовательской реплики
        uname = ex.user[1]
        ex.print(uname, voice)

        cmd = voice

        # Удаляем все упоминания имени бота из реплики
        cmd = del_extra_words(cmd, ex.opts["alias"])

        # Удаляем все вспомогательные слова
        cmd = del_extra_words(cmd, ex.opts["tbr"])

        # Распознаем и выполняем команду
        cmd = ex.recognize_cmd(cmd)
        ex.execute_cmd(cmd)

    # Вывод в окно чата соответствущей информации в случае ошибки
    except sr.UnknownValueError:
        ex.print("[Error]", "Голос не распознан!", bold=True)

    except sr.RequestError:
        ex.print("[Error]", "Неизвестная ошибка, проверьте подключение к интернету!", bold=True)


class BotWindow(QMainWindow):
    """Главное окно графического интерфейса бота"""

    def __init__(self):

        super().__init__()

        # Функция остановки прослушивания (по умолчанию ничего не делает)
        # (Вводим сейчас чтобы не было ошибки при сохранении нового пользователя)
        self.stop_listening = lambda x: x

        # Создаём распознаватель речи и устройство ввода звука
        self.r = sr.Recognizer()
        self.m = sr.Microphone()

        # Калибровка микрофона
        # Чтобы в будущем отличать шумы от слов пользователя
        with self.m as source:
            self.r.adjust_for_ambient_noise(source)

        self.speak_engine = pyttsx3.init()
        # Через speak_engine будет воспроизводиться звук (речь бота)

        # Меняем голос боту
        # voices = self.speak_engine.getProperty('voices')
        # self.speak_engine.setProperty('voice', voices[0].id)

        # Изначально бот не слушает
        self.is_listening = False

        # Загружаем форму
        self.initUI()

    def initUI(self):

        # Загружаем и устанавливаем настройки пользователей
        self.refresh_data()

        # Переменная хранящая данные о текущем пользователе (None пока пользователь не выбран)
        self.user = None

        # Загружаем форму
        uic.loadUi('bot.ui', self)

        # Настраиваем тулбар
        self.tune_toolbar()

        # Ссылка для открытия в окне браузере при надобности (по умолчанию https://yandex.ru/)
        self.link = QUrl("https://yandex.ru/")

        # Задаём действия кнопок
        self.btn1.clicked.connect(self.save_table)
        self.btn2.clicked.connect(self.my_close)
        self.btn3.clicked.connect(lambda: self.create_web(self.link))

        # Создаём виджеты таблицы настройки и просмотра веб-страниц
        # Изначально не указваем объект-родителя
        self.browser = QWebEngineView()
        self.table = QTableWidget()

        # Показываем окно
        self.show()

    def my_close(self):
        """Функуия закрытия программы"""

        if DRIVER:
            logout(DRIVER)

        if self.is_listening:
            # Если бот активен, он прощается
            self.speak("Пока!")

        # Закрываем приложение
        self.close()

    def refresh_data(self):
        """Функция для обновления загруженного списка пользователей"""

        # Подключение к БД
        con = sqlite3.connect("user_settings.db")

        # Создание курсора
        cur = con.cursor()

        # Выполнение запроса и получение всех результатов, запись в self.data
        self.data = cur.execute("""SELECT * FROM Users""").fetchall()

        # Закрываем таблицу
        con.close()

    def tune_toolbar(self):
        """Настройка тулбара"""

        # Список для хранения кнопок тулбара для выбора пользователя
        self.user_list = []

        # Добавляем пользователей для выбора из БД
        for uname in self.data:
            act = QAction(f'{uname[0]}. {uname[1]} {uname[2]}', self)
            self.user_list.append(act)
            self.choose_user.addAction(act)

        # Задаем действия кнопок в тулбаре
        self.change_settings.triggered.connect(self.editUser)
        self.new_user.triggered.connect(self.newUser)

        for act in self.user_list:
            act.triggered.connect(self.chooseUser)

        self.help.triggered.connect(self.print_help)
        self.developers.triggered.connect(self.about_developers)

    def opentab(self, new=False):
        """Загрузка данных о текущем пользователе в виджет-таблицу"""

        # Если новый пользователь
        if new:
            # Заполняем user_data новым id, именем бота по умолчанию ("помощник") и пустыми данными
            ids = map(lambda x: int(x[0]), self.data)
            u_id = max(ids) + 1
            user_data = str(u_id), '', '', '', '', 'Помощник'
        else:
            # Иначе устанавливаем данные из текущего пользователя
            user_data = self.user

        # Удаление предыдущего содержания дополнительного вывода
        self.remove(self.additional)

        # Создаём таблицу для вывода данных пользователя
        table = self.table
        table.setParent(self)
        table.setColumnCount(2)
        table.setRowCount(6)

        # Устанавливаем названия строк
        table.setItem(0, 0, QTableWidgetItem("id"))
        table.setItem(1, 0, QTableWidgetItem("Имя"))
        table.setItem(2, 0, QTableWidgetItem("Фамилия"))
        table.setItem(3, 0, QTableWidgetItem("Логин от\nэлектронного\nдневника"))
        table.setItem(4, 0, QTableWidgetItem("Пароль от\nэлектронного\nдневника"))
        table.setItem(5, 0, QTableWidgetItem("Обращение\nк боту"))

        # И наполняем таблицу данными из user_data
        for i, inf in enumerate(user_data):
            item = QTableWidgetItem(str(inf))
            table.setItem(i, 1, item)

        # Устанавливаем шрифты для всех ячеек
        for i in range(6):
            for j in range(2):
                table.item(i, j).setFont(QFont('Comic Sans MS', 14))

        # Запрещаем изменение названий строк
        for i in range(6):
            item = table.item(i, 0)
            item.setFlags(Qt.ItemIsEnabled)

        # Запрещаем менять id по умолчанию
        table.item(0, 1).setFlags(Qt.ItemIsEditable)

        # Устанавливаем размер ечеек
        table.resizeColumnsToContents()
        table.resizeRowsToContents()

        # Добавляем таблицу в сетку
        self.remove(self.additional)
        self.grid.addWidget(table, 1, 0)

        # Устанавливаем таблицу как дополнительный вывод
        self.additional = table

        # Делаем доступной кнопку сохранения
        self.btn1.setEnabled(True)

    def save_table(self):
        """Сохранение новых пользовательских данных"""

        table = self.additional

        # Подключение к БД
        con = sqlite3.connect("user_settings.db")

        # Создание курсора
        cur = con.cursor()

        # Формирование данных для записи в БД
        rc = table.rowCount()
        data = map(lambda x: table.item(x, 1).text(), range(rc))
        data = tuple(data)

        # Удаление старой записи об этом пользователе
        cur.execute("""DELETE FROM Users
            WHERE id = ?""", (data[0], ))

        # Добавление нового пользователя в БД
        cur.execute("""INSERT INTO Users VALUES(? ,?, ?, ?, ?, ?)""", data)

        # Сохраняем изменения в БД
        con.commit()

        # Добавление возможности выбора пользователя в тулбаре или изменение существующего варианта
        for el in self.user_list:
            uid = el.text().split('.')[0]
            if uid == data[0]:
                el.setText(f"{data[0]}. {data[1]} {data[2]}")
                self.user = data
                break
        else:
            act = QAction(f"{data[0]}. {data[1]} {data[2]}", self)
            self.user_list.append(act)
            act.triggered.connect(self.chooseUser)
            self.choose_user.addAction(act)

        # Обновляем данные в программе
        self.refresh_data()
        self.set_properties(self.user)

        # Перезапускаем бота для обновления информации если он был запущен
        if self.is_listening:
            self.stop_listening()
            self.start()

    def chooseUser(self):
        """Выбор текущего поьзователя при нажатии на кнопку в тулбаре"""

        # Ищем данные нужного пользователя и записываем их в self.user
        u_id = self.sender().text().split('.')[0]
        for user in self.data:
            if str(user[0]) == u_id:
                self.user = user
                break

        # Устанавливаем настройки пользователя
        self.set_properties(self.user)

        # Делаем доступной кнопку настроек пользователя
        self.change_settings.setEnabled(True)

        # Создаём новый элемент списка чата и пишем туда приветствие, озвучивая его
        if self.user[1]:
            self.speak("Привет, " + self.user[1] + "!")
        else:
            self.speak("Привет!")

        # Бот автоматически включается и начинает слушать
        print(self.user)
        self.start()

    def newUser(self):
        """Открытие таблицы для создания нового пользователя"""

        self.opentab(new=True)

    def editUser(self):
        """Открытие таблицы для изменения данных текущего пользователя"""

        self.opentab()

    def remove(self, obj):
        """Метод для удаления объекта"""

        if type(obj) == QTableWidget:
            # Если удаляется таблица, то делаем недоступной кнопку сохранения
            self.btn1.setEnabled(False)
        else:
            # Иначе делаем недоступной кнопку загрузки веб-страницы
            self.btn3.setEnabled(False)

        try:
            self.grid.removeWidget(obj)
            obj.setParent(None)
        except Exception as err:
            # Если исключение, выводим его и через 3 секунды закрываем программу
            self.print("[Fatal error]", err)
            sleep(3)
            self.close()

    def start(self):
        """Запуск бота"""

        # Задаём функцию отключения бота. Включаем прослушивание в фоновом режиме
        self.stop_listening = self.r.listen_in_background(self.m, callback)

        # Задаём переменную self.is_listening, хранящую состояние прослушки
        self.is_listening = True

    def set_properties(self, data):
        """Установка настроек для логики бота"""

        # Создание словаря с настройками
        self.opts = {
            "alias": (data[-1],),
            "tbr": ('скажи', 'расскажи', 'покажи', 'сколько', 'произнеси',
                    'и', 'в', 'что', 'за', 'на', 'а', 'ну', 'мне', 'по'),
            "cmds": {
                "search": ("найди", "поищи", "загугли", "погугли", "ищи", "такое", "интернете"),
                "ctime": ('текущее время', 'сейчас времени', 'который час'),
                "joke": (
                    'расскажи анекдот', 'рассмеши меня', 'ты знаешь анекдоты', 'шутка', 'пошути'
                ),
                "book": ("учебник", "книга", "электронный учебник"),
                "leave": ("пока", "до свидания", "спокойной ночи"),
                "thanks": ("спсибо", "благодарю"),
                "greeting": ("привет", "здравствуйте", "хай"),
                "netschool": ("электронный дневник", "электронный журнал", "задали",
                              "домашнее задание", "расписание", "уроки", "делать", "расписание")
            }
        }

    def speak(self, what):
        """Метод для переведения текста в речь и озвучивания (текст также выводится в чат)"""

        # Озвучиваем
        self.speak_engine.say(what)
        self.speak_engine.runAndWait()
        self.speak_engine.stop()

        # Выводим в окно чата
        bot_name = self.user[-1]
        self.print(bot_name, what)

    def print(self, who, what, bold=False):
        """Метод вывода реплики в чатовое окно. Требуется передать говорящего и реплику"""

        # Формируем ListWidgetItem для последующего вывода
        item = QListWidgetItem(who + ": " + what)

        # Устанавливаем шрифт
        if bold:
            item.setFont(QFont('Comic Sans MS', 10, QFont.Bold))
        else:
            item.setFont(QFont('Comic Sans MS', 10))

        # Добавляем в окно чата
        self.chat.addItem(item)

    def recognize_cmd(self, cmd):
        """Функция для определения конкретной команды по словам в реплике"""

        # Словарь для потенциальной команды и вероятности, что это именно она
        rc = {'cmd': '', 'percent': 0, 'request': cmd}

        # Перебираем все виды команд и считаем с помощью fuzzywuzzy совпадение с cmd
        for c, v in self.opts['cmds'].items():
            for x in v:
                vrt = fuzz.ratio(cmd, x)
                if vrt > rc['percent']:
                    rc['cmd'] = c
                    rc['percent'] = vrt

        # Возвращается словарь, содержащий наиболее вероятную команду
        return rc

    def execute_cmd(self, cmd):
        """Функция для непосредственного выполнения команды ботом"""

        cmd, user_words = cmd['cmd'], cmd['request']

        if cmd == 'ctime':
            # Сказать текущее время
            now = datetime.datetime.now()
            hour = str(now.hour)
            minute = ('0' + str(now.minute))[:2]
            self.speak("Сейчас " + hour + ":" + minute)

        elif cmd == 'joke':
            # Рассказать рандомный "анекдот" из списка
            jokes = [
                "Запись в дневнике: «Орал на уроке пения, а надо было петь тихо».",
                "Учиться, учиться и еще раз учиться!" +\
                "на практике означает один экзамен и две пересдачи",
                "- Петров, - говорит учитель во время урока, - разбуди своего соседа." +\
                " - Почему я? Ведь это вы его усыпили!",
                "Я сегодня не в настроении шутить!" +\
                "Хотя какое у меня может быть настроение, я же бот!"
            ]

            joke = choice(jokes)
            self.speak(joke)

            # Проиграть звук "Ba-Dum-Tss" после шутки
            winsound.PlaySound('SOUND/joke.wav', winsound.SND_FILENAME)

        elif cmd == 'leave':
            # Прощание, окончание работы

            uname = self.user[1]

            if uname:
                self.speak("Пока, " + uname)
            else:
                self.speak("Пока")

            self.close()

        elif cmd == 'greeting':
            # Ответ на пользовательское приветствие: бот слушает
            uname = self.user[1]

            if uname:
                self.speak("Слушаю, " + uname)
            else:
                self.speak("Слушаю тебя")

        elif cmd == 'thanks':
            # Ответ на благодарность пользователя

            # Вариантв ответов
            answers = [
                "Всегда пожалуйста",
                "Наздоровье",
                "Всегда рад помочь",
                "Обращайся",
                "Не благодари"
            ]

            # Выбор рандомного ответа
            ans = choice(answers)

            # Ответ бота
            self.speak(ans)

        elif cmd == 'search':
            # Поиск в Интернете

            # Т.к. при распознавании речи слова могут "перетасовываться" внутри реплики
            # Удалим предлоги, союзы

            # Убираем из реплики пользователя слова, потенциально не имеющие отношения к запросу
            excess_words = self.opts['cmds']['search']

            request = del_extra_words(user_words, excess_words)

            # Отправляем запрос в Википедию
            wiki_req = search_in_wiki(request)

            # Если что-то нашлось в Википедии, бот говорит это, иначе просто ищет в Яндексе
            if wiki_req:
                self.speak(wiki_req)
            else:
                self.speak("Вот что я нашёл по запросу")

            # Создаём ссылку для загрузки запроса поиска в Яндексе
            link = gen_link(request)
            self.link = QUrl(link)

            # Делаем доступной кнопку загрузки
            self.btn3.setEnabled(True)

            # Подсказка пользователю
            self.speak(
                "Чтобы увидеть результат поиска в Яндексе, пожалуйста, нажми на кнопку Загрузить"
            )

        elif cmd == 'book':
            # Открыть электронный учебник/книгу

            # Получаем список файлов в директории /BOOKS
            books = os.listdir('BOOKS')

            # Убираем лишние слова из запроса
            book_name = del_extra_words(user_words, self.opts['cmds']['book'])

            # Находим учебник с наиболее подходящим названием

            pb = dict(book='', percent=0)

            for book in books:
                vrt = fuzz.ratio(book.rstrip('.pdf').lower(), book_name)
                if vrt > pb['percent']:
                    pb['book'] = book
                    pb['percent'] = vrt

            book = pb['book']

            # Находим абсолютный путь к файлу учебника
            abs_path = os.path.abspath("BOOKS/" + book)

            # Создаём ссылку для QWebView для просмотра PDF файла
            link_path = "file:///" + abs_path.replace("\\", "/")
            self.link = QUrl(link_path)

            # Делаем доступной кнопку загрузки
            self.btn3.setEnabled(True)

            # Подсказка пользователю
            self.speak("Чтобы открыть книгу, пожалуйста, нажми на кнопку Загрузить")

        elif cmd == 'netschool':
            self.speak("Подожди минутку...")

            hw = ("делать", "задали", "задания", "учить", "выучить")

            pb = dict(cmd='', percent=0)
            for word in user_words.split():
                for command in hw:
                    vrt = fuzz.ratio(word, command)
                    if vrt > pb['percent']:
                        pb['cmd'] = command
                        pb['percent'] = vrt
                        print(word, command, vrt)
            if pb['percent'] >= 85:
                hw = True
            else:
                hw = False

            date = datetime.datetime.now()
            week_days = ["понедельник", "вторник", "сред", "четверг", "пятниц", "суббот"]

            if "сегодня" in user_words:
                date = date.strftime('%d %m %Y').replace(' ', '-')
            else:
                for n, day in enumerate(week_days):
                    if day in user_words:
                        delta = timedelta((n - date.timetuple().tm_wday + 6) % 6)
                        break
                else:
                    if date.timetuple().tm_wday == 5:
                        delta = timedelta(2)
                    else:
                        delta = timedelta(1)

                date = date + delta
                date = date.strftime('%d %m %Y').replace(' ', '-')

            login, password = self.user[3:5]
            print(date, login, password)
            try:
                response = netschool(login, password, date)

                if type(response) == str:
                    self.speak(response)
                else:
                    if hw:
                        for lesson in response:
                            if lesson[1]:
                                self.speak(': '.join(lesson))
                        if all(map(lambda x: not x[1], response)):
                            self.speak("Нет никакого домашнего задания в электронном дневнике")

                    else:
                        speech = '; '.join(map(lambda x: x[0], response))
                        self.speak(speech)

                # Открываем во встроенном браузере электронный дневник
                self.speak("Чтобы открыть электронный дневник нажми на кнопку Загрузить")
                self.link = QUrl('http://netschool.eduportal44.ru/')

                # Делаем доступной кнопку загрузки
                self.btn3.setEnabled(True)

            except Exception as err:
                with open('logs.txt', 'w') as logs:
                    logs.write(str(err))

                self.speak("Произошла непредвиденная ошибка. Проверь, пожалуйста, интернет-соединение")
                self.print("[Error]", "Если ошибка продолжит появляться, обратись к разработчику")

        else:
            # Если команда не распознана
            self.speak('Я тебя не понимаю!')

    def create_web(self, data):
        """Открытие окна для промотра веб-страниц. Подаётся ссылка (QUrl) или HTML код"""

        # Удаление предыдущего содержания дополнительного вывода
        self.remove(self.additional)

        # Настраиваем окно просмотра веб-страниц
        self.browser.setParent(self)
        self.browser.resize(340, 430)
        self.browser.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)

        # Добавляем его в сетку
        self.grid.addWidget(self.browser, 1, 0)

        # Устанавливаем его как дополнительный вывод
        self.additional = self.browser

        if type(data) == QUrl:
            # Загружаем ссылку
            self.browser.load(data)
        else:
            # Загружаем HTML код
            self.browser.setHtml(data)

    def print_help(self):
        """Вывод html странички с описанием программы"""

        html = """<!DOCTYPE html>
            <html>
            <head>
                <link rel="stylesheet">
            </head>
            <body>
                <h1>Помощь</h1>
                <p> • Данная программа представляет из себя голосового помощника. Цель бота - 
                элементарная помощь, общение. Он обращается к пользователю по имени, может 
                пошутить, найти информацию в Интернет-ресурсах, сказать, сколько времени. 
                Бот реагирует на вежливые слова (Здравствуй, спасибо, до свидания и т.п.)</p>
                <p> • Для корректной работы голосового помощника необходимо следующее:<br>
                1) База данных в одной папке с программой;<br>
                2)В папке с программой папка BOOKS с электронными книгами/учебниками<br>
                3)Все книги должны быть в формате PDF и содержать в названии только символы 
                кирилического алфавита<br>
                4)К компьютеру должен быть подключен микрофон<br>
                5)Пользователь должен уметь говорить по-русски))))</p>
                <p> • Если у вас возникли какие-нибудь вопросы или в программе происходят 
                непредвиденные ошибки, пожалуйста пишите создателю (контакты можно найти во 
                вкладке "О разработчиках")</p>
            </body>
            </html>"""

        self.create_web(html)

    def about_developers(self):
        """Вывод информации о разработчиках в виде html странички"""

        html = """<!DOCTYPE html>
            <html>
            <head>
                <link rel="stylesheet">
            </head>
            <body>
                <h1>О разработчиках</h1>
                <p>Программу разработал Сахаров Роман</p>
                <p>Контакты:<br>
                Почта: gersagvalperius@yandex.ru<br>
                Telegram: @Ramzzzes44</p>
                <p>2019</p>
            </body>
            </html>"""

        self.create_web(html)


if __name__ == '__main__':
    try:
        app = QApplication(sys.argv)
        ex = BotWindow()
        sys.exit(app.exec_())
    except Exception as err:
        with open('logs.txt', 'w') as logs:
            logs.write(str(err))
        sys.exit(-1)

