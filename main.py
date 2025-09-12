import json
import logging
import random
import time
import tomllib

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("sufecoursehelper")
log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)
logger.setLevel(logging.INFO)


class LessonElector:
    def __init__(self, profile_id, request_config, headers):
        self.profile_id = profile_id
        self.headers = headers

        self.delay = (
            request_config["delay"]["min"],
            request_config["delay"]["max"],
        )
        self.max_retry = request_config["max_retry"]

    def _make_request(self, url):
        for retry_cnt in range(1, self.max_retry + 1):
            try:
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                if response.status_code == 200:
                    logger.debug(f"请求成功: {url}")
                    return response
                else:
                    logger.error(
                        f"{retry_cnt}/{self.max_retry}, 请求失败: {response.status_code}. 正在重试..."
                    )
                    time.sleep(random.uniform(*self.delay))
            except requests.RequestException as e:
                logger.error(
                    f"{retry_cnt}/{self.max_retry}, 请求失败: {e}. 正在重试..."
                )
                time.sleep(random.uniform(*self.delay))

    def get_lesson_cnt(self):
        url = f"https://eams.sufe.edu.cn/eams/stdElectCourse!queryStdCount.action?profileId={self.profile_id}"
        response = self._make_request(url)
        if response:
            res_text = response.text
            json_text = res_text[res_text.index("{") :]
            json_text = json_text.replace("'", '"')
            json_text = json_text.replace("sc:", '"sc":').replace("lc:", '"lc":')
            lesson_cnt = json.loads(json_text)
            return {int(k): (v["sc"], v["lc"]) for k, v in lesson_cnt.items()}
        return None

    def _extract_elect_lesson_response(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table")
        if table:
            first_tr = table.find("tr")  # type: ignore
            if first_tr:
                first_td = first_tr.find("td")  # type: ignore
                if first_td:
                    first_div = first_td.find("div")  # type: ignore
                    if first_div:
                        text = first_div.get_text(strip=True)  # type: ignore
                        text = text.replace("</br>", "").strip()
                        return text

    def elect_lesson(self, lesson_id):
        url = f"https://eams.sufe.edu.cn/eams/stdElectCourse!batchOperator.action?profileId={self.profile_id}&electLessonIds={lesson_id}&withdrawLessonIds=&v={time.time()}"
        response = self._make_request(url)
        if response:
            message = self._extract_elect_lesson_response(response)
            return message


def main():
    with open("config/config.toml", "rb") as f:
        config = tomllib.load(f)
    profile_id = config["profile_id"]
    wanted_lessons = config["wanted_lessons"]
    request_config = config["request_config"]
    headers = config["headers"]

    elector = LessonElector(profile_id, request_config, headers)

    cnt = 0
    while True:
        cnt += 1
        logger.info(
            f"第 {cnt} 次检查课程 {', '.join(map(str, wanted_lessons))} 空缺..."
        )
        for lesson_id in wanted_lessons:
            lesson_cnt = elector.get_lesson_cnt()

            if not (lesson_cnt and lesson_id in lesson_cnt):
                time.sleep(random.uniform(*elector.delay))
                logger.error(f"获取课程空缺失败, 课程 {lesson_id} 未找到")
                continue

            current_num, limit_num = lesson_cnt[lesson_id]
            if current_num < limit_num:
                logger.info(f"课程 {lesson_id} 发现空缺: {current_num}/{limit_num}")
                message = elector.elect_lesson(lesson_id)

                if message is None:
                    logger.error(f"选课请求失败: 课程 {lesson_id}")
                    continue

                logger.info(f"选课结果: {message}")

                if "成功" in message:
                    logger.info(f"课程 {lesson_id} 选课成功，停止尝试")
                    wanted_lessons.remove(lesson_id)
                elif "冲突" in message or "学分" in message or "已经选过" in message:
                    logger.info(f"课程 {lesson_id} 选课失败，停止尝试")
                    wanted_lessons.remove(lesson_id)

            time.sleep(random.uniform(*elector.delay))


if __name__ == "__main__":
    main()
