import sys
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image

from addons.base import _find_template2
from util.richlog import get_logger
from . import common
from . import imgops
from . import minireco
from . import resources
from . import util

logger = get_logger(__name__)

@lru_cache(1)
def load_data():
    reco = minireco.MiniRecognizer(resources.load_pickle('minireco/NotoSansCJKsc-Medium.dat'))
    reco2 = minireco.MiniRecognizer(resources.load_pickle('minireco/Novecentosanswide_Medium.dat'))
    return (reco, reco2)


consume_icon = common.convert_to_cv(resources.load_image_cached('before_operation/consume_icon.png'), cv2.COLOR_BGR2GRAY)
consume_icon = cv2.threshold(consume_icon, 127, 255, cv2.THRESH_BINARY)[1]
ap_icon = common.convert_to_cv(resources.load_image_cached('before_operation/ap_icon2.png'), cv2.COLOR_BGR2GRAY)
ap_icon = cv2.threshold(ap_icon, 127, 255, cv2.THRESH_BINARY)[1]
delegation_checked = common.convert_to_cv(resources.load_image_cached('before_operation/delegation_checked2.png'), cv2.COLOR_BGR2GRAY)


@lru_cache(1)
def recognize(img):
    vw, vh = util.get_vwvh(img.size)
    scale = vh / 7.2

    cv_screen = common.convert_to_cv(img, cv2.COLOR_BGR2GRAY)
    thr_screen = cv2.threshold(cv_screen, 127, 255, cv2.THRESH_BINARY)[1]
    # cv2.imshow('test', thr_screen)
    # cv2.waitKey(0)
    max_val, max_loc = _find_template2(ap_icon, thr_screen, scale)
    ap_rect = map(int, (max_loc[0] + 6.53 * vh, max_loc[1], max_loc[0] + 23 * vh, max_loc[1] + 6.388 * vh))
    consume_ap = max_val > 0.8

    apimg = img.crop(ap_rect).convert('L')
    reco_Noto, reco_Novecento = load_data()
    apimg = imgops.enhance_contrast(apimg, 80, 255)
    logger.logimage(apimg)
    aptext, _ = reco_Noto.recognize2(apimg, subset='0123456789/')
    logger.logtext(aptext)
    # print("AP:", aptext)

    opidimg = img.crop((100 * vw - 49.444 * vh, 10.972 * vh, 100 * vw - 38.472 * vh, 15.556 * vh)).convert('L')
    opidimg = imgops.enhance_contrast(opidimg, 80, 255)
    logger.logimage(opidimg)
    opidtext = str(reco_Novecento.recognize(opidimg))
    if opidtext.endswith('-'):
        opidtext = opidtext[:-1]
    opidtext = opidtext.upper()
    logger.logtext(opidtext)
    fixup, opidtext = minireco.fix_stage_name(opidtext)
    if fixup:
        logger.logtext('fixed to ' + opidtext)

    nofriendshiplist = ['OF-F']
    no_friendship = any(opidtext.startswith(header) for header in nofriendshiplist)

    max_val, max_loc = _find_template2(delegation_checked, cv_screen, scale)
    logger.logtext(f'delegated max_val, max_loc: {max_val, max_loc}')
    delegated = max_val > 0.9
    logger.logtext('delegated: %s' % delegated)

    max_val, max_loc = _find_template2(consume_icon, common.convert_to_cv(img, cv2.COLOR_BGR2GRAY), scale)
    consume_rect = list(map(int, (max_loc[0] + 4.863*vh, max_loc[1], max_loc[0] + 12.5*vh, max_loc[1] + 3.333*vh)))
    start_rect = list(map(int, (max_loc[0], max_loc[1] - 4.58*vh, max_loc[0] + 12.5 * vh, max_loc[1] + 3.333 * vh)))
    delegate_button_rect = list(map(int, (max_loc[0], max_loc[1] - 13.194 * vh, max_loc[0] + 12.5 * vh, max_loc[1] - 12.9 * vh)))
    consumeimg = img.crop(consume_rect).convert('L')
    consumeimg = imgops.enhance_contrast(consumeimg, 80, 255)
    logger.logimage(consumeimg)
    consumetext, minscore = reco_Noto.recognize2(consumeimg, subset='-0123456789')
    consumetext = ''.join(c for c in consumetext if c in '0123456789')
    logger.logtext('{}, {}'.format(consumetext, minscore))

    if not aptext:
        # ASSUMPTION: 只有在战斗前界面才能识别到右上角体力
        return None
    if not consumetext.isdigit():
        # ASSUMPTION: 所有关卡都显示并能识别体力消耗
        return None

    return {
        'AP': aptext,
        'consume_ap': consume_ap,
        'no_friendship': no_friendship,
        'operation': opidtext,
        'delegated': delegated,
        'consume': int(consumetext) if consumetext.isdigit() else None,
        'style': 'main',
        'delegate_button': delegate_button_rect,
        'start_button': start_rect
    }
    # print('consumption:', consumetext)

#
# def recognize_interlocking(img):
#     vw, vh = util.get_vwvh(img)
#
#     consume_ap = imgops.compare_region_mse(img, (100*vw-31.944*vh, 2.407*vh, 100*vw-25.648*vh, 8.426*vh), 'before_operation/interlocking/ap_icon.png', logger=logger)
#
#     apimg = img.crop((100*vw-25.278*vh, 2.407*vh, 100*vw-10.093*vh, 8.426*vh)).convert('L')
#     reco_Noto, reco_Novecento = load_data()
#     apimg = imgops.enhance_contrast(apimg, 80, 255)
#     logger.logimage(apimg)
#     aptext, _ = reco_Noto.recognize2(apimg, subset='0123456789/')
#     logger.logtext(aptext)
#
#     delegated = imgops.compare_region_mse(img, (100*vw-32.963*vh, 78.333*vh, 100*vw-5.185*vh, 84.167*vh), 'before_operation/interlocking/delegation_checked.png', logger=logger)
#
#     consumeimg = img.crop((100*vw-11.944*vh, 94.259*vh, 100*vw-5.185*vh, 97.500*vh)).convert('L')
#     consumeimg = imgops.enhance_contrast(consumeimg, 80, 255)
#     logger.logimage(consumeimg)
#     consumetext, minscore = reco_Noto.recognize2(consumeimg, subset='-0123456789')
#     consumetext = ''.join(c for c in consumetext if c in '0123456789')
#     logger.logtext('{}, {}'.format(consumetext, minscore))
#
#     return {
#         'AP': aptext,
#         'consume_ap': consume_ap,
#         'no_friendship': False,
#         'operation': 'interlocking',
#         'delegated': delegated,
#         'consume': int(consumetext) if consumetext.isdigit() else None,
#         'style': 'interlocking',
#         'delegate_button': (100*vw-32.083*vh, 81.111*vh, 100*vw-6.111*vh, 86.806*vh),
#         'start_button': (100*vw-32.083*vh, 89.306*vh, 100*vw-6.111*vh, 96.528*vh)
#     }


def check_confirm_troop_rect(img):
    vw, vh = util.get_vwvh(img.size)
    icon1 = img.crop((50 * vw + 57.083 * vh, 64.722 * vh, 50 * vw + 71.389 * vh, 79.167 * vh)).convert('RGB')
    icon2 = resources.load_image_cached('before_operation/operation_start.png', 'RGB')
    icon1, icon2 = imgops.uniform_size(icon1, icon2)
    coef = imgops.compare_ccoeff(np.asarray(icon1), np.asarray(icon2))
    logger.logimage(icon1)
    logger.logtext('ccoeff=%f' % coef)
    return coef > 0.9


def get_confirm_troop_rect(viewport):
    vw, vh = util.get_vwvh(viewport)
    return (50 * vw + 55.833 * vh, 52.963 * vh, 50 * vw + 72.778 * vh, 87.361 * vh)


def check_ap_refill_type(img):
    vw, vh = util.get_vwvh(img.size)
    icon1 = img.crop((50*vw-3.241*vh, 11.481*vh, 50*vw+42.685*vh, 17.130*vh)).convert('RGB')
    icon2 = resources.load_image_cached('before_operation/refill_with_item.png', 'RGB')
    icon1, icon2 = imgops.uniform_size(icon1, icon2)
    mse1 = imgops.compare_mse(icon1, icon2)
    logger.logimage(icon1)

    icon1 = img.crop((50*vw+41.574*vh, 11.481*vh, 50*vw+87.315*vh, 17.130*vh)).convert('RGB')
    icon2 = resources.load_image_cached('before_operation/refill_with_originium.png', 'RGB')
    icon1, icon2 = imgops.uniform_size(icon1, icon2)
    mse2 = imgops.compare_mse(icon1, icon2)

    logger.logimage(icon1)
    logger.logtext('mse1=%f, mse2=%f' % (mse1, mse2))

    if min(mse1, mse2) > 1500:
        return None
    if mse1 < mse2:
        return 'item'

    icon1 = img.crop((50*vw+25.972*vh, 36.250*vh, 50*vw+54.722*vh, 61.250*vh)).convert('RGB')
    icon2 = resources.load_image_cached('before_operation/no_originium.png', 'RGB')
    icon1, icon2 = imgops.uniform_size(icon1, icon2)
    mse3 = imgops.compare_mse(icon1, icon2)
    logger.logimage(icon1)
    logger.logtext('mse=%f' % mse3)
    if mse3 < 500:
        return None
    else:
        return 'originium'


def get_ap_refill_confirm_rect(viewport):
    vw, vh = util.get_vwvh(viewport)
    return (50*vw+49.537*vh, 77.222*vh, 50*vw+74.352*vh, 84.815*vh)


def get_ap_refill_cancel_rect(viewport):
    vw, vh = util.get_vwvh(viewport)
    return (50*vw+14.259*vh, 77.130*vh, 50*vw+24.352*vh, 83.611*vh)


if __name__ == "__main__":
    print(recognize(Image.open(sys.argv[-1])))
