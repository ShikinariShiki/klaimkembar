from klaimkembar.postgres_database import HybridRow, PostgresConnection, PostgresDatabase, _translate


def test_row_supports_named_and_positional_lookup():
    row = HybridRow(('demo', 7), ('label', 'version'))
    assert row[0] == row['label'] == 'demo'
    assert row[1] == row['version'] == 7


def test_sql_translation_covers_filters_and_facets():
    sql = "SELECT * FROM cases c WHERE json_extract(c.payload,'$.risk_level')=? AND json_extract(c.payload,'$.needs_data')=1"
    translated = _translate(sql)
    assert 'json_extract' not in translated
    assert "c.payload::jsonb->>'risk_level'" in translated
    assert "c.payload::jsonb->>'needs_data'" in translated
    assert '%s' in translated
    facets = "SELECT DISTINCT value FROM cases,json_each(cases.payload,'$.triggered_reasons') WHERE dataset_id=? ORDER BY value"
    assert 'jsonb_array_elements_text' in _translate(facets)


def test_review_lock_is_scoped_to_first_case_lookup():
    class FakeConnection:
        def __init__(self):
            self.queries = []

        def execute(self, sql, params=()):
            self.queries.append(sql)
            return None

    raw = FakeConnection()
    connection = PostgresConnection(raw)
    connection.execute('BEGIN IMMEDIATE')
    connection.execute('SELECT * FROM cases WHERE id=?', ('synthetic-id',))
    connection.execute('SELECT * FROM cases WHERE id=?', ('synthetic-id',))
    assert raw.queries[1].endswith('FOR UPDATE')
    assert not raw.queries[2].endswith('FOR UPDATE')


def test_vercel_pooler_url_removes_only_supa_parameter():
    db = PostgresDatabase('postgresql://synthetic:synthetic@localhost/db?sslmode=require&supa=ignored')
    assert 'supa=' not in db._url
    assert 'sslmode=require' in db._url
