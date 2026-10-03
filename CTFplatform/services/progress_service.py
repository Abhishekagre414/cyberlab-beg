from extensions import db
from models import Lab, Mission, LabProgress, MissionProgress

def initialize_user_progress(user_id):
    """
    Discovers all active labs and creates progress rows.
    Implements standard unlocking rule: Lab 1 AVAILABLE, others LOCKED initially.
    """
    labs = Lab.query.order_by(Lab.id.asc()).all()
    
    # Lab unlock logic:
    # Lab 1 is always available for a new user.
    # Other labs are locked initially.
    for i, lab in enumerate(labs):
        lab_id = lab.id
        status = 'AVAILABLE' if i == 0 else 'LOCKED'
        
        # Insert lab progress if it doesn't exist
        existing_lp = LabProgress.query.filter_by(user_id=user_id, lab_id=lab_id).first()
        if not existing_lp:
            lp = LabProgress(user_id=user_id, lab_id=lab_id, status=status)
            db.session.add(lp)
        
        # Initialize mission progress for this lab
        missions = Mission.query.filter_by(lab_id=lab_id).order_by(Mission.mission_number.asc()).all()
        for j, mission in enumerate(missions):
            mission_id = mission.id
            # Only the first mission is available IF the lab is available, else locked
            m_status = 'AVAILABLE' if (i == 0 and j == 0) else 'LOCKED'
            
            existing_mp = MissionProgress.query.filter_by(user_id=user_id, mission_id=mission_id).first()
            if not existing_mp:
                mp = MissionProgress(user_id=user_id, lab_id=lab_id, mission_id=mission_id, status=m_status)
                db.session.add(mp)
                
    # Caller should commit

def update_unlocks(user_id):
    """
    Evaluates progression rules. If Lab N is COMPLETED, Lab N+1 becomes AVAILABLE.
    Also handles mission unlocks within a lab.
    """
    labs = Lab.query.order_by(Lab.id.asc()).all()
    
    for i in range(len(labs) - 1):
        current_lab = labs[i].id
        next_lab = labs[i+1].id
        
        curr_progress = LabProgress.query.filter_by(user_id=user_id, lab_id=current_lab).first()
        next_progress = LabProgress.query.filter_by(user_id=user_id, lab_id=next_lab).first()
        
        if curr_progress and curr_progress.status == 'COMPLETED':
            if next_progress and next_progress.status == 'LOCKED':
                next_progress.status = 'AVAILABLE'
                db.session.add(next_progress)
                
                # Unlock first mission of next lab
                first_mission = Mission.query.filter_by(lab_id=next_lab).order_by(Mission.mission_number.asc()).first()
                if first_mission:
                    fm_progress = MissionProgress.query.filter_by(user_id=user_id, mission_id=first_mission.id).first()
                    if fm_progress:
                        fm_progress.status = 'AVAILABLE'
                        db.session.add(fm_progress)
    # Caller should commit
