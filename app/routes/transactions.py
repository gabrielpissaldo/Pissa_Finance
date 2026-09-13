from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import get_connection

from datetime import datetime
from zoneinfo import ZoneInfo


class TransactionCreate(BaseModel):
    description: str
    amount: float
    type: str
    category: str | None = None
    transaction_date: str


class TransactionUpdate(BaseModel):
    description: str 
    amount: float 
    type: str 
    category: str | None = None
    transaction_date: str


router = APIRouter(
    prefix="/api/transactions",
    tags=["transactions"]
)


@router.post("/")
def create_transaction(transaction: TransactionCreate):
    connection = get_connection()
    
    created_at = datetime.now(
        ZoneInfo("America/Sao_Paulo")
        ).isoformat()

    cursor = connection.execute("""
    INSERT INTO transactions (
        description,
        amount,
        type,
        category,
        transaction_date,
        created_at
    )
    VALUES (?, ?, ?, ?, ?, ?)
""", (
    transaction.description,
    transaction.amount,
    transaction.type,
    transaction.category,
    transaction.transaction_date,
    created_at
))

    connection.commit()

    transaction_id = cursor.lastrowid

    connection.close()

    return {
        "id": transaction_id,
        "message": "Transaction created"
    }


@router.get("/")
def list_transactions():
    connection = get_connection()

    rows = connection.execute("""
        SELECT *
        FROM transactions
        ORDER BY id DESC
    """).fetchall()

    connection.close()

    return [dict(row) for row in rows]


@router.delete("/{transaction_id}")
def delete_transaction(transaction_id: int):
    connection = get_connection()

    cursor = connection.execute("""
        DELETE FROM transactions
        WHERE id = ?
    """, (transaction_id,))

    connection.commit()

    if cursor.rowcount == 0:
        connection.close()
        raise HTTPException(
            status_code=404,
            detail="Transaction not found"
        )

    connection.close()

    return {
        "message": "Transaction deleted"
    }
    
@router.put("/{transaction_id}")
def update_transaction(
    transaction_id: int,
    transaction: TransactionUpdate
):
    connection = get_connection()

    cursor = connection.execute("""
        UPDATE transactions
        SET
            description = ?,
            amount = ?,
            type = ?,
            category = ?,
            transaction_date = ?
        WHERE id = ?
    """, (
        transaction.description,
        transaction.amount,
        transaction.type,
        transaction.category,
        transaction.transaction_date,
        transaction_id
    ))

    connection.commit()

    if cursor.rowcount == 0:
        connection.close()
        raise HTTPException(
            status_code=404,
            detail="Transaction not found"
        )

    connection.close()

    return {
        "message": "Transaction updated"
    }