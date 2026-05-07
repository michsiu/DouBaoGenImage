"""兼容占位模块"""

class ContextType:
    TEXT = "text"
    IMAGE = "image"

class Event:
    ON_HANDLE_CONTEXT = "on_handle_context"

class EventAction:
    BREAK_PASS = "break_pass"
    CONTINUE = "continue"