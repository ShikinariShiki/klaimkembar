import math

from klaimkembar.engine import detect
from klaimkembar.evaluation import benchmark, evaluate, metrics
from klaimkembar.models import TruthPair
from klaimkembar.settings import ROOT, Rules
from klaimkembar.synthetic import generate
from klaimkembar.validation import eligible_pairs


def test_confusion_counts_average_precision_and_top_budget_are_hand_checked():
    truth = [TruthPair(claim_a='A', claim_b=str(index), is_duplicate=label) for index, label in enumerate([True, False, True, False])]
    scores = {('A', str(index)): score for index, score in enumerate([100, 90, 40, 0])}
    actual = metrics(truth, scores, 50, 10)
    assert (actual.true_positives, actual.false_positives, actual.false_negatives) == (1, 1, 1)
    assert actual.precision == actual.recall == actual.f1 == 0.5
    assert math.isclose(actual.pr_auc, (1 + 2 / 3) / 2)
    assert actual.false_positive_pairs_per_1000_claims == 100
    assert actual.recall_at_top_10_percent == 0.5


def test_metric_undefined_denominators_are_null_not_fabricated_zero():
    actual = metrics([], {}, 50, 10)
    assert actual.precision is None and actual.recall is None and actual.f1 is None and actual.pr_auc is None
    assert actual.detected_pairs == 0


def test_tied_score_average_precision_is_order_independent():
    truth = [TruthPair(claim_a='A', claim_b='B', is_duplicate=True), TruthPair(claim_a='A', claim_b='C', is_duplicate=False)]
    scores = {('A', 'B'): 80, ('A', 'C'): 80}
    assert metrics(truth, scores, 50, 3).pr_auc == 0.5
    assert metrics(truth[::-1], scores, 50, 3).pr_auc == 0.5


def test_generator_is_deterministic_and_truth_covers_blocking_misses():
    claims, truth = generate(104, 5000)
    second, second_truth = generate(104, 5000)
    assert claims == second and truth == second_truth
    assert len(claims) == 5000
    assert {(pair.claim_a, pair.claim_b) for pair in truth} == eligible_pairs(claims, 200000)
    pairs = detect(claims, Rules.load(ROOT / 'rules.json'))
    blocked_out = {(pair.claim_a, pair.claim_b) for pair in truth if pair.is_duplicate} - {(pair.claim_a, pair.claim_b) for pair in pairs}
    assert blocked_out
    assert all(claim.participant_token.startswith('SYN-') for claim in claims)


def test_benchmark_reports_five_seeds_ranges_failures_and_simulation():
    rules = Rules.load(ROOT / 'rules.json')
    report = benchmark(rules, [104, 211, 307, 409, 503], 500)
    assert len(report.seeds) == 5
    assert report.simulation and report.rules_hash == rules.fingerprint
    assert len({seed.prevalence for seed in report.seeds}) > 1
    for method, fields in report.aggregates.items():
        assert fields['recall'].minimum <= fields['recall'].mean <= fields['recall'].maximum
        assert any(seed.failure_examples[method] for seed in report.seeds)


def test_ground_truth_is_not_an_input_to_detector():
    import inspect
    assert list(inspect.signature(detect).parameters) == ['claims', 'rules']
    claims, truth = generate(211, 100)
    rules = Rules.load(ROOT / 'rules.json')
    pairs = detect(claims, rules)
    actual = evaluate(claims, truth, pairs, rules)
    positives = sum(pair.is_duplicate for pair in truth)
    for method in actual.values():
        assert method.true_positives + method.false_negatives == positives
