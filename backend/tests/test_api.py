from fastapi.testclient import TestClient
from app.main import app, jobs, rate


def test_demo_flow_and_health():
    with TestClient(app) as client:
        assert client.get('/health').json()['status'] == 'ok'
        response = client.post('/analyses', json={'url': 'https://example.com/audifonos', 'mode': 'demo'})
        assert response.status_code == 202
        result = client.get('/analyses/' + response.json()['id']).json()
        assert result['status'] == 'completed' and result['mode'] == 'demo'
        assert result['store_profile']['domain'] == 'demo.buenpaso.mx'
        assert result['store_profile']['image'] == '/demo-store.svg'
        assert result['store_profile']['seller_name'] == 'Vendedor de ejemplo'
        assert len(result['alternatives']) == 3
        assert all(p['demo'] for p in result['alternatives'])
        assert result['alternatives'][2]['branches'] == []
        assert result['alternatives'][0]['branches'][0]['inventory'] == 'pending'


def test_errors_are_consistent():
    with TestClient(app) as client:
        response = client.post('/analyses', json={'url': 'http://127.0.0.1'})
        assert response.status_code == 422 and 'message' in response.json()['error']
        assert client.get('/analyses/missing').status_code == 404
        large = client.post('/analyses', content=b'x' * 20000, headers={'Content-Type': 'application/json'})
        assert large.status_code == 413


def test_cors_allows_the_next_development_port():
    with TestClient(app) as client:
        response = client.options('/analyses', headers={
            'Origin': 'http://localhost:3001',
            'Access-Control-Request-Method': 'POST',
        })
        assert response.status_code == 200
        assert response.headers['access-control-allow-origin'] == 'http://localhost:3001'
