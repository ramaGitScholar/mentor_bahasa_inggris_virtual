import telegramify_markdown

def to_telegram_markdown(text: str) -> str:
    """Ubah markdown standar (output dari LLM) menjadi telegram markdownV2 yang valid"""
    return telegramify_markdown.markdownify(text)
    