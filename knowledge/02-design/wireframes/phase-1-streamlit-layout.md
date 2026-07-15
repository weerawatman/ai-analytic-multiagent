# Wireframe Notes — Streamlit Phase 1 Layout

**Status:** Text wireframe only (no visual redesign)  
**Principle:** เน้น output quality — UI พอใช้ ไม่ refactor ใหญ่

---

## Page Structure (Single Page + Sidebar)

```
┌─────────────────────────────────────────────────────────────────┐
│  AI Fabric Insight Explorer                    [Explore|Trusted]│
├──────────────┬──────────────────────────────────────────────────┤
│  SIDEBAR     │  MAIN AREA                                       │
│              │                                                  │
│ Fabric: ● OK │  ┌─ Theme: [Sales ▼] ─────────────────────────┐  │
│              │  │ คำถามสำรวจ: [chip] [chip] [chip]            │  │
│ [สแกน Schema]│  └────────────────────────────────────────────┘  │
│              │                                                  │
│ ── Backlog ──│  ┌─ Chat ─────────────────────────────────────┐  │
│ • item 1 🟡  │  │ 🤖 Draft · Explore                        │  │
│ • item 2 🟢  │  │ สรุป: ...                                 │  │
│              │  │ SQL: ```...```                            │  │
│ [ดูทั้งหมด]  │  │ Assumptions: ...                          │  │
│              │  │ Sample: [table]                           │  │
│ ── Trusted ──│  │ ❓ ถาม BA/DA: ...                         │  │
│ • metric A   │  └───────────────────────────────────────────┘  │
│              │  [💾 บันทึก Backlog] [📄 Export]               │
│              │  ┌─ Input ──────────────────────────────────┐  │
│              │  │ พิมพ์คำถาม...                    [ส่ง]  │  │
│              │  └──────────────────────────────────────────┘  │
└──────────────┴──────────────────────────────────────────────────┘
```

---

## Key UI Elements

| Element | Behavior |
|---------|----------|
| **Mode toggle** | Explore / Trusted — สี/badge ต่างกันชัด |
| **Fabric status** | ● เขียว = connected, ● แดง = error + tooltip |
| **Draft badge** | ทุก Explore output มี "Draft · รอ validate" |
| **Progress** | Spinner + ข้อความ "กำลังวิเคราะห์... (อาจใช้เวลา)" |
| **Backlog sidebar** | สี status: new/discussing/validated/promoted |
| **HITL panel** | Modal/expander เมื่อ promote — preview + Approve/Reject |

---

## Backlog Detail View (Expander or Second Panel)

```
Insight: ยอดขายรายเดือน Q1 vs Q2
Status: [discussing ▼]
─────────────────────────
SQL Primary | SQL Alternative | Sample data
Assumptions | Unknowns | Questions for BA/DA
─────────────────────────
BA/DA Feedback: [textarea]
[บันทึก Feedback] [Promote to Trusted]
```

---

## Language

- Labels, buttons, reports: **ภาษาไทย**
- SQL, metric_key, table names: **English**

---

## Non-Goals (UI)

- Custom CSS / design system
- Multi-page navigation
- Mobile layout
- Dark mode
