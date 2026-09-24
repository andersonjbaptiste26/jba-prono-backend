# ============================================================================
# DÉPRÉCIÉ depuis v0.3.0 — Les paris sont désormais gérés en localStorage
# côté client. Ce routeur n'est plus enregistré dans main.py.
# Conservé en commentaire pour référence future.
# ============================================================================
#
# from datetime import datetime, timezone
# from math import prod
# import uuid as uuid_lib
#
# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session
# from pydantic import BaseModel
# from typing import List, Optional
#
# from ..database import get_db
# from ..models import Bet, BetSelection, Event, Prediction, User
#
# router = APIRouter(prefix="/bets", tags=["bets"])
#
#
# class SelectionIn(BaseModel):
#     event_id: int
#     odds_value: Optional[float] = None
#     probability: Optional[float] = None
#     event_type: Optional[str] = None
#     event_label: Optional[str] = None
#
#
# class BetIn(BaseModel):
#     user_id: str
#     selections: List[SelectionIn]
#
#
# def _get_or_create_anonymous_user(db: Session, user_id: str) -> str:
#     try:
#         parsed = uuid_lib.UUID(user_id)
#     except ValueError:
#         raise HTTPException(status_code=400, detail="user_id doit être un UUID valide.")
#     user = db.query(User).filter(User.id == parsed).first()
#     if not user:
#         user = User(
#             id=parsed,
#             email=f"anon-{parsed}@device.local",
#             password_hash="",
#             display_name="Utilisateur anonyme",
#         )
#         db.add(user)
#         db.flush()
#     return str(parsed)
#
#
# @router.post("")
# def create_bet(payload: BetIn, db: Session = Depends(get_db)):
#     if not payload.selections:
#         raise HTTPException(status_code=400, detail="Aucune sélection fournie.")
#     user_id = _get_or_create_anonymous_user(db, payload.user_id)
#     event_ids = [s.event_id for s in payload.selections]
#     if len(set(event_ids)) != len(event_ids):
#         raise HTTPException(status_code=400, detail="Sélections dupliquées.")
#     events = db.query(Event).filter(Event.id.in_(event_ids)).all()
#     if len(events) != len(event_ids):
#         raise HTTPException(status_code=400, detail="Un ou plusieurs événements sont introuvables.")
#     sent_by_event = {s.event_id: s for s in payload.selections}
#     now = datetime.now(timezone.utc)
#     started = [e.id for e in events if e.match and e.match.kickoff_at < now]
#     if started:
#         raise HTTPException(status_code=400, detail=f"Matchs déjà commencés : {started}")
#     preds_by_event = {
#         p.event_id: float(p.probability)
#         for p in db.query(Prediction).filter(Prediction.event_id.in_(event_ids)).all()
#     }
#     resolved = []
#     for e in events:
#         sent = sent_by_event[e.id]
#         db_odds = float(e.odds_value) if e.odds_value is not None else None
#         user_odds = float(sent.odds_value) if sent.odds_value is not None else db_odds
#         if user_odds is None:
#             raise HTTPException(status_code=400, detail=f"Cote manquante pour l'événement {e.id}")
#         if db_odds and (user_odds / db_odds > 1.20 or db_odds / user_odds > 1.20):
#             raise HTTPException(
#                 status_code=409,
#                 detail=f"Cote pour l'événement {e.id} trop différente de la cote actuelle.",
#             )
#         resolved.append({
#             "event": e,
#             "odds": user_odds,
#             "proba": sent.probability if sent.probability is not None else preds_by_event.get(e.id),
#             "event_type": sent.event_type or e.type,
#             "event_label": sent.event_label or e.label,
#         })
#     odds_values = [r["odds"] for r in resolved]
#     total_odds = prod(odds_values)
#     bet = Bet(
#         user_id=user_id, stake=None,
#         total_odds=round(total_odds, 3),
#         potential_gain=None, status="en_cours",
#     )
#     db.add(bet)
#     db.flush()
#     for r in resolved:
#         db.add(BetSelection(
#             bet_id=bet.id, event_id=r["event"].id,
#             event_type=r["event_type"], event_label=r["event_label"],
#             odds_value=r["odds"], probability_at_bet=r["proba"],
#         ))
#     db.commit()
#     return {
#         "bet_id": str(bet.id),
#         "total_odds": float(bet.total_odds),
#         "selections_count": len(events),
#     }
#
#
# @router.get("/history")
# def bet_history(user_id: str, db: Session = Depends(get_db)):
#     try:
#         parsed = uuid_lib.UUID(user_id)
#     except ValueError:
#         raise HTTPException(status_code=400, detail="user_id invalide.")
#     bets = db.query(Bet).filter(Bet.user_id == parsed).order_by(Bet.created_at.desc()).all()
#     total = len(bets)
#     won = len([b for b in bets if b.status == "gagne"])
#     lost = len([b for b in bets if b.status == "perdu"])
#     return {
#         "bets": [
#             {
#                 "id": str(b.id),
#                 "total_odds": float(b.total_odds),
#                 "status": b.status,
#                 "created_at": b.created_at.isoformat(),
#                 "selections": [
#                     {
#                         "match": f"{s.event.match.home_team.name} vs {s.event.match.away_team.name}" if s.event and s.event.match else None,
#                         "event": s.event_label or (s.event.label if s.event else None),
#                         "event_type": s.event_type or (s.event.type if s.event else None),
#                         "odds": float(s.odds_value),
#                         "probability_at_bet": float(s.probability_at_bet) if s.probability_at_bet is not None else None,
#                         "result": s.result,
#                     }
#                     for s in b.selections
#                 ],
#             }
#             for b in bets
#         ],
#         "stats": {
#             "total_bets": total, "won": won, "lost": lost,
#             "en_cours": total - won - lost,
#             "success_rate": round((won / (won + lost) * 100), 1) if (won + lost) > 0 else 0,
#         },
#     }
