from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from datetime import datetime
from zoneinfo import ZoneInfo

from app.database import get_connection

class GoalCreate(BaseModel):
    name: str
    target_amount: float
    current_amount: float | None = 0
    deadline: str | None = None
    
class GoalUpdate(BaseModel):
    name: str
    target_amount: float
    current_amount: float | None = 0
    deadline: str | None = None
    
router = APIRouter(
    prefix="/api/goals",
    tags=["goals"]
)

@router.get("/")
def list_goals():
    connection = get_connection()

    rows = connection.execute("""
        SELECT *
        FROM goals
        ORDER BY id DESC
    """).fetchall()

    connection.close()

    return [dict(row) for row in rows]

@router.post("/")
def create_goal(goal: GoalCreate):
    connection = get_connection()
    
    created_at = datetime.now(
        ZoneInfo("America/Sao_Paulo")
    ).isoformat()
    
    cursor = connection.execute("""
             INSERT INTO goals (
                    name,
                    target_amount,
                    current_amount,
                    deadline,
                    created_at
             )
             VALUES (?, ?, ?, ?, ?)
    """, (
        goal.name,
        goal.target_amount,
        goal.current_amount,
        goal.deadline,
        created_at
    )) 
    
    connection.commit()
    
    goal_id = cursor.lastrowid
    
    connection.close()
    
    return {
        "id": goal_id,
        "message": "Goal created successfully"
    }

@router.delete("/{goal_id}")
def delete_goal(goal_id: int):
    connection = get_connection()

    cursor = connection.execute("""
        DELETE FROM goals
        WHERE id = ?
    """, (goal_id,))

    connection.commit()

    if cursor.rowcount == 0:
        connection.close()
        raise HTTPException(
            status_code=404,
            detail="Goal not found"
        )

    connection.close()

    return {
        "message": "Goal deleted"
    }
    
@router.put("/{goal_id}")
def update_goal(
    goal_id: int,
    goal: GoalUpdate
):
    connection = get_connection()

    cursor = connection.execute("""
        UPDATE goals
        SET
            name = ?,
            target_amount = ?,
            current_amount = ?,
            deadline = ?
        WHERE id = ?
    """, (
        goal.name,
        goal.target_amount,
        goal.current_amount,
        goal.deadline,
        goal_id
    ))

    connection.commit()

    if cursor.rowcount == 0:
        connection.close()
        raise HTTPException(
            status_code=404,
            detail="Goal not found"
        )

    connection.close()

    return {
        "message": "Goal updated"
    }               