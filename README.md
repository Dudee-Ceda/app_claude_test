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
- เหล็ก SR24 / SD30 / SD40 / SD50, เหล็ก RB6–DB20, ระยะห่าง ≤ 300 mm และทุกตำแหน่งในแผ่นหารลงตัวกับระยะ Module 300/250/200 mm (หรม./ครน. พอดี)
- **ตารางเหล็กพื้นรูปแบบสำนักงาน** (SLAB / SLAB TYPE / SECTION / SPAN / T / L1 / L2 / CAMBER / Bottom 1–2 / Top 1–6) อ้างอิงแบบมาตรฐาน RC SLAB TYPE A–L; ตารางเดิม: ตั้งชื่อพื้น S1, S2, … รวมเป็นตารางเดียว แยกเหล็กทิศทางสั้น/ยาว ล่าง/บน ขอบต่อเนื่อง/ไม่ต่อเนื่อง พร้อมหมายเหตุสำหรับแบบ (ระยะทาบ, ระยะยื่นเหล็กบน) ส่งออก Excel (.csv), PDF A4 แนวนอน
  - ครบสำหรับส่งดราฟ: เหล็กบนที่ขอบไม่ต่อเนื่อง/ช่วงเดียว (−M = wL²/24), เหล็กกันร้าวบนใต้เหล็กบน, เหล็กล่างพื้นยื่น
  - ใช้เหล็กขนาดเดียวทั้งแผ่น (เหล็กหลักและเหล็กกันร้าว)
- **BOQ**: ปริมาตรคอนกรีต, ไม้แบบ, รายการเหล็กเสริม (จำนวน/ความยาว/น้ำหนัก) พร้อมเผื่อระยะทาบ
- แผนภาพโมเมนต์, แปลนแผ่นพื้นพร้อมเหล็กเสริม
- ดาวน์โหลดรายการคำนวณเป็น **PDF** (ฟอนต์ไทย Sarabun, OFL) หรือ Markdown

## อัปโหลดขึ้นเว็บ

มี 2 แบบ เลือกได้ตามต้องการ

| | เว็บไฟล์เดียว (`docs/index.html`) | แอป Streamlit (`app.py`) |
|---|---|---|
| ที่ฝาก | GitHub Pages, Netlify, Cloudflare Pages, โฮสต์ใดก็ได้ | Streamlit Community Cloud (ฟรี) |
| คำนวณที่ | เบราว์เซอร์ผู้ใช้ (JavaScript) — เร็ว ไม่ต้องมีเซิร์ฟเวอร์ | เซิร์ฟเวอร์ Python |
| ส่งออก | คัดลอกไป Excel / Markdown | ดาวน์โหลด PDF, Excel (.csv), Markdown |
| ตารางเหล็กพื้น | เก็บในเบราว์เซอร์เครื่องนั้น | เก็บระหว่างเปิดหน้าเว็บ |

ทั้งสองแบบให้ผลคำนวณเท่ากัน (ตรวจด้วย `tests/test_web_parity.py`)

### แบบที่ 1: GitHub Pages (เว็บไฟล์เดียว)
1. GitHub → repo นี้ → **Settings → Pages**
2. Source: **Deploy from a branch** → เลือก branch `claude/rc-slab-design-streamlit-o8fost` (หรือ `main` หลัง merge) → โฟลเดอร์ **`/docs`** → Save
3. รอ 1–2 นาที จะได้ URL `https://<user>.github.io/app_claude_test/`

หมายเหตุ: repo แบบ private ต้องใช้ GitHub แบบเสียเงินจึงจะเปิด Pages ได้ ถ้าไม่ใช่ ให้ใช้ Netlify แทน

### แบบที่ 1 (ทางเลือก): Netlify / Cloudflare Pages
ลากโฟลเดอร์ `docs/` ไปวางที่ https://app.netlify.com/drop จะได้ URL ทันที ไม่ต้องตั้งค่าอะไร

### แบบที่ 2: Streamlit Community Cloud
1. เข้า https://share.streamlit.io แล้วล็อกอินด้วย GitHub
2. **Create app** → repo `dudee-ceda/app_claude_test`, branch `claude/rc-slab-design-streamlit-o8fost`, main file `app.py`
3. Advanced settings → Python 3.12 → **Deploy** จะได้ `https://<ชื่อแอป>.streamlit.app`

### แก้ไขเว็บไฟล์เดียว
แก้ที่ `web/index.html` แล้วรัน `python scripts/build_web.py` เพื่อสร้าง `docs/index.html` ใหม่
(`tests/test_site.py` จะเตือนถ้าลืม build)

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
web/index.html      # เว็บไฟล์เดียว (ต้นฉบับ)
docs/index.html     # เว็บสำหรับอัปโหลด (สร้างด้วย scripts/build_web.py)
.streamlit/         # ค่าตั้ง Streamlit
tests/              # unit tests
```

> ⚠️ เครื่องมือช่วยคำนวณเบื้องต้น ผลลัพธ์ต้องตรวจสอบและรับรองโดยวิศวกรโยธาผู้มีใบอนุญาต
