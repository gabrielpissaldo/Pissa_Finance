"""Pure investment valuation calculations; no market/index rates are invented.

A prefixed rate is treated as an effective annual rate, accrued over actual
calendar days on an ACT/365 basis. Movement dates are the cash-flow dates.
"""
from datetime import date
from math import isclose, isfinite


_EXTERNAL_INDEX_RATES = {"cdi", "selic", "ipca"}
_MOVEMENT_TYPES = {"initial_contribution", "contribution", "withdrawal"}
_COST_TOLERANCE = 1e-7


def _number(value):
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if isfinite(parsed) else None


def _iso_date(value):
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None


def _growth_factor(rate_percent, start, end, maturity_date):
    accrual_end = min(end, maturity_date) if maturity_date is not None else end
    days = (accrual_end - start).days
    if days <= 0:
        return 1.0
    base = 1.0 + rate_percent / 100.0
    if not isfinite(base) or base <= 0:
        return None
    try:
        factor = base ** (days / 365.0)
    except (OverflowError, ValueError):
        return None
    return factor if isfinite(factor) else None


def _base_result(as_of, status, realized=None):
    return {
        "current_value": None,
        "unrealized_profit_loss": None,
        "unrealized_return_percent": None,
        "realized_profit_loss": realized,
        "total_profit_loss": None,
        "total_return_percent": None,
        "valuation_status": status,
        "valuation_as_of": as_of.isoformat(),
    }


def _movement_summary(movements, started_at, current_cost):
    normalized = []
    initial_rows = []
    contribution_total = 0.0
    withdrawal_principal_total = 0.0
    realized_total = 0.0
    withdrawals_complete = True

    for movement in movements:
        kind = movement.get("movement_type")
        amount = _number(movement.get("amount"))
        movement_date = _iso_date(movement.get("movement_date"))
        if kind not in _MOVEMENT_TYPES or amount is None or movement_date is None:
            return None
        if movement_date < started_at:
            return None
        if kind in {"initial_contribution", "contribution"}:
            if amount <= 0:
                return None
            if kind == "initial_contribution":
                initial_rows.append((movement_date, amount, movement.get("id", 0)))
            else:
                contribution_total += amount
                normalized.append((movement_date, movement.get("id", 0), kind, amount, None))
        else:
            principal = _number(movement.get("principal_amount"))
            if amount <= 0 or principal is None or principal <= 0:
                withdrawals_complete = False
                continue
            withdrawal_principal_total += principal
            realized_total += amount - principal
            normalized.append((movement_date, movement.get("id", 0), kind, amount, principal))

    if len(initial_rows) > 1:
        return None

    if initial_rows:
        initial_date, initial_amount, initial_id = initial_rows[0]
        if initial_date != started_at:
            return None
    else:
        # Older investments may have no initial movement; reconstruct its basis
        # from the current cost plus the later contributions and withdrawals.
        initial_amount = current_cost + withdrawal_principal_total - contribution_total
        if not isfinite(initial_amount) or initial_amount < -_COST_TOLERANCE:
            return None
        initial_amount = max(0.0, initial_amount)
        initial_date = started_at
        initial_id = -1

    gross_contributions = initial_amount + contribution_total
    ledger_cost = gross_contributions - withdrawal_principal_total
    if ledger_cost < -_COST_TOLERANCE or not isclose(
        ledger_cost, current_cost, rel_tol=1e-9, abs_tol=_COST_TOLERANCE
    ):
        return None

    if initial_amount > 0:
        normalized.append((initial_date, initial_id, "initial_contribution", initial_amount, None))
    normalized.sort(key=lambda event: (event[0], event[1]))
    return {
        "events": normalized,
        "gross_contributions": gross_contributions,
        "realized_profit_loss": realized_total if withdrawals_complete else None,
        "history_complete": withdrawals_complete,
    }


def _closed_result(as_of, movement_summary, current_cost):
    if abs(current_cost) > _COST_TOLERANCE:
        return _base_result(as_of, "inconsistent_history")
    realized = (
        movement_summary["realized_profit_loss"]
        if movement_summary is not None else None
    )
    result = _base_result(as_of, "closed", realized)
    result["current_value"] = 0.0
    result["unrealized_profit_loss"] = 0.0
    if realized is not None and movement_summary is not None:
        result["total_profit_loss"] = realized
        gross = movement_summary["gross_contributions"]
        if gross > 0:
            result["total_return_percent"] = realized / gross * 100.0
    return result


def calculate_investment_valuation(investment, details, movements, as_of):
    """Return valuation fields for an investment row and its movement ledger."""
    if not isinstance(as_of, date):
        as_of = _iso_date(as_of)
    if as_of is None:
        # There is no trustworthy date to use for this result.
        as_of = date.today()

    current_cost = _number(investment.get("amount_invested"))
    started_at = _iso_date(investment.get("started_at"))
    if current_cost is None or current_cost < 0 or started_at is None:
        return _base_result(as_of, "unavailable")

    movement_summary = _movement_summary(movements, started_at, current_cost)
    if movement_summary is not None and any(
        event[0] > as_of for event in movement_summary["events"]
    ):
        return _base_result(as_of, "unavailable")
    if investment.get("status") == "closed":
        return _closed_result(as_of, movement_summary, current_cost)
    if started_at > as_of:
        return _base_result(as_of, "unavailable")
    if movement_summary is None:
        return _base_result(as_of, "inconsistent_history")

    realized = movement_summary["realized_profit_loss"]
    if not movement_summary["history_complete"]:
        return _base_result(as_of, "inconsistent_history", realized)

    investment_type = investment.get("investment_type")
    if investment_type == "market_investment":
        return _base_result(as_of, "pending_quote", realized)
    if investment_type != "fixed_income" or not isinstance(details, dict):
        return _base_result(as_of, "unavailable", realized)

    rate_type = str(details.get("rate_type") or "").strip().lower()
    if rate_type in _EXTERNAL_INDEX_RATES:
        return _base_result(as_of, "pending_external_index", realized)
    if rate_type != "prefixed":
        return _base_result(as_of, "unavailable", realized)

    fixed_rate = _number(details.get("fixed_rate"))
    if fixed_rate is None or fixed_rate < 0:
        return _base_result(as_of, "unavailable", realized)

    maturity_date = None
    if details.get("maturity_date") not in (None, ""):
        maturity_date = _iso_date(details.get("maturity_date"))
        if maturity_date is None or maturity_date < started_at:
            return _base_result(as_of, "unavailable", realized)

    lots = []
    cursor_date = started_at
    for movement_date, movement_id, kind, amount, principal in movement_summary["events"]:
        if movement_date > as_of:
            return _base_result(as_of, "unavailable", realized)
        factor = _growth_factor(fixed_rate, cursor_date, movement_date, maturity_date)
        if factor is None:
            return _base_result(as_of, "unavailable", realized)
        for lot in lots:
            lot["value"] *= factor
            if not isfinite(lot["value"]):
                return _base_result(as_of, "unavailable", realized)

        if kind in {"initial_contribution", "contribution"}:
            lots.append({"basis": amount, "value": amount})
        else:
            total_basis = sum(lot["basis"] for lot in lots)
            total_value = sum(lot["value"] for lot in lots)
            if (principal is None or principal > total_basis + _COST_TOLERANCE
                    or amount > total_value + _COST_TOLERANCE or total_basis <= 0
                    or total_value <= 0):
                return _base_result(as_of, "unavailable", realized)
            basis_factor = max(0.0, (total_basis - principal) / total_basis)
            value_factor = max(0.0, (total_value - amount) / total_value)
            for lot in lots:
                lot["basis"] *= basis_factor
                lot["value"] *= value_factor
        cursor_date = movement_date

    factor = _growth_factor(fixed_rate, cursor_date, as_of, maturity_date)
    if factor is None:
        return _base_result(as_of, "unavailable", realized)
    for lot in lots:
        lot["value"] *= factor
        if not isfinite(lot["value"]):
            return _base_result(as_of, "unavailable", realized)

    calculated_cost = sum(lot["basis"] for lot in lots)
    current_value = sum(lot["value"] for lot in lots)
    if (not isclose(calculated_cost, current_cost, rel_tol=1e-9, abs_tol=_COST_TOLERANCE)
            or current_value < -_COST_TOLERANCE):
        return _base_result(as_of, "inconsistent_history", realized)
    current_value = max(0.0, current_value)
    unrealized = current_value - current_cost
    total = unrealized + realized if realized is not None else None
    result = _base_result(as_of, "available", realized)
    result.update({
        "current_value": current_value,
        "unrealized_profit_loss": unrealized,
        "unrealized_return_percent": (
            unrealized / current_cost * 100.0 if current_cost > 0 else None
        ),
        "total_profit_loss": total,
    })
    gross = movement_summary["gross_contributions"]
    if total is not None and gross > 0:
        result["total_return_percent"] = total / gross * 100.0
    return result
