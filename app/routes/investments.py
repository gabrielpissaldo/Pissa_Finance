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


class InvestmentContributionCreate(BaseModel):
    amount: float
    contribution_date: str

    # only for market investment
    quantity: float | None = None

class InvestmentContributionUpdate(BaseModel):
    amount: float
    contribution_date: str

    # only for market investment
    quantity: float | None = None
    
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

        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid investment type"
            )

        transaction_cursor = connection.execute("""
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
            f"Aporte inicial em {investment.name}",
            investment.amount_invested,
            "investment",
            investment.name,
            investment_id,
            investment.started_at,
            created_at
        ))

        transaction_id = transaction_cursor.lastrowid

        connection.execute("""
            INSERT INTO investment_movements (
                investment_id,
                transaction_id,
                movement_type,
                amount,
                quantity,
                movement_date,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            investment_id,
            transaction_id,
            "initial_contribution",
            investment.amount_invested,
            investment.quantity,
            investment.started_at,
            created_at
        ))

        connection.commit()

        return {
            "id": investment_id,
            "message": "Investment created successfully"
        }

    except HTTPException:
        connection.rollback()
        raise

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


@router.post("/{investment_id}/contributions")
def create_contribution(
    investment_id: int,
    contribution: InvestmentContributionCreate
):
    connection = get_connection()

    try:
        investment = connection.execute("""
            SELECT
                id,
                name,
                investment_type,
                amount_invested
            FROM investments
            WHERE id = ?
        """, (investment_id,)).fetchone()

        if investment is None:
            raise HTTPException(
                status_code=404,
                detail="Investment not found"
            )

        if contribution.amount <= 0:
            raise HTTPException(
                status_code=400,
                detail="Contribution amount must be greater than zero"
            )

        new_amount = (
            investment["amount_invested"]
            + contribution.amount
        )

        connection.execute("""
            UPDATE investments
            SET amount_invested = ?
            WHERE id = ?
        """, (
            new_amount,
            investment_id
        ))

        if investment["investment_type"] == "market_investment":

            if (
                contribution.quantity is None
                or contribution.quantity <= 0
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Quantity is required for market investments"
                )

            details = connection.execute("""
                SELECT
                    quantity,
                    average_price
                FROM market_investment_details
                WHERE investment_id = ?
            """, (investment_id,)).fetchone()

            if details is None:
                raise HTTPException(
                    status_code=404,
                    detail="Market investment details not found"
                )

            current_quantity = details["quantity"] or 0

            new_quantity = (
                current_quantity
                + contribution.quantity
            )

            new_average_price = (
                new_amount / new_quantity
            )

            connection.execute("""
                UPDATE market_investment_details
                SET
                    quantity = ?,
                    average_price = ?
                WHERE investment_id = ?
            """, (
                new_quantity,
                new_average_price,
                investment_id
            ))

        created_at = datetime.now(
            ZoneInfo("America/Sao_Paulo")
        ).isoformat()

        transaction_cursor = connection.execute("""
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
            f"Aporte em {investment['name']}",
            contribution.amount,
            "investment",
            investment["name"],
            investment_id,
            contribution.contribution_date,
            created_at
        ))

        transaction_id = transaction_cursor.lastrowid

        movement_cursor = connection.execute("""
            INSERT INTO investment_movements (
                investment_id,
                transaction_id,
                movement_type,
                amount,
                quantity,
                movement_date,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            investment_id,
            transaction_id,
            "contribution",
            contribution.amount,
            contribution.quantity,
            contribution.contribution_date,
            created_at
        ))

        connection.commit()

        return {
            "message": "Contribution created successfully",
            "investment_id": investment_id,
            "movement_id": movement_cursor.lastrowid,
            "amount_invested": new_amount
        }

    except HTTPException:
        connection.rollback()
        raise

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


@router.put("/{investment_id}/contributions/{movement_id}")
def update_contribution(
    investment_id: int,
    movement_id: int,
    contribution: InvestmentContributionUpdate
):
    connection = get_connection()

    try:
        if contribution.amount <= 0:
            raise HTTPException(
                status_code=400,
                detail="Contribution amount must be greater than zero"
            )

        investment = connection.execute("""
            SELECT
                id,
                name,
                investment_type,
                amount_invested
            FROM investments
            WHERE id = ?
        """, (investment_id,)).fetchone()

        if investment is None:
            raise HTTPException(
                status_code=404,
                detail="Investment not found"
            )

        movement = connection.execute("""
            SELECT
                id,
                transaction_id,
                amount,
                quantity,
                movement_date
            FROM investment_movements
            WHERE id = ?
              AND investment_id = ?
              AND movement_type = 'contribution'
        """, (
            movement_id,
            investment_id
        )).fetchone()

        if movement is None:
            raise HTTPException(
                status_code=404,
                detail="Contribution not found"
            )

        old_amount = movement["amount"]

        new_total_amount = (
            investment["amount_invested"]
            - old_amount
            + contribution.amount
        )

        connection.execute("""
            UPDATE investments
            SET amount_invested = ?
            WHERE id = ?
        """, (
            new_total_amount,
            investment_id
        ))

        new_quantity = None

        if investment["investment_type"] == "market_investment":

            if (
                contribution.quantity is None
                or contribution.quantity <= 0
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Quantity is required for market investments"
                )

            details = connection.execute("""
                SELECT
                    quantity
                FROM market_investment_details
                WHERE investment_id = ?
            """, (investment_id,)).fetchone()

            if details is None:
                raise HTTPException(
                    status_code=404,
                    detail="Market investment details not found"
                )

            old_quantity = movement["quantity"] or 0
            current_total_quantity = details["quantity"] or 0

            new_quantity = (
                current_total_quantity
                - old_quantity
                + contribution.quantity
            )

            if new_quantity <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="Resulting quantity must be greater than zero"
                )

            new_average_price = (
                new_total_amount / new_quantity
            )

            connection.execute("""
                UPDATE market_investment_details
                SET
                    quantity = ?,
                    average_price = ?
                WHERE investment_id = ?
            """, (
                new_quantity,
                new_average_price,
                investment_id
            ))

        connection.execute("""
            UPDATE investment_movements
            SET
                amount = ?,
                quantity = ?,
                movement_date = ?
            WHERE id = ?
        """, (
            contribution.amount,
            contribution.quantity,
            contribution.contribution_date,
            movement_id
        ))

        connection.execute("""
            UPDATE transactions
            SET
                description = ?,
                amount = ?,
                category = ?,
                transaction_date = ?
            WHERE id = ?
        """, (
            f"Aporte em {investment['name']}",
            contribution.amount,
            investment["name"],
            contribution.contribution_date,
            movement["transaction_id"]
        ))

        connection.commit()

        return {
            "message": "Contribution updated successfully",
            "investment_id": investment_id,
            "movement_id": movement_id,
            "amount_invested": new_total_amount
        }

    except HTTPException:
        connection.rollback()
        raise

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
        
@router.delete("/{investment_id}/contributions/{movement_id}")
def delete_contribution(
    investment_id: int,
    movement_id: int
):
    connection = get_connection()

    try:
        investment = connection.execute("""
            SELECT
                id,
                investment_type,
                amount_invested
            FROM investments
            WHERE id = ?
        """, (investment_id,)).fetchone()

        if investment is None:
            raise HTTPException(
                status_code=404,
                detail="Investment not found"
            )

        movement = connection.execute("""
            SELECT
                id,
                transaction_id,
                amount,
                quantity
            FROM investment_movements
            WHERE id = ?
              AND investment_id = ?
              AND movement_type = 'contribution'
        """, (
            movement_id,
            investment_id
        )).fetchone()

        if movement is None:
            raise HTTPException(
                status_code=404,
                detail="Contribution not found"
            )

        new_total_amount = (
            investment["amount_invested"]
            - movement["amount"]
        )

        if new_total_amount < 0:
            raise HTTPException(
                status_code=400,
                detail="Resulting investment amount cannot be negative"
            )

        connection.execute("""
            UPDATE investments
            SET amount_invested = ?
            WHERE id = ?
        """, (
            new_total_amount,
            investment_id
        ))

        if investment["investment_type"] == "market_investment":

            details = connection.execute("""
                SELECT
                    quantity
                FROM market_investment_details
                WHERE investment_id = ?
            """, (investment_id,)).fetchone()

            if details is None:
                raise HTTPException(
                    status_code=404,
                    detail="Market investment details not found"
                )

            current_quantity = details["quantity"] or 0
            movement_quantity = movement["quantity"] or 0

            new_quantity = (
                current_quantity
                - movement_quantity
            )

            if new_quantity < 0:
                raise HTTPException(
                    status_code=400,
                    detail="Resulting quantity cannot be negative"
                )

            if new_quantity > 0:
                new_average_price = (
                    new_total_amount / new_quantity
                )
            else:
                new_average_price = 0

            connection.execute("""
                UPDATE market_investment_details
                SET
                    quantity = ?,
                    average_price = ?
                WHERE investment_id = ?
            """, (
                new_quantity,
                new_average_price,
                investment_id
            ))

        if movement["transaction_id"] is not None:
            connection.execute("""
                DELETE FROM transactions
                WHERE id = ?
            """, (movement["transaction_id"],))

        connection.execute("""
            DELETE FROM investment_movements
            WHERE id = ?
        """, (movement_id,))

        connection.commit()

        return {
            "message": "Contribution deleted successfully",
            "investment_id": investment_id,
            "movement_id": movement_id,
            "amount_invested": new_total_amount
        }

    except HTTPException:
        connection.rollback()
        raise

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
                
@router.get("/")
def list_investments():
    connection = get_connection()

    try:
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
                dict(details)
                if details
                else None
            )

            result.append(investment)

        return result

    finally:
        connection.close()


@router.put("/{investment_id}")
def update_investment(
    investment_id: int,
    investment: InvestmentUpdate
):
    connection = get_connection()

    try:
        current = connection.execute("""
            SELECT
                id,
                investment_type
            FROM investments
            WHERE id = ?
        """, (investment_id,)).fetchone()

        if current is None:
            raise HTTPException(
                status_code=404,
                detail="Investment not found"
            )

        contributions = connection.execute("""
            SELECT
                COALESCE(SUM(amount), 0) AS total_amount,
                COALESCE(SUM(quantity), 0) AS total_quantity
            FROM investment_movements
            WHERE investment_id = ?
              AND movement_type = 'contribution'
        """, (investment_id,)).fetchone()

        contribution_amount = contributions["total_amount"] or 0
        contribution_quantity = contributions["total_quantity"] or 0

        initial_amount = (
            investment.amount_invested
            - contribution_amount
        )

        if initial_amount < 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Investment amount cannot be lower than "
                    "the sum of later contributions"
                )
            )

        initial_quantity = None

        if investment.investment_type == "market_investment":
            total_quantity = investment.quantity or 0

            initial_quantity = (
                total_quantity
                - contribution_quantity
            )

            if initial_quantity < 0:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Investment quantity cannot be lower than "
                        "the sum of later contribution quantities"
                    )
                )

        connection.execute("""
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

        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid investment type"
            )

        initial_movement = connection.execute("""
            SELECT
                id,
                transaction_id
            FROM investment_movements
            WHERE investment_id = ?
              AND movement_type = 'initial_contribution'
            LIMIT 1
        """, (investment_id,)).fetchone()

        if initial_movement is not None:

            connection.execute("""
                UPDATE investment_movements
                SET
                    amount = ?,
                    quantity = ?,
                    movement_date = ?
                WHERE id = ?
            """, (
                initial_amount,
                initial_quantity,
                investment.started_at,
                initial_movement["id"]
            ))

            connection.execute("""
                UPDATE transactions
                SET
                    description = ?,
                    amount = ?,
                    category = ?,
                    transaction_date = ?
                WHERE id = ?
            """, (
                f"Aporte inicial em {investment.name}",
                initial_amount,
                investment.name,
                investment.started_at,
                initial_movement["transaction_id"]
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