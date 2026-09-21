import fitz, os
from PIL import Image, ImageDraw, ImageFont

SI_TEXT = [
 "SHIPPING INSTRUCTION",
 "Shipper: BLUE OCEAN COMMODITIES LLC",
 "Consignee: FARWEST TRADING CO LTD",
 "Notify Party: FARWEST TRADING CO LTD",
 "Port of Loading: COLOMBO, SRI LANKA",
 "Port of Discharge: BUENAVENTURA, COLOMBIA",
 "Container Count: 2 x 20'GP",
 "Gross Weight: 19,850 KG",
]
BL_TEXT_MISMATCH = [
 "BILL OF LADING",
 "Shipper: BLUE OCEAN COMMODITIES LLC",
 "Consignee: FARWEST TRADING CO LTD",
 "Notify Party: FARWEST TRADING CO LTD",
 "Port of Loading: COLOMBO, SRI LANKA",
 "Port of Discharge: BUENAVENTURA, COLOMBIA",
 "Container Count: 3 x 20'GP",
 "Gross Weight: 19,850 KG",
]

def make_image_pdf(lines, path, font_size=30):
    img = Image.new("RGB", (1300, 750), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()
    y = 45
    for ln in lines:
        d.text((45, y), ln, fill="black", font=font)
        y += font_size + 20
    tmp_png = path + ".png"
    img.save(tmp_png)
    doc = fitz.open()
    page = doc.new_page(width=1300, height=750)
    page.insert_image(page.rect, filename=tmp_png)
    doc.save(path)
    doc.close()
    os.remove(tmp_png)

OUT = os.path.dirname(__file__) + "/data/fresh_scan2"
os.makedirs(OUT, exist_ok=True)
make_image_pdf(SI_TEXT, OUT + "/SI2.pdf")
make_image_pdf(BL_TEXT_MISMATCH, OUT + "/BL2.pdf")
print("built", OUT)
