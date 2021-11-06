import os
import time
import logging
import yaml

from typing import List
from uuid import uuid1
from selenium import webdriver
from paddleocr import PaddleOCR
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.chrome.options import Options

from config import loadConfig
from mail import sendMail

MAJSOUL_URL = "https://game.maj-soul.com/1/"
WIDTH = 1200
HEIGHT = 800

logging.getLogger('majsoul')
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s[:%(lineno)d] - %(message)s"')

CONFIG = loadConfig(logging)
lang = CONFIG['lang']
I18N = yaml.full_load(open('i18n.yaml', 'r').read())

args = {'use_angle_cls': True}
if CONFIG['headless']:
    args['use_gpu'] = False
    args['enable_mkldnn'] = True

if lang == 'cht':
    args['rec_model_dir'] = 'i18n_infer/cht_infer'
else:
    args['lang'] = 'ch'

OCR = PaddleOCR(**args)

class POS():
    def __init__(self, left, right, top, bottom):
        self.left = left
        self.right = right
        self.top = top
        self.bottom = bottom
        self.x = (left + right) // 2
        self.y = (top + bottom) // 2

    def __str__(self) -> str:
        return f"POS(l:{self.left}, r:{self.right}, t:{self.top}: b:{self.bottom})"


class Action():
    CLICK = 1
    SEND_KEY = 2
    MOVE = 3

    def __init__(self, actionType: int, delay: int, *args) -> None:
        self.actionType = actionType
        self.args = args
        self.delay = delay

    def act(self, driver):
        if self.actionType == Action.CLICK:
            logging.info("[ACTION] click")
            ActionChains(driver).click().perform()
        elif self.actionType == Action.SEND_KEY:
            logging.info(f"[ACTION] send keys, {self.args}")
            ActionChains(driver).send_keys(*self.args).perform()
        elif self.actionType == Action.MOVE:
            logging.info(f"[ACTION] move to {self.args}")
            ActionChains(driver).move_by_offset(*self.args).perform()

        if self.delay > 0:
            time.sleep(self.delay)


def getTextPosByOcr(imagePath: str, pattern: str, precise: bool = False) -> POS:
    """根据图片获取宽松匹配文本的位置(文本的中心位置)

    Args:
        imagePath (str): 图片路径
        pattern (str): 匹配文本
        precise (bool): True - 完整匹配整个字符串, False - 包含即可

    Returns:
        POS: 位置对象
    """
    
    boxes = OCR.ocr(imagePath, cls=True)
    if not boxes:
        logging.info("ocr未读取到任何文本")
        return None

    matchIdx = -1
    matchTextList = [matchTextPart[1][0] for matchTextPart in boxes]
    for idx, matchText in enumerate(matchTextList):
        if (precise and pattern == matchText) or (not precise and pattern in matchText):
            matchIdx = idx
            break

    logging.info(
        f"ocr识别完成, 识别文本:{matchTextList}, 匹配文本:{pattern}, 匹配位置:{matchIdx}")

    if matchIdx >= 0:
        # 获取匹配文字的中间位置
        return POS(boxes[matchIdx][0][0][0], boxes[matchIdx][0][2][0], boxes[matchIdx][0][0][1], boxes[matchIdx][0][2][1])
    return None


def screenShotThenOcrMatch(driver: WebDriver, pattern: str, precise: bool, retryTimes: int, retryPeriod: int, step: str = '') -> POS:
    """截图并ocr识别,返回pattern所在位置

    Args:
        driver (WebDriver): driver
        pattern (str): 匹配文本
        precise (bool): 完整匹配字符串
        retryTimes (int): 重试次数
        retryPeriod (int): 重试间隔/秒
        step (str, optional): 步骤名称,用于日志展示. Defaults to ''.

    Raises:
        RuntimeError: 最终未匹配到文本

    Returns:
        POS: 匹配文本的位置
    """
    filename = str(uuid1()) + '.png'
    try:
        for i in range(1, retryTimes + 1):
            if step:
                logging.info(f"[{step}] 进行第{i}次ocr识别...")
            driver.get_screenshot_as_file(filename)
            res = getTextPosByOcr(filename, pattern, precise)
            if res:
                logging.info(f'成功获取[{pattern}]文本位置, {res}\n')
                return res
            else:
                if i != retryTimes:
                    logging.info(f'获取失败, 等待{retryPeriod}s进行下一次识别\n')
                    time.sleep(retryPeriod)
    finally:
        os.remove(filename)
    raise RuntimeError(f'无法定位到[{pattern}],请手动处理')


def driverExecute(driver: WebDriver, actions: List[Action]):
    for action in actions:
        action.act(driver)

options = Options()
if CONFIG['headless']:
    options.add_argument('--headless')
driver = webdriver.Chrome(options=options)
driver.set_window_size(WIDTH, HEIGHT)

try:
    # 登录, 并等待加载
    driver.get(MAJSOUL_URL)
    userNamePos = screenShotThenOcrMatch(driver=driver, pattern=I18N[lang]['username'], precise=False,
                           retryTimes=20, retryPeriod=5, step='输入用户名')
    userPassPos = screenShotThenOcrMatch(driver=driver, pattern=I18N[lang]['password'], precise=True,
                           retryTimes=4, retryPeriod=2, step='输入密码')
    loginPos = screenShotThenOcrMatch(driver=driver, pattern=I18N[lang]['login'], precise=False,
                           retryTimes=4, retryPeriod=2, step='登录账号')

    # 用户名
    driverExecute(driver, [
        Action(Action.MOVE, 0, userNamePos.x, userNamePos.y),
        Action(Action.CLICK, 1),
        Action(Action.SEND_KEY, 2, CONFIG['username']),
        Action(Action.MOVE, 0, -userNamePos.x, -userNamePos.y),
    ])
    # 密码
    driverExecute(driver, [
        Action(Action.MOVE, 0, userPassPos.x, userPassPos.y),
        Action(Action.CLICK, 1),
        Action(Action.SEND_KEY, 2, CONFIG['password']),
        Action(Action.MOVE, 0, -userPassPos.x, -userPassPos.y),
    ])
    # 进入游戏
    driverExecute(driver, [
        Action(Action.MOVE, 0, loginPos.x, loginPos.y),
        Action(Action.CLICK, 1),
        Action(Action.MOVE, 0, -loginPos.x, -loginPos.y),
    ])

    time.sleep(10)

    yuekaPos = screenShotThenOcrMatch(driver=driver, pattern=I18N[lang]['yueka'], precise=False,
                            retryTimes=10, retryPeriod=5, step='等待月卡页面加载')

    driverExecute(driver, [
        Action(Action.MOVE, 0, yuekaPos.x, yuekaPos.y),
        Action(Action.CLICK, 2),
        Action(Action.MOVE, 0, -yuekaPos.x, -yuekaPos.y),
    ])

    time.sleep(2)

    acquirePos = screenShotThenOcrMatch(driver=driver, pattern=I18N[lang]['checkIn'], precise=False,
                            retryTimes=10, retryPeriod=2, step='领取辉玉')

    driverExecute(driver, [
        Action(Action.MOVE, 0, acquirePos.x, acquirePos.y),
        Action(Action.CLICK, 2),
        Action(Action.MOVE, 0, -acquirePos.x, -acquirePos.y),
    ])
except Exception as e:
    try:
        driver.get_screenshot_as_file('final.png')
        if CONFIG['mail']:
            mailConfig = CONFIG['mail']
            sendMail(mailConfig['smtp-server'], mailConfig['smtp-port'], mailConfig['email'], mailConfig['password'], [mailConfig['receiver']], '签到失败', str(e), 'final.png')
    except Exception as e:
        logging.error("截图发送邮件失败")
finally:
    if os.path.exists('final.png'):
        os.remove('final.png')
    driver.close()
