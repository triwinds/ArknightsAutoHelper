import cv2
import cv2 as cv
import numpy as np
from PIL import Image

from util.richlog import get_logger
from . import imgops
from . import resources
from . import util
from . import ocr
from imgreco.common import convert_to_cv, convert_to_pil

LOGFILE = 'recruit.html'
logger = get_logger(__name__)

from resources.recruit_database import recruit_database
known_tags = set(y for x in recruit_database for y in x[2])
known_tags.update(('资深干员', '高级资深干员'))
known_tagchars = ''.join(set(c for t in known_tags for c in t))

def remove_unknown_chars(s, known_chars):
    result = ''.join(c for c in s if c in known_chars)
    return result


def get_recruit_tags(screen):
    res = get_recruit_tags_with_rect(screen)
    return list(res.keys())


def crop_image_only_outside(gray_img, raw_img, threshold=128, padding=3):
    mask = gray_img > threshold
    m, n = gray_img.shape
    mask0, mask1 = mask.any(0), mask.any(1)
    col_start, col_end = mask0.argmax(), n - mask0[::-1].argmax()
    row_start, row_end = mask1.argmax(), m - mask1[::-1].argmax()
    return raw_img[max(0, row_start - padding):min(m, row_end + padding),
           max(0, col_start - padding):min(n, col_end + padding)]


def preprocess(pil_img):
    cv_img = convert_to_cv(pil_img, cv2.COLOR_BGR2GRAY)
    cv_img = crop_image_only_outside(cv_img, cv_img)
    return Image.fromarray(cv_img)


def get_recruit_tags_with_rect(screen):
    import textdistance
    vw, vh = util.get_vwvh(screen)
    tag_rects = [
        (50 * vw - 36.481 * vh, 50.185 * vh, 50 * vw - 17.315 * vh, 56.111 * vh),
        (50 * vw - 13.241 * vh, 50.185 * vh, 50 * vw + 6.111 * vh, 56.111 * vh),
        (50 * vw + 10.000 * vh, 50.185 * vh, 50 * vw + 29.259 * vh, 56.111 * vh),
        (50 * vw - 36.481 * vh, 60.278 * vh, 50 * vw - 17.315 * vh, 66.019 * vh),
        (50 * vw - 13.241 * vh, 60.278 * vh, 50 * vw + 6.111 * vh, 66.019 * vh)
    ]

    eng = ocr.acquire_engine_global_cached('zh-cn')
    recognize = lambda img: eng.recognize(imgops.invert_color(img), int(vh * 20), hints=[ocr.OcrHint.SINGLE_LINE], char_whitelist=known_tagchars).text.replace(' ', '')
    cookedtags = {}
    for tag_rect in tag_rects:
        img = screen.crop(tag_rect)
        logger.logimage(img)
        img = preprocess(img)
        tag = recognize(img)
        logger.logtext(tag)
        if not tag:
            continue
        if tag in known_tags:
            cookedtags[tag] = tag_rect
            continue
        distances = [(target, textdistance.levenshtein(tag, target)) for target in known_tags.difference(cookedtags)]
        distances.sort(key=lambda x: x[1])
        mindistance = distances[0][1]
        matches = [x[0] for x in distances if x[1] == mindistance]
        if mindistance > 2:
            logger.logtext('autocorrect: minimum distance %d too large' % mindistance)
            cookedtags[tag] = tag_rect
        elif len(matches) == 1:
            logger.logtext('autocorrect to %s, distance %d' % (matches[0], mindistance))
            cookedtags[matches[0]] = tag_rect
        else:
            logger.logtext('autocorrect: failed to match in %s with distance %d' % (','.join(matches), mindistance))
            cookedtags[tag] = tag_rect

    return cookedtags
