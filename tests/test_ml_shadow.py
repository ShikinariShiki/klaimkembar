import math

from klaimkembar.ml_shadow import score_in_shadow
from tests.test_api import api, assert_contract  # noqa: F401


class Scorer:
    version = 'test-only'

    def score(self, features):
        return 0.7


class BrokenScorer:
    version = 'test-only'

    def score(self, features):
        raise RuntimeError('sensitive detail')


def test_shadow_scaffold_is_opt_in_and_fails_closed():
    assert score_in_shadow((1.0,), None).status == 'not_available'
    assert score_in_shadow((math.nan,), Scorer()).status == 'fallback'
    assert score_in_shadow((1.0,), BrokenScorer()).status == 'fallback'
    result = score_in_shadow((1.0,), Scorer())
    assert result.status == 'shadow_scored'
    assert result.score == 0.7
    assert result.model_version == 'test-only'


def test_status_is_authenticated_and_truthful(api):  # noqa: F811
    client, reviewer, *_ = api
    path = '/api/v1/ml/status'
    response = client.get(path)
    assert response.status_code == 401
    assert_contract(response, 'get', path)
    response = client.get(path, headers=reviewer)
    assert response.status_code == 200
    assert_contract(response, 'get', path)
    assert response.json()['mode'] == 'rules_only'
    assert response.json()['model_status'] == 'not_available'
    assert response.json()['shadow_enabled'] is False
    assert response.json()['model_version'] is None

