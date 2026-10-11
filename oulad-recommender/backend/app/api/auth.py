from fastapi import APIRouter, Depends, HTTPException
from app.core.security import create_token, current_user, verify_password
from app.db.mongodb import get_db
from app.models.schemas import LoginRequest

router = APIRouter(prefix="/auth", tags=["auth"])
PUBLIC = {"_id": 0, "password_hash": 0}


@router.post("/login")
def login(body: LoginRequest):
    db = get_db()
    user = db.users.find_one({"email": body.email.lower(), "is_active": True})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Incorrect email or password")
    safe = {k: v for k, v in user.items() if k not in ("_id", "password_hash")}
    return {"access_token": create_token(user), "token_type": "bearer", "user": safe}


@router.post("/logout")
def logout(_: dict = Depends(current_user)):
    # JWTs are stateless: the client discards the token. Tokens expire on their own.
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(current_user)):
    out = {k: v for k, v in user.items() if k not in ("_id", "password_hash")}
    if user.get("student_id") is not None:
        out["profile"] = get_db().students.find_one(
            {"id_student": user["student_id"]}, {"_id": 0}, sort=[("code_presentation", -1)])
    return out
