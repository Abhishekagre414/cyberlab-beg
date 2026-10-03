from extensions import db
from models import MissionQuiz, QuizAttempt, MissionProgress, LabProgress

def evaluate_quiz(user_id, lab_id, mission_id, answer):
    """
    Evaluates a quiz answer against the database.
    Returns (success, message, xp_awarded)
    """
    quiz = MissionQuiz.query.filter_by(mission_id=mission_id).first()
    if not quiz:
        return False, "No quiz found for this mission.", 0

    correct = (quiz.answer.strip().lower() == answer.strip().lower())
    
    # Record attempt
    attempt = QuizAttempt(user_id=user_id, mission_id=mission_id, answer=answer, correct=correct)
    db.session.add(attempt)
    
    if correct:
        # Check if already completed
        mission_prog = MissionProgress.query.filter_by(user_id=user_id, mission_id=mission_id).first()
        if mission_prog and mission_prog.status == 'COMPLETED':
             db.session.commit()
             return True, "Correct! But already completed.", 0
             
        # Add XP
        xp = quiz.xp_reward
        lab_prog = LabProgress.query.filter_by(user_id=user_id, lab_id=lab_id).first()
        if lab_prog:
            lab_prog.score += xp
            db.session.add(lab_prog)
        
        # Mark as completed
        if mission_prog:
            mission_prog.status = 'COMPLETED'
            db.session.add(mission_prog)
            
        db.session.commit()
        return True, "Correct! Next mission unlocked.", xp
    
    db.session.commit()
    return False, "Incorrect answer. Try again.", 0
