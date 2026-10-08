# Modified/added 2026-10-08 for this unofficial GPL-3.0-only application.
# Upstream MIT notices are preserved in LICENSES/.
"""User-authored profiles only. Windows current-user DPAPI; atomic encrypted writes.

Modified 2026-10-08. GPL-3.0-only as part of this application.
"""
import ctypes
from ctypes import wintypes
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import uuid

PERSONAL = ('name', 'background', 'boundaries')
FIELDS = ('relationship', 'goal', 'background', 'boundaries', 'experiences')
GOALS = ('自然接话', '邀约', '澄清', '修复', '拒绝', '退出')


class StoreError(Exception):
    pass


def default_path():
    return Path(os.environ['LOCALAPPDATA']) / 'JevAdvisorCommunity' / 'advisor' / 'profiles.dat'


def protect(data, decrypt=False):
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise StoreError('档案加密或解密失败，请使用原 Windows 用户登录；原文件未被覆盖。')
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel = ctypes.WinDLL('kernel32')
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree.restype = ctypes.c_void_p
        kernel.LocalFree(target.data)


def clean(values, keys):
    return {k: str(values.get(k, ''))[:3000].strip() for k in keys}


class ProfileStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else default_path()
        self.data = {'version': 1, 'personal': clean({}, PERSONAL), 'profiles': {}, 'links': {}}
        try:
            self.original = self.path.read_bytes() if self.path.exists() else None
            if self.original is not None:
                self.data = json.loads(protect(self.original, decrypt=True))
                self._validate()
        except StoreError:
            raise
        except (OSError, ValueError, TypeError, KeyError):
            raise StoreError('无法读取档案或档案格式不正确；原文件已保留，未创建空白档案覆盖。') from None

    def _validate(self):
        d = self.data
        if not isinstance(d, dict) or d.get('version') != 1:
            raise ValueError()
        for key in ('personal', 'profiles', 'links'):
            if not isinstance(d.get(key), dict):
                raise ValueError()
        if any(not isinstance(d['personal'].get(k), str) for k in PERSONAL):
            raise ValueError()
        for ident, p in d['profiles'].items():
            if not isinstance(p, dict) or any(not isinstance(p.get(k), str) for k in (*FIELDS, 'name')):
                raise ValueError()
        if any(not isinstance(k, str) or not isinstance(v, str) or v not in d['profiles'] for k, v in d['links'].items()):
            raise ValueError()

    def commit(self, data):
        temp = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Serialize writers across app instances; reject stale forms instead of overwriting.
            import msvcrt
            with open(self.path.with_suffix('.lock'), 'a+b') as lock:
                lock.seek(0)
                lock.write(b'0')
                lock.flush()
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                try:
                    current = self.path.read_bytes() if self.path.exists() else None
                    if current != self.original:
                        raise StoreError('档案已在另一个窗口更新，请关闭并重新打开军师窗口后再编辑。')
                    encrypted = protect(json.dumps(data, ensure_ascii=False).encode('utf-8'))
                    fd, temp = tempfile.mkstemp(dir=self.path.parent, suffix='.tmp')
                    with os.fdopen(fd, 'wb') as stream:
                        stream.write(encrypted)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(temp, self.path)
                    self.original = encrypted
                    self.data = deepcopy(data)
                finally:
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            raise StoreError('档案保存失败或正被其他窗口使用；修改尚未保存，请重试。') from None
        finally:
            if temp and os.path.exists(temp):
                os.unlink(temp)

    def save(self, ident, name, profile, personal, link=None, associate=True):
        if not name.strip():
            raise StoreError('请填写一个便于区分对象的档案名称。')
        ident = ident or uuid.uuid4().hex
        d = deepcopy(self.data)
        d['personal'] = clean(personal, PERSONAL)
        p = clean(profile, FIELDS)
        if p['goal'] not in GOALS:
            p['goal'] = GOALS[0]
        d['profiles'][ident] = {**p, 'name': name.strip()[:100]}
        if link and associate:
            d['links'][link] = ident
        elif link and d['links'].get(link) == ident:
            d['links'].pop(link)
        self.commit(d)
        return ident

    def delete(self, ident):
        d = deepcopy(self.data)
        d['profiles'].pop(ident, None)
        d['links'] = {k: v for k, v in d['links'].items() if v != ident}
        self.commit(d)

    def candidate(self, link):
        return self.data['links'].get(link)
