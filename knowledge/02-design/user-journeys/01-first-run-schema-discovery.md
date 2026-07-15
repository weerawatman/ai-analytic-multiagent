# User Journey — First Run & Schema Discovery

**Persona:** Data Engineer (solo Phase 1)  
**Goal:** เชื่อมต่อ Fabric และเลือก theme แรกเพื่อเริ่ม Explore  
**Derived from:** `knowledge/01-discovery/discovery-brief.md`

---

## Journey Map

```
[เปิดแอป localhost] → [ตรวจสถานะ Fabric] → [สแกน Schema] → [ดู 3 Themes] → [เลือก 1 Theme] → [เข้า Explore Session]
```

---

## Steps

| Step | User action | System response | Emotion / need |
|------|-------------|-----------------|----------------|
| 1 | เปิด Streamlit (`localhost:8501`) | แสดงหน้าแรก + สถานะ Fabric (connected/disconnected) | ต้องการรู้ว่าพร้อมใช้หรือยัง |
| 2 | กด "สแกน Schema" (ครั้งแรก auto-prompt) | DE Agent query metadata จาก `WH_SAP_PRD` | ไม่รู้จะเริ่มถามอะไร — ต้องการทางเลือก |
| 3 | อ่าน 3 themes ที่เสนอ (ภาษาไทย) | แต่ละ theme: ชื่อ, เหตุผล, จำนวนตารางโดยประมาณ, คำถามเริ่มต้น 2–3 ข้อ | ต้องการทิศทาง ไม่ใช่คำถามกระจัด |
| 4 | เลือก 1 theme | บันทึก theme ที่เลือก → เปิด Explore session | มั่นใจว่าโฟกัสถูก domain |
| 5 | ดูคำถามสำรวจที่ AI แตกให้ | แสดง list คำถamodel Explore (draft) | พร้อมลงลึกทีละข้อ |

---

## Pain Points Addressed

| Pain | How this journey helps |
|------|------------------------|
| ไม่มี starter questions | Schema scan → theme proposal |
| กลัวเลือก domain ผิด | 3 ตัวเลือก ranked + rationale |
| ไม่รู้ว่า Fabric ต่อได้ไหม | Health indicator ก่อน scan |

---

## Edge Cases

| Case | UX behavior |
|------|-------------|
| Fabric ไม่ connect | แสดง error ภาษาไทย + checklist (.env, SP permissions) |
| Schema ใหญ่มาก | แสดง progress "กำลังสแกน..." — ไม่ timeout เงียบๆ |
| User เปลี่ยน theme กลางคัน | เริ่ม session ใหม่ — แจ้งว่า backlog เดิมยังอยู่ |

---

## Success Criteria (Journey)

- User เลือก theme ได้ภายใน 1 session แรก
- ไม่ต้องพิมพ์ SQL เองเพื่อค้นหา theme
