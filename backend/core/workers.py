import easyocr

def extract_text(path):
    reader = easyocr.Reader(['en']) 
    result = reader.readtext(path, detail=0)
    text = "\n".join(result)
    return text