from markitdown import MarkItDown


def convert_to_md(file):
    md = MarkItDown(enable_plugins=False)
    print(md.convert(file))
