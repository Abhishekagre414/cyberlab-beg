import os
import sys
from app import app
from extensions import db
from models import LabProgress, MissionProgress, EvidenceProgress, ManualLabProgress, ChallengeProgress, LabSessionProgress, LabSessionMissionProgress, LabSessionQuestionAttempt, LabSessionFlagAttempt

def reset_progress():
    with app.app_context():
        print("Resetting all lab progress...")
        
        # 1. Update LabProgress: make ALL labs AVAILABLE, but reset score and completed_at
        db.session.query(LabProgress).update({
            'status': 'AVAILABLE',
            'score': 0,
            'percentage': 0,
            'completed_at': None
        })
        
        # 2. Update MissionProgress: make ALL missions LOCKED and reset completed_at
        db.session.query(MissionProgress).update({
            'status': 'LOCKED',
            'completed_at': None
        })
        
        # 3. For EVERY lab, make its FIRST mission (mission_number=1) AVAILABLE
        # This fixes the "Lab Completed!" bug when a user visits a lab with no AVAILABLE missions.
        from models import Mission
        first_missions = db.session.query(Mission.id).filter_by(mission_number=1).subquery()
        db.session.query(MissionProgress).filter(
            MissionProgress.mission_id.in_(first_missions)
        ).update({
            'status': 'AVAILABLE'
        }, synchronize_session=False)
        
        # 4. Clean up evidence, manual labs, and dynamic lab sessions
        db.session.query(EvidenceProgress).delete()
        db.session.query(ManualLabProgress).delete()
        db.session.query(ChallengeProgress).delete()
        
        db.session.query(LabSessionProgress).delete()
        db.session.query(LabSessionMissionProgress).delete()
        db.session.query(LabSessionQuestionAttempt).delete()
        db.session.query(LabSessionFlagAttempt).delete()
        
        from models import LabSession
        db.session.query(LabSession).delete()
        
        db.session.commit()
        print("All lab progress has been successfully reset. All labs are now unlocked and ready to be replayed.")

if __name__ == '__main__':
    reset_progress()
