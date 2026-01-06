# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "beautifulsoup4",
#     "playwright",
#     "requests",
# ]
# ///

from __future__ import annotations

import json
import logging
import random
import re
import subprocess
import sys
import time
from argparse import ArgumentParser, RawTextHelpFormatter
from dataclasses import dataclass
from enum import Enum

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


class SelectResult(Enum):
    SUCCESS = "成功"
    FULL = "人数已满"
    CONFLICT = "冲突"
    CREDITS_LIMIT = "学分"
    REPEAT = "已经选过"
    UNKNOWN = "未知状况"


@dataclass
class Course:
    no: str
    id: str
    name: str


class CourseHelper:
    def __init__(
        self,
        stu_id: str,
        password: str,
        max_retry: int = 3,
        interval_range: tuple[int, int] = (5, 10),
    ):
        self.base_url = "https://eams.sufe.edu.cn/eams/stdElectCourse"
        self.login_url = f"{self.base_url}.action"

        self.login(stu_id, password)

        self.spots_url = (
            f"{self.base_url}!queryStdCount.action?profileId={self.profile_id}"
        )
        self.no2id_url = f"{self.base_url}!data.action?profileId={self.profile_id}"
        self.select_url = (
            f"{self.base_url}!batchOperator.action?profileId={self.profile_id}"
            + "&electLessonIds={course_id}"
        )

        # self.headers = {"Technological": "Equality"}
        self.headers = {}
        self.headers["Cookie"] = ";".join([f"{k}={v}" for k, v in self.cookies.items()])

        self.download_no2id()

        self.max_retry = max_retry
        self.interval_range = interval_range

    def login(self, stu_id: str, password: str) -> None:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()

            page = context.new_page()
            page.goto(self.login_url)
            page.wait_for_selector(".qrcode-close")
            page.locator(".qrcode-close").click()
            page.get_by_role("textbox", name="请输入学号 / 工号").fill(stu_id)
            page.get_by_role("textbox", name="请输入密码").fill(password)
            page.get_by_role("button", name="登 录").click()

            page.wait_for_url(self.login_url)
            page.once("dialog", lambda d: d.accept())
            with page.expect_popup() as page1_info:
                page.get_by_role("button").click()
            page1 = page1_info.value

            url = page1.url
            all_cookies = context.cookies()
            browser.close()

        self.cookies = {
            c["name"]: c["value"]  # type: ignore
            for c in all_cookies
            if c["name"] in ("JSESSIONID", "SF_cookie_75")  # type: ignore
        }
        self.profile_id = url.split("=")[-1]

    def download_no2id(self):
        res = requests.get(self.no2id_url, headers=self.headers)
        res.raise_for_status()

        pattern = re.compile(r"id:\s*(\d+),\s*no:\s*'([^']+)'")
        matches = pattern.findall(res.text)
        self.no2id = {no: course_id for course_id, no in matches}

    def sleep(self):
        time.sleep(random.uniform(*self.interval_range))

    def get_spots(self):
        res = requests.get(self.spots_url, headers=self.headers)
        res.raise_for_status()
        res_text = res.text
        # /*sc 当前人数, lc 人数上限*/ window.lessonId2Counts = { '407027': { sc: 12, lc: 20 }, ... }
        json_text = (
            res_text[res_text.index("{") :]
            .replace("'", '"')
            .replace("sc:", '"sc":')
            .replace("lc:", '"lc":')
        )
        spots = json.loads(json_text)
        return {k: (v["sc"], v["lc"]) for k, v in spots.items()}

    def select_(self, course_id: str):
        res = requests.get(
            self.select_url.format(course_id=course_id), headers=self.headers
        )
        soup = BeautifulSoup(res.text, "html.parser")
        target = soup.select_one("table tr td div")
        if target:
            result = target.get_text(separator="\n", strip=True)
            logging.debug(result)
            for status in SelectResult:
                if status.value in result:
                    return status
        return SelectResult.UNKNOWN


def main(args):
    helper = CourseHelper(
        args.stu_id,
        args.password,
        args.max_retry,
        (args.min_interval, args.max_interval),
    )

    cnt = 1
    courses = [(no, helper.no2id[no]) for no in args.courses]
    while courses:
        logging.info(f"第 {cnt} 次检查课程 {', '.join([no for no, _ in courses])} 空缺")
        spots = helper.get_spots()
        for course_no, course_id in courses:
            if spots[course_id][0] < spots[course_id][1]:
                result = helper.select_(course_id)

                if result == SelectResult.SUCCESS:
                    logging.info(f"课程 {course_no} 选课成功，停止尝试")
                    courses.remove((course_no, course_id))
                    continue

                if result in (
                    SelectResult.CONFLICT,
                    SelectResult.CREDITS_LIMIT,
                    SelectResult.REPEAT,
                ):
                    logging.info(
                        f"课程 {course_no} 选课失败（{result.name}），停止尝试"
                    )
                    courses.remove((course_no, course_id))
                    continue

                logging.info(f"课程 {course_no} 选课失败（{result.name}），继续尝试")

        helper.sleep()
        cnt += 1


if __name__ == "__main__":
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"], check=True
    )

    parser = ArgumentParser(
        prog="SUFE Course Helper",
        formatter_class=RawTextHelpFormatter,
        description="上海财经大学选课助手\n用于自动化登录 SSO 并针对指定课程序号进行选课。",
        usage="uv run helper.py 学号 密码 课程序号 [课程序号 ...]",
        add_help=False,
    )

    required = parser.add_argument_group("必需参数")
    config = parser.add_argument_group("运行配置")
    debug_grp = parser.add_argument_group("调试与帮助")

    required.add_argument("stu_id", metavar="学号", help="您的学号")
    required.add_argument("password", metavar="密码", help="您的统一身份认证密码")
    required.add_argument(
        "courses",
        metavar="课程序号",
        nargs="+",
        help="待选课程的序号 (例如: 0359 1234)",
    )

    config.add_argument(
        "--max-retry",
        dest="max_retry",
        type=int,
        default=3,
        metavar="N",
        help="单个请求失败后的最大重试次数 (默认: 3)",
    )
    config.add_argument(
        "--min-interval",
        dest="min_interval",
        type=int,
        default=5,
        metavar="SEC",
        help="请求间的最小等待秒数 (默认: 5)",
    )
    config.add_argument(
        "--max-interval",
        dest="max_interval",
        type=int,
        default=10,
        metavar="SEC",
        help="请求间的最大等待秒数 (默认: 10)",
    )

    debug_grp.add_argument(
        "--debug", action="store_true", help="开启调试模式，显示详细的网络交互日志"
    )
    debug_grp.add_argument("-h", "--help", action="help", help="显示此帮助信息并退出")

    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        level=logging.DEBUG if args.debug else logging.INFO,
        datefmt="%y%m%d %H:%M:%S",
    )

    main(args)
