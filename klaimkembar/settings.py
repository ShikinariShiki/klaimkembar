import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Rules:
    version: str
    blocking_days: int
    procedure_candidate_similarity: float
    code_similarity_minimum: float
    amount_relative_tolerance: float
    submission_days: int
    queue_threshold: float
    high_priority: float
    medium_priority: float
    missing_information_reduction: float
    cancelled_reduction: float
    protect_reduction: float
    maximum_candidates: int
    maximum_eligible_pairs: int
    weights: dict[str, float]
    fingerprint: str
    snapshot: str

    @classmethod
    def load(cls, path: Path) -> 'Rules':
        raw = path.read_bytes()
        values = json.loads(raw)
        weights = values['weights']
        if sum(weights.values()) != 100 or any(weight < 0 for weight in weights.values()):
            raise ValueError('weights must total 100 with no negative contribution')
        if not 0 <= values['queue_threshold'] <= values['medium_priority'] <= values['high_priority'] <= 100:
            raise ValueError('priority thresholds must be ordered within 0..100')
        for key in ['procedure_candidate_similarity', 'code_similarity_minimum', 'amount_relative_tolerance']:
            if not 0 < values[key] <= 1:
                raise ValueError(f'{key} must be in (0,1]')
        for key in ['blocking_days', 'submission_days', 'maximum_candidates', 'maximum_eligible_pairs']:
            if values[key] <= 0:
                raise ValueError(f'{key} must be positive')
        for key in ['missing_information_reduction', 'cancelled_reduction', 'protect_reduction']:
            if not 0 <= values[key] <= 100:
                raise ValueError(f'{key} must be in 0..100')
        return cls(**values, fingerprint=hashlib.sha256(raw).hexdigest(), snapshot=raw.decode())


@dataclass(frozen=True)
class Settings:
    db_path: Path
    reviewer_token: str
    auditor_token: str
    origins: tuple[str, ...] = ('http://localhost:5173',)
    rules_path: Path = ROOT / 'rules.json'
    benchmark_path: Path = ROOT / 'examples/benchmark.json'
    max_upload_bytes: int = 5 * 1024 * 1024
    max_rows: int = 10000
    local_ui: bool = False
    cloud_demo: bool = False
    cloud_origin: str = ""
    cloud_session_secret: str = ""
    cloud_demo_passcode: str = ""
    postgres_url: str = ""

    def __post_init__(self) -> None:
        if min(len(self.reviewer_token), len(self.auditor_token)) < 32 or self.reviewer_token == self.auditor_token:
            raise ValueError('two distinct tokens of at least 32 characters are required')
        if self.cloud_demo:
            parts = urlsplit(self.cloud_origin)
            if self.local_ui or parts.scheme != 'https' or not parts.hostname or parts.path or parts.query or parts.fragment:
                raise ValueError('cloud demo requires an explicit HTTPS origin and cannot use local UI')
            if len(self.cloud_session_secret) < 32 or len(self.cloud_demo_passcode) < 32 or self.cloud_session_secret == self.cloud_demo_passcode:
                raise ValueError('cloud demo requires distinct session secret and passcode of at least 32 characters')
        if '*' in self.origins:
            raise ValueError('explicit frontend origins are required')

    @classmethod
    def from_env(cls) -> 'Settings':
        if os.environ.get("CLOUD_DEMO", "false").lower() == "true" and not os.environ.get("POSTGRES_URL"):
            raise ValueError("cloud demo requires POSTGRES_URL")
        return cls(
            postgres_url=os.environ.get("POSTGRES_URL", ""),
            local_ui=os.environ.get('LOCAL_UI', 'false').lower() == 'true',
            cloud_demo=os.environ.get('CLOUD_DEMO', 'false').lower() == 'true',
            max_upload_bytes=4 * 1024 * 1024 if os.environ.get('CLOUD_DEMO', 'false').lower() == 'true' else 5 * 1024 * 1024,
            cloud_origin=os.environ.get('CLOUD_ORIGIN', ''),
            cloud_session_secret=os.environ.get('CLOUD_SESSION_SECRET', ''),
            cloud_demo_passcode=os.environ.get('CLOUD_DEMO_PASSCODE') or ('kk-default-passcode-' + 'x' * 24),
            db_path=Path(os.environ.get('DATABASE_PATH', 'var/klaimkembar.sqlite')),
            reviewer_token=os.environ.get('REVIEWER_TOKEN', ''),
            auditor_token=os.environ.get('AUDITOR_TOKEN', ''),
            origins=tuple(origin.strip() for origin in os.environ.get('CORS_ORIGINS', 'http://localhost:5173').split(',') if origin.strip()),
            rules_path=Path(os.environ.get('RULES_PATH', str(ROOT / 'rules.json'))),
            benchmark_path=Path(os.environ.get('BENCHMARK_PATH', str(ROOT / 'examples/benchmark.json'))),
        )
