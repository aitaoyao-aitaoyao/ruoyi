from datetime import date, datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db import get_db

router = APIRouter(prefix="/finance/transactions", tags=["finance-transactions"])


@router.get("/")
def list_transactions(
    type: str = Query(None),
    person_id: int = Query(None),
    date_from: date = Query(None),
    date_to: date = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    queries = []
    params = {}

    if not type or type == "loan":
        q = "SELECT id, 'loan' as type, person_id, amount, created_at FROM loans WHERE 1=1"
        if person_id:
            q += " AND person_id = :person_id"
            params["person_id"] = person_id
        if date_from:
            q += " AND created_at >= :date_from"
            params["date_from"] = date_from
        if date_to:
            q += " AND created_at <= :date_to"
            params["date_to"] = date_to
        queries.append(q)

    if not type or type == "pos":
        q = "SELECT id, 'pos' as type, person_id, amount, created_at FROM pos_swipes WHERE 1=1"
        if person_id:
            q += " AND person_id = :person_id"
        if date_from:
            q += " AND created_at >= :date_from"
        if date_to:
            q += " AND created_at <= :date_to"
        queries.append(q)

    if not type or type == "installment":
        q = "SELECT id, 'installment' as type, person_id, amount, created_at FROM card_installments WHERE 1=1"
        if person_id:
            q += " AND person_id = :person_id"
        if date_from:
            q += " AND created_at >= :date_from"
        if date_to:
            q += " AND created_at <= :date_to"
        queries.append(q)

    if not type or type == "card_trans":
        q = "SELECT id, 'card_trans' as type, person_id, amount, created_at FROM credit_card_transactions WHERE 1=1"
        if person_id:
            q += " AND person_id = :person_id"
        if date_from:
            q += " AND created_at >= :date_from"
        if date_to:
            q += " AND created_at <= :date_to"
        queries.append(q)

    if not type or type == "income":
        q = "SELECT id, 'income' as type, person_id, amount, created_at FROM incomes WHERE 1=1"
        if person_id:
            q += " AND person_id = :person_id"
        if date_from:
            q += " AND created_at >= :date_from"
        if date_to:
            q += " AND created_at <= :date_to"
        queries.append(q)

    if not type or type == "expense":
        q = "SELECT id, 'expense' as type, person_id, amount, created_at FROM expenses WHERE 1=1"
        if person_id:
            q += " AND person_id = :person_id"
        if date_from:
            q += " AND created_at >= :date_from"
        if date_to:
            q += " AND created_at <= :date_to"
        queries.append(q)

    if not queries:
        return {"items": [], "total": 0}

    union_sql = " UNION ALL ".join(queries)
    count_sql = f"SELECT COUNT(*) FROM ({union_sql})"
    total = db.execute(text(count_sql), params).scalar()

    offset = (page - 1) * page_size
    items = db.execute(
        text(f"{union_sql} ORDER BY created_at DESC LIMIT :limit OFFSET :offset"),
        {**params, "limit": page_size, "offset": offset},
    ).fetchall()

    return {
        "items": [{"id": r[0], "type": r[1], "person_id": r[2], "amount": r[3], "created_at": str(r[4])} for r in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
