import wikipediaapi
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from time import sleep

opt = webdriver.ChromeOptions()
opt.add_argument('headless')
DRIVER = webdriver.Chrome('chromedriver.exe', options=opt)


def gen_link(request):
    """Функция для генерации ссылки поиска в Яндексе по запросу"""

    yan = "https://yandex.ru/search/?lr=7&text="

    return yan + request


def search_in_wiki(what):
    """Поиск статьи в Википедии по запросу с помощью Wikipedia-API"""

    # Создаём объект Wikipedia и устанавливаем русский язык
    wiki = wikipediaapi.Wikipedia('ru')

    # Находим страницу по запросу
    page = wiki.page(what)

    # Берём первые 2 предложения с найденной страницы по запросу
    text = wiki.extracts(page, exsentences=2)

    # Удаляем материал в скобках (он часто на иностранном языке)
    while text.find('(') != -1:
        l = text.find('(') - 1
        r = text.find(')') + 1
        text = text[:l] + text[r:]

    # Возвращаем получившийся текст
    return text


def netschool(login, password, day):
    """Функция для парсинга информации из электронного дневника"""

    driver = DRIVER

    driver.get('https://netschool.eduportal44.ru/about.html')

    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.NAME, "UN")))

    elem = driver.find_element_by_name("scid")
    elem.send_keys('МБОУ "Лицей № 17"')
    elem.send_keys(Keys.ENTER)

    elem = driver.find_element_by_name("UN")
    elem.send_keys(login)
    sleep(0.5)
    elem = driver.find_element_by_name("PW")
    elem.send_keys(password)
    elem.send_keys(Keys.ENTER)

    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "footer")))
    except TimeoutException:
        try:
            error = driver.find_element_by_xpath('//div[@class="bootstrap-dialog-message"]')
            err = error.text
        except Exception as error:
            err = error

        if 'пароль' in err:
            return "Не удалось войти в систему. Пожалуйста, укажи верные данные в настройках"
        else:
            raise TimeoutException

    if driver.title == "Сетевой Город. Образование. Предупреждение о безопасности":
        driver.execute_script("doContinue(); ; return false;")
        WebDriverWait(driver, 10).until_not(EC.title_is("Сетевой Город. Образование. Предупреждение о безопасности"))

    driver.execute_script("SetSelectedTab(30, '/angular/school/studentdiary/'); return false;")

    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//div[@class="day_table"]')))
    sleep(1)

    days = driver.find_elements_by_xpath('//div[@class="day_table"]')

    for d in days:
        date = d.find_element_by_xpath('.//span[@class="ng-binding"]').get_attribute("innerHTML")

        date = date.split()[1:-1]
        m = date[1]
        date[0] = ('0' + date[0])[-2:]

        if 'янв' in m:
            date[1] = '01'
        elif 'фев' in m:
            date[1] = '02'
        elif 'мар' in m:
            date[1] = '03'
        elif 'апр' in m:
            date[1] = '04'
        elif 'май' in m:
            date[1] = '05'
        elif 'сен' in m:
            date[1] = '09'
        elif 'окт' in m:
            date[1] = '10'
        elif 'ноя' in m:
            date[1] = '11'
        else:
            date[1] = '12'

        date = '-'.join(date)

        if day == date:
            res = tuple(homework(d))
            logout(driver)
            return res

    else:
        logout(driver)
        return "Неизвестная ошибка!"

    # yield driver.get_screenshot_as_png()


def homework(day):
    """Функция парсинга домашнего задания из электронного дневника"""

    lessons = day.find_elements_by_xpath('.//tr[@ng-repeat="lesson in diaryDay.lessons"]')

    for lesson in lessons:
        try:
            name = lesson.find_element_by_xpath('.//a[@class="subject ng-binding ng-scope"]').get_attribute("innerHTML")
            try:
                hw = lesson.find_element_by_xpath('.//a[@class="ng-binding ng-scope"]').get_attribute("innerHTML")
            except NoSuchElementException:
                hw = ''
            yield name, hw
        except NoSuchElementException:
            pass


def logout(driver):
    """Функция выхода из системы"""

    try:
        driver.execute_script("JavaScript:Logout(true);")
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((
            By.XPATH, '//div[@class="bootstrap-dialog-footer-buttons"]')))
        btn = driver.find_element_by_xpath('//div[@class="bootstrap-dialog-footer-buttons"]')
        btn.find_element_by_xpath('.//button[@class="btn btn-primary"]').click()
        sleep(0.5)
    except Exception as err:
        return err


