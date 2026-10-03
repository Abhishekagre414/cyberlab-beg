def test_rate_limiting(client):
    from app import limiter
    limiter.enabled = True
    
    # Test rate limiting on login route (5 per minute)
    for i in range(5):
        response = client.post('/login', data={'username': 'a', 'password': 'b'})
        assert response.status_code == 200 # Failed login returns 200 with error template

    # The 6th attempt should be rate limited (429 Too Many Requests)
    response = client.post('/login', data={'username': 'a', 'password': 'b'})
    assert response.status_code == 429
    
    limiter.enabled = False
