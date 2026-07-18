# แผนภาพระบบ — AI Fabric Insight Explorer

เอกสารภาพสำหรับอ่านร่วมกันระหว่างผู้ใช้ธุรกิจ เจ้าของระบบ และนักพัฒนา โดยอ้างอิงจากโค้ดและเอกสารสถานะ ณ วันที่ 2026-07-18

> ป้ายแหล่งข้อมูลที่ระบบใช้จริง: **Fabric** = แหล่งหลัก, **Postgres mirror** = แหล่งสำรองเมื่อ Fabric ใช้ไม่ได้, **Offline** = ใช้ cache/discovery บนดิสก์และไม่รัน SQL จริง ทุกคำตอบหรือ insight ต้องแสดง provenance และห้าม fallback แบบเงียบ

## 1. ภาพรวมสถาปัตยกรรม

```mermaid
flowchart TB
    user["ผู้ใช้: Data Engineer / BA / DA"]

    subgraph frontendLayer["Streamlit UI"]
        chatUi["Chat: Explore / Trusted"]
        insightUi["Insights feed"]
        digestUi["Board Digest"]
        knowledgeUi["Knowledge / Promotion"]
    end

    subgraph apiLayer["FastAPI Backend"]
        apiRoutes["API routes"]
        jobRunner["job_runner + job_store"]
        scheduler["APScheduler"]
    end

    subgraph agentLayer["LangGraph Orchestrator"]
        prepare["Prepare context"]
        de["DE: schema + data context"]
        ds["DS: hypotheses + checks"]
        da["DA: SQL + analysis"]
        ba["BA: business meaning"]
        quality["Quality assembly"]
        prepare --> de --> ds --> da --> ba --> quality
    end

    subgraph dataLayer["Read-only data access"]
        sqlGuard["SQL guard + row-count guard"]
        sourceChoice{"เลือก source"}
        fabric[("Fabric DW WH_Silver")]
        postgres[("Postgres WH_Silver mirror")]
        offline[("Offline discovery cache")]
        provenance["Provenance label: fabric / postgres / offline"]
        sqlGuard --> sourceChoice
        sourceChoice -->|"primary"| fabric
        sourceChoice -->|"fallback"| postgres
        sourceChoice -->|"ไม่มี live source"| offline
        fabric --> provenance
        postgres --> provenance
        offline --> provenance
    end

    subgraph localStores["Local stores: data/local"]
        appDb[("app.db: chat + ratings")]
        analyticsDb[("analytics.db: snapshots + insights + learning")]
        jsonStores[("JSON: knowledge + semantic + backlog + memory + eval + digests")]
    end

    subgraph engineLayer["Analytics / Insight / Learning / Digest"]
        metrics["Metric Registry"]
        analytics["Detectors + Forecasting + Contribution"]
        insightEngine["Insight pipeline"]
        learning["Embeddings + SQL patterns + lessons + ranker"]
        digestEngine["Digest + Study + Eval trend"]
    end

    user --> frontendLayer
    frontendLayer -->|"HTTP"| apiRoutes
    apiRoutes --> jobRunner
    scheduler --> jobRunner
    jobRunner --> prepare
    da --> sqlGuard
    provenance --> da
    quality --> apiRoutes

    apiRoutes --> appDb
    quality --> jsonStores
    metrics --> sqlGuard
    insightEngine --> analytics
    insightEngine --> analyticsDb
    learning --> analyticsDb
    learning --> jsonStores
    digestEngine --> analyticsDb
    digestEngine --> jsonStores
    apiRoutes --> engineLayer
```

**คำอธิบายแบบสั้น:** ผู้ใช้คุยผ่าน Streamlit แล้ว FastAPI ส่งงานยาวให้ `job_runner` ทีม AI ทำงานตามลำดับและอ่านข้อมูลแบบ read-only เท่านั้น ผลที่ได้ถูกติดป้ายแหล่งข้อมูลก่อนแสดงหรือเก็บลง local stores ส่วนงานวิเคราะห์อัตโนมัติใช้ engine ชุดเดียวกันผ่าน backend

## 2. ลำดับการร่วมงานของ Agent

```mermaid
flowchart LR
    question["คำถาม Explore"]
    context["เตรียม discovery, knowledge, memory, metrics"]
    de["DE: schema, joins, data gaps"]
    ds["DS: hypotheses, grain, filters, sanity checks"]
    da["DA: สร้าง SQL ตาม dialect"]
    guard{"SQL ผ่าน guard และรันสำเร็จ?"}
    retry{"ครบ 3 ครั้งหรือยัง?"}
    fix["DA: แก้ SQL ตาม error class"]
    ba["BA: KPI meaning, so-what, recommendation"]
    quality["Quality Bar D: summary, SQL, assumptions, confidence, BA/DA questions, provenance"]
    answer["คำตอบ Draft"]
    partial["คำตอบบางส่วนจาก agent ที่ทำเสร็จแล้ว"]

    question --> context --> de --> ds --> da --> guard
    guard -->|"สำเร็จ"| ba --> quality --> answer
    guard -->|"ไม่สำเร็จ"| retry
    retry -->|"ยังไม่ครบ"| fix --> da
    retry -->|"ครบแล้ว"| ba
    de -. "job timeout หลังมีผลงาน" .-> partial
    ds -. "job timeout หลังมีผลงาน" .-> partial
    da -. "job timeout หลังมีผลงาน" .-> partial
```

**คำอธิบายแบบสั้น:** DE ช่วยให้ทีมเข้าใจข้อมูล, DS วางวิธีตรวจ, DA เขียนและลองแก้ SQL ได้สูงสุด 3 รอบ, BA แปลผลเป็นภาษาธุรกิจ แล้วระบบประกอบคำตอบตาม Quality Bar D หากงานหมดเวลา ระบบคืนผลงานที่ทำเสร็จแล้วเป็น “คำตอบบางส่วน” แทนหน้าว่าง

## 3. Explore question แบบ end-to-end

```mermaid
sequenceDiagram
    participant user as ผู้ใช้
    participant ui as Streamlit
    participant api as FastAPI
    participant runner as job_runner
    participant graph as LangGraph
    participant agents as DE-DS-DA-BA
    participant guard as SQL guard
    participant source as Fabric-Postgres
    participant store as Local stores

    user->>ui: ส่งคำถาม Explore
    ui->>api: POST /api/v1/chat/
    api->>runner: สร้าง chat job
    api-->>ui: 202 + job_id
    runner->>runner: heartbeat ทุกประมาณ 10 วินาที
    runner->>graph: เริ่ม graph + prepare context

    loop UI poll ทุก 3 วินาที
        ui->>api: GET /api/v1/jobs/{job_id}
        api-->>ui: status + progress + heartbeat
    end

    graph->>agents: DE เตรียม data context
    agents->>agents: DS วาง hypotheses และ checks
    agents->>guard: DA ส่ง SELECT + source dialect
    guard->>guard: read-only validation + row-count preflight
    guard->>source: รันกับ Fabric หรือ Postgres mirror

    alt SQL สำเร็จ
        source-->>agents: aggregate rows + source
    else SQL ผิดและยังไม่ครบ 3 รอบ
        source-->>agents: sanitized error class
        agents->>guard: DA แก้ SQL แล้วลองใหม่
    else ไม่มี live source
        guard-->>agents: offline + Draft SQL
    end

    agents->>agents: BA สรุปผลเชิงธุรกิจ
    agents->>graph: Quality assembly + provenance
    graph-->>runner: final answer
    runner->>store: บันทึก messages + quality payload
    runner-->>api: job done
    api-->>ui: answer + provenance
    ui-->>user: คำตอบ Draft + ปุ่ม rating
```

**คำอธิบายแบบสั้น:** หน้าจอไม่ต้องรอ request เดียวยาว ๆ เพราะ backend คืน `job_id` ทันที จากนั้น UI ติดตามชีพจรและขั้นตอนของทีม ระหว่างทาง SQL ถูกจำกัดเป็น read-only และตรวจขนาดผลลัพธ์ ก่อนประกอบคำตอบพร้อมป้ายแหล่งข้อมูล

## 4. Deep onboarding: Homework + Starter Pack

```mermaid
sequenceDiagram
    participant user as ผู้ใช้
    participant ui as Streamlit
    participant api as FastAPI
    participant runner as job_runner
    participant homework as deep_profile
    participant starter as starter_pack
    participant source as Source resolver
    participant disk as Theme evidence files
    participant team as Onboarding DE-DS-DA-BA

    user->>ui: เริ่ม onboarding ของ theme
    ui->>api: POST /api/v1/onboarding/{theme}/run
    api->>runner: สร้าง onboarding job
    api-->>ui: 202 + job_id
    runner->>homework: สร้าง deterministic homework
    homework->>source: เลือก Fabric ก่อน แล้ว Postgres แล้ว offline

    alt Fabric หรือ Postgres พร้อม
        source-->>homework: bounded read-only aggregates + sample สูงสุด 200 แถว
        homework->>disk: evidence_level = fabric_live หรือ postgres_live
    else ไม่มี live source หรือ query ใช้ไม่ได้
        source-->>homework: ใช้ discovery cache
        homework->>disk: evidence_level = disk_cache
    end

    runner->>starter: สร้าง candidate insights จาก approved metrics
    starter->>source: รัน baseline ได้ไม่เกิน 1 query

    alt baseline สำเร็จ
        source-->>starter: aggregate rows เท่านั้น
        starter->>disk: evidence_status = validated
    else ยังไม่รันหรือรันไม่ผ่าน
        starter->>disk: evidence_status = not_run หรือ failed
    end

    runner->>team: DE -> DS -> DA -> BA
    team->>disk: Team Memory + role artifacts
    runner-->>api: onboarding done
    api-->>ui: progress + evidence summary
    ui-->>user: CEO Briefing และสิ่งที่ต้องยืนยัน
```

**คำอธิบายแบบสั้น:** ก่อนทีม AI สรุป onboarding ระบบทำ “การบ้านข้อมูล” แบบ deterministic ก่อน โดย query ถูกจำกัดขอบเขตและอ่านอย่างเดียว หลักฐานจะแยกชัดว่าเป็น live จาก Fabric/Postgres หรือเป็นเพียง disk cache และ starter insight ที่ยังไม่รันจะไม่ถูกเรียกว่าเป็นข้อค้นพบ

## 5. การเลือกแหล่งข้อมูล

```mermaid
flowchart TD
    request["ต้องอ่านข้อมูลหรือ schema"]
    fabricEnabled{"Fabric เปิดใช้ ตั้งค่าครบ และ reachable?"}
    useFabric["ใช้ Fabric DW"]
    postgresReady{"Postgres mirror ตั้งค่าครบและ reachable?"}
    usePostgres["ใช้ Postgres mirror"]
    useOffline["ใช้ discovery / theme cache บนดิสก์"]
    labelFabric["ติดป้าย provenance: fabric"]
    labelPostgres["ติดป้าย provenance: postgres พร้อมคำเตือน freshness"]
    labelOffline["ติดป้าย provenance: offline และไม่รัน SQL"]
    result["ส่งผลกลับผู้เรียก"]

    request --> fabricEnabled
    fabricEnabled -->|"ใช่"| useFabric --> labelFabric --> result
    fabricEnabled -->|"ไม่"| postgresReady
    postgresReady -->|"ใช่"| usePostgres --> labelPostgres --> result
    postgresReady -->|"ไม่"| useOffline --> labelOffline --> result
```

**คำอธิบายแบบสั้น:** ระบบเลือกแหล่งข้อมูลก่อนสร้าง SQL เพื่อให้ใช้ dialect ถูกต้อง โดยให้ Fabric มาก่อนเสมอ หาก fallback ไป Postgres หรือ offline ผู้ใช้ต้องเห็นป้ายชัดเจน ไม่มีการสลับแหล่งข้อมูลแบบเงียบ

## 6. วงจรเรียนรู้จากการใช้งาน

```mermaid
flowchart TB
    answers["คำตอบ Chat"]
    insights["Proactive insights"]
    ratings["Answer ratings: up / down"]
    insightFeedback["Insight feedback: useful / not useful / wrong"]
    sqlSuccess["SQL ที่รันสำเร็จ"]
    sqlFailure["SQL failures"]

    appDb[("app.db: answer_ratings")]
    analyticsDb[("analytics.db")]
    pdca[("PDCA failures JSONL")]
    patterns["SQL pattern store"]
    lessons["Lesson miner"]
    embeddings["Ollama embeddings + cosine top-k"]
    heuristic["Heuristic ranker"]
    labelGate{"มี feedback อย่างน้อย 100 labels?"}
    train["Logistic regression"]
    aucGate{"Holdout AUC อย่างน้อย 0.6?"}
    mlRanker["ML ranker active"]
    future["คำตอบและลำดับ insight รอบถัดไป"]

    answers --> ratings --> appDb
    insights --> insightFeedback --> analyticsDb
    answers --> sqlSuccess --> patterns --> analyticsDb
    answers --> sqlFailure --> pdca --> lessons
    appDb -->|"กรอง pattern ที่เคยถูก downvote"| patterns
    patterns --> embeddings
    analyticsDb --> heuristic
    heuristic --> future
    analyticsDb --> labelGate
    labelGate -->|"ยังไม่ถึง"| heuristic
    labelGate -->|"ถึงแล้ว"| train --> aucGate
    aucGate -->|"ผ่าน"| mlRanker --> future
    aucGate -->|"ไม่ผ่าน"| heuristic
    embeddings --> future
    lessons --> future
```

**คำอธิบายแบบสั้น:** ระบบจำทั้งสิ่งที่ทำสำเร็จและสิ่งที่ผิด SQL patterns กับ lessons ช่วย DA รอบถัดไป ส่วน insight ranker ใช้สูตร heuristic เป็นค่าเริ่มต้น และจะใช้โมเดลที่ฝึกจริงก็ต่อเมื่อมีอย่างน้อย 100 labels และผ่าน AUC gate เท่านั้น ปัจจุบัน live labels ยังเป็น cold start

## 7. Proactive insight pipeline

```mermaid
flowchart LR
    triggers["Scheduler catch-up / nightly / ปุ่มรันทันที"]
    runner["job_runner: insight_pipeline"]
    refresh["Refresh snapshots"]
    registry["Approved Metric Registry"]
    source["Fabric / Postgres ผ่าน guard"]
    snapshots[("analytics.db snapshots")]
    detectors["Anomaly + Changepoint + Trend"]
    forecast["Forecast residual"]
    contribution["Contribution module"]
    score["Score: significance x impact x novelty"]
    ranker["Ranker: heuristic หรือ gated ML"]
    narrative["Ollama narrative จาก evidence"]
    validator{"ตัวเลขอยู่ใน evidence ครบ?"}
    retry["Narrate ใหม่ 1 ครั้ง"]
    template["Deterministic fallback template"]
    publish["Publish insight + provenance"]
    feed["Streamlit Insights feed"]
    feedback["Useful / Not useful / Wrong"]

    triggers --> runner --> refresh
    registry --> refresh
    refresh --> source --> snapshots
    snapshots --> detectors --> score
    snapshots --> forecast --> score
    snapshots -. "มีโมดูลแล้ว แต่ current scheduled pipeline ยังไม่เรียก" .-> contribution
    score --> ranker --> narrative --> validator
    validator -->|"ผ่าน"| publish
    validator -->|"ไม่ผ่าน"| retry --> validator
    validator -->|"ยังไม่ผ่าน"| template --> publish
    publish --> feed --> feedback
```

**คำอธิบายแบบสั้น:** Scheduler ส่งงานผ่าน `job_runner` แล้ว refresh snapshot จากสูตร KPI ที่อนุมัติแบบ deterministic จากนั้น detector และ forecast หาเหตุการณ์, rank, เล่าเรื่อง และตรวจว่าตัวเลขทุกตัวมีใน evidence ก่อน publish ส่วน `contribution.py` มีใน analytics engine แล้ว แต่โค้ด scheduled pipeline ปัจจุบันยังไม่ได้เรียกโมดูลนี้โดยตรง

## 8. วงจร Knowledge, Metric และ Trusted

```mermaid
stateDiagram-v2
    [*] --> draftKnowledge
    state "Draft knowledge / metric" as draftKnowledge
    state "Approved knowledge / metric" as approvedKnowledge
    state "Explore insight candidate" as insightCandidate
    state "BA/DA validated" as validatedInsight
    state "Trusted semantic definition" as trustedDefinition
    state "Rejected / needs revision" as rejectedItem
    state "Deprecated metric" as deprecatedMetric

    draftKnowledge --> approvedKnowledge: Owner HITL approve
    draftKnowledge --> rejectedItem: Reject
    rejectedItem --> draftKnowledge: Revise
    approvedKnowledge --> insightCandidate: ใช้เป็น context ใน Explore
    insightCandidate --> validatedInsight: BA/DA feedback
    validatedInsight --> trustedDefinition: HITL promote
    trustedDefinition --> insightCandidate: ใช้ตอบรอบถัดไป
    approvedKnowledge --> deprecatedMetric: Deprecate metric version
```

**คำอธิบายแบบสั้น:** ข้อมูลที่เพิ่งเพิ่มยังเป็น Draft และยังไม่ควรถูกใช้เป็นความจริง จนกว่า owner จะ approve ส่วนคำตอบ Explore ต้องผ่าน BA/DA validation และ human promotion อีกชั้นก่อนเข้า Trusted semantic layer

## 9. เส้นทาง Phase D ถึง K

```mermaid
flowchart LR
    phaseD["D: Pipeline hardening; Code complete; Live Fabric checks pending"]
    phaseF["F: Postgres fallback; Code complete; DBA parity pending"]
    deep["Deep onboarding; Homework + partial answers; ไม่มี formal gate"]
    phaseG["G: Heartbeat + Registry + Eval; Code complete; Live eval pending"]
    phaseH["H: Analytics engine; Code complete; Live backfill pending"]
    phaseI["I: Proactive insights; Code complete; Unattended live run pending"]
    phaseJ["J: Learning loops; Code complete; Live labels and metrics pending"]
    phaseK["K: Digest + Study; Code complete; 4-week live evidence pending"]

    phaseD --> phaseF --> phaseG --> phaseH --> phaseI --> phaseJ --> phaseK
    phaseF -. "งานระหว่างทางก่อน G" .-> deep
    deep -.-> phaseG
```

**คำอธิบายแบบสั้น:** ทุก phase ในเส้นหลัก D, F, G, H, I, J, K มีโค้ดและ automated tests แล้ว แต่ยังไม่เท่ากับยืนยันบน production งาน live ที่ค้างต่างกัน เช่น parity, backfill, eval, scheduler, labels และการรัน digest ต่อเนื่อง

## 10. Readiness map: Code-complete เทียบกับ Production-verified

```mermaid
flowchart TB
    system["AI Fabric Insight Explorer"]

    subgraph codeReady["Code-complete"]
        chat["Chat jobs + heartbeat + partial answer"]
        agents["Explore agents + SQL retry + Quality Bar D"]
        fallback["Fabric to Postgres to offline provenance"]
        metric["Metric Registry + deterministic SQL"]
        engine["Analytics + Insights + Learning + Digest"]
        tests["Automated suite: 390 passed ตาม phase summary"]
    end

    subgraph livePending["Production verification ยังไม่ครบ"]
        gateMetric["BA สูตร Net Profit และ discount rate"]
        gateBackfill["Live snapshot backfill 36 เดือน"]
        gateEval["Golden eval v2 ผ่าน Ollama + SQL"]
        gateInsight["Insight pipeline อย่างน้อย 1 สัปดาห์"]
        gateEvents["Owner validate detector อย่างน้อย 3 เหตุการณ์"]
        gateLearning["Live labels, accuracy uplift, retry reduction, ranker AUC"]
        gateDigest["Digest + Study ต่อเนื่อง 4 สัปดาห์"]
        gateParity["Postgres parity + DBA checklist"]
    end

    system --> codeReady
    system --> livePending
    codeReady --> handover{"พร้อมเรียก production-verified หรือยัง?"}
    livePending --> handover
    handover -->|"ยัง"| collect["เก็บ live evidence + owner sign-off"]
    collect -->|"ผ่านทุก gate ที่เกี่ยวข้อง"| verified["Production-verified"]
```

**คำอธิบายแบบสั้น:** ระบบพร้อมในระดับโค้ด แต่หลักฐานจาก environment จริงยังไม่ครบ จุดที่สำคัญที่สุดคือยืนยันสูตร KPI, เติม snapshot จริง, รัน eval จริง และปล่อย pipeline ทำงานต่อเนื่องพร้อม owner sign-off

## 11. Loop Engineering QA (readiness before real testing)

```mermaid
flowchart TD
  userAsk["ผู้ใช้สั่ง: ทดสอบความพร้อม"]
  skill["Skill loop-engineering-qa"]
  runner["scripts/run-readiness-check.ps1"]
  l0["L0: env + Ollama smoke"]
  l1["L1: pytest + conformance"]
  l2["L2: live chat / golden optional"]
  triage["Triage: env llm sql code test human-gate"]
  fix["แก้ + regression สูงสุด 2-3 รอบ"]
  report["run-report + readiness sanitized"]
  stop["หยุดก่อน commit/push"]
  owner["Owner human gates"]

  userAsk --> skill --> runner
  runner --> l0 --> l1
  l1 --> l2
  l0 --> triage
  l1 --> triage
  l2 --> triage
  triage -->|"product/env/llm"| fix --> report
  triage -->|"human-gate"| owner
  triage -->|"coverage gap"| qaEng["qa-test-engineer"]
  qaEng --> fix
  report --> stop
  owner --> stop
```

**คำอธิบายแบบสั้น:** Loop Engineering เป็นศูนย์กลางทดสอบความพร้อมก่อนใช้งานจริง รันชั้น L0–L2 แล้ว triage และแนะนำ readiness — **ไม่แทน** Trusted/KPI/production sign-off และไม่ commit/push เองจนกว่าเจ้าของระบบจะสั่ง ดู catalog ที่ `knowledge/07-testing/loop-engineering/scenario-catalog.md`

## ตัวเลือกภาพแบบ Interactive

Canvas ภาพรวมเดิมยังมีอยู่และใช้เป็นตัวเลือกสำหรับเปิดดูแบบ interactive ใน Cursor:

`C:\Users\weerawat.m\.cursor\projects\c-Projects-ai-analytic-multiagent\canvases\project-overview.canvas.tsx`

ไฟล์ Canvas อยู่นอก repository และไม่ได้ถูกแก้ในงานเอกสารชุดนี้

## Maintenance

ไฟล์นี้เป็น **mandatory handover artifact** ตาม `AGENTS.md` → **Documentation & Handover Contract** — อัปเดตใน change set เดียวกับโค้ด/เอกสารที่เกี่ยวข้อง ไม่ใช่ภาพประกอบเสริม

### เมื่อไหร่ต้องอัปเดต

| การเปลี่ยนในระบบ | Section ที่แก้ |
|---|---|
| สถาปัตยกรรมชั้นบริการ, local stores, engine modules | §1 |
| ลำดับ agent, SQL retry, partial answer, Quality Bar | §2 |
| Explore chat flow, job polling, API sequence | §3 |
| Deep onboarding, homework, starter pack | §4 |
| Fabric → Postgres → offline fallback, provenance | §5 |
| Learning loops, ratings, ranker gates | §6 |
| Proactive insight pipeline, detectors, narrative | §7 |
| Knowledge / metric / Trusted lifecycle | §8 |
| Phase timeline D→K, code-complete labels | §9 |
| Readiness map, live gates, verification status | §10 |
| Loop Engineering QA flow / readiness runner | §11 |

### กฎการดูแล

- ใช้ชื่อ service และสถานะจากโค้ด/phase summaries — ไม่ใช้ชื่อเชิงการตลาดแทน behavior จริง
- แยก **Code-complete** กับ **Production-verified** เสมอ (ห้ามสื่อว่า live verified จาก tests อย่างเดียว)
- Mermaid ใช้เฉพาะ `flowchart`, `sequenceDiagram`, `stateDiagram-v2` เพื่อ render ได้ทั้ง Cursor และ GitHub
- ถ้าอัปเดต diagram ไม่ทัน — บันทึก **diagram debt** ใน phase summary และ `PROJECT_OVERVIEW.md` §11
