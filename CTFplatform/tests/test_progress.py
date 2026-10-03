import os
import sqlite3

def test_initial_progress_state(auth_client):
    client, user_id = auth_client
    db = sqlite3.connect(os.environ['DATABASE_PATH'])
    db.row_factory = sqlite3.Row
    
    # Lab 1 should be AVAILABLE, Lab 2 should be LOCKED
    l1 = db.execute("SELECT status FROM lab_progress WHERE user_id = ? AND lab_id = 'lab1'", (user_id,)).fetchone()
    l2 = db.execute("SELECT status FROM lab_progress WHERE user_id = ? AND lab_id = 'lab2'", (user_id,)).fetchone()
    
    assert l1['status'] == 'AVAILABLE'
    assert l2['status'] == 'LOCKED'

def test_lab_unlocks_on_completion(auth_client):
    client, user_id = auth_client
    db = sqlite3.connect(os.environ['DATABASE_PATH'])
    db.row_factory = sqlite3.Row
    
    # Simulate completing Lab 1 flag
    db.execute("INSERT INTO flags (id, lab_id, flag_value) VALUES ('f1', 'lab1', 'FLAG')")
    db.commit()
    
    response = client.post('/api/flag', json={'lab_id': 'lab1', 'flag': 'FLAG'})
    assert response.json['success'] == True
    
    # Lab 2 should now be unlocked
    l2 = db.execute("SELECT status FROM lab_progress WHERE user_id = ? AND lab_id = 'lab2'", (user_id,)).fetchone()
    assert l2['status'] == 'AVAILABLE'

def test_evidence_duplicate_protection(auth_client):
    client, user_id = auth_client
    db = sqlite3.connect(os.environ['DATABASE_PATH'])
    db.row_factory = sqlite3.Row
    
    # Initial score
    l1 = db.execute("SELECT score FROM lab_progress WHERE user_id = ? AND lab_id = 'lab1'", (user_id,)).fetchone()
    initial_score = l1['score']
    
    # Submit evidence
    response = client.post('/api/evidence', json={'lab_id': 'lab1', 'evidence_id': 'ev1'})
    assert response.json['success'] == True
    
    l1 = db.execute("SELECT score FROM lab_progress WHERE user_id = ? AND lab_id = 'lab1'", (user_id,)).fetchone()
    assert l1['score'] == initial_score + 25
    
    # Submit duplicate evidence
    response2 = client.post('/api/evidence', json={'lab_id': 'lab1', 'evidence_id': 'ev1'})
    assert response2.json['success'] == False
    
    # Score should not have increased
    l1_new = db.execute("SELECT score FROM lab_progress WHERE user_id = ? AND lab_id = 'lab1'", (user_id,)).fetchone()
    assert l1_new['score'] == l1['score']


def test_evidence_must_exist_and_belong_to_the_lab(auth_client):
    client, _ = auth_client
    # invented ids used to award +25 each
    assert client.post('/api/evidence', json={'lab_id': 'lab1', 'evidence_id': 'made-up'}).status_code == 404
    # real evidence, wrong lab
    assert client.post('/api/evidence', json={'lab_id': 'lab2', 'evidence_id': 'ev1'}).status_code == 404
    # non-string ids don't blow up
    assert client.post('/api/evidence', json={'lab_id': 'lab1', 'evidence_id': ['ev1']}).status_code == 404
