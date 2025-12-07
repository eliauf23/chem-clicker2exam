from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Question:
    topic: int
    qnum: int                 # 1–100 for regular, 0 for challenge
    is_challenge: bool
    question_text: str
    solution_text: Optional[str] = None
    question_page: Optional[int] = None
    solution_page: Optional[int] = None

    level: Optional[int] = None
    learning_goals: Optional[List[str]] = None


