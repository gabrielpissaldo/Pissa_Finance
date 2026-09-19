from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from zoneinfo import ZoneInfo

from app.database import get_connection

class InvestmentCreate(BaseModel):
    name: str
    investment_type: str
    amount_invested: float
    started_at: str
    
    # fixed income
    rate_type: str | None = None
    rate_modifier: float | None = None
    fixed_rate: float | None = None
    maturity_date: str | None = None
    
    # market investment
    asset_type: str | None = None
    symbol: str | None = None
    quantity: float | None = None
    average_price: float | None = None
    
class InvestmentUpdate(BaseModel):
    name: str
    investment_type: str
    amount_invested: float
    started_at: str

    # fixed income
    rate_type: str | None = None
    rate_modifier: float | None = None
    fixed_rate: float | None = None
    maturity_date: str | None = None

    # market investment
    asset_type: str | None = None
    symbol: str | None = None
    quantity: float | None = None
    average_price: float | None = None

router = APIRouter(
    prefix="/api/investments",
    tags=["investments"]
)

@router.post("/")
def create_investment(investment: InvestmentCreate):
    connection = get_connection()

    try:
        created_at = datetime.now(
            ZoneInfo("America/Sao_Paulo")
        ).isoformat()

        cursor = connection.execute("""
            INSERT INTO investments (
                name,
                investment_type,
                amount_invested,
                started_at,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            investment.name,
            investment.investment_type,
            investment.amount_invested,
            investment.started_at,
            created_at
        ))

        investment_id = cursor.lastrowid

        if investment.investment_type == "fixed_income":
            connection.execute("""
                INSERT INTO fixed_income_details (
                    investment_id,
                    rate_type,
                    rate_modifier,
                    fixed_rate,
                    maturity_date
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                investment_id,
                investment.rate_type,
                investment.rate_modifier,
                investment.fixed_rate,
                investment.maturity_date
            ))

        elif investment.investment_type == "market_investment":
            connection.execute("""
                INSERT INTO market_investment_details (
                    investment_id,
                    asset_type,
                    symbol,
                    quantity,
                    average_price
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                investment_id,
                investment.asset_type,
                investment.symbol,
                investment.quantity,
                investment.average_price
            ))
        
        connection.execute("""
            INSERT INTO transactions (
                description,
                amount,
                type,
                category,
                investment_id,
                transaction_date,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            f"Aporte em {investment.name}",
            investment.amount_invested,
            "investment",
            investment.name,
            investment_id,
            investment.started_at,
            created_at
        ))

        connection.commit()

        return {
            "id": investment_id,
            "message": "Investment created successfully"
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
    
@router.get("/")
def list_investments():
    connection = get_connection()

    rows = connection.execute("""
        SELECT *
        FROM investments
        ORDER BY id DESC
    """).fetchall()

    result = []

    for row in rows:
        investment = dict(row)

        if investment["investment_type"] == "fixed_income":
            details = connection.execute("""
                SELECT
                    rate_type,
                    rate_modifier,
                    fixed_rate,
                    maturity_date
                FROM fixed_income_details
                WHERE investment_id = ?
            """, (investment["id"],)).fetchone()

        elif investment["investment_type"] == "market_investment":
            details = connection.execute("""
                SELECT
                    asset_type,
                    symbol,
                    quantity,
                    average_price
                FROM market_investment_details
                WHERE investment_id = ?
            """, (investment["id"],)).fetchone()

        else:
            details = None

        investment["details"] = (
            dict(details) if details else None
        )

        result.append(investment)

    connection.close()

    return result

@router.put("/{investment_id}")
def update_investment(
    investment_id: int,
    investment: InvestmentUpdate
):
    connection = get_connection()

    try:
        cursor = connection.execute("""
            UPDATE investments
            SET
                name = ?,
                investment_type = ?,
                amount_invested = ?,
                started_at = ?
            WHERE id = ?
        """, (
            investment.name,
            investment.investment_type,
            investment.amount_invested,
            investment.started_at,
            investment_id
        ))

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Investment not found"
            )

        if investment.investment_type == "fixed_income":

            connection.execute("""
                DELETE FROM market_investment_details
                WHERE investment_id = ?
            """, (investment_id,))

            connection.execute("""
                INSERT INTO fixed_income_details (
                    investment_id,
                    rate_type,
                    rate_modifier,
                    fixed_rate,
                    maturity_date
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(investment_id)
                DO UPDATE SET
                    rate_type = excluded.rate_type,
                    rate_modifier = excluded.rate_modifier,
                    fixed_rate = excluded.fixed_rate,
                    maturity_date = excluded.maturity_date
            """, (
                investment_id,
                investment.rate_type,
                investment.rate_modifier,
                investment.fixed_rate,
                investment.maturity_date
            ))

        elif investment.investment_type == "market_investment":

            connection.execute("""
                DELETE FROM fixed_income_details
                WHERE investment_id = ?
            """, (investment_id,))

            connection.execute("""
                INSERT INTO market_investment_details (
                    investment_id,
                    asset_type,
                    symbol,
                    quantity,
                    average_price
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(investment_id)
                DO UPDATE SET
                    asset_type = excluded.asset_type,
                    symbol = excluded.symbol,
                    quantity = excluded.quantity,
                    average_price = excluded.average_price
            """, (
                investment_id,
                investment.asset_type,
                investment.symbol,
                investment.quantity,
                investment.average_price
            ))
        connection.execute("""
            UPDATE transactions
            SET
                description = ?,
                amount = ?,
                category = ?,
            transaction_date = ?
            WHERE investment_id = ?
            AND type = 'investment'
        """, (
            f"Aporte em {investment.name}",
            investment.amount_invested,
            investment.name,
            investment.started_at,
            investment_id
        ))
        
        connection.commit()

        return {
            "message": "Investment updated successfully"
        }

    except HTTPException:
        connection.rollback()
        raise

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

@router.delete("/{investment_id}")
def delete_investment(investment_id: int):
    connection = get_connection()

    try:
        investment = connection.execute("""
            SELECT id
            FROM investments
            WHERE id = ?
        """, (investment_id,)).fetchone()

        if investment is None:
            raise HTTPException(
                status_code=404,
                detail="Investment not found"
            )

        connection.execute("""
            DELETE FROM transactions
            WHERE investment_id = ?
              AND type = 'investment'
        """, (investment_id,))

        connection.execute("""
            DELETE FROM investments
            WHERE id = ?
        """, (investment_id,))

        connection.commit()

        return {
            "message": "Investment deleted successfully"
        }

    except HTTPException:
        connection.rollback()
        raise

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()