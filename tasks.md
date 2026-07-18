# NEXUS Forge: Implementation Master Roadmap

This roadmap organizes the development of **NEXUS Forge** into 6 execution phases, mapping directly to the modules defined in `ARCHITECTURE.md`. Use this checklist to track project progress.

---

## 📋 Phase 1: Ingestion & Data Fabric Foundation (Week 1)
*Focus: Setting up raw data structures, ingestion pipelines, AI schema profiling, and the foundational lakehouse.*

### Epic 1: Intelligent Ingestion & Streaming ✅
- [x] **1.1 Ingestion Scaffolding**  
  Set up Redpanda (Kafka-compatible), Airflow DAG scheduler, and FastAPI batch ingestion endpoints in docker-compose.
- [x] **1.2 AI-Assisted Schema Inference**  
  Build a profiling service that infers datatypes and uses LLMs (Gemini/OpenAI) to generate semantic tags and descriptions, with rule-based fallback.
- [x] **1.3 Mock Data Simulator**  
  Wire up real-time manufacturing IoT stream generators (temperature, vibration) and batch log output to validate ingestion paths.

### Epic 2: Autonomous Data Engineering Layer
- [ ] **2.1 Baseline Transformation Pipelines**  
  Implement cleaning, deduplication, and normalization using dbt + Spark/DuckDB, with version control.
- [ ] **2.2 Drift & Anomaly Detection**  
  Add statistical checks for column schema drift and out-of-bounds value anomalies per pipeline run.
- [ ] **2.3 Auto-Remediation & Self-Healing**  
  Prototype a library of automatic repair actions (schema coercion, default backfills) for low-risk pipeline drift.

### Epic 3: AI-Native Data Fabric
- [ ] **3.1 Lakehouse Storage (Iceberg)**  
  Configure Apache Iceberg tables in MinIO S3 storage using DuckDB, tracking trust and freshness scores.
- [ ] **3.2 Causal Metadata Layer**  
  Design a schema mapping events (e.g., component wear) to downstream metric impacts (e.g., machine downtime).

---

## 📋 Phase 2: Living Enterprise Context Graph (Week 2)
*Focus: Stand up the graph database and integrate semantic search to power context-aware retrieval.*

### Epic 4: Knowledge Graph Core
- [ ] **4.1 Neo4j Graph DB Integration**  
  Deploy Neo4j, define the ontology (nodes: machine, sensor, operator; edges: maps_to, reports_to, affects).
- [ ] **4.2 Entity Resolution Engine**  
  Build matching rules to resolve column variances (e.g., `cust_id` vs `customer_num`) into unified nodes.
- [ ] **4.3 ER Diagrams & Business Glossary**  
  Develop a service that automatically derives and visualizes physical schemas and glossary maps from Neo4j.

### Epic 5: Context Layer & Graph RAG
- [ ] **5.1 Graph RAG Retrieval API**  
  Connect Qdrant or FAISS with Sentence Transformers to perform semantic and vector search over graph relationships.
- [ ] **5.2 Dynamic Context Injection**  
  Deliver real-time query contexts (lineage, metadata, historical logs) directly into downstream agent memory.

---

## 📋 Phase 3: Multi-Agent Intelligence Core & Governance (Week 3)
*Focus: Orchestrate collaborative AI agents and active background governance.*

### Epic 6: Agent Orchestration (LangGraph)
- [ ] **6.1 Multi-Agent Workspaces**  
  Build LangGraph agent state workflows with an Executive Coordinator routing tasks to Specialist agents (e.g., Manufacturing Specialist, Maintenance Specialist).
- [ ] **6.2 Collaborative Memory & Context**  
  Wire agents to read and record decision traces back to the Neo4j Context Graph.
- [ ] **6.3 Human-in-the-Loop (HITL) Gateways**  
  Establish an approval queue that requires human confirmation before agents write to production databases.

### Epic 7: Data Steward AI (Active Governance)
- [ ] **7.1 Governance Monitoring**  
  Configure background audits for compliance, checking data partitions for exposed PII or duplicate profiles.
- [ ] **7.2 Autonomous Compliance Remediation**  
  Enable the Data Steward agent to automatically flag and mask sensitive fields, logging all steps in the lineage graph.

---

## 📋 Phase 4: Natural Language to Action BI (Week 4)
*Focus: Conversational analytical pipelines and adaptive frontend dashboard panels.*

### Epic 8: NL to Action BI
- [ ] **8.1 Semantic SQL Generator**  
  Parse questions to SQL using schema context from the database, executing safely inside sandbox environments.
- [ ] **8.2 Multi-Step Reasoning Chains**  
  Compile pipelines that translate: `Natural Language Prompt` → `SQL Generation` → `ECharts Visualization` → `Causal Risk Explanation`.

### Epic 9: Adaptive Dashboard Studio
- [ ] **9.1 Interactive Dashboard Panels**  
  Set up React & TypeScript visual workspace using Tailwind UI, ECharts, and interactive data grids.
- [ ] **9.2 Dynamic Layout Adaptation**  
  Track user interactions and update default charts automatically based on highlighted metrics or anomalies.

---

## 📋 Phase 5: Decision Intelligence & Copilot (Week 5)
*Focus: Predictive scenario modeling and conversational enterprise assistant.*

### Epic 10: AI Decision Intelligence Engine
- [ ] **10.1 Causal Simulation & "What-If" Analysis**  
  Implement mathematical modeling of actions (e.g., "reduce rotational speed by 10%") to simulate downstream wear and yield results.
- [ ] **10.2 Risk-Aware Recommendations**  
  Score recommendations by confidence and safety boundaries, referencing graph lineage.

### Epic 11: Enterprise Knowledge Copilot
- [ ] **11.1 Context-Aware Chat Interface**  
  Deliver a conversational interface that explains SQL, documents pipeline configurations, and queries the context graph.
- [ ] **11.2 Autonomous Task Executions**  
  Configure scheduled tasks (e.g., generating shift PDF summaries) triggered by copilot request under supervisor gates.

---

## 📋 Phase 6: Democratization, Novelty Features & Observability (Week 6)
*Focus: Security features, user learning sandbox, system-wide metrics monitoring, and demo polish.*

### Epic 12: Data Democratization & Literacy Hub
- [ ] **12.1 Interactive Sandbox Playgrounds**  
  Provide safe, isolated databases for users to practice SQL queries with AI tutoring support.
- [ ] **12.2 Engagement & Literacy Metrics**  
  Generate gamified analytics reflecting user SQL success rates and semantic definitions contributions.

### Epic 13: Advanced Novelty Features
- [ ] **13.1 Privacy-Preserving Layer**  
  Introduce mock differential privacy noise injection and bias validation filters for agent models.
- [ ] **13.2 Self-Improving Loop**  
  Store user query corrections back into the context database to improve future agent generation.

### Epic 14: System Observability & Demo Polish
- [ ] **14.1 MLOps Monitoring Dashboard**  
  Provide Grafana-style dashboards to display Kafka latency, database resource status, and LLM token usage.
- [ ] **14.2 End-to-End Walkthrough Demos**  
  Polish the layout, compile mock manufacturing databases, and film screen captures showcasing self-healing schema changes and analytical queries.
