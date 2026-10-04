import math
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean

from klaimkembar.engine import detect, exact_match
from klaimkembar.models import BenchmarkReport, Claim, MethodMetrics, MetricRange, PairAssessment, SeedReport, TruthPair
from klaimkembar.settings import Rules

METHODS = ('exact_match', 'similarity_without_guardrails', 'similarity_with_guardrails')
DEFINITIONS = {
    'population': 'Seluruh pasangan klaim dengan participant_token sama dalam dataset; termasuk pasangan yang gagal blocking.',
    'precision': 'TP/(TP+FP); null bila tidak ada temuan.',
    'recall': 'TP/(TP+FN); null bila tidak ada pasangan duplikat berlabel.',
    'f1': '2*TP/(2*TP+FP+FN); null bila penyebut nol.',
    'pr_auc': 'Average precision (step area), threshold ties grouped; bukan trapezoid PR-AUC.',
    'false_positive_pairs_per_1000_claims': '1000*FP pairs/jumlah claims; jumlah alert pasangan, bukan jumlah peserta.',
    'recall_at_top_10_percent': 'TP di ceil(10% populasi pasangan) ranking skor positif / semua pasangan duplikat. Ties diurutkan ID.',
    'time': 'Median elapsed_seconds keputusan pertama per kasus; laporan klien, bukan uji usability.',
}


def metrics(truth: list[TruthPair], scores: dict[tuple[str, str], float], threshold: float, claim_count: int) -> MethodMetrics:
    ranked = sorted(((scores.get((pair.claim_a, pair.claim_b), 0.0), pair) for pair in truth),
                    key=lambda entry: (-entry[0], entry[1].claim_a, entry[1].claim_b))
    positives = sum(pair.is_duplicate for pair in truth)
    predicted = [pair for score, pair in ranked if score >= threshold]
    tp = sum(pair.is_duplicate for pair in predicted)
    fp = len(predicted) - tp
    fn = positives - tp
    precision = tp / len(predicted) if predicted else None
    recall = tp / positives if positives else None
    f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else None
    by_score: dict[float, list[bool]] = defaultdict(list)
    for score, pair in ranked:
        by_score[score].append(pair.is_duplicate)
    seen, found = 0, 0
    average_precision = 0.0
    for score in sorted(by_score, reverse=True):
        block = by_score[score]
        added = sum(block)
        seen += len(block)
        found += added
        if positives:
            average_precision += added / positives * found / seen
    budget = math.ceil(0.1 * len(truth))
    top = [pair for score, pair in ranked[:budget] if score > 0]
    return MethodMetrics(detected_pairs=len(predicted), true_positives=tp, false_positives=fp, false_negatives=fn,
                         precision=precision, recall=recall, f1=f1, pr_auc=average_precision if positives else None,
                         false_positive_pairs_per_1000_claims=1000 * fp / claim_count if claim_count else 0,
                         recall_at_top_10_percent=sum(pair.is_duplicate for pair in top) / positives if positives else None)


def method_scores(claims: list[Claim], truth: list[TruthPair], pairs: list[PairAssessment]) -> dict[str, dict[tuple[str, str], float]]:
    by_id = {claim.claim_id: claim for claim in claims}
    return {
        'exact_match': {(pair.claim_a, pair.claim_b): 100.0 if exact_match(by_id[pair.claim_a], by_id[pair.claim_b]) else 0.0 for pair in truth},
        'similarity_without_guardrails': {(pair.claim_a, pair.claim_b): pair.raw_score for pair in pairs},
        'similarity_with_guardrails': {(pair.claim_a, pair.claim_b): pair.risk_score for pair in pairs},
    }


def evaluate(claims: list[Claim], truth: list[TruthPair], pairs: list[PairAssessment], rules: Rules) -> dict[str, MethodMetrics]:
    scores = method_scores(claims, truth, pairs)
    return {method: metrics(truth, scores[method], 100 if method == 'exact_match' else rules.queue_threshold, len(claims))
            for method in METHODS}


def benchmark(rules: Rules, seeds: list[int], claim_count: int) -> BenchmarkReport:
    from klaimkembar.synthetic import generate
    reports = []
    for seed in seeds:
        claims, truth = generate(seed, claim_count)
        pairs = detect(claims, rules)
        assessed = evaluate(claims, truth, pairs, rules)
        scores = method_scores(claims, truth, pairs)
        failures = {}
        for method in METHODS:
            threshold = 100 if method == 'exact_match' else rules.queue_threshold
            failures[method] = [pair for pair in truth if pair.is_duplicate != (scores[method].get((pair.claim_a, pair.claim_b), 0) >= threshold)][:8]
        reports.append(SeedReport(seed=seed, claim_count=len(claims), eligible_pair_count=len(truth),
                                  positive_pairs=sum(pair.is_duplicate for pair in truth),
                                  prevalence=sum(pair.is_duplicate for pair in truth) / len(truth) if truth else 0,
                                  methods=assessed, failure_examples=failures,
                                  missing_information_count=sum(not claim.diagnosis_group or not claim.procedure_group for claim in claims)))
    aggregates: dict[str, dict[str, MetricRange]] = {}
    for method in METHODS:
        aggregates[method] = {}
        for field in MethodMetrics.model_fields:
            values = [float(value) for report in reports if (value := getattr(report.methods[method], field)) is not None]
            aggregates[method][field] = MetricRange(mean=mean(values) if values else None,
                                                   minimum=min(values) if values else None, maximum=max(values) if values else None)
    return BenchmarkReport(simulation=True, rules_version=rules.version, rules_hash=rules.fingerprint,
                           generated_at=datetime.now(timezone.utc).isoformat(), seeds=reports, aggregates=aggregates,
                           limitations=['Label dan bukti kasus dibuat generator internal, bukan anotasi verifikator klinis.',
                                        'Holdout dibuat setelah rules hash dibekukan; desain generator tetap diketahui pembuat detector.',
                                        'PR-AUC memakai average precision. Ties Top-10% dipecah berdasarkan ID sintetis.',
                                        'False positive dihitung per alert pasangan, bukan per peserta.',
                                        'Waktu benchmark tidak dianggap waktu pemeriksaan manusia.',
                                        'Simulasi ini tidak membuktikan performa pada data JKN asli.'])
