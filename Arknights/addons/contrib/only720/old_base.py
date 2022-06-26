import random
import time
from abc import ABC, abstractmethod

import cv2
import numpy as np
from PIL import Image

from Arknights.helper import ArknightsHelper
from automator import AddonBase


def cv2pil(cv_img):
    return Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))


def pil2cv(pil_img, mode=cv2.COLOR_BGR2RGB):
    return cv2.cvtColor(np.asarray(pil_img), mode)


def _find_template2(template, gray_screen, scale, center_pos=False):
    res = cv2.matchTemplate(gray_screen, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    if center_pos:
        h, w = template.shape[:2]
        max_loc = (int(max_loc[0] + w / 2), int(max_loc[1] + h / 2))
    if scale != 1:
        max_loc = (int(max_loc[0] * scale), int(max_loc[1] * scale))
    # print(max_val, max_loc)
    return max_val, max_loc


def crop_cv_by_rect(cv_img, rect):
    l, t, r, b = tuple(map(int, rect))
    return cv_img[t:b, l:r]


def show_img(img):
    cv2.imshow('test', img)
    cv2.waitKey()


class OldMixin(AddonBase):
    def __init__(self, helper):
        super().__init__(helper)
        if helper is None:
            helper = ArknightsHelper()
        self.helper = helper
        self.width, self.height = self.helper.viewport

    @abstractmethod
    def run(self, **kwargs):
        pass

    def click(self, pos, sleep_time=0.5, randomness=(5, 5)):
        self.tap_point(pos, sleep_time, randomness)

    def screenshot_raw(self):
        return self.screenshot().array

    def _find_template(self, template, center_pos=False):
        gray_screen, scale = self.gray_screenshot()
        return _find_template2(template, gray_screen, scale, center_pos)

    def gray_screenshot(self, base_height=720):
        screen = self.screenshot()
        gray_screen = screen.convert('L').array
        scale = self.height / base_height
        if self.height != base_height:
            gray_screen = cv2.resize(gray_screen, (int(self.width / scale), base_height))
        return gray_screen, scale