import io
import os
import re
import json
import pandas as pd
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

# Precompile fallback rules
FALLBACK_RULES = [
    (r"(?i)email|phone|addr|ssn|social|pwd|password|name", "PII", "Potential Personally Identifiable Information"),
    (r"(?i)time|date|created|updated|epoch", "TIMESTAMP", "Time-series logging timestamp"),
    (r"(?i)id$|^id|_id", "IDENTIFIER", "Unique record or entity identifier"),
    (r"(?i)temp", "MEASUREMENT_TEMPERATURE", "Industrial temperature measurement"),
    (r"(?i)vibr|amplitude|freq", "METRIC_VIBRATION", "Vibration analysis measurement"),
    (r"(?i)speed|rpm|rotational", "MEASUREMENT_SPEED", "Rotational speed in RPM"),
    (r"(?i)status|state|code", "STATUS", "Operational state indicator"),
    (r"(?i)cost|price|revenue|amount|val|usd|eur", "METRIC_FINANCE", "Financial metric values"),
    (r"(?i)lat|lon|coord|gps", "GEOLOCATION", "Geographic coordinates"),
]

def run_llm_inference(df: pd.DataFrame, stats: List[Dict[str, Any]]) -> Optional[Dict[str, Dict[str, Any]]]:
    """
    Attempt to use Gemini or OpenAI API to infer business descriptions and semantic tags.
    Returns a dictionary mapping column_name -> {"description": str, "tags": List[str]}
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if not gemini_key and not openai_key:
        return None

    # Prepare sample data and schema stats to feed to the model
    sample_rows = df.head(5).to_dict(orient="records")
    
    prompt = f"""
Analyze the columns of this dataset and output a JSON object mapping each column to a business-ready 'description' and standard 'tags' (e.g. PII, TIMESTAMP, IDENTIFIER, MEASUREMENT_TEMPERATURE, METRIC_VIBRATION, MEASUREMENT_SPEED, STATUS, METRIC_FINANCE, GEOLOCATION, METRIC_GENERAL).

Sample Data (first 5 rows):
{json.dumps(sample_rows, indent=2, default=str)}

Statistical Summary of Columns:
{json.dumps(stats, indent=2, default=str)}

Return ONLY a JSON object of this structure:
{{
  "column_name": {{
    "description": "Brief, business-focused description explaining what this is",
    "tags": ["TAG1", "TAG2"]
  }}
}}
Do not write markdown formatting other than JSON.
"""

    # 1. Try Gemini first if installed and configured
    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            text = response.text.strip()
            # Clean possible markdown wrap ```json ... ```
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\n", "", text)
                text = re.sub(r"\n```$", "", text)
            return json.loads(text)
        except Exception as e:
            print(f"Gemini schema inference failed: {e}. Trying OpenAI...")

    # 2. Try OpenAI fallback if configured
    if openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            text = response.choices[0].message.content.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\n", "", text)
                text = re.sub(r"\n```$", "", text)
            return json.loads(text)
        except Exception as e:
            print(f"OpenAI schema inference failed: {e}")

    return None

def run_heuristic_inference(column_name: str) -> Dict[str, Any]:
    """
    Fallback regex heuristic rule engine to infer tags and descriptions.
    """
    tags = []
    description = f"Generic raw input data column: {column_name}"
    
    for pattern, tag, desc in FALLBACK_RULES:
        if re.search(pattern, column_name):
            tags.append(tag)
            description = f"{desc} derived from column name '{column_name}'"
            
    if not tags:
        tags.append("METRIC_GENERAL")
        
    return {
        "description": description,
        "tags": tags
    }

def infer_schema_from_df(df: pd.DataFrame, table_name: str = "raw_table") -> Dict[str, Any]:
    """
    Analyze pandas dataframe, infer datatypes, calculate profile stats, 
    and call AI or heuristic layer for descriptions and semantic tags.
    """
    columns_meta = []
    stats_summary = []
    
    # 1. Gather stats and infer types
    for col in df.columns:
        col_series = df[col]
        
        # Deduce type
        if pd.api.types.is_datetime64_any_dtype(col_series):
            inferred_type = "datetime"
        elif pd.api.types.is_bool_dtype(col_series):
            inferred_type = "boolean"
        elif pd.api.types.is_integer_dtype(col_series):
            inferred_type = "integer"
        elif pd.api.types.is_float_dtype(col_series):
            inferred_type = "float"
        else:
            # Try parsing strings as date
            try:
                # Only try to coerce if it's string object
                if col_series.dtype == "object":
                    parsed = pd.to_datetime(col_series.dropna().head(100), errors="raise")
                    inferred_type = "datetime"
                else:
                    inferred_type = "string"
            except (ValueError, TypeError):
                inferred_type = "string"

        # Calculate statistics
        null_count = int(col_series.isnull().sum())
        distinct_vals = int(col_series.nunique())
        
        col_stat = {
            "name": str(col),
            "data_type": inferred_type,
            "nullable": null_count > 0,
            "statistics": {
                "null_count": null_count,
                "distinct_values": distinct_vals
            }
        }
        
        # If numeric, calculate min/max/mean
        if inferred_type in ["integer", "float"]:
            non_null = col_series.dropna()
            if not non_null.empty:
                col_stat["statistics"]["min"] = float(non_null.min())
                col_stat["statistics"]["max"] = float(non_null.max())
                col_stat["statistics"]["mean"] = float(non_null.mean())

        stats_summary.append(col_stat)

    # 2. Call AI or Heuristic for semantic context
    ai_enrichment = None
    try:
        ai_enrichment = run_llm_inference(df, stats_summary)
    except Exception as e:
        print(f"Skipping AI enrichment due to error: {e}")

    # 3. Assemble final schema
    for col_stat in stats_summary:
        col_name = col_stat["name"]
        
        # Enrich from AI or Heuristics
        if ai_enrichment and col_name in ai_enrichment:
            col_stat["description"] = ai_enrichment[col_name].get("description", f"Data field {col_name}")
            col_stat["tags"] = ai_enrichment[col_name].get("tags", ["METRIC_GENERAL"])
        else:
            heuristics = run_heuristic_inference(col_name)
            col_stat["description"] = heuristics["description"]
            col_stat["tags"] = heuristics["tags"]
            
        columns_meta.append(col_stat)
        
    return {
        "table_name": table_name,
        "columns": columns_meta,
        "row_count": len(df)
    }

def infer_schema_from_bytes(data: bytes, format_type: str, table_name: str = "raw_table") -> Dict[str, Any]:
    """
    Load bytes data (csv/json) into a pandas dataframe and run inference.
    """
    try:
        if format_type.lower() == "csv":
            df = pd.read_csv(io.BytesIO(data))
        elif format_type.lower() == "json":
            df = pd.read_json(io.BytesIO(data))
        else:
            raise ValueError(f"Unsupported format type: {format_type}")
    except Exception as e:
        raise ValueError(f"Failed to parse input bytes as {format_type}: {e}")
        
    return infer_schema_from_df(df, table_name)
