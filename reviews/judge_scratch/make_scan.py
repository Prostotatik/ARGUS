"""Build a brand-new synthetic image-only PDF pair (never seen by DEVELOPER) and run through OCR+pipeline."""
import fitz, os
from PIL import Image, ImageDraw, ImageFont

SI_TEXT = [
 "SHIPPING INSTRUCTION",
 "Shipper: GREENFIELD AGRO EXPORTS SDN BHD",
 "Consignee: NORTHSTAR IMPORTS PTE LTD",
 "Notify Party: NORTHSTAR IMPORTS PTE LTD",
 "Port of Loading: PORT KLANG, MALAYSIA",
 "Port of Discharge: JEBEL ALI, UAE",
 "Container Count: 4 x 40'HC",
 "Gross Weight: 48,300 KG",
]
BL_TEXT = [
 "BILL OF LADING",
 "Shipper: GREENFIELD AGRO EXPORTS SDN BHD",
 "Consignee: NORTHSTAR IMPORTS PTE LTD",
 "Notify Party: NORTHSTAR IMPORTS PTE LTD",
 "Port of Loading: PORT KLANG, MALAYSIA",
 "Port of Discharge: JEBEL ALI, UAE",
 "Container Count: 4 x 40'HC",
 "Gross Weight: 48,300 KG",
]

def make_image_pdf(lines, path, font_size=28):
    img = Image.new("RGB", (1240, 700), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()
    y = 40
    for ln in lines:
        d.text((40, y), ln, fill="black", font=font)
        y += font_size + 18
    tmp_png = path + ".png"
    img.save(tmp_png)
    doc = fitz.open()
    page = doc.new_page(width=1240, height=700)
    page.insert_image(page.rect, filename=tmp_png)
    doc.save(path)
    doc.close()
    os.remove(tmp_png)

OUT = os.path.dirname(__file__) + "/data/fresh_scan"
os.makedirs(OUT, exist_ok=True)
make_image_pdf(SI_TEXT, OUT + "/SI_fresh.pdf")
make_image_pdf(BL_TEXT, OUT + "/BL_fresh.pdf")
print("built", OUT)
