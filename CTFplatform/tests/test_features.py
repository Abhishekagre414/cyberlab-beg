import os
import sqlite3

def test_quiz_evaluation(auth_client):
    client, user_id = auth_client
    
    # Lab 4 Mission 1 has a quiz. 
    db = sqlite3.connect(os.environ['DATABASE_PATH'])
    db.row_factory = sqlite3.Row
    
    # Try an incorrect answer
    response = client.post('/api/quiz', json={'lab_id': 'lab4', 'mission_id': 'lab4_m1', 'answer': 'wrong'})
    assert response.json['success'] == False
    
    # Try the correct answer
    response = client.post('/api/quiz', json={'lab_id': 'lab4', 'mission_id': 'lab4_m1', 'answer': 'browser'})
    assert response.json['success'] == True
    
    # Check that score went up
    lp = db.execute("SELECT score FROM lab_progress WHERE user_id = ? AND lab_id = 'lab4'", (user_id,)).fetchone()
    assert lp['score'] >= 150
    db.close()

def test_hint_usage(auth_client):
    client, user_id = auth_client
    db = sqlite3.connect(os.environ['DATABASE_PATH'])
    db.row_factory = sqlite3.Row
    
    # Give user some XP so they can afford a hint
    db.execute("UPDATE lab_progress SET score = 50 WHERE user_id = ? AND lab_id = 'lab1'", (user_id,))
    db.commit()
    
    # Request a hint
    response = client.post('/api/hint', json={'lab_id': 'lab1', 'mission_id': 'lab1_m1'})
    assert response.json['success'] == True
    assert 'Network tab' in response.json['hint']
    
    # Verify XP was deducted (Hint 1 costs 10 XP)
    lp = db.execute("SELECT score FROM lab_progress WHERE user_id = ? AND lab_id = 'lab1'", (user_id,)).fetchone()
    assert lp['score'] == 40
    
    # Try requesting again to get the NEXT hint
    response = client.post('/api/hint', json={'lab_id': 'lab1', 'mission_id': 'lab1_m1'})
    assert response.json['success'] == True
    assert 'X-Custom-Flag' in response.json['hint']
    
    # Verify XP deducted again (Hint 2 costs 20 XP)
    lp = db.execute("SELECT score FROM lab_progress WHERE user_id = ? AND lab_id = 'lab1'", (user_id,)).fetchone()
    assert lp['score'] == 20
    db.close()

def test_admin_access(auth_client):
    client, user_id = auth_client
    # By default, auth_client creates a 'student' role.
    response = client.get('/admin/')
    assert response.status_code == 403
