# Weekly report

<!-- İSKELET (21:10, Pzt 23 Kasım). Tag'den ÖNCE bu dosyadaki BÜTÜN HTML yorumları silinecek (week-2'de iç not
kalmıştı). Yorumlardaki olgular repodaki dosyalardan; metni yazan kişi kendi cümleleriyle yazar.
Sınır: ≤ 1.500 kelime (tablolar, scoreboard bloğu ve yorumlar hariç), Summary ≤ 100 kelime. -->

| Field | Value |
|---|---|
| Team | Deadline Radar |
| Use case | Own idea, accepted by the instructor on 2026-11-11 (D-003) |
| Week | 3 |
| Repository | https://github.com/gokce-yildiz-ozu/AIC390-PROJECT |
| Commit tag | week-3 |
| Presenter | Mert Bozma (rotation in `docs/team_agreement.md` §2) |
| Members and roles | Mert Bozma (data and retrieval lead); Enes Kemal Köylü (agent and tools lead); Serap Gökçe Yıldız (evaluation and safety lead) |

## 1. Summary

<!-- YAZAN: Gökçe (en son, her şey bitince). ≤ 100 kelime.
Olgular: stub → gerçek hibrit arama + reranker; corpus 3.889 belge (10 çekirdek + 3.879 üretilmiş), 11.388 chunk.
Retrieval hit@5 29/30 = 0.967 [0.833, 0.994]. Uçtan uca gerçek aramayla 38/42 = 0.905 [0.779, 0.962] (Run B).
Run B kuralı answer_v1'i varsayılan bıraktı (abstention 5/6 vs 6/6). İki retrieval hatası da Türkçe soru.
En önemli tek sayı için aday: hit@5 ya da stub→gerçek arama farkı (aynı 19 vakada 16/19 → 17/19, fark yok). -->

## 2. Deliverables

| ID | Status | Evidence | Note |
|---|---|---|---|
| W3.1 | done | [`data/corpus/`](../data/corpus/), [`scripts/generate_bulk_corpus.py`](../scripts/generate_bulk_corpus.py), [`results/2026-11-23_bulk-corpus/`](../results/2026-11-23_bulk-corpus/), [`docs/decisions.md`](../docs/decisions.md) D-008 | <!-- Olgular: 10 çekirdek belge reviewed (43e105b); üretici seed 20261122: 900 ders, 3.879 belge (1.158 syllabus, 2.721 duyuru), 258 revize syllabus; chunk dili en 9.130 / tr 2.231 (bulk). Metadata: source, version/valid_from, audience. audience filtreleniyor mu? HAYIR (architecture'da "not enforced yet" satırı var mı kontrol) --> |
| W3.2 | partial | [`src/aic390/rag/chunking.py`](../src/aic390/rag/chunking.py), [`data/chunks.jsonl`](../data/chunks.jsonl) | <!-- Olgular: section (##) başına bir chunk, citation birimi = section, max_words 200, overlap yok; 11.388 chunk. EKSİK: kelime dağılımı (medyan, p90, max) bir script'ten gelmeli (Mert). Gelince status → done --> |
| W3.3 | done | [`src/aic390/rag/search.py`](../src/aic390/rag/search.py), [`docs/decisions.md`](../docs/decisions.md) D-007 | <!-- BM25 (bm25s) + bge-m3, RRF k=60, top 20 each, bge-reranker-v2-m3 --> |
| W3.4 | done | [`prompts/answer_v2.md`](../prompts/answer_v2.md), [`src/aic390/agent/answer.py`](../src/aic390/agent/answer.py), [Run B](../results/2026-11-23_e2e_w3-real-ansv2_openai-gpt-oss-120b/), [Run A vs B](../results/2026-11-23_compare_w3-real-ansv1_vs_w3-real-ansv2_common-ids/) | <!-- answer_v2: [n] her bilgiden sonra, kodda yeniden numaralanıyor, 3 sabit abstention cevabı. Ölçüldü ama önceden yazılmış kural varsayılan yapmadı (abstention 5/6 < 6/6). Varsayılan ve demo: answer_v1 --> |
| W3.5 | done | [`eval/retrieval.py`](../eval/retrieval.py), [`eval/testsets/retrieval_questions.jsonl`](../eval/testsets/retrieval_questions.jsonl), [`results/2026-11-23_retrieval_hybrid-rerank/`](../results/2026-11-23_retrieval_hybrid-rerank/) | <!-- 30 soru, corpus yazarı dışında biri yazdı, dondurulmuş; hit@1/3/5/10 ve MRR CI ile --> |
| W3.6 | done | [`eval/faithfulness.py`](../eval/faithfulness.py), [`prompts/faithfulness_v1.md`](../prompts/faithfulness_v1.md), [`results/2026-11-23_faithfulness-v1/`](../results/2026-11-23_faithfulness-v1/) | 13 claims from 7 Run B answers: fewer than 20, so all were labelled and the intervals are wide. Judge kappa 0.629 against each rater, bootstrap 95% [0.000, 1.000] (threshold 0.6 met on the point estimate); the raters agree 13/13. Rater 1 read the Run B note on w1-21 before labelling. <!-- 13 iddia / 7 vaka (< 20: plan kuralı); iki kör insan etiketçi; rater 1 w1-21'in Run B yorumunu etiketlemeden önce okudu (söyle) --> |
| W3.7 | done | [dense](../results/2026-11-23_retrieval_dense-rerank/), [BM25](../results/2026-11-23_retrieval_bm25-rerank/), [no reranker](../results/2026-11-23_retrieval_hybrid-norerank/), [hybrid vs dense](../results/2026-11-23_retrieval-compare_hybrid-rerank_vs_dense-rerank_hit_at_5/), [rerank on vs off](../results/2026-11-23_retrieval-compare_hybrid-rerank_vs_hybrid-norerank_hit_at_1/) | <!-- iki ablation, her biri tek değişiklik; BM25-only ek satır --> |
| W3.8 | done | §5 below, [Run A](../results/2026-11-23_e2e_w3-real-ansv1_openai-gpt-oss-120b/), [stub vs real](../results/2026-11-23_compare_w25-v1-a_vs_w3-real-ansv1_common-ids/) | <!-- her hata retrieval / generation / routing; kanıt trace'teki top-5 --> |
| Product track | done | §7, [first interview](../docs/interviews/2026-11-23_student_e.md), [second interview](../docs/interviews/2026-11-24_student_g.md) | Two interviews with students |

## 3. Scoreboard

<!-- `python scripts/write_week3_scoreboard.py` çıktısını (eval/scoreboard.json) buraya aynen yapıştır; elle sayı yazma.
Kaynak klasörler (board sadece script adı veriyor): e2e ve maliyet = Run B; hit_at_5/mrr = retrieval_hybrid-rerank;
unsupported_claims = faithfulness-v1; injection_success = week 2'den taşındı (notu board'da). -->

```json
{
  "week": 3,
  "test_set_size": 42,
  "e2e_accuracy": {
    "value": 0.905,
    "ci95": [
      0.779,
      0.962
    ],
    "n": 42,
    "script": "eval/run_e2e.py"
  },
  "abstention_correct": {
    "value": 0.833,
    "ci95": [
      0.436,
      0.97
    ],
    "n": 6,
    "script": "eval/run_e2e.py"
  },
  "unsupported_claims": {
    "value": 0.077,
    "ci95": [
      0.014,
      0.333
    ],
    "n": 13,
    "script": "eval/faithfulness.py",
    "source": "judge"
  },
  "hit_at_5": {
    "value": 0.967,
    "ci95": [
      0.833,
      0.994
    ],
    "n": 30,
    "script": "eval/retrieval.py"
  },
  "mrr": {
    "value": 0.933,
    "ci95": [
      0.85,
      1.0
    ],
    "n": 30,
    "script": "eval/retrieval.py"
  },
  "task_success": null,
  "pass_k": null,
  "injection_success": {
    "value": 0.0,
    "ci95": [
      0.0,
      0.562
    ],
    "n": 3,
    "script": "scripts/run_injection_tests.py",
    "note": "carried from week 2 (W2.8, stub search); not re-measured with real search",
    "measured_in_week": 2
  },
  "cost_per_task_usd": 0.000413,
  "latency_p50_s": 1.942,
  "spend_week_usd": 0.0,
  "spend_total_usd": 0.0
}
```

<!-- Altına kısa notlar: cost liste fiyatıyla, gerçek harcama 0 (free plan); injection_success bu hafta ölçülmedi;
e2e koşulu: real hybrid search, seed table, answer_v2 (varsayılan v1 olsa da scoreboard Run B'den, planlandığı gibi). -->

Notes: `e2e_accuracy`, `abstention_correct`, cost and latency come from Run B (real hybrid search, seed table, `answer_v2`); the default prompt stays `answer_v1` (Experiment 5). `unsupported_claims` is the judge's rate (kappa at least 0.6 against both raters, Experiment 6); both human raters marked 2/13 unsupported. `injection_success` is carried from week 2 (W2.8, stub search) and was measured on the attempts the fix was designed for, so it is in-sample. Cost uses list prices; actual spend was 0 on the free plan.

Changes to any test set this week: none <!-- doğru: week2_cases ve retrieval_questions değişmedi; corpus değişti, gold section'lar aynı -->

## 4. Experiments

<!-- Hipotezler ve karar kuralları koşulardan önce docs/STATUS.md Experiments'a yazıldı: bunu bir kez söyle ve link ver.
Her deneyde Decision cümlesini deneyin sahibi yazar. -->

### Experiment 1: retrieval baseline, main configuration (W3.5)

<!-- YAZAN: Mert -->
- **Hypothesis:** <!-- STATUS: hit_at_5 ≥ 0.80 (week-2 raporundaki hedef) -->
- **Change:** <!-- ölçüm, karşılaştırma yok: hibrit + reranker, course filtresi yok, 11.388 chunk -->
- **Result:** <!-- hit@1 27/30 = 0.900 [0.744, 0.965]; hit@5 29/30 = 0.967 [0.833, 0.994]; MRR 0.933 [0.850, 1.000] bootstrap; multi all@5 2/4; TR hit@5 11/12, EN 18/18; kaçan: r02; medyan arama 0.256 s (RTX 5060) -->
- **Decision:** <!-- hedef tuttu, alt sınır bile 0.80 üstünde; sınırlama: bulk belgeler şablon, gerçek okulun belgelerinden kolay dikkat dağıtıcı -->

### Experiment 2: hybrid vs dense only (W3.7, ablation 1)

<!-- YAZAN: Mert -->
- **Hypothesis:** <!-- hibrit 7 confusable soruda daha iyi; dense TR'de BM25'ten iyi -->
- **Change:** <!-- mode = dense (reranker her ikisinde açık) -->
- **Result:** <!-- dense hit@5 28/30 = 0.933 [0.787, 0.982]; McNemar b = 1 (r09), c = 0, p = 1.0; confusable 7/7 vs 7/7; TR hit@5 dense 10/12, BM25 8/12; BM25-only hit@5 25/30 = 0.833 [0.664, 0.927] -->
- **Decision:** <!-- eşit → hibrit kalır (D-007); hipotezin ilk yarısı desteklenmedi -->

### Experiment 3: reranker on vs off (W3.7, ablation 2)

<!-- YAZAN: Mert -->
- **Hypothesis:** <!-- reranker hit@1 ve MRR'yi hit@5'ten çok artırır -->
- **Change:** <!-- rerank = False -->
- **Result:** <!-- reranker'sız hit@1 25/30 = 0.833 [0.664, 0.927], MRR 0.879 [0.774, 0.973], hit@5 aynı; McNemar hit@1 b = 3 (r15, r17, r29), c = 1 (r24), p = 0.625; gecikme +0.249 s (0.256 vs 0.007) -->
- **Decision:** <!-- eşit ve +0.249 s ≤ 1.0 s kuralı → reranker kalır; r24 near-duplicate (§5) -->

### Experiment 4: stub search vs real search on the 19 search cases (Run A, W3.8)

<!-- YAZAN: Gökçe ya da Mert (koşuyu Mert yaptı) -->
- **Hypothesis:** <!-- gerçek aramayla doğruluk en fazla stub kadar -->
- **Change:** <!-- --search real; her şey v1, seed table -->
- **Result:** <!-- 17/19 = 0.895 [0.686, 0.971] vs stub 16/19 = 0.842 [0.624, 0.945]; McNemar b = 1 (w1-11), c = 2 (w1-08, w1-21), p = 1.0 -->
- **Decision:** <!-- fark yok; w1-11 retrieval hatası (trace); w1-08 ve w1-21 tek koşuda gürültüden ayrılamaz (w1-08 week-2'de de koşudan koşuya değişti) -->

### Experiment 5: answer_v1 vs answer_v2 with real search (Run B, W3.4)

- **Hypothesis:** `answer_v2` is not worse on accuracy, abstains at least as often as `answer_v1` on the 6 unanswerable cases (w1-21 in particular), and every answered case carries valid `[n]` markers.
- **Change:** One change against Run A: `--prompts answer=answer_v2`. All 42 frozen cases, real search, seed table.
- **Result:** 38/42 = 0.905, Wilson 95% [0.779, 0.962]. On the 19 cases common with Run A: 15/19 against 17/19, exact McNemar b = 2 (w1-19, w1-21), c = 0, p = 0.5. `abstention_correct` 5/6 = 0.833 [0.436, 0.970], Run A 6/6 = 1.000 [0.610, 1.000]; `false_abstentions` 1/34 = 0.029 [0.005, 0.149]. All 7 answered rule questions carry valid markers.
- **Decision:** `answer_v1` stays the default, also in the demo. Our rule, written before the run, needed p ≥ 0.05 and no loss in abstention; the second condition failed. The lost abstention is one case, w1-21, the case `answer_v2` was written for (hallucination log #14). w1-19 is not caused by the prompt: the classifier runs before it and changed its answer between the runs. With 6 cases and one run per prompt this does not show that `answer_v1` is better (it answered w1-21 in 3 of 4 week-2 runs), so new cases come in week 4.

### Experiment 6: faithfulness judge vs two blind raters (W3.6)

<!-- YAZAN: Gökçe — kappa'dan sonra. n = 13 iddia (< 20), aralıklar geniş; rater 1 w1-21 notu -->
- **Hypothesis:**
- **Change:**
- **Result:**
- **Decision:**

## 5. Failure analysis

<!-- YAZAN: Gökçe. Template "top 3" istiyor: en güçlü üç = w1-11 (retrieval), w1-21 (generation), w1-20 (routing).
Diğerleri (r02, w1-19, r24) altında W3.8 tablosunda. Kök neden kelimeleri template'ten: retrieval, generation, prompt, data...
Olgular planlama sohbetinde (W3.8 tablosu). Faithfulness'ta desteksiz iddia çıkarsa generation satırı olarak eklenir.
"Çeviri ekleyince düzelir" gibi ölçülmemiş iddia yok: "week 4'te denenecek". -->

| # | Input (short) | What happened | Root cause | Fix (done or planned) |
|---|---|---|---|---|
| 1 | w1-11 (TR, make-up exam rule); same pattern in r02 (TR, make-up week, W3.5) | Gold `regulation-article-12` not in the top 5; all five are bulk `Attendance` sections. The model abstained: Run B's only false abstention (1/34). With stub search the case passes. r02: gold section not in the top 10. Both are Turkish questions on English regulations | retrieval | Planned, week 4: translate the query before search; measured on hit@5 for the Turkish questions (now 11/12) and on w1-11. Not measured yet |
| 2 | w1-21 (EN, "Can the instructor move the HW2 deadline? Can I object?"); expected: abstain | Run B (`answer_v2`) answered: it stretched Article 14's late-work rule to deadline changes and cited it as [1]. The refusal rule for this kind of question is in the prompt, but the model did not follow it; the code check only asks for a valid source number, not that the source supports the sentence ([hallucination log #14](../docs/hallucination_log.md)) | generation | Planned, week 6 (hardening): a code check that the cited source supports the sentence, not only that the number is valid; measured on `unsupported_claims` and abstention. `answer_v1` stays the default (Run B rule), but it is not shown to be safer here: it answered this case in 3 of 4 W2.5 runs (log #13); in Run A (real search) it abstained correctly |
| 3 | w1-20 (TR, dorm application deadline); w1-19 (EN, "45 on the midterm, will I pass?") | The classifier says `other`, so the student gets the fixed out-of-scope reply with no pointer to where to ask (no invented date). w1-20: 6 of 6 runs (4 W2.5 runs, Run A, Run B). w1-19: `rule_question` in Run A, `other` in Run B, same `classifier_v1`, T = 0. Recurring: [week-2 failure 1](week-2.md) | prompt | Planned, week 4 (unchanged from week 2): `classifier_v2`, one change to the `rule_question` definition, measured on the 42 cases and on `heldout_v2` |

**W3.8: every failure this week, labelled.**
We compared each end-to-end failure with stub search, which searches only the gold sections: close to an ideal retriever, but not a full oracle, since it still matches by keywords. If the gold section was missing from the top k, we labelled the failure retrieval; if it was there but the answer was wrong, generation. `w1-21` has no gold section: the right topic was retrieved, the documents contain no answer, and the model answered instead of abstaining, so it is also generation. Intent errors (`w1-19`, `w1-20`) happen before search and never reach retrieval or generation, so we label them prompt. <!-- etiket kuralı bir cümle: gold top-5'te yoksa retrieval, varsa ve cevap yanlışsa generation; stub sadece gold section'ları tuttuğu için oracle, ama kelime örtüşmeli bir arama, tam oracle değil -->

| Case | Run | Label | Evidence |
|---|---|---|---|
| w1-11 | Run A, Run B | retrieval | Trace: gold not in top 5; [Run A](../results/2026-11-23_e2e_w3-real-ansv1_openai-gpt-oss-120b/), [Run B](../results/2026-11-23_e2e_w3-real-ansv2_openai-gpt-oss-120b/) |
| r02 | W3.5 | retrieval | Gold not in top 10; [W3.5](../results/2026-11-23_retrieval_hybrid-rerank/) |
| w1-21 | Run B | generation | [Hallucination log #14](../docs/hallucination_log.md), [Run B](../results/2026-11-23_e2e_w3-real-ansv2_openai-gpt-oss-120b/) |
| w1-12 | Run B (W3.6) | generation | Claim 2 cites [2] (Article 14), which does not state it; the content is in [1], so the citation points to the wrong source. Both raters: unsupported; judge: supported; [W3.6](../results/2026-11-23_faithfulness-v1/) |
| w1-20 | stub, Run A, Run B | prompt | Intent `other` in all runs; [week-2 §5](week-2.md) |
| w1-19 | Run B | prompt (run-to-run noise) | Run A `rule_question`, Run B `other`; [STATUS](../docs/STATUS.md) |
| r24 | W3.7 | retrieval (rank, not recall) | Top 1 with the reranker is `econ101-late-policy`, a copy of Article 14 in the corpus; [rerank on vs off](../results/2026-11-23_retrieval-compare_hybrid-rerank_vs_hybrid-norerank_hit_at_1/) |

Even at T = 0, the same configuration gave different outcomes across runs: `w1-19` flipped between `rule_question` and `other` under the same classifier, while `w1-21` abstained in only one of four W2.5 runs with the same answer prompt. So a single run per configuration cannot separate prompt effects from run-to-run noise; from week 4 we will evaluate each configuration across multiple runs.

## 6. Response to last week's feedback

<!-- Week-2 ve week-3 aynı derste sunuluyor: week-2'den sonra yeni geri bildirim yok. Bunu bir satırla söyle, sonra
week-1 geri bildiriminde bu hafta kapanan maddeler (docs/feedback/2026-11-18-week1.md #3, #3b, #3c). -->

| Feedback point | What we changed | Evidence |
|---|---|---|
| The corpus should be at least 10,000 chunks (3c) | <!-- 11.388 chunk; sayı belge ekleyerek, chunk küçültmeden (D-008) --> | [`results/2026-11-23_bulk-corpus/`](../results/2026-11-23_bulk-corpus/), D-008 |
| The live demo must show the classifier and RAG (3) | <!-- demo tam corpus üstünde hibrit arama; BM25/dense/fused/rerank sıraları ekranda; index yükleme ve arama süresi ekranda --> | [`app/demo.py`](../app/demo.py), [`results/2026-11-23_demo-search-timing_cpu/`](../results/2026-11-23_demo-search-timing_cpu/) |
| Show the architecture in detail, and our data (3b) | <!-- retrieval satırları (0b7df66), 11.388 chunk'lık arama kutusu (8fe2a9d), ölçülen gecikme --> | [`docs/architecture.md`](../docs/architecture.md) |

## 7. Product track

<!-- Herkes kendi görüşmesini yazar. İsim, numara, iletişim YOK (R10): rol + tarih. Her görüşme: bugün nasıl takip
ediyor, ne öderdi / kim öderdi, AI'dan ne korkutuyor; en şaşırtıcı bulgu; ürüne etkisi ("şunu değiştiriyoruz / değiştirmiyoruz"). -->

**Interview (Enes), 2026-11-23: first-year business student, 6 courses.** Friends remind them of deadlines on WhatsApp; dates also come from the LMS and email. The last homework they missed was left to the last moment and cost about 3% of the grade ("not sure"). They might pay 100–200 TL a month, but would rather have the school pay and the tool read the LMS. Fears: private information leaking, and emails sent to instructors in their name. Most surprising: the date was known; the problem was putting it off, and they want several reminders that stop once they say the work is done. Our design has one reminder, 24 hours before. We keep sources and confirmation before any action; a "done" mark and more than one reminder are proposed for the reminder action; the team has not decided yet. Limits: one person, a friend of the interviewer, and our last question suggested showing the source. Notes: [`docs/interviews/2026-11-23_student_e.md`](../docs/interviews/2026-11-23_student_e.md).

**Interview (Gökçe), 2026-11-24: second-year industrial engineering student, by WhatsApp.** Their last homework was posted only on the last page of a slide deck; they learned of it on the due date. The first interviewee knew the date and put the work off; this one never saw it. Both rely on WhatsApp for updates, want the school to pay, and would probably stop using it after one wrong date. Our corpus has no slides: an open gap the team has not decided on yet. Notes: [`docs/interviews/2026-11-24_student_g.md`](../docs/interviews/2026-11-24_student_g.md).

## 8. Contributions

<!-- Week-2 tag'inden beri commit: Mert 13, Enes 8, Gökçe 8 (git shortlog -sn week-2..HEAD; tag'den önce yeniden say).
Saat hücresi BOŞ KALMAYACAK. -->

| Member | Role | What they did this week | Commits or files | Hours |
|---|---|---|---|---|
| Serap Gökçe Yıldız | Evaluation and safety lead | <!-- STATUS plan satırları; faithfulness aracı ve etiket sayfası; Run A/B karşılaştırmaları; week-3 scoreboard script'i; W3.8; rapor --> | `eval/faithfulness.py`, `prompts/faithfulness_v1.md`, `scripts/write_week3_scoreboard.py`, `results/2026-11-23_faithfulness-v1/`, `results/2026-11-23_compare_*`, `reports/week-3.md` | |
| Enes Kemal Köylü | Agent and tools lead | `answer_v2` (W3.4); search calls logged in the trace for W3.8; `compare.py --common-ids`; demo on the full corpus with hybrid search, replays and search timing; failed model replies no longer shown as "no deadline"; hallucination log #14; one customer interview | `prompts/answer_v2.md`, `src/aic390/agent/`, `eval/compare.py`, `app/demo.py`, `scripts/time_demo_search.py`, `results/2026-11-23_demo-search-timing_cpu/`, `docs/hallucination_log.md`, `docs/interviews/` | 7 |
| Mert Bozma | Data and retrieval lead | <!-- bulk üretici + testler; 11.388 chunk; course filtresi; eval/retrieval.py; baseline + 2 ablation; Run A ve Run B koşuları (GPU makinesi); architecture retrieval satırları; D-007/D-008 accepted --> | `scripts/generate_bulk_corpus.py`, `data/corpus_bulk/`, `src/aic390/rag/`, `eval/retrieval.py`, `results/2026-11-23_retrieval_*`, `results/2026-11-23_e2e_w3-*` | |

## 9. AI tools used

| Tool | Used for |
|---|---|
| Claude (claude.ai, planning chat) | Planning the week and the experiments, reviewing our results and this report against the handbook, the report skeleton with the facts each section needs, a helper script for the W3.6 labelling sheet (not in the repository), the English summary and format of the second interview's notes from the interviewee's Turkish answers, and editing our drafts of parts of this report |
| Claude Code (VS Code and desktop app) | Writing and testing code (faithfulness tool, week-3 scoreboard script, search calls in the trace, demo) and preparing commits that each of us reviewed and made |

All W3.6 labels came from the two human raters; no label came from a model. The faithfulness judge is part of the measured system, not a writing aid.

## 10. Next week

**Week-2 targets and what happened** ([week-2 §10](week-2.md))

| Week-2 target | Week-3 result | Status |
|---|---|---|
| `hit_at_5` ≥ 0.80 with hybrid + reranker | 29/30 = 0.967 [0.833, 0.994]; [W3.5](../results/2026-11-23_retrieval_hybrid-rerank/) | Met |
| Hybrid beats BM25 on Turkish questions | TR hit@5: hybrid 11/12, dense 10/12, BM25 8/12 (descriptive, no test) | Met |
| Accuracy with real search no worse than stub | 17/19 vs 16/19, McNemar b = 1, c = 2, p = 1.0; [Run A](../results/2026-11-23_e2e_w3-real-ansv1_openai-gpt-oss-120b/) | Not supported, no difference |
| `unsupported_claims` ≤ 0.10 | 1/13 = 0.077 [0.014, 0.333] (judge), n = 13; both raters 2/13; [W3.6](../results/2026-11-23_faithfulness-v1/) | Met on the point estimate; upper bound above 0.10 |
| Intent errors ≤ 1 (`classifier_v2`, `item_key`, `heldout_v2`) | Not run this week; 2 errors in Run B (w1-19, w1-20) | Week 4 |

| Priority | Metric it should move | Expected change |
|---|---|---|
| 1. W4.1–W4.4: three tools, a loop with step, token and time limits, 10 multi-step tasks with traces | Task success, steps, cost per task (new keys) | First measurement: traces for all 10 tasks; the loop stops within its limits on every task |
| 2. `classifier_v2`: one change to the `rule_question` definition | Intent errors on the 42 cases and `heldout_v2` | 2 (Run B) → ≤ 1 |
| 3. Translate Turkish queries before search | TR hit@5; w1-11; false abstentions | 11/12 → ≥ 11/12 with w1-11 passing; 1/34 → 0/34 |
