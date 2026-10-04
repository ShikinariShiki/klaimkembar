import hmac
import json
import logging
import sqlite3
import time
from typing import Annotated, Any, Literal, cast
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, File, Form, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from klaimkembar.errors import Rejection
from klaimkembar.local_ui import install_ui, session_actor
from klaimkembar.models import (
    CaseDetail,
    CasesResponse,
    ErrorBody,
    ErrorEnvelope,
    EvaluationResponse,
    FacetsResponse,
    FieldIssue,
    HealthResponse,
    Priority,
    ReviewRequest,
    ReviewResponse,
    ReviewStatus,
    UploadResponse,
)
from klaimkembar.settings import ROOT, Settings
from klaimkembar.workflow import Actor, ClaimsWorkflow

LOGGER = logging.getLogger('klaimkembar')
BEARER = HTTPBearer(auto_error=False)


class ContractApp(FastAPI):
    def openapi(self) -> dict[str, Any]:
        return cast(dict[str, Any], self.state.contract)


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()
    workflow = ClaimsWorkflow(config)
    contract = json.loads((ROOT / 'openapi.json').read_text())
    app = ContractApp(title='KlaimKembar Prototype API', version='1.0.0', docs_url=None, redoc_url=None, openapi_url='/openapi.json')
    app.state.workflow = workflow
    app.state.contract = contract

    def envelope(request: Request, status: int, code: str, message: str,
                 details: list[FieldIssue] | None = None, rejection: Rejection | None = None) -> JSONResponse:
        body = ErrorEnvelope(error=ErrorBody(code=code, message=message, details=details or [], request_id=request.state.request_id,
                                            validation=rejection.validation if rejection else None))
        headers = {'WWW-Authenticate': 'Bearer'} if status == 401 else None
        return JSONResponse(status_code=status, content=body.model_dump(), headers=headers)

    @app.middleware('http')
    async def request_boundary(request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.request_id = str(uuid4())
        started = time.monotonic()
        try:
            response = await call_next(request)
        except Exception as exc:
            # Boundary redacts exception values; detailed failures remain test-visible.
            LOGGER.error(json.dumps({'event': 'internal_failure', 'request_id': request.state.request_id, 'exception_type': type(exc).__name__}))
            response = envelope(request, 500, 'INTERNAL_ERROR', 'Permintaan belum dapat diselesaikan. Hubungi pengelola dengan request_id ini.')
            if request.headers.get('origin') in config.origins:
                response.headers['Access-Control-Allow-Origin'] = request.headers['origin']
                response.headers['Vary'] = 'Origin'
        if request.method == 'OPTIONS' and response.status_code >= 400:
            response = envelope(request, 400, 'CORS_REJECTED', 'Origin atau header frontend tidak diizinkan. Periksa CORS_ORIGINS.')
        response.headers['X-Request-ID'] = request.state.request_id
        route = getattr(request.scope.get('route'), 'path', 'unmatched')
        LOGGER.info(json.dumps({'event': 'request', 'request_id': request.state.request_id, 'method': request.method,
                                'route': route, 'status': response.status_code, 'duration_ms': round((time.monotonic() - started) * 1000, 2)}))
        return response

    @app.exception_handler(Rejection)
    async def rejected(request: Request, exc: Rejection) -> JSONResponse:
        return envelope(request, exc.status, exc.code, exc.message, exc.details, exc)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        issues = [FieldIssue(field='.'.join(map(str, issue['loc'])), code=issue['type'],
                             message='Periksa tipe, format, dan batas nilai sesuai kontrak API.') for issue in exc.errors()]
        return envelope(request, 422, 'REQUEST_INVALID', 'Permintaan tidak sesuai kontrak API.', issues)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        messages = {404: ('ROUTE_NOT_FOUND', 'Alamat API tidak ditemukan.'), 405: ('METHOD_NOT_ALLOWED', 'Metode HTTP tidak tersedia untuk alamat ini.'),
                    400: ('REQUEST_BODY_INVALID', 'Body permintaan tidak dapat dibaca. Periksa JSON atau multipart.')}
        code, message = messages.get(exc.status_code, ('HTTP_ERROR', 'Permintaan ditolak. Periksa kontrak API.'))
        return envelope(request, exc.status_code, code, message)

    @app.exception_handler(sqlite3.OperationalError)
    async def storage_error(request: Request, exc: sqlite3.OperationalError) -> JSONResponse:
        LOGGER.error(json.dumps({'event': 'storage_unavailable', 'request_id': request.state.request_id, 'exception_type': type(exc).__name__}))
        return envelope(request, 503, 'STORAGE_UNAVAILABLE', 'Penyimpanan belum tersedia. Coba lagi atau hubungi pengelola.')

    def authenticated(request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(BEARER)]) -> Actor:
        if credentials is None and config.local_ui and session_actor(request, app.state.ui_sessions):
            return Actor('prototype-reviewer', 'reviewer')
        if credentials is None:
            raise Rejection(401, 'AUTH_REQUIRED', 'Gunakan token akses prototype pada header Authorization.')
        supplied = credentials.credentials
        if hmac.compare_digest(supplied.encode(), config.reviewer_token.encode()):
            return Actor('prototype-reviewer', 'reviewer')
        if hmac.compare_digest(supplied.encode(), config.auditor_token.encode()):
            return Actor('prototype-auditor', 'auditor')
        raise Rejection(401, 'AUTH_INVALID', 'Token akses tidak dikenali.')

    def reviewer(actor: Annotated[Actor, Depends(authenticated)]) -> Actor:
        if actor.role != 'reviewer':
            raise Rejection(403, 'ROLE_FORBIDDEN', 'Hanya petugas pemeriksa yang dapat mengunggah dan menyimpan keputusan.')
        return actor

    @app.get('/health', response_model=HealthResponse)
    def health() -> HealthResponse:
        with workflow.db.connect() as connection:
            connection.execute('SELECT version FROM schema_version').fetchone()
        return HealthResponse(status='ok', database='sqlite', rules_version=workflow.rules.version)

    @app.post('/api/v1/datasets/upload', response_model=UploadResponse, status_code=201)
    async def upload(request: Request, file: Annotated[UploadFile, File()], synthetic: Annotated[bool, Form()],
                     actor: Annotated[Actor, Depends(reviewer)], labels: Annotated[UploadFile | None, File()] = None) -> UploadResponse:
        form = await request.form()
        if set(form.keys()) - {'file', 'synthetic', 'labels'} or any(len(form.getlist(key)) != 1 for key in form.keys()):
            raise Rejection(422, 'UPLOAD_FIELDS', 'Gunakan satu file, satu synthetic, dan paling banyak satu labels.')
        content = await file.read(config.max_upload_bytes + 1)
        truth = await labels.read(config.max_upload_bytes + 1) if labels is not None else None
        return await run_in_threadpool(workflow.upload, file.filename or '', content, synthetic, truth)

    @app.get('/api/v1/cases', response_model=CasesResponse)
    def cases(dataset_id: UUID, actor: Annotated[Actor, Depends(authenticated)], page: Annotated[int, Query(ge=1)] = 1,
              page_size: Annotated[int, Query(ge=1, le=100)] = 20, risk_level: Priority | None = None,
              review_status: ReviewStatus | None = None, facility_id: Annotated[str | None, Query(max_length=100)] = None,
              reason: Annotated[str | None, Query(max_length=100)] = None,
              sort: Literal['score_desc', 'score_asc', 'service_date'] = 'score_desc', include_protected: bool = False) -> CasesResponse:
        return workflow.cases(str(dataset_id), page, page_size, risk_level, review_status, facility_id, reason, sort, include_protected)

    @app.get('/api/v1/facets', response_model=FacetsResponse)
    def facets(dataset_id: UUID, actor: Annotated[Actor, Depends(authenticated)]) -> FacetsResponse:
        with workflow.db.connect() as connection:
            workflow._dataset(connection, str(dataset_id))
            facilities = [row[0] for row in connection.execute(
                'SELECT DISTINCT facility_id FROM claims WHERE dataset_id=? ORDER BY facility_id', (str(dataset_id),))]
            reasons = [row[0] for row in connection.execute(
                "SELECT DISTINCT value FROM cases,json_each(cases.payload,'$.triggered_reasons') WHERE dataset_id=? ORDER BY value",
                (str(dataset_id),))]
        return FacetsResponse(facilities=facilities, reasons=reasons)

    @app.get('/api/v1/cases/{case_id}', response_model=CaseDetail)
    def detail(case_id: UUID, actor: Annotated[Actor, Depends(authenticated)]) -> CaseDetail:
        return workflow.detail(str(case_id))

    @app.post('/api/v1/cases/{case_id}/review', response_model=ReviewResponse)
    def review(case_id: UUID, payload: ReviewRequest, actor: Annotated[Actor, Depends(reviewer)]) -> ReviewResponse:
        return workflow.review(str(case_id), payload, actor)

    @app.get('/api/v1/evaluation', response_model=EvaluationResponse)
    def evaluation(dataset_id: UUID, actor: Annotated[Actor, Depends(authenticated)]) -> EvaluationResponse:
        return workflow.evaluation(str(dataset_id))

    app.user_middleware.append(Middleware(CORSMiddleware, allow_origins=list(config.origins), allow_credentials=False,
                                             allow_methods=['GET', 'POST'], allow_headers=['Authorization', 'Content-Type'],
                                             expose_headers=['X-Request-ID']))
    if config.local_ui:
        install_ui(app, ROOT)
    return app
