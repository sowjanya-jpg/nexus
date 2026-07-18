"""
NEXUS Forge — Dashboard Service

Logic for AI-generated dashboard layouts and narrative summaries.
"""
from typing import Dict, Any, List


def generate_dashboard_config(user_goal: str) -> Dict[str, Any]:
    """
    Takes a user's stated goal and returns a JSON layout of dashboard widgets.
    For MVP, we use keyword matching to determine appropriate widget types.
    """
    goal_lower = user_goal.lower()

    widgets = []

    # Always include a KPI summary row
    widgets.append({
        "id": "kpi-row",
        "type": "kpi_row",
        "position": {"row": 0, "col": 0, "width": 12},
        "config": {
            "metrics": [
                {"label": "Revenue", "value": "$2.4M", "trend": "+5.2%", "trend_direction": "up"},
                {"label": "Production Uptime", "value": "94.3%", "trend": "-1.1%", "trend_direction": "down"},
                {"label": "Trust Score (Avg)", "value": "87/100", "trend": "+2", "trend_direction": "up"},
                {"label": "Open Approvals", "value": "3", "trend": "0", "trend_direction": "neutral"},
            ]
        }
    })

    if any(kw in goal_lower for kw in ["production", "manufacturing", "maintenance", "transformer"]):
        widgets.extend([
            {
                "id": "production-trend",
                "type": "line_chart",
                "position": {"row": 1, "col": 0, "width": 6},
                "config": {
                    "title": "Production Uptime Trend",
                    "data_source": "/api/v1/bi/query",
                    "x_axis": "month",
                    "y_axis": "uptime_pct"
                }
            },
            {
                "id": "maintenance-schedule",
                "type": "bar_chart",
                "position": {"row": 1, "col": 6, "width": 6},
                "config": {
                    "title": "Maintenance Events by Region",
                    "data_source": "/api/v1/bi/query",
                    "x_axis": "region",
                    "y_axis": "event_count"
                }
            },
            {
                "id": "what-if-sim",
                "type": "what_if_widget",
                "position": {"row": 2, "col": 0, "width": 12},
                "config": {
                    "title": "What-If: Adjust Maintenance Budget",
                    "simulation_endpoint": "/api/v1/decision/simulate"
                }
            }
        ])
    elif any(kw in goal_lower for kw in ["revenue", "finance", "cost", "budget"]):
        widgets.extend([
            {
                "id": "revenue-breakdown",
                "type": "bar_chart",
                "position": {"row": 1, "col": 0, "width": 6},
                "config": {
                    "title": "Revenue by Product Line",
                    "data_source": "/api/v1/bi/query",
                    "x_axis": "product",
                    "y_axis": "revenue"
                }
            },
            {
                "id": "cost-trend",
                "type": "line_chart",
                "position": {"row": 1, "col": 6, "width": 6},
                "config": {
                    "title": "Operating Cost Trend",
                    "data_source": "/api/v1/bi/query",
                    "x_axis": "quarter",
                    "y_axis": "cost"
                }
            }
        ])
    else:
        # Default overview
        widgets.extend([
            {
                "id": "data-quality",
                "type": "gauge_chart",
                "position": {"row": 1, "col": 0, "width": 4},
                "config": {"title": "Data Quality Score", "value": 87, "max": 100}
            },
            {
                "id": "agent-activity",
                "type": "table",
                "position": {"row": 1, "col": 4, "width": 8},
                "config": {
                    "title": "Recent Agent Actions",
                    "data_source": "/api/v1/agents/approvals"
                }
            }
        ])

    return {
        "goal": user_goal,
        "layout": {"columns": 12},
        "widgets": widgets
    }


def generate_narrative(dashboard_config: Dict[str, Any]) -> str:
    """
    Produces a plain-English narrative summary of the current dashboard state.
    """
    widget_count = len(dashboard_config.get("widgets", []))
    goal = dashboard_config.get("goal", "general overview")

    # Extract KPI data if present
    kpi_widget = next((w for w in dashboard_config.get("widgets", []) if w["type"] == "kpi_row"), None)
    kpi_summary = ""
    if kpi_widget:
        metrics = kpi_widget["config"]["metrics"]
        highlights = []
        for m in metrics:
            direction = "improved" if m["trend_direction"] == "up" else "declined" if m["trend_direction"] == "down" else "remained stable"
            highlights.append(f"{m['label']} is at {m['value']} and has {direction} ({m['trend']})")
        kpi_summary = " ".join(highlights)

    narrative = (
        f"This dashboard was generated for the goal: \"{goal}\". "
        f"It contains {widget_count} widgets. "
        f"{kpi_summary} "
        f"Use the what-if simulation widgets to explore the impact of different interventions."
    )
    return narrative
