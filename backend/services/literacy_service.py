"""
NEXUS Forge — Data Democratization & Literacy Hub Service

Provides personalized learning roadmaps, synthetic sandbox assets, and literacy quiz grading.
"""
from typing import Dict, Any, List

# Dummy database of lessons and sandboxes
LESSONS = [
    {
        "id": "lesson-1",
        "title": "Understanding Data Fabric Zones",
        "role": "Analyst",
        "level": "Beginner",
        "description": "Learn the difference between Raw, Clean, and Curated lakehouse tiers.",
        "exercise": "Which zone should you query to get validated, deduplicated, and drift-checked metrics?",
        "options": ["Raw Zone", "Clean Zone", "Ingestion Queue"],
        "correct_answer": "Clean Zone",
        "points": 10
    },
    {
        "id": "lesson-2",
        "title": "Causal Lineage Scaffolding",
        "role": "Engineer",
        "level": "Intermediate",
        "description": "How causal events link directly to business-critical downstream KPIs.",
        "exercise": "What metric does 'transformer_maintenance' directly impact in our demo ontology?",
        "options": ["Production Uptime", "Customer Retention", "Employee Payroll"],
        "correct_answer": "Production Uptime",
        "points": 20
    }
]

def get_learning_path(role: str) -> List[Dict[str, Any]]:
    """
    Returns personalized lessons based on the user's role.
    """
    path = [l for l in LESSONS if l["role"] == role]
    if not path:
        return LESSONS  # Fallback to all
    return path

def get_sandbox_dataset(sandbox_id: str) -> List[Dict[str, Any]]:
    """
    Returns a synthetic sandbox dataset.
    """
    if sandbox_id == "maintenance_sandbox":
        return [
            {"plant": "West-1", "transformer_id": "T-100", "temp_c": 82, "status": "nominal"},
            {"plant": "West-2", "transformer_id": "T-200", "temp_c": 115, "status": "critical_anomaly"},
            {"plant": "East-1", "transformer_id": "T-300", "temp_c": 64, "status": "nominal"}
        ]
    return [
        {"customer": "Acme Corp", "orders_ytd": 42, "trust_score": 95},
        {"customer": "Globex Corp", "orders_ytd": 12, "trust_score": 88}
    ]

def grade_literacy_exercise(lesson_id: str, submitted_answer: str) -> Dict[str, Any]:
    """
    Grades the literacy lesson response and rewards points.
    """
    lesson = next((l for l in LESSONS if l["id"] == lesson_id), None)
    if not lesson:
        return {"status": "error", "message": "Lesson not found"}
        
    is_correct = lesson["correct_answer"] == submitted_answer
    
    return {
        "status": "success",
        "correct": is_correct,
        "points_awarded": lesson["points"] if is_correct else 0,
        "explanation": f"The correct answer is '{lesson['correct_answer']}'. " + 
                       ("Excellent work!" if is_correct else "Review the lesson material and try again!")
    }
