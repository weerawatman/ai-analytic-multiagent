# User Journey — Explore → Backlog → BA/DA → Trusted

**Persona:** Data Engineer (solo Phase 1)  
**Goal:** สำรวจ insight ลึก ส่งต่อ BA/DA และ promote เป็น Trusted  
**Derived from:** `knowledge/01-discovery/discovery-brief.md`

---

## Journey Map

```
[Explore คำถาม] → [ได้คำตอบ Draft + Quality Bar D] → [Save Backlog]
       ↓
[Export รายงานไทย] → [คุย BA/DA นอกระบบ] → [บันทึก Feedback]
       ↓
[Promote → HITL Preview] → [Approve] → [Trusted Definition + Playbook]
       ↓
[ถามใน Trusted Mode ด้วยนิยามที่ยอมรับแล้ว]
```

---

## Steps — Explore Phase

| Step | User action | System response |
|------|-------------|-----------------|
| 1 | เลือกคำถามสำรวจจาก theme หรือพิมพ์เอง | แสดง badge **Explore · Draft** |
| 2 | รอ agent วิเคราะห์ (อาจนาน) | Progress indicator + agent ที่กำลังทำงาน (Analyst/Scientist/DE) |
| 3 | อ่านคำตอบ | แสดง: สรุป (TH), SQL, assumptions, sanity check, sample rows, คำถามถาม BA/DA |
| 4 | กด "บันทึกเป็น Insight Candidate" | สร้าง backlog item (JSON) |
| 5 | ทำซ้ำกับคำถามอื่นใน theme เดียวกัน | Backlog list เติบโต |

---

## Steps — Handoff Phase

| Step | User action | System response |
|------|-------------|-----------------|
| 6 | เปิด backlog item → กด "Export รายงาน" | สร้าง Markdown ภาษาไทย ใน `data/local/exports/` |
| 7 | นำรายงานไปคุย BA/DA (meeting/chat) | — (นอกระบบ) |
| 8 | กลับมาบันทึก feedback | Text field + status: discussing → validated/rejected |

---

## Steps — Trusted Phase

| Step | User action | System response |
|------|-------------|-----------------|
| 9 | กด "Promote to Trusted" (item ที่ validated) | HITL preview: metric, assumptions, playbook, example Q |
| 10 | Approve | เขียน `data/local/semantic/trusted.json` |
| 11 | สลับโหมดเป็น **Trusted** | Badge เปลี่ยน — คำตอบอ้างอิงนิยามที่ approve แล้ว |

---

## Emotional Arc

| Phase | Feeling | Design response |
|-------|---------|-----------------|
| Explore | อยากรู้ / ไม่มั่นใจ | Label Draft ชัด — ไม่หลอกว่าถูกต้องแล้ว |
| รอ agent | อึดอัดถ้ารอเงียบ | Progress + แสดงขั้นตอน |
| Export | ต้องการ credibility กับทีม | รายงานครบ ภาษาไทย มีตัวเลข |
| Promote | ต้องการ control | HITL บังคับ approve ทุกครั้ง |

---

## Out of Scope (This Journey)

- BA/DA login เข้ามาดู backlog เอง
- Auto-notify ทีม
- Write-back Fabric

---

## Success Criteria (Journey)

- ≥1 backlog item ผ่าน Quality Bar D
- ≥1 item promote เป็น Trusted หลัง feedback
- User รู้เสมอว่าอยู่โหมด Explore หรือ Trusted
