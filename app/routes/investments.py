from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from datetime import date, datetime
from zoneinfo import ZoneInfo
from math import isclose, isfinite

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


class InvestmentWithdrawalCreate(BaseModel):
    amount: float
    withdrawal_date: str
    quantity: float | None = None
    principal_amount: float | None = None


def _parse_movement_date(value: str, *, existing: bool = False) -> date:
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() == value:
            return parsed
    except (TypeError, ValueError):
        pass
    if existing:
        raise HTTPException(status_code=409, detail="Existing investment movement has an invalid date")
    raise HTTPException(status_code=400, detail="Movement date must be YYYY-MM-DD")


def _latest_movement_date(connection, investment_id: int, movement_type: str | None = None):
    query = "SELECT movement_date FROM investment_movements WHERE investment_id = ?"
    parameters = (investment_id,)
    if movement_type is not None:
        query += " AND movement_type = ?"
        parameters = (investment_id, movement_type)
    dates = [
        _parse_movement_date(row["movement_date"], existing=True)
        for row in connection.execute(query, parameters)
    ]
    return max(dates, default=None)


def _normalize_idempotency_key(value: str | None) -> str | None:
    if value is None:
        return None
    key = value.strip()
    if not key or len(key) > 128:
        raise HTTPException(status_code=400, detail="Idempotency-Key must contain 1 to 128 characters")
    return key


def _idempotent_replay(
    connection,
    *,
    investment_id: int,
    movement_type: str,
    amount: float,
    movement_date: str,
    quantity: float | None,
    principal_amount: float | None,
    compare_principal: bool,
    idempotency_key: str | None,
    payload_fields_match: bool = True,
):
    if idempotency_key is None:
        return None

    existing = connection.execute("""
        SELECT id, investment_id, movement_type, amount, principal_amount,
               quantity, movement_date
        FROM investment_movements
        WHERE idempotency_key = ?
    """, (idempotency_key,)).fetchone()
    if existing is None:
        return None

    matches = (
        existing["investment_id"] == investment_id
        and existing["movement_type"] == movement_type
        and existing["amount"] == amount
        and existing["movement_date"] == movement_date
        and existing["quantity"] == quantity
        and (not compare_principal or existing["principal_amount"] == principal_amount)
        and payload_fields_match
    )
    if not matches:
        raise HTTPException(
            status_code=409,
            detail="Idempotency-Key was already used with a different operation payload"
        )

    investment = connection.execute("""
        SELECT amount_invested, status FROM investments WHERE id = ?
    """, (investment_id,)).fetchone()
    if investment is None:
        raise HTTPException(status_code=404, detail="Investment not found")

    result = {
        "message": "Operation already recorded",
        "investment_id": investment_id,
        "movement_id": existing["id"],
        "amount_invested": investment["amount_invested"],
        "idempotent_replay": True
    }
    if movement_type == "withdrawal":
        result["status"] = investment["status"]
    return result
    
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


@router.post("/{investment_id}/withdrawals")
def create_withdrawal(
    investment_id: int,
    withdrawal: InvestmentWithdrawalCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")
):
    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        idempotency_key = _normalize_idempotency_key(idempotency_key)
        investment = connection.execute("""
            SELECT id, name, investment_type, amount_invested, status
            FROM investments WHERE id = ?
        """, (investment_id,)).fetchone()
        if investment is None:
            raise HTTPException(status_code=404, detail="Investment not found")
        is_market = investment["investment_type"] == "market_investment"
        replay = _idempotent_replay(
            connection,
            investment_id=investment_id,
            movement_type="withdrawal",
            amount=withdrawal.amount,
            movement_date=withdrawal.withdrawal_date,
            quantity=withdrawal.quantity,
            principal_amount=withdrawal.principal_amount,
            compare_principal=not is_market,
            payload_fields_match=(not is_market or withdrawal.principal_amount is None),
            idempotency_key=idempotency_key
        )
        if replay is not None:
            connection.commit()
            return replay
        if is_market and withdrawal.principal_amount is not None:
            raise HTTPException(status_code=400, detail="Principal amount is calculated for market investments")
        if not is_market and withdrawal.quantity is not None:
            raise HTTPException(status_code=400, detail="Quantity is only valid for market investments")
        if investment["status"] != "active":
            raise HTTPException(status_code=409, detail="Investment is closed")
        withdrawal_date = _parse_movement_date(withdrawal.withdrawal_date)
        latest_date = _latest_movement_date(connection, investment_id)
        if latest_date is not None and withdrawal_date < latest_date:
            raise HTTPException(status_code=400, detail="Withdrawal cannot precede existing movements")
        if not isfinite(withdrawal.amount) or withdrawal.amount <= 0:
            raise HTTPException(status_code=400, detail="Withdrawal amount must be greater than zero")

        current_principal = investment["amount_invested"]
        if investment["investment_type"] == "market_investment":
            if (withdrawal.quantity is None or not isfinite(withdrawal.quantity)
                    or withdrawal.quantity <= 0):
                raise HTTPException(status_code=400, detail="Quantity is required for market withdrawals")
            details = connection.execute("""
                SELECT quantity, average_price FROM market_investment_details
                WHERE investment_id = ?
            """, (investment_id,)).fetchone()
            if details is None:
                raise HTTPException(status_code=404, detail="Market investment details not found")
            current_quantity = details["quantity"] or 0
            average_price = details["average_price"] or 0
            if (not isfinite(current_principal) or not isfinite(current_quantity)
                    or not isfinite(average_price) or current_quantity <= 0
                    or average_price <= 0 or not isclose(
                        current_principal, average_price * current_quantity,
                        rel_tol=1e-9, abs_tol=0
                    )):
                raise HTTPException(status_code=409, detail="Market position has an inconsistent cost basis")
            if withdrawal.quantity > current_quantity:
                raise HTTPException(status_code=400, detail="Quantity exceeds current position")
            principal = average_price * withdrawal.quantity
            if not isfinite(principal) or principal <= 0 or principal > current_principal:
                raise HTTPException(status_code=400, detail="Invalid principal for current position")
            closed = withdrawal.quantity == current_quantity
            remaining_quantity = 0 if closed else current_quantity - withdrawal.quantity
            remaining_principal = 0 if closed else current_principal - principal
            if not closed and (
                remaining_quantity <= 0 or remaining_quantity >= current_quantity
                or remaining_principal <= 0 or remaining_principal >= current_principal
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Withdrawal is too small to reduce the market position"
                )
            connection.execute("""
                UPDATE market_investment_details
                SET quantity = ?, average_price = ?
                WHERE investment_id = ?
            """, (remaining_quantity, 0 if closed else average_price, investment_id))
        elif investment["investment_type"] == "fixed_income":
            principal = withdrawal.principal_amount
            if (principal is None or not isfinite(principal) or principal <= 0
                    or principal > current_principal):
                raise HTTPException(status_code=400, detail="Principal must be positive and cannot exceed amount invested")
            remaining_principal = current_principal - principal
            if remaining_principal == current_principal:
                raise HTTPException(
                    status_code=400,
                    detail="Principal is too small to reduce the position"
                )
            closed = remaining_principal == 0
        else:
            raise HTTPException(status_code=400, detail="Invalid investment type")

        connection.execute("""
            UPDATE investments
            SET amount_invested = ?, status = ?, closed_at = ?
            WHERE id = ?
        """, (remaining_principal, "closed" if closed else "active",
              withdrawal.withdrawal_date if closed else None, investment_id))
        created_at = datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat()
        transaction_cursor = connection.execute("""
            INSERT INTO transactions
                (description, amount, type, category, investment_id, transaction_date, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (f"Resgate de {investment['name']}", withdrawal.amount,
              "investment_withdrawal", investment["name"], investment_id,
              withdrawal.withdrawal_date, created_at))
        movement_cursor = connection.execute("""
            INSERT INTO investment_movements
                (investment_id, transaction_id, movement_type, amount,
                 principal_amount, quantity, idempotency_key, movement_date, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (investment_id, transaction_cursor.lastrowid, "withdrawal",
              withdrawal.amount, principal, withdrawal.quantity, idempotency_key,
              withdrawal.withdrawal_date, created_at))
        connection.commit()
        return {
            "message": "Withdrawal created successfully",
            "investment_id": investment_id,
            "movement_id": movement_cursor.lastrowid,
            "amount_invested": remaining_principal,
            "status": "closed" if closed else "active"
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@router.post("/{investment_id}/contributions")
def create_contribution(
    investment_id: int,
    contribution: InvestmentContributionCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")
):
    connection = get_connection()

    try:
        connection.execute("BEGIN IMMEDIATE")
        idempotency_key = _normalize_idempotency_key(idempotency_key)
        investment = connection.execute("""
            SELECT
                id,
                name,
                investment_type,
                amount_invested,
                status
            FROM investments
            WHERE id = ?
        """, (investment_id,)).fetchone()

        if investment is None:
            raise HTTPException(
                status_code=404,
                detail="Investment not found"
            )

        replay = _idempotent_replay(
            connection,
            investment_id=investment_id,
            movement_type="contribution",
            amount=contribution.amount,
            movement_date=contribution.contribution_date,
            quantity=contribution.quantity,
            principal_amount=None,
            compare_principal=False,
            idempotency_key=idempotency_key
        )
        if replay is not None:
            connection.commit()
            return replay

        if investment["status"] != "active":
            raise HTTPException(status_code=409, detail="Investment is closed")

        contribution_date = _parse_movement_date(contribution.contribution_date)
        latest_withdrawal = _latest_movement_date(connection, investment_id, "withdrawal")
        if latest_withdrawal is not None and contribution_date < latest_withdrawal:
            raise HTTPException(status_code=400, detail="Contribution cannot precede a withdrawal")

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
                idempotency_key,
                quantity,
                movement_date,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            investment_id,
            transaction_id,
            "contribution",
            contribution.amount,
            idempotency_key,
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
        connection.execute("BEGIN IMMEDIATE")
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

        if connection.execute("""
            SELECT 1 FROM investment_movements
            WHERE investment_id = ? AND movement_type = 'withdrawal'
            LIMIT 1
        """, (investment_id,)).fetchone():
            raise HTTPException(
                status_code=409,
                detail="Contributions cannot be edited after a withdrawal"
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
        connection.execute("BEGIN IMMEDIATE")
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

        if connection.execute("""
            SELECT 1 FROM investment_movements
            WHERE investment_id = ? AND movement_type = 'withdrawal'
            LIMIT 1
        """, (investment_id,)).fetchone():
            raise HTTPException(
                status_code=409,
                detail="Contributions cannot be deleted after a withdrawal"
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
        connection.execute("BEGIN IMMEDIATE")
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

        if connection.execute("""
            SELECT 1 FROM investment_movements
            WHERE investment_id = ? AND movement_type = 'withdrawal'
            LIMIT 1
        """, (investment_id,)).fetchone():
            raise HTTPException(
                status_code=409,
                detail="Investment cannot be edited after a withdrawal"
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