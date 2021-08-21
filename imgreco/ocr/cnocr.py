from cnocr import CnOcr
from .common import *
import cv2
import numpy as np

cn_ocr = CnOcr(name='imgreco-cnocr')

is_online = False
# OCR 过程是否需要网络


info = "cnocr"


# 模块说明，用于在 log 中显示

def check_supported():
    """返回模块是否可用"""
    return True


class MyCnOcr(OcrEngine):
    def recognize(self, image, ppi=70, hints=None, **kwargs):
        cv_img = cv2.cvtColor(np.asarray(image), cv2.COLOR_GRAY2RGB)
        result = cn_ocr.ocr(cv_img)
        line = [OcrLine([OcrWord(Rect(0, 0), w) for w in ocrline]) for ocrline in result]
        return OcrResult(line)


def ocr_for_single_line(img):
    return ''.join(cn_ocr.ocr_for_single_line(img)).strip()


Engine = MyCnOcr
