from markitdown import MarkItDown

def convert_to_md(filepath: str) -> str:
    md = MarkItDown()
    return md.convert(filepath).text_content
