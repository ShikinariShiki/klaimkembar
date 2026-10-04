# Assumptions
Angka operasional di bawah belum menjadi aturan klinis. Pemilik keputusan: pengguna dan verifikator pada pilot.

| AS | Area | Reading | Source/owner |
| --- | --- | --- | --- |
| AS-1 | API | [ASSUMPTION] /api/v1 JSON; error code/message/details/request_id; UUID IDs; UTC dates | file5 defaults; pengguna |
| AS-2 | Pagination | [ASSUMPTION] default20 max100 for queue; dataset_id explicit | file5 defaults; F2 filters; pengguna |
| AS-3 | Stack | [ASSUMPTION] Python FastAPI SQLite single-workspace prototype; embedded assurance, no PostgreSQL concurrency claim | rulebook silent; pengguna |
| AS-4 | Auth | [ASSUMPTION] Reviewer bearer can read/upload/review; auditor bearer reads only, generated local tokens, no production login | F2 excludes complex auth; pengguna |
| AS-5 | Validation | [ASSUMPTION] Malformed rows/header/duplicate IDs reject batch; absent diagnosis/procedure accepted with needs_data, not evidence of wrongdoing | F3 strict branch and F2 missing information; pengguna |
| AS-6 | Synthetic | [ASSUMPTION] synthetic=true declaration plus SYN- tokens/facilities/claim IDs; unknown columns rejected, no real data allowed | F1 privacy; technical enforcement is partial not anonymization; pengguna |
| AS-7 | Blocking | [ASSUMPTION] same participant, same facility or explicit facility_group; 3-day window; procedure similarity >=0.5 or absent | F1/F2 range unspecified; pengguna |
| AS-8 | Scores | [ASSUMPTION] date/amount/code/submission formulas, 50 queue threshold, high85 medium65; amount10%,submission7days | weights only specified; rules.json values provisional; pengguna |
| AS-9 | Guardrail evidence | [ASSUMPTION] optional schedule date+scheduled_service, visit_id, episode_id,facility_group; no inference from truth labels | F2 cannot prove schedules from 10 fields; pengguna |
| AS-10 | Suppression | [ASSUMPTION] confirmed correction/scheduled repeats/distinct visits suppress; missing info reduces30, cancelled reduces50; protected excluded queue by default | F2 guardrail intent, reductions unspecified; pengguna |
| AS-11 | Episodes | [ASSUMPTION] connected time-window candidates, provisional groups, explicit episode evidence adds reason only not fraud conclusion | F2 episode grouping; pengguna |
| AS-12 | Review | [ASSUMPTION] expected_version, UUID review_id for retries, note up to2000, elapsed_seconds optional0..3600 client report | F2 audit/change decision; pengguna |
| AS-13 | Labels | [ASSUMPTION] optional labels CSV exhaustive same-participant pair population; no labels means current dataset metrics null | F2 hidden truth/evaluation; pengguna |
| AS-14 | Benchmark | [ASSUMPTION] 5 seeds 5000 rows each; independently generated holdout after rules hash freeze; configs varied, not external validation | Arena test requirements; pengguna |
| AS-15 | Bounds | [ASSUMPTION] upload5MB,row count10000,candidate pairs100000 and eligible pairs200000; synchronous atomic processing | prototype safeguards not business rules; pengguna |
| AS-16 | Retention | [ASSUMPTION] local DB persists until operator deletion; no automatic clinical retention policy; no production security claim | F1 prototype; pengguna |

| AS-17 | Amount bound | [ASSUMPTION] 0..1000000000000, Decimal dua digit; bukan plafon manfaat JKN. | Technical input bound; pengguna |

## Ambiguity register
AMB-1 source FE absent: integration handoff only, no claim functional FE.
AMB-2 complete means backend coverage, not production/deployment.
AMB-3 exactly two Notion references are rulebook and both read.
AMB-4 JSON and PNG match; 4 label nodes are arrow labels.
AMB-5 live Figma inaccessible, screenshots proxy; confirm exports later.
AMB-6 stack selected for executable suite; no prescribed stack.
AMB-7 F2 mockup vs prototype completion conflict: functional system unverified until tests; FE progress based on mockup only.
AMB-8 unrelated laundry topic excluded; historical legal/financial statements not backend rules.
AMB-9 F3 requires data valid, F2 permits missing information: malformed rows reject, incomplete clinical values flagged and reviewable.
AMB-10 F2 screenshot sums 2367+117 !=2448; UI illustration not a data constraint. Real counts computed.
AMB-11 screenshot 'Tidak ada pembatalan' under lowering risk is inconsistent: absence of cancellation is never reducer.
AMB-12 current user asks functional FE but file5 forbids FE edits: implement BE and handoff; no source exists to wire.

## Pembaruan scope atas konfirmasi pengguna

- FE hanya tersedia sebagai desain Figma. Implementasi FE baru kini diizinkan, bukan mengedit source yang sudah ada.
- Aplikasi lokal dipilih; deployment online tidak diminta.
- Proposal DOCX boleh diselesaikan dengan penjelasan implementasi dan hasil simulasi.
- Target GitHub adalah repo baru private milik ShikinariShiki; koneksi menolak pembuatan dengan 403, sehingga push belum selesai.
- Beranda menggunakan alur unggah yang sudah ada; tidak dibuat halaman atau workflow baru di luar 12 frame.
- Sesi reviewer lokal berlaku untuk pengguna komputer ini saja. Bukan identitas individu atau autentikasi produksi.
- Evaluasi tanpa label menggunakan lima seed benchmark yang dinyatakan eksplisit, bukan hasil dataset tanpa truth.
