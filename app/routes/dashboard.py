from fastapi import APIRouter
from datetime import date, datetime
from zoneinfo import ZoneInfo

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
    category_totals = {}
    current_date = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    month_names = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    months = []

    for offset in range(5, -1, -1):
        month = current_date.month - offset
        year = current_date.year
        if month <= 0:
            month += 12
            year -= 1
        months.append((year, month))

    monthly_totals = {month: 0 for month in months}

    for transaction in transactions:
        if transaction["type"] == "income":
            income += transaction["amount"]
            monthly_value = transaction["amount"]

        elif transaction["type"] == "expense":
            expenses += transaction["amount"]
            category = (transaction["category"] or "").strip() or "Sem categoria"
            category_totals[category] = category_totals.get(category, 0) + transaction["amount"]
            monthly_value = -transaction["amount"]

        elif transaction["type"] == "investment":
            invested += transaction["amount"]
            monthly_value = -transaction["amount"]

        else:
            continue

        try:
            transaction_month = date.fromisoformat(transaction["transaction_date"])
        except (TypeError, ValueError):
            continue

        month_key = (transaction_month.year, transaction_month.month)
        if month_key in monthly_totals:
            monthly_totals[month_key] += monthly_value

    balance = income - expenses - invested
    categories = [
        {"name": name, "value": value}
        for name, value in sorted(
            category_totals.items(), key=lambda item: item[1], reverse=True
        )
    ]
    monthly = [
        {"month": month_names[month - 1], "value": monthly_totals[(year, month)]}
        for year, month in months
    ]

    return {
        "income": income,
        "expenses": expenses,
        "invested": invested,
        "balance": balance,
        "categories": categories,
        "monthly": monthly
    }
