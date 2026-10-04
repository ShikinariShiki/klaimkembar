import json
from pathlib import Path

from openapi_spec_validator import validate
from pydantic import BaseModel

from klaimkembar import models

schemas = {}
for name in dir(models):
    cls = getattr(models, name)
    if isinstance(cls, type) and issubclass(cls, BaseModel) and cls not in (BaseModel, models.Record):
        body = cls.model_json_schema(ref_template='#/components/schemas/{model}')
        schemas.update(body.pop('$defs', {}))
        schemas[name] = body


def response(name):
    return {'description': name, 'content': {'application/json': {'schema': {'$ref': f'#/components/schemas/{name}'}}}}


def parameter(name, kind, schema, required=False):
    return {'name': name, 'in': kind, 'required': required, 'schema': schema}


uuid = {'type': 'string', 'format': 'uuid'}
paths = {}
operations = [
    ('get', '/health', 'health', 'HealthResponse', []),
    ('post', '/api/v1/datasets/upload', 'uploadDataset', 'UploadResponse', []),
    ('get', '/api/v1/cases', 'listCases', 'CasesResponse', [
        parameter('dataset_id', 'query', uuid, True),
        parameter('page', 'query', {'type': 'integer', 'minimum': 1, 'default': 1}),
        parameter('page_size', 'query', {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 20}),
        parameter('risk_level', 'query', {'type': 'string', 'enum': ['high', 'medium', 'low']}),
        parameter('review_status', 'query', {'type': 'string', 'enum': ['unreviewed', 'valid', 'needs_documents', 'further_review']}),
        parameter('facility_id', 'query', {'type': 'string', 'maxLength': 100}),
        parameter('reason', 'query', {'type': 'string', 'maxLength': 100}),
        parameter('sort', 'query', {'type': 'string', 'enum': ['score_desc', 'score_asc', 'service_date'], 'default': 'score_desc'}),
        parameter('include_protected', 'query', {'type': 'boolean', 'default': False})]),
    ('get', '/api/v1/facets', 'getFacets', 'FacetsResponse', [parameter('dataset_id', 'query', uuid, True)]),
    ('get', '/api/v1/cases/{case_id}', 'getCase', 'CaseDetail', [parameter('case_id', 'path', uuid, True)]),
    ('post', '/api/v1/cases/{case_id}/review', 'reviewCase', 'ReviewResponse', [parameter('case_id', 'path', uuid, True)]),
    ('get', '/api/v1/evaluation', 'getEvaluation', 'EvaluationResponse', [parameter('dataset_id', 'query', uuid, True)])]
for method, path, op, name, params in operations:
    success = '201' if name == 'UploadResponse' else '200'
    item = {'operationId': op, 'parameters': params, 'responses': {success: response(name)}}
    for status in ['400', '401', '403', '404', '405', '409', '413', '422', '500', '503']:
        item['responses'][status] = response('ErrorEnvelope')
    if path != '/health':
        item['security'] = [{'DemoBearer': []}]
    if op == 'uploadDataset':
        item['requestBody'] = {'required': True, 'content': {'multipart/form-data': {'schema': {
            'type': 'object', 'required': ['file', 'synthetic'], 'additionalProperties': False,
            'properties': {'file': {'type': 'string', 'format': 'binary'}, 'synthetic': {'type': 'boolean', 'const': True}, 'labels': {'type': 'string', 'format': 'binary'}}}}}}
    if op == 'reviewCase':
        item['requestBody'] = {'required': True, 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/ReviewRequest'}}}}
    paths.setdefault(path, {})[method] = item
contract = {'openapi': '3.1.0', 'info': {'title': 'KlaimKembar Prototype API', 'version': '1.0.0',
    'description': 'Data sintetis. Skor prioritas pemeriksaan, bukan vonis atau persetujuan pembayaran.'},
    'servers': [{'url': 'http://127.0.0.1:8000'}], 'paths': paths,
    'components': {'schemas': schemas, 'securitySchemes': {'DemoBearer': {'type': 'http', 'scheme': 'bearer'}}}}
Path('openapi.json').write_text(json.dumps(contract, ensure_ascii=False, indent=2) + '\n')
validate(contract)
print(f'Contract lint PASS: {len(operations)} operations, {len(schemas)} schemas')
