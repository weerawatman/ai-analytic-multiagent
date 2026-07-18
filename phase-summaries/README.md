# Phase Summaries

โฟลเดอร์นี้เก็บสรุปงานท้ายแต่ละ phase ไว้ข้าง `README.md` ที่ root ของ repo — ใช้ทบทวนตอนปิด phase / ก่อนเริ่ม phase ถัดไป

**กฎ binding:** ดู `AGENTS.md` → **Documentation & Handover Contract** และ `.cursor/rules/project-documentation-governance.mdc`

---

## เมื่อไหร่ต้องเขียน/อัปเดต

| เหตุการณ์ | การกระทำ |
|---|---|
| ปิด phase (หรือปิดบางส่วน) | สร้าง/อัปเดต `phase-{letter}.md` |
| Push commit ที่เกี่ยวกับ phase | เติม hash + วันที่ push ใน **commits ที่เกี่ยวข้อง** |
| Live gate ผ่านหรือยังค้าง | อัปเดตบรรทัด **สถานะ** + **เกตที่ค้าง** + `PROJECT_OVERVIEW.md` §3 |
| งานคงเหลือเปลี่ยน | อัปเดต **งานคงเหลือ** + overview §11 |
| Phase เปลี่ยน architecture / flows | ยืนยัน `docs/diagrams/SYSTEM_DIAGRAMS.md` อัปเดตแล้ว — หรือบันทึก **diagram debt** ใน **หมายเหตุ** |

---

## Template (คัดลอกไปไฟล์ใหม่)

```markdown
# Phase {X} — {ชื่อ phase} (สรุปท้าย phase)

**วันที่:** YYYY-MM-DD
**สถานะ:** {code-complete | production-verified บางส่วน | ค้าง live} — อธิบายสั้น ๆ ว่า verified อะไรแล้ว vs ยังไม่
**เอกสารหลัก:** [phase-{x}-….md](../knowledge/05-architecture/phases/…)
**เกต:** [X-done.md](../knowledge/05-architecture/phases/gates/X-done.md) (ถ้ามี)

## สิ่งที่ทำแล้ว

- {เฉพาะสิ่งที่พิสูจน์ได้จาก commit, gate, หรือ phase doc}
- **Tests:** {N passed} — {คำสั่ง pytest ถ้าสำคัญ}

## งานคงเหลือ

- {งานที่ยังไม่ merge / ยังไม่ verify live}

## เกตที่ค้าง

- {gate หรือ §10 criteria ที่ยังไม่ผ่าน — อ้าง path}

## commits ที่เกี่ยวข้อง

- `{hash}` — {ข้อความ commit สั้น ๆ}
- pushed: YYYY-MM-DD → origin/{branch}   ← เติม **หลัง push เท่านั้น**

## หมายเหตุ

- {ข้อจำกัด, deferred work, ลinks อื่น}
```

---

## Checklist ก่อนถือว่า summary พร้อม handover

- [ ] ครบหัวข้อ: สิ่งที่ทำแล้ว · งานคงเหลือ · เกตที่ค้าง · commits · วันที่
- [ ] บรรทัด **สถานะ** แยก **code-complete** กับ **production-verified** ชัดเจน
- [ ] ลิงก์ phase doc + gate (ถ้ามี) ถูก path
- [ ] Commit hash ใส่หลัง push — ไม่ใส่ hash ที่ยังไม่ push
- [ ] ไม่ invent งาน — อ้าง evidence เท่านั้น
- [ ] `PROJECT_OVERVIEW.md` §3 / §11 สอดคล้องกับ summary นี้
- [ ] ถ้า phase เปลี่ยน flows/architecture — diagrams อัปเดตแล้ว หรือระบุ diagram debt ใน **หมายเหตุ**

---

## รายการไฟล์

| ไฟล์ | Phase |
|------|--------|
| [phase-k.md](phase-k.md) | Phase K — World-class Layer |
| [phase-j.md](phase-j.md) | Phase J — Learning Loops |
| [phase-i.md](phase-i.md) | Phase I — Proactive Insight Pipeline |
| [phase-h.md](phase-h.md) | Phase H — Analytics Engine |
| [phase-g.md](phase-g.md) | Phase G — Foundation |
| [phase-f.md](phase-f.md) | Phase F — Postgres fallback |
| [phase-d.md](phase-d.md) | Phase D — Pipeline hardening |
| [deep-onboarding.md](deep-onboarding.md) | Deep onboarding (ระหว่าง phase) |
