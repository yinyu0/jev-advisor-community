# -*- coding: utf-8 -*-
# Modified/added 2026-10-07 for this unofficial GPL-3.0-only application.
# Upstream MIT portions retain their notices in LICENSES/Jev-MIT.txt.
"""父进程：只管界面。截图 + OCR 在 app/worker.py 的子进程里跑，队列里收新消息 →
冒出新的对方消息才调 engine → 悬浮窗给 3 条候选 → 人点「填入」。发送永远手动。静默期零调用。
上下文、结果、聊天记录都按会话名（子进程 OCR 头部标题得来）分开存，切会话不串味。

    pip install rapidocr-onnxruntime numpy windows-capture PySide6-Fluent-Widgets
两个模型（判断 Jev / 起草语言模型）的来源和 key 在独立设置页填写，不用改代码。IDE 里直接 Run。
"""
import ctypes
import multiprocessing
import queue
import threading
import traceback
from collections import deque

from app import settings, update, worker
from app.capture import find_chat_hwnd
from app.fill import fill
from app.overlay import Overlay
from app.capture_hotkey import CaptureHotkey
from app.version import VERSION
from core.engine import analyze
from app.i18n import T
from app.advisor_state import AdvisorSessions
from app.advisor_dialog import AdvisorDialog

advisor_sessions = AdvisorSessions()

def open_advisor():
    title = state['chat']
    if not title or title != ov.current_chat():
        ov.set_status('请先在微信打开要分析的单聊', 'warning')
        return
    if state['busy']:
        ov.set_status('正在生成，请稍后打开军师设置', 'warning')
        return
    msgs = list(chat_of(title)['history'])[-settings.context():]
    if not msgs or any(len(m) > 2 and m[2] for m in msgs):
        ov.set_status('请等待识别到单聊文字，初版不支持群聊', 'warning')
        return
    revision = chat_of(title)['rev']
    def apply(profile, deep):
        if state['chat'] != title or chat_of(title)['rev'] != revision:
            ov.set_status('会话或消息已变化，请关闭后重新核对', 'warning')
            return False
        advisor_sessions.activate(title, profile)
        chat_of(title)['rev'] += 1
        chat_of(title)['result'] = None
        start_analyze(title, msgs, deep=deep)
        return True
    def forget():
        advisor_sessions.forget(title)
        chat_of(title)['rev'] += 1
        chat_of(title)['result'] = None
        ov.show_cached(None)
        ov.set_status('军师已停用，临时背景已清除')
    # Never prefill a nickname-associated profile without confirming identity anew.
    dialog = AdvisorDialog(title, msgs, advisor_sessions.get(title) or {}, apply, forget)
    dialog.exec()

# {会话名: {history, result, rev, target, senders}}：每个会话各自的上下文、上次结果和版本号，互不串味
# history 里是 [(who, text, name)]，engine 只认 her/me，name 是群里的发言人（单聊/自己说的是 None）；
# 只是缓冲区，实际喂模型几条由设置里的「参考上下文」决定
# senders：这个群里发过言的人，去重、最近的排最前；target：用户挑的回复对象（None = 跟着最近那个走）
chats = {}
state = {"area": None, "busy": False, "rerun": None, "hwnd": None, "chat": ""}
results = queue.Queue()
update_result = queue.Queue()  # 独立小队列，别跟 results 的 (kind, r, title, revision) 形状搅在一起


def chat_of(title):
    return chats.setdefault(title, {"history": deque(maxlen=60), "result": None, "rev": 0,
                                    "target": None, "senders": []})


def target_of(title):
    """这个会话现在的回复对象：用户挑过且人还在就用它，否则用最近说话的那个；单聊没有发言人 → None。"""
    chat = chat_of(title)
    if chat["target"] in chat["senders"]:
        return chat["target"]
    return chat["senders"][0] if chat["senders"] else None


def fill_reply(text):
    if ov.current_chat() != state['chat'] or not capture_on.is_set():
        raise RuntimeError('会话已切换或采集已暂停，请重新核对后复制回复')
    if state["hwnd"] is None:  # 子进程重开过，hwnd 可能换了，用最新的
        raise RuntimeError(T("未找到聊天窗口，请确认已经打开"))
    if state["area"] is None:
        raise RuntimeError(T("输入区域尚不可用，请确认聊天窗口可见（不要最小化）"))
    if settings.reply_target() and ov.at_prefix_enabled():
        target = target_of(ov.current_chat())  # 填进去的是界面上正看着的那个会话的对象
        if target:
            text = f"@{target} " + text  # 纯文本，微信不认成真正的 @，只是让群里看得出在跟谁说
    fill(state["hwnd"], state["area"], text)


def spawn_worker():
    """开一个采集子进程，它跟着 capture_on 走：置位=采集，清掉=暂停。"""
    p = multiprocessing.Process(target=worker.run,
                                args=(q, state["hwnd"], capture_on, debug_on, state.get("app")),
                                daemon=True)
    p.start()
    return p


def set_debug(on):
    """调试视图开关：开 → 开窗 + 置位（子进程这才开始送帧，一帧 2~3MB）；关 → 清掉 + 收窗。"""
    global dbg
    if not on:
        debug_on.clear()
        if dbg is not None:
            dbg.hide()
        return
    if dbg is None:
        from app.debugwin import DebugWindow

        dbg = DebugWindow(on_close=on_debug_closed)
    dbg.show()
    debug_on.set()


def on_debug_closed():
    """用户直接关了调试窗 = 把开关也关了，否则设置页显示开着但没窗。"""
    debug_on.clear()
    ov.set_debug_switch(False)
    settings.save(debug_view_on=False)


def on_language_changed():
    """主界面切换语言后，同步刷新已经打开过的调试窗。"""
    if dbg is not None:
        dbg.retranslate()


def toggle_capture_hotkey():
    on_toggle_capture(not capture_on.is_set())


def on_toggle_capture(on):
    """标题栏开关。启动时没找到微信就没有子进程，这会儿再找一次，找到了才真开得起来。"""
    global child
    if not on:
        capture_on.clear()
        state['rerun'] = None
        for c in chats.values():
            c['rev'] += 1
            c['result'] = None
        ov.invalidate_replies()
        ov.set_capture(False)
        return
    if child is None:
        try:
            state["hwnd"], found = find_chat_hwnd()
            state["app"] = found.key
        except RuntimeError:
            ov.set_capture(False, "未找到聊天窗口，打开后再开启采集")
            return
        child = spawn_worker()
    capture_on.set()
    ov.set_capture(True)


def analyze_bg(msgs, title, revision, reply_to=None, profile=None, deep=False):
    """后台线程只跑网络调用，结果丢队列；UI 只在主线程的 tick 里动（Qt 不能跨线程碰）。"""
    try:
        results.put(("ok", analyze(msgs, profile.get('relationship') if profile else settings.relationship(), context=settings.context(),
                                   model=settings.draft_model() or None,
                                   provider=settings.draft_provider(),
                                   base_url=settings.draft_base_url() or None,
                                   reply_to=reply_to, style=settings.style(),
                                   thinking=settings.thinking(),
                                   single_model=True,
                                   advisor_profile=profile, deep=deep),
                     title, revision))
    except Exception as e:
        results.put(("err", '分析失败，请检查模型配置或重试（错误正文不记录）', title, revision))


def check_update_bg():
    """启动时后台查一次新版本，跟 analyze_bg 一个套路：网络调用在线程里，UI 只在 tick() 里动。"""
    r = update.check_latest(VERSION)
    if r:
        update_result.put(r)


def start_analyze(title, msgs, deep=False):
    if title != state['chat'] or not capture_on.is_set():
        ov.set_busy(False)
        return
    profile = advisor_sessions.get(title)
    if profile:
        msgs = msgs[-settings.context():]
    if not settings.has_llm_key():
        ov.set_status(lambda name=settings.draft_provider_name():
                      f"{T('起草来源 ')}{name}{T(' 没填密钥，去设置里补上')}", "warning")
        return
    state["busy"] = True
    ov.set_busy(True)
    reply_to = target_of(title) if settings.reply_target() else None  # 开关关着就是今天的行为
    threading.Thread(target=analyze_bg, args=(msgs, title, chat_of(title)["rev"], reply_to,
                                            profile, deep),
                     daemon=True).start()


def on_target_change(title, name):
    """用户挑了回复对象：记下来，这个会话里有对方的话就照新对象重跑一次。"""
    chat = chat_of(title)
    chat["target"] = name
    msgs = list(chat["history"])
    if not any(m[0] == "her" for m in msgs):
        return
    if state["busy"]:
        state["rerun"] = (title, msgs)
        ov.set_busy(True)
    else:
        start_analyze(title, msgs)


def drain():
    """把子进程队列里攒的东西全收掉。"""
    global child
    while True:
        try:
            msg = q.get_nowait()
        except queue.Empty:
            return
        kind = msg[0]
        if kind == "area":  # 只是窗口挪了位置，坐标跟着更新，别的什么都不用动
            state["area"] = msg[1]
            continue
        if kind == "chat":  # 微信切了会话，界面跟过去（用户正浏览别的会话时也跟，微信是准的）
            if state['chat'] != msg[1]:
                advisor_sessions.leave()
                state['rerun'] = None
                for c in chats.values():
                    c['rev'] += 1
                    c['result'] = None
            state["chat"] = msg[1]
            ov.set_chat(msg[1])
            continue
        if kind == "debug":  # 调试视图的一帧；窗口不在就直接丢掉
            if dbg is not None:
                dbg.show_packet(msg[1])
            continue
        if kind == "status":  # 单帧识别失败/报错，提示一下就好，别把正在跑的分析和已知坐标清掉
            ov.set_status(msg[1], "warning")
            ov.log(msg[1])
            continue
        if kind == "paused":  # 子进程确认已暂停
            if not capture_on.is_set():
                ov.set_capture(False)
            continue
        if kind == "resumed":  # 子进程重新开始采集
            if capture_on.is_set():
                ov.set_capture(True)
            continue
        if kind == "dead":  # 采集彻底停了（微信关了之类），这才是真的要清状态
            capture_on.clear()
            state["area"] = None
            for c in chats.values():  # 在跑的分析作废，回来的结果不再往界面上贴
                c["rev"] += 1
            state["rerun"] = None
            ov.invalidate_replies()
            ov.set_busy(False)
            ov.set_capture(False, msg[1])
            ov.log(msg[1])
            if child is not None:  # 子进程已经不干活了，收掉引用，下次打开开关重开一个
                child.terminate()
                child.join()
                child = None
            continue
        _, title, new, area = msg
        state["area"] = area
        chat = chat_of(title)
        chat["rev"] += 1  # 这个会话有新消息了，它在跑的分析作废
        if title == ov.current_chat():  # 看的是别的会话就别把人家的候选划掉
            ov.invalidate_replies()
        for who, name, text in new:
            chat["history"].append((who, text, name))
            ov.log_message(who, text, name, chat=title)
            if who == "her" and name:  # 群里发过言的人，去重后最近的排最前
                if name in chat["senders"]:
                    chat["senders"].remove(name)
                chat["senders"].insert(0, name)
        ov.set_targets(title, chat["senders"], target_of(title))  # 显不显示这一行由悬浮窗按开关决定
        if new[-1][0] == "her":  # 只有对方最新说话才值得分析
            msgs = list(chat["history"])
            if state["busy"]:
                state["rerun"] = (title, msgs)
                ov.set_busy(True)
            else:
                start_analyze(title, msgs)
        else:
            state["rerun"] = None
            ov.set_busy(False)
            ov.set_status("你已回复，等待对方的新消息")


def tick():
    try:
        drain()
        while not update_result.empty():
            latest, url = update_result.get()
            ov.set_update(latest, url)
        while not results.empty():
            kind, r, title, revision = results.get()
            state["busy"] = False
            if state["rerun"]:  # 分析期间又来了新消息，接着跑最新的
                (t, msgs), state["rerun"] = state["rerun"], None
                start_analyze(t, msgs)
                continue
            if revision != chat_of(title)["rev"]:  # 这个会话后来又说话了，这份结果过期了
                ov.set_busy(False)
                continue
            if kind == "ok":
                chat_of(title)["result"] = r  # 先存着；正看着这个会话才立刻贴上去
                if title == ov.current_chat():
                    ov.show(r)
                else:
                    ov.set_busy(False)
            else:
                ov.set_busy(False)
                ov.set_status("生成失败，请检查网络和服务设置；新消息到来后会重试。", "error")
                ov.log(r)
    except Exception:
        traceback.print_exc()  # 一帧出错不退出
    ov.after(50, tick)


if __name__ == "__main__":  # Windows 的 spawn 会让子进程重新执行本文件，没这行就无限套娃开进程
    multiprocessing.freeze_support()  # 打包成 exe 后 spawn 出来的子进程会重跑一遍 exe，没这行就无限弹界面
    ctypes.windll.user32.SetProcessDPIAware()
    q = multiprocessing.Queue()
    capture_on = multiprocessing.Event()  # 父子进程共用的开关，置位=采集
    debug_on = multiprocessing.Event()  # 同上，置位=子进程往队列里送整帧给调试窗
    child = dbg = None
    ov = Overlay(on_fill=fill_reply, on_toggle_capture=on_toggle_capture,
                 on_target_change=on_target_change, on_toggle_debug=set_debug,
                 on_language_changed=on_language_changed,
                 result_of=lambda t: chats.get(t, {}).get("result"))
    ov.advisorButton.clicked.connect(open_advisor)
    try:
        state["hwnd"], found = find_chat_hwnd()
        state["app"] = found.key
    except RuntimeError:
        ov.set_capture(False, "未找到聊天窗口，打开后再开启采集")
    else:
        child = spawn_worker()
        ov.set_capture(False, '采集默认暂停，配置完成后手动开启')
    if settings.debug_view():  # 上次开着就直接开回来
        set_debug(True)
    if not settings.has_llm_key():
        ov.set_status("请先在设置中配置模型", "warning")
        ov.after(0, ov.open_settings)
    if settings.check_update() and update.parse_version(VERSION):  # 开发版没有版本号，不查也不烦源码用户
        threading.Thread(target=check_update_bg, daemon=True).start()
    ov.after(50, tick)
    hotkey = CaptureHotkey(ov.app, toggle_capture_hotkey)
    try:
        if hotkey.register():
            ov.hotkeyHint.setText("Ctrl + Alt + J · 开始 / 暂停采集")
        else:
            ov.hotkeyHint.setText("Ctrl + Alt + J 注册失败（可能被占用），请使用采集开关")
        ov.run()
    finally:
        hotkey.close()
        if child is not None:
            child.terminate()
