from fastapi import APIRouter

from app.database import get_connection


router = APIRouter(
    prefix="/api/dashboard",
    tags=["dashboard"]
)


@router.get("/")
def get_dashboard():
    connection = get_connection()

    transactions = connection.execute("""
        SELECT *
        FROM transactions
    """).fetchall()

    connection.close()

    income = 0
    expenses = 0
    invested = 0

    for transaction in transactions:
        if transaction["type"] == "income":
            income += transaction["amount"]

        elif transaction["type"] == "expense":
            expenses += transaction["amount"]

        elif transaction["type"] == "investment":
            invested += transaction["amount"]

    balance = income - expenses - invested

    return {
        "income": income,
        "expenses": expenses,
        "invested": invested,
        "balance": balance
    }