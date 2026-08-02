# Sanuvia — Persistent Reasoning Core: Reasoning Lineage Graph

The visual companion to `reasoning_trace.md`. Generated automatically from the RevisionLedger and the immutable reasoning objects — not hand-drawn. Re-running produces an identical diagram.

**Legend** — `[[version]]` WorldModel version · `([evidence])` · `[hypothesis]` · `[/prediction/]` · `((inquiry))` · `{anomaly}`. Solid evidence→hypothesis edges strengthen/hypothesise; dashed edges contradict.

```mermaid
flowchart LR
    START(("start"))
    V_wm_1[["wm-1<br/>u=0.500"]]
    V_wm_2[["wm-2<br/>u=0.380"]]
    V_wm_3[["wm-3<br/>u=0.308"]]
    V_wm_4[["wm-4<br/>u=0.415"]]
    V_wm_5[["wm-5<br/>u=0.415"]]
    E_evidence_1(["evidence-1<br/>behavioural · r=0.700"])
    E_evidence_2(["evidence-2<br/>behavioural · r=0.800"])
    E_evidence_3(["evidence-3<br/>behavioural · r=0.800"])
    E_evidence_4(["evidence-4<br/>contradictory · r=0.800"])
    E_evidence_5(["evidence-5<br/>failed_acquisition · r=0.300"])
    E_evidence_6(["evidence-6<br/>contradictory · r=0.300"])
    H_H_external_routine["H_external_routine<br/>support 0.640<br/>0.40→0.64"]
    H_H_emotional_distance["H_emotional_distance<br/>support 0.470<br/>0.40→0.64→0.78→0.47"]
    H_H_avoiding_topic["H_avoiding_topic<br/>support 0.300<br/>0.30"]
    H_H_external_stressor["H_external_stressor<br/>support 0.300<br/>0.30"]
    P_pred_1[/"pred-1<br/>L=0.640<br/>@wm-2"/]
    P_pred_2[/"pred-2<br/>L=0.784<br/>@wm-3"/]
    P_pred_3[/"pred-3<br/>L=0.640<br/>@wm-4"/]
    P_pred_4[/"pred-4<br/>L=0.640<br/>@wm-5"/]
    Q_inq_1(("inq-1<br/>u=0.500"))
    Q_inq_2(("inq-2<br/>u=0.415"))
    Q_inq_3(("inq-3<br/>u=0.415"))
    A_anom_1{"anom-1<br/>revise"}
    A_anom_2{"anom-2<br/>escalate"}

    START -->|hypothesize| V_wm_1
    V_wm_1 -->|strengthen| V_wm_2
    V_wm_2 -->|strengthen| V_wm_3
    V_wm_3 -->|strengthen, contradict| V_wm_4
    V_wm_4 -->|hypothesize| V_wm_5
    E_evidence_1 -->|hypothesize| H_H_external_routine
    E_evidence_1 -->|hypothesize| H_H_emotional_distance
    E_evidence_2 -->|strengthen| H_H_emotional_distance
    E_evidence_3 -->|strengthen| H_H_emotional_distance
    E_evidence_4 -->|strengthen| H_H_external_routine
    E_evidence_4 -.->|contradict| H_H_emotional_distance
    E_evidence_5 -->|hypothesize| H_H_avoiding_topic
    E_evidence_5 -->|hypothesize| H_H_external_stressor
    H_H_emotional_distance -->|yields| P_pred_1
    H_H_emotional_distance -->|yields| P_pred_2
    H_H_external_routine -->|yields| P_pred_3
    H_H_external_routine -->|yields| P_pred_4
    V_wm_1 -->|raises| Q_inq_1
    V_wm_4 -->|raises| Q_inq_2
    V_wm_5 -->|raises| Q_inq_3
    A_anom_1 -.->|on| E_evidence_4
    A_anom_1 -->|→revise| V_wm_4
    A_anom_2 -.->|on| E_evidence_6

    classDef start fill:#6b7280,color:#ffffff,stroke:#111827;
    classDef version fill:#0f766e,color:#ffffff,stroke:#111827;
    classDef evidence fill:#64748b,color:#ffffff,stroke:#111827;
    classDef hypothesis fill:#1d4ed8,color:#ffffff,stroke:#111827;
    classDef prediction fill:#15803d,color:#ffffff,stroke:#111827;
    classDef inquiry fill:#7c3aed,color:#ffffff,stroke:#111827;
    classDef anomaly fill:#b91c1c,color:#ffffff,stroke:#111827;
    class START start;
    class V_wm_1,V_wm_2,V_wm_3,V_wm_4,V_wm_5 version;
    class E_evidence_1,E_evidence_2,E_evidence_3,E_evidence_4,E_evidence_5,E_evidence_6 evidence;
    class H_H_external_routine,H_H_emotional_distance,H_H_avoiding_topic,H_H_external_stressor hypothesis;
    class P_pred_1,P_pred_2,P_pred_3,P_pred_4 prediction;
    class Q_inq_1,Q_inq_2,Q_inq_3 inquiry;
    class A_anom_1,A_anom_2 anomaly;
```

