import json
import re
import time

import requests
from selenium import webdriver
from selenium.common.exceptions import ElementNotVisibleException
from selenium.webdriver.common.action_chains import ActionChains

URL_PREFIX = "https://hfut.xuetangx.com"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.80 Safari/537.36"
# 对应调整速度的按钮的 CSS 选择器
SPEED_BUTTON_SELECTOR = "#video-box > div > div > div.xt_video_player_controls.cf.xt_video_player_controls_show > div.xt_video_player_speed.xt_video_player_common.fr > div"
# 对应 2.5x 速度的按钮的 CSS 选择器
SPEED_UP_BUTTON_SELECTOR = "#video-box > div > div > div.xt_video_player_controls.cf.xt_video_player_controls_show > div.xt_video_player_speed.xt_video_player_common.fr > ul > li:nth-child(1)"
DEBUG = True

def getTime():
    return time.asctime().split(' ')[3]


def debugLog(mess):
    if DEBUG:
        print(f"\033[0;37m[\033[0;33mDEBUG\033[0;37m] {getTime()} {mess}")


def getSess():
    sess = requests.session()
    sess.headers["User-Agent"] = USER_AGENT
    sess.headers["X-Requested-With"] = "XMLHttpRequest"
    cookies = open('cookies.json').read()
    cookies = json.loads(cookies)
    for cookie in cookies:
        sess.cookies[cookie["name"]] = cookie["value"]
    return sess


def getCourseInfo(courseid, classid):
    url = URL_PREFIX + f"/lms/api/v1/course/{courseid}/courseware/"
    sess = getSess()
    data = {"class_id": str(classid)}
    return sess.post(url, json=data).json()


def getCourseId():
    sess = getSess()
    platId = sess.get(URL_PREFIX + "/api/v1/platform/material").json()['data']['platform_id']
    termId = sess.get(URL_PREFIX + f"/api/v1/plat_term?plat_id={platId}").json()['data'][-1]['term_id']
    page = 1
    result = list()
    while True:
        res = sess.get(URL_PREFIX + f"/mycourse_list?term_id={termId}&page={page}").json()
        if res['code'] == 0:
            for i in res['data']['results']:
                result.append({
                    "courseId": i['course_id'],
                    "classId": i['class_id'],
                    "name": i['course_name']
                })
            page += 1
        else:
            break
    return result


def loadCookie(driver):
    cookies = open('cookies.json').read()
    cookies = json.loads(cookies)
    for cookie in cookies:
        driver.add_cookie(cookie)


def getDriver(mute=True):
    chromeOptions = webdriver.ChromeOptions()
    if mute:
        chromeOptions.add_argument("--mute-audio")
    driver = webdriver.Chrome(options=chromeOptions)
    driver.get(URL_PREFIX)
    loadCookie(driver)
    return driver


def getVideoLinks(driver, courseId):
    classid = courseId['classId']
    courseid = courseId['courseId']

    info = getCourseInfo(courseid, classid)['coursewareArray']
    result = list()
    for i in info:
        if not i["done"] and 'items' in i['children']:  # 如果 'items' 不在 i['children'] 里面, 是作业而不是视频
            result.append(f"/lms#/video/{courseid}/{classid}/{i['unit_id']}/{i['children']['items']['item_id']}/0/videoDiscussion")
    return result


def speedUpVideo(driver):
    debugLog("正在尝试加速视频")
    while True:
        time.sleep(0.5)
        elements = driver.find_elements_by_css_selector(SPEED_BUTTON_SELECTOR)
        if elements:
            ActionChains(driver).move_to_element(elements[0]).perform()
            element = driver.find_element_by_css_selector(SPEED_UP_BUTTON_SELECTOR)
            try: # 如果点击不了重来
                element.click()
                break
            except ElementNotVisibleException:
                pass
        else:
            continue


def watchVideo(driver, link):
    driver.get(URL_PREFIX + link)
    speedUpVideo(driver)
    while True:
        time.sleep(0.5)
        element = driver.find_elements_by_class_name("xt_video_player_play_btn_pause")
        # 如果没有 xt_video_player_play_btn_pause 这个元素, 说明视频被暂停了
        if element:
            pass
        else:
            element = driver.find_elements_by_class_name("xt_video_player_current_time_display")
            # 如果暂停了, 先检查是否视频播放完成, 没有播放完成点播放键
            if element:
                regExp = "[0-9]{1,}:[0-9]{1,}"
                content = element[0].get_attribute('textContent')
                times = re.findall(regExp, content)
                if times[1] == "0:00": # 若第二个时间是 0:00, 也没有加载完成
                    continue
                if times[0] == times[1]:
                    debugLog(f"观看已完成, 进度条状态为 {times}")
                    break  # 如果时间相同, 播放完成
                else:
                    debugLog("视频被暂停, 尝试点击继续播放")
                    element = driver.find_element_by_class_name("xt_video_player_play_btn")
                    ActionChains(driver).move_to_element(element).perform()
                    element.click()
            else:
                continue  # 如果播放时间不存在, 说明这个页面没加载完


driver = getDriver()
courses = getCourseId()
for course in courses:
    debugLog(f"正在加载 {course['name']}")
    links = getVideoLinks(driver, course)
    for link in links:
        debugLog(f"正在观看 {URL_PREFIX + link}")
        watchVideo(driver, link)
