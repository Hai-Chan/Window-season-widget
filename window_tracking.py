import ctypes
from ctypes import wintypes
import os


user32 = ctypes.WinDLL("user32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)

DWMWA_EXTENDED_FRAME_BOUNDS = 9


user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND

user32.GetWindowThreadProcessId.argtypes = [
    wintypes.HWND,
    ctypes.POINTER(wintypes.DWORD),
]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD

user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL

user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL

user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL

dwmapi.DwmGetWindowAttribute.argtypes = [
    wintypes.HWND,
    wintypes.DWORD,
    ctypes.c_void_p,
    wintypes.DWORD,
]
dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long


class WindowTracker:
    def __init__(self):
        self.hwnd = None
        self.process_id = None

    def _get_process_id(self, hwnd):
        process_id = wintypes.DWORD()

        result = user32.GetWindowThreadProcessId(
            hwnd, ctypes.byref(process_id)
        )

        return process_id.value if result else None

    def capture_foreground(self):
        hwnd = user32.GetForegroundWindow()

        if not hwnd:
            return False

        process_id = self._get_process_id(hwnd)

        if process_id is None or process_id == os.getpid():
            return False

        old_target = (self.hwnd, self.process_id)
        self.hwnd = hwnd
        self.process_id = process_id

        if self.rectangle() is None:
            self.hwnd, self.process_id = old_target
            return False

        return True

    def rectangle(self):
        """Return physical screen coordinates, or None."""
        if not self.hwnd:
            return None

        if not user32.IsWindow(self.hwnd):
            self.hwnd = None
            self.process_id = None
            return None

        # Avoid tracking a handle reused by another process.
        if self._get_process_id(self.hwnd) != self.process_id:
            self.hwnd = None
            self.process_id = None
            return None

        if (
            not user32.IsWindowVisible(self.hwnd)
            or user32.IsIconic(self.hwnd)
        ):
            return None

        rect = wintypes.RECT()

        result = dwmapi.DwmGetWindowAttribute(
            self.hwnd,
            DWMWA_EXTENDED_FRAME_BOUNDS,
            ctypes.byref(rect),
            ctypes.sizeof(rect),
        )

        if result != 0:
            return None

        if rect.right <= rect.left or rect.bottom <= rect.top:
            return None

        return rect.left, rect.top, rect.right, rect.bottom