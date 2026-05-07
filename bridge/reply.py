"""兼容占位模块"""

class ReplyType:
    TEXT = "text"
    IMAGE = "image"
    IMAGE_URL = "image_url"
    INFO = "info"
    ERROR = "error"

class Reply:
    def __init__(self, reply_type, content):
        self.type = reply_type
        self.content = content