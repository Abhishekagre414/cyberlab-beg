from extensions import db
from models import Hint, HintUsage, LabProgress

def get_hint(user_id, lab_id, mission_id):
    """
    Retrieves the next available hint for a mission, deducting XP.
    Returns (success, message, hint_text)
    """
    # Get all hints for this mission ordered by sort_order
    hints = Hint.query.filter_by(mission_id=mission_id).order_by(Hint.sort_order.asc()).all()
    if not hints:
        return False, "No hints available for this mission.", None
        
    # Find the next unused hint
    for hint in hints:
        usage = HintUsage.query.filter_by(user_id=user_id, hint_id=hint.id).first()
        if not usage:
            # We found the next hint. Do they have enough XP?
            lp = LabProgress.query.filter_by(user_id=user_id, lab_id=lab_id).first()
            if not lp or lp.score < hint.xp_cost:
                return False, f"Not enough XP. Need {hint.xp_cost} XP.", None
                
            # Deduct XP and record usage
            lp.score -= hint.xp_cost
            db.session.add(lp)
            
            new_usage = HintUsage(user_id=user_id, hint_id=hint.id)
            db.session.add(new_usage)
            db.session.commit()
            
            return True, "Hint unlocked.", hint.hint_text
            
    return False, "You have unlocked all hints for this mission.", None
