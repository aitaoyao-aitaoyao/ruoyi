from datetime import date, datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db import get_db
from app.auth import get_current_user
from app.models import User

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
    user: User = Depends(get_current_user),
):
    queries = []
    params = {}

    if not type or type == "loan":
        q = "SELECT id, 'loan' as type, person_id, amount, start_date as txn_date FROM loans WHERE 1=1"
        if person_id:
            q += " AND person_id = :person_id"
        if date_from:
            q += " AND start_date >= :date_from"
            params["date_from"] = date_from
        if date_to:
            q += " AND start_date <= :date_to"
            params["date_to"] = date_to
        queries.append(q)

    if not type or type == "pos":
        q = "SELECT id, 'pos' as type, person_id, amount, swipe_date as txn_date FROM pos_swipes WHERE 1=1"
        if person_id:
            q += " AND person_id = :person_id"
        if date_from:
            q += " AND swipe_date >= :date_from"
        if date_to:
            q += " AND swipe_date <= :date_to"
        queries.append(q)

    if not type or type == "installment":
        q = "SELECT id, 'installment' as type, person_id, amount, start_date as txn_date FROM card_installments WHERE 1=1"
        if person_id:
            q += " AND person_id = :person_id"
        if date_from:
            q += " AND start_date >= :date_from"
        if date_to:
            q += " AND start_date <= :date_to"
        queries.append(q)

    if not type or type == "card_trans":
        q = "SELECT id, 'card_trans' as type, person_id, amount, trans_date as txn_date FROM credit_card_transactions WHERE 1=1"
        if person_id:
            q += " AND person_id = :person_id"
        if date_from:
            q += " AND trans_date >= :date_from"
        if date_to:
            q += " AND trans_date <= :date_to"
        queries.append(q)

    if not type or type == "income":
        q = "SELECT id, 'income' as type, person_id, amount, created_at as txn_date FROM incomes WHERE 1=1"
        if person_id:
            q += " AND person_id = :person_id"
        if date_from:
            q += " AND created_at >= :date_from"
        if date_to:
            q += " AND created_at <= :date_to"
        queries.append(q)

    if not type or type == "expense":
        q = "SELECT id, 'expense' as type, person_id, amount, expense_date as txn_date FROM expenses WHERE 1=1"
        if person_id:
            q += " AND person_id = :person_id"
        if date_from:
            q += " AND expense_date >= :date_from"
        if date_to:
            q += " AND expense_date <= :date_to"
        queries.append(q)

    if not queries:
        return {"items": [], "total": 0}

    union_sql = " UNION ALL ".join(queries)
    count_sql = f"SELECT COUNT(*) FROM ({union_sql})"
    total = db.execute(text(count_sql), params).scalar()

    offset = (page - 1) * page_size
    items = db.execute(
        text(f"{union_sql} ORDER BY txn_date DESC LIMIT :limit OFFSET :offset"),
        {**params, "limit": page_size, "offset": offset},
    ).fetchall()

    return {
        "items": [{"id": r[0], "type": r[1], "person_id": r[2], "amount": r[3], "txn_date": str(r[4])} for r in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
