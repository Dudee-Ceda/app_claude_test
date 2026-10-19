# RC Slab Design

โปรแกรมออกแบบพื้นคอนกรีตเสริมเหล็ก (Reinforced Concrete Slab) ด้วย Streamlit — วิธีกำลัง (Strength Design Method), หน่วย kg · cm · m · ksc

## ความสามารถ
- **พื้นทางเดียว (One-way slab)** — สัมประสิทธิ์โมเมนต์ ACI: ช่วงเดียว, ต่อเนื่องปลายเดียว (2 ช่วง / มากกว่า 2 ช่วง), ต่อเนื่องสองปลาย, พื้นยื่น
  - ตรวจความหนาต่ำสุด ACI 318 Table 9.5(a) (ปรับตาม fy), ออกแบบเหล็กหลัก + เหล็กกันร้าว, ตรวจแรงเฉือน
  - พื้นยื่นรับน้ำหนักแนวเส้นที่ปลาย (ผนัง/ราวกันตก)
  - **การแอ่นตัว**: Ie แบบ Branson, ΔL ≤ L/360 และ λΔD + ΔL ≤ L/240 (ξ เลือกตามระยะเวลา)
- **พื้นสองทาง (Two-way slab)** — ACI 318-63 Method 2 (วิธีสัมประสิทธิ์ที่ใช้ทั่วไปในไทย / ว.ส.ท.)
  - เลือกความต่อเนื่องของขอบแต่ละด้าน → Case 1–5 อัตโนมัติ, ประมาณค่าเชิงเส้นตาม m = S/L
  - ความหนาต่ำสุด เส้นรอบรูป/180, d ช่วงยาว = d ช่วงสั้น − db, น้ำหนักถ่ายลงคาน
- เลือก Load combination: EIT / ACI 318-99 (1.4D+1.7L) หรือ ACI 318-19 (1.2D+1.6L)
- เหล็ก SR24 / SD30 / SD40 / SD50, เหล็ก RB6–DB20, ระยะห่างปัดลงทีละ 2.5 cm (≤ 3h, ≤ 45 cm)
- **ตารางเหล็กพื้น (Slab Schedule)** สำหรับทำแบบ: ตั้งชื่อพื้น S1, S2, … รวมเป็นตารางเดียว แยกเหล็กทิศทางสั้น/ยาว ล่าง/บน ขอบต่อเนื่อง/ไม่ต่อเนื่อง พร้อมหมายเหตุสำหรับแบบ (ระยะทาบ, ระยะยื่นเหล็กบน) ส่งออก Excel (.csv), PDF A4 แนวนอน
- **BOQ**: ปริมาตรคอนกรีต, ไม้แบบ, รายการเหล็กเสริม (จำนวน/ความยาว/น้ำหนัก) พร้อมเผื่อระยะทาบ
- แผนภาพโมเมนต์, แปลนแผ่นพื้นพร้อมเหล็กเสริม
- ดาวน์โหลดรายการคำนวณเป็น **PDF** (ฟอนต์ไทย Sarabun, OFL) หรือ Markdown

## เว็บเวอร์ชันเบราว์เซอร์ (ไม่ต้องติดตั้ง)
`web/index.html` เป็นเว็บไฟล์เดียว คำนวณด้วย JavaScript ในเบราว์เซอร์ ผลตรงกับ engine Python
(ตรวจด้วย `tests/test_web_parity.py`) เปิดไฟล์ได้ทันที หรือ deploy เป็น GitHub Pages ได้
ข้อต่างจากเวอร์ชัน Streamlit: ไม่มีปุ่มดาวน์โหลด PDF (ใช้ปุ่มคัดลอกรายการคำนวณแทน)

## Deploy เวอร์ชัน Streamlit (Streamlit Community Cloud)
1. เข้า https://share.streamlit.io แล้วล็อกอินด้วย GitHub
2. Create app → เลือก repo `dudee-ceda/app_claude_test`, branch `claude/rc-slab-design-streamlit-o8fost`, main file `app.py`
3. Deploy — จะได้ URL แบบ `https://<ชื่อแอป>.streamlit.app`

## การใช้งาน (เครื่องตัวเอง)
```bash
pip install -r requirements.txt
streamlit run app.py
```

## ทดสอบ
```bash
pip install pytest
python -m pytest
```

## โครงสร้าง
```
app.py              # Streamlit UI
rcslab/materials.py # วัสดุ, ตารางเหล็กเสริม, มาตรฐาน
rcslab/flexure.py   # ออกแบบแรงดัด/เฉือน แถบกว้าง 1 m
rcslab/one_way.py   # พื้นทางเดียว
rcslab/two_way.py   # พื้นสองทาง (Method 2)
rcslab/deflection.py# การแอ่นตัว
rcslab/boq.py       # ถอดปริมาณวัสดุ
rcslab/report_pdf.py# สร้าง PDF รายการคำนวณ
rcslab/schedule.py  # ตารางเหล็กพื้น
rcslab/fonts/       # ฟอนต์ Sarabun (SIL OFL 1.1)
tests/              # unit tests
```

> ⚠️ เครื่องมือช่วยคำนวณเบื้องต้น ผลลัพธ์ต้องตรวจสอบและรับรองโดยวิศวกรโยธาผู้มีใบอนุญาต
