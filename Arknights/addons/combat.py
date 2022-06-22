from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, Optional

import app
import imgreco.before_operation
import penguin_stats.reporter
from Arknights.flags import *
from automator import AddonBase, cli_command
from imgreco.end_operation import EndOperationResult
from util.excutil import guard


@dataclass
class combat_session:
    state: Callable[['combat_session'], None] = None
    stop: bool = False
    operation_start: float = 0
    first_wait: bool = True
    mistaken_delegation: bool = False
    request_exit: bool = False
    prepare_reco: dict = None

def item_name_guard(item):
    return str(item) if item is not None else '<无法识别的物品>'

def item_qty_guard(qty):
    return str(qty) if qty is not None else '?'

def _parse_opt(argv):
    ops = []
    ops.append(lambda helper: helper.addon('CombatAddon').reset_refill())
    if len(argv) >= 2 and argv[1][:1] in ('+', '-'):
        opts = argv.pop(1)
        enable_refill = None
        for i, c in enumerate(opts):
            if c == '+':
                enable_refill = True
            elif c == '-':
                enable_refill = False
            elif c == 'r' and enable_refill is not None:
                def op(helper):
                    helper.addon('CombatAddon').use_refill = enable_refill
                    helper.addon('CombatAddon').refill_with_item = enable_refill
                ops.append(op)
            elif c == 'R' and enable_refill is not None:
                def op(helper):
                    helper.addon('CombatAddon').refill_with_originium = enable_refill
                ops.append(op)
            elif c in '0123456789' and enable_refill:
                num = int(opts[i:])
                def op(helper):
                    helper.addon('CombatAddon').max_refill_count = num
                ops.append(op)
                break
            else:
                raise ValueError('unrecognized token: %r in option %r' % (c, opts))
    return ops


class OperationOnceStatemachine:
    def __init__(self, c_id, addon: CombatAddon):
        self.logger = addon.logger
        self.c_id = c_id
        self.addon = addon
        self.vh, self.vw = self.addon.vh, self.addon.vw

    def prepare_operation(self):
        count_times = 0
        while True:
            screenshot = self.addon.screenshot()
            recoresult = imgreco.before_operation.recognize(screenshot)
            if recoresult is not None:
                self.logger.debug('当前画面关卡：%s', recoresult['operation'])
                if self.c_id is not None:
                    # 如果传入了关卡 ID，检查识别结果
                    if recoresult['operation'] != self.c_id:
                        self.logger.error('不在关卡界面')
                        raise StopIteration()
                break
            else:
                count_times += 1
                self.addon.delay(1, False)
                if count_times <= 7:
                    self.logger.warning('不在关卡界面')
                    self.addon.delay(TINY_WAIT, False)
                    continue
                else:
                    self.logger.error('{}次检测后都不再关卡界面，退出进程'.format(count_times))
                    raise StopIteration()

        current_ap = int(recoresult['AP'].split('/')[0])
        ap_text = '理智' if recoresult['consume_ap'] else '门票'
        self.logger.info('当前%s %d, 关卡消耗 %d', ap_text, current_ap, recoresult['consume'])
        if current_ap < int(recoresult['consume']):
            self.logger.error(ap_text + '不足 无法继续')
            if recoresult['consume_ap'] and self.addon.can_perform_refill():
                self.logger.info('尝试回复理智')
                self.addon.tap_rect(recoresult['start_button'])
                self.addon.delay(SMALL_WAIT)
                screenshot = self.addon.screenshot()
                refill_type = imgreco.before_operation.check_ap_refill_type(screenshot)
                confirm_refill = False
                if refill_type == 'item' and self.addon.refill_with_item:
                    self.logger.info('使用道具回复理智')
                    confirm_refill = True
                if refill_type == 'originium' and self.addon.refill_with_originium:
                    self.logger.info('碎石回复理智')
                    confirm_refill = True
                # FIXME: 道具回复量不足时也会尝试使用
                if confirm_refill:
                    self.addon.tap_rect(imgreco.before_operation.get_ap_refill_confirm_rect(self.addon.viewport))
                    self.addon.refill_count += 1
                    self.addon.delay(MEDIUM_WAIT)
                    return recoresult, True
                self.logger.error('未能回复理智')
                self.addon.tap_rect(imgreco.before_operation.get_ap_refill_cancel_rect(self.addon.viewport))
            raise StopIteration()

        if not recoresult['delegated']:
            self.logger.info('设置代理指挥')
            self.addon.tap_rect(recoresult['delegate_button'])
            return recoresult, True
        return recoresult, False

    def on_prepare(self, smobj):
        recoresult, rerun_prepare_operation = self.prepare_operation()
        if rerun_prepare_operation:
            return
        self.logger.info("理智充足 开始行动")
        self.addon.tap_rect(recoresult['start_button'])
        smobj.prepare_reco = recoresult
        smobj.state = self.on_troop

    def on_troop(self, smobj):
        count_times = 0
        while True:
            self.addon.delay(TINY_WAIT, False)
            screenshot = self.addon.screenshot()
            recoresult = imgreco.before_operation.check_confirm_troop_rect(screenshot)
            if recoresult:
                self.logger.info('确认编队')
                break
            else:
                count_times += 1
                if count_times <= 7:
                    self.logger.warning('等待确认编队')
                    continue
                else:
                    self.logger.error('{} 次检测后不再确认编队界面'.format(count_times))
                    raise StopIteration()
        self.addon.tap_rect(imgreco.before_operation.get_confirm_troop_rect(self.addon.viewport))
        smobj.operation_start = time.monotonic()
        smobj.state = self.on_operation

    def on_operation(self, smobj):
        import imgreco.end_operation
        import imgreco.common
        if smobj.first_wait:
            if len(self.addon.operation_time) == 0:
                wait_time = BATTLE_NONE_DETECT_TIME
            else:
                wait_time = sum(self.addon.operation_time) / len(self.addon.operation_time) - 7
            self.logger.info('等待 %d s' % wait_time)
            smobj.first_wait = False
        else:
            wait_time = BATTLE_FINISH_DETECT

        t = time.monotonic() - smobj.operation_start
        finish_log_level = logging.INFO if int(t) % 10 == 0 else logging.DEBUG
        if smobj.request_exit:
            self.addon.delay(1, allow_skip=True)
        else:
            self.addon.delay(wait_time, allow_skip=True)
            t = time.monotonic() - smobj.operation_start
            finish_log_level = logging.INFO if int(t) % 10 == 0 else logging.DEBUG
            self.logger.log(finish_log_level, '已进行 %.1f s，判断是否结束', t)

        screenshot = self.addon.screenshot()

        if self.addon.match_roi('combat/topbar', method='ccoeff', screenshot=screenshot):
            if self.addon.match_roi('combat/lun', method='ccoeff', screenshot=screenshot) and not smobj.mistaken_delegation:
                self.logger.info('伦了。')
                smobj.mistaken_delegation = True
            else:
                self.logger.log(finish_log_level, '战斗未结束')
                return

        if self.addon.match_roi('combat/topbar_camp', method='ccoeff', screenshot=screenshot):
            if self.addon.match_roi('combat/lun_camp', method='ccoeff', screenshot=screenshot) and not smobj.mistaken_delegation:
                self.logger.info('伦了。')
                smobj.mistaken_delegation = True
            else:
                self.logger.log(finish_log_level, '战斗未结束')
                return

        if smobj.mistaken_delegation and not app.config.combat.mistaken_delegation.settle:
            if not smobj.request_exit:
                self.logger.info('退出关卡')
                self.addon.tap_rect(self.addon.load_roi('combat/exit_button').bbox)
                smobj.request_exit = True
                return

        if self.addon.match_roi('combat/failed', mode='L', method='ccoeff', screenshot=screenshot):
            self.logger.info("行动失败")
            smobj.mistaken_delegation = True
            smobj.request_exit = True
            self.addon.tap_rect((20*self.vw, 20*self.vh, 80*self.vw, 80*self.vh))
            return

        if self.addon.match_roi('combat/ap_return', screenshot=screenshot):
            self.logger.info("确认理智返还")
            self.addon.tap_rect((20*self.vw, 20*self.vh, 80*self.vw, 80*self.vh))
            return

        if imgreco.end_operation.check_level_up_popup(screenshot):
            self.logger.info("等级提升")
            self.addon.operation_time.append(t)
            smobj.state = self.on_level_up_popup
            return

        end_flag = imgreco.end_operation.check_end_operation(smobj.prepare_reco['style'], not smobj.prepare_reco['no_friendship'], screenshot)
        if not end_flag and t > 300:
            if imgreco.end_operation.check_end_operation2(screenshot):
                self.addon.tap_rect(imgreco.end_operation.get_end2_rect(screenshot))
                screenshot = self.addon.screenshot()
                end_flag = imgreco.end_operation.check_end_operation_legacy(screenshot)
        if end_flag:
            self.logger.info(f'战斗结束, 用时: {t:.2f} s')
            self.addon.operation_time.append(t)
            if self.addon.wait_for_still_image(timeout=15, raise_for_timeout=True, check_delay=0.5, iteration=3):
                smobj.state = self.on_end_operation
            return
        dlgtype, ocrresult = imgreco.common.recognize_dialog(screenshot)
        if dlgtype is not None:
            if dlgtype == 'yesno' and '代理指挥' in ocrresult:
                self.logger.warning('代理指挥出现失误')
                self.addon.frontend.alert('代理指挥', '代理指挥出现失误', 'warn')
                smobj.mistaken_delegation = True
                if app.config.combat.mistaken_delegation.settle:
                    self.logger.info('以 2 星结算关卡')
                    self.addon.tap_rect(imgreco.common.get_dialog_right_button_rect(screenshot))
                    self.addon.delay(2)
                    smobj.stop = True
                    return
                else:
                    self.logger.info('放弃关卡')
                    smobj.request_exit = True
                    self.addon.tap_rect(imgreco.common.get_dialog_left_button_rect(screenshot))
                    # 关闭失败提示
                    self.addon.wait_for_still_image()
                    return
            elif dlgtype == 'yesno' and '将会恢复' in ocrresult:
                if smobj.request_exit:
                    self.logger.info('确认退出关卡')
                    self.addon.tap_rect(imgreco.common.get_dialog_right_button_rect(screenshot))
                else:
                    self.logger.info('发现放弃行动提示，关闭')
                    self.addon.tap_rect(imgreco.common.get_dialog_left_button_rect(screenshot))
                return
            else:
                self.logger.error('未处理的对话框：[%s] %s', dlgtype, ocrresult)
                raise RuntimeError('unhandled dialog')

        self.logger.info('战斗未结束')

    def on_level_up_popup(self, smobj):
        import imgreco.end_operation
        self.addon.delay(SMALL_WAIT, randomize=True)
        self.logger.info('关闭升级提示')
        self.addon.tap_rect(imgreco.end_operation.get_dismiss_level_up_popup_rect(self.addon.viewport))
        self.addon.wait_for_still_image()
        smobj.state = self.on_end_operation

    def on_end_operation(self, smobj):
        screenshot = self.addon.screenshot()
        reportresult = penguin_stats.reporter.ReportResult.NotReported
        try:
            # 掉落识别
            drops = imgreco.end_operation.recognize(smobj.prepare_reco['style'], screenshot, True)
            self.logger.debug('%s', repr(drops))
            self.logger.info('掉落识别结果：%s', self.addon.format_recoresult(drops))
            log_total = len(self.addon.loots)
            for _, group in drops.items:
                for record in group:
                    if record.name is not None and record.quantity is not None:
                        self.addon.loots[record.name] = self.addon.loots.get(record.name, 0) + record.quantity
            self.addon.frontend.notify("combat-result", drops.to_json())
            self.addon.frontend.notify("loots", self.addon.loots)
            if log_total:
                self.addon.log_total_loots()
            if self.addon.use_penguin_report:
                reportresult = self.addon.penguin_reporter.report(drops)
                if isinstance(reportresult, penguin_stats.reporter.ReportResult.Ok):
                    self.logger.debug('report hash = %s', reportresult.report_hash)
        except Exception as e:
            self.logger.error('', exc_info=True)
        if self.addon.use_penguin_report and reportresult is penguin_stats.reporter.ReportResult.NotReported:
            filename = app.screenshot_path / ('未上报掉落-%d.png' % time.time())
            with open(filename, 'wb') as f:
                screenshot.save(f, format='PNG')
            self.logger.error('未上报掉落截图已保存到 %s', filename)
        self.logger.info('离开结算画面')
        self.addon.tap_rect(imgreco.end_operation.get_dismiss_end_operation_rect(self.addon.viewport))
        smobj.stop = True

    def create_combat_session(self):
        smobj = combat_session()
        smobj.state = self.on_prepare
        smobj.stop = False
        smobj.operation_start = 0
        return smobj

    def start(self):
        smobj = self.create_combat_session()
        while not smobj.stop:
            oldstate = smobj.state
            smobj.state(smobj)
            if smobj.state != oldstate:
                self.logger.debug('state changed to %s', smobj.state.__name__)

        if smobj.mistaken_delegation and app.config.combat.mistaken_delegation.skip:
            raise StopIteration()


class CombatAddon(AddonBase):
    def on_attach(self):
        self.operation_time = []
        self.reset_refill()
        self.loots = {}
        self.use_penguin_report = app.config.combat.penguin_stats.enabled
        if self.use_penguin_report:
            self.penguin_reporter = penguin_stats.reporter.PenguinStatsReporter()
        self.refill_count = 0
        self.max_refill_count = None

        # self.helper.register_gui_handler(self.gui_handler)

    def configure_refill(self, with_item: Optional[bool] = None, with_originium: Optional[bool] = None):
        if with_item is not None:
            self.refill_with_item = bool(with_item)
        if with_originium is not None:
            self.refill_with_originium = bool(with_originium)
        self.use_refill = self.refill_with_item or self.refill_with_originium
        return self

    def reset_refill(self):
        return self.configure_refill(False, False)

    def format_recoresult(self, recoresult: EndOperationResult):
        result = None
        with guard(self.logger):
            result = '[%s] %s' % (recoresult.operation,
                '; '.join('%s: %s' % (grpname, ', '.join('%sx%s' % (item_name_guard(item.name), item_qty_guard(item.quantity))
                for item in grpcont))
                for grpname, grpcont in recoresult.items))
        if result is None:
            result = '<发生错误>'
        return result

    def create_operation_once_statemachine(self, c_id) -> OperationOnceStatemachine:
        return OperationOnceStatemachine(c_id, self)

    def combat_on_current_stage(self,
                           desired_count=1000,  # 战斗次数
                           c_id=None,  # 待战斗的关卡编号
                           **kwargs):  # 扩展参数:
        '''
        :param MAX_TIME 最大检查轮数, 默认在 config 中设置,
            每隔一段时间进行一轮检查判断作战是否结束
            建议自定义该数值以便在出现一定失误,
            超出最大判断次数后有一定的自我修复能力
        :return:
            True 完成指定次数的作战
            False 理智不足, 退出作战
        '''
        if desired_count == 0:
            return c_id, 0
        self.operation_time = []
        count = 0
        remain = 0
        try:
            for _ in range(desired_count):
                # self.logger.info("开始第 %d 次战斗", count + 1)
                self.create_operation_once_statemachine(c_id).start()
                count += 1
                self.logger.info("第 %d 次作战完成", count)
                self.frontend.notify('completed-count', count)
                if count != desired_count:
                    # 2019.10.06 更新逻辑后，提前点击后等待时间包括企鹅物流
                    if app.config.combat.penguin_stats.enabled:
                        self.delay(SMALL_WAIT, randomize=True, allow_skip=True)
                    else:
                        self.delay(BIG_WAIT, randomize=True, allow_skip=True)
        except StopIteration:
            # count: succeeded count
            self.logger.error('未能进行第 %d 次作战', count + 1)
            remain = desired_count - count
            if remain > 1:
                self.logger.error('已忽略余下的 %d 次战斗', remain - 1)

        return c_id, remain

    def can_perform_refill(self):
        if not self.use_refill:
            return False
        if self.max_refill_count is not None:
            return self.refill_count < self.max_refill_count
        else:
            return True

    def log_total_loots(self):
        self.logger.info('目前已获得：%s', ', '.join('%sx%d' % tup for tup in self.loots.items()))

    @cli_command('quick')
    def cli_quick(self, argv):
        """
        quick [+-rR[N]] [n]
        重复挑战当前画面关卡特定次数或直到理智不足
        +r/-r 是否自动回复理智，最多回复 N 次
        +R/-R 是否使用源石回复理智（需要同时开启 +r）
        """

        ops = _parse_opt(argv)
        if len(argv) == 2:
            count = int(argv[1])
        else:
            count = 114514
        for op in ops:
            op(self)
        with self.helper.frontend.context:
            self.combat_on_current_stage(count)
        return 0


