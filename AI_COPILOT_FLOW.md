# AI Copilot Request Flow

This document explains the complete flow of how the AI Copilot processes user requests from the frontend chatbot.

## Example Query

**User asks:** "What is the current sales pattern and net projection for this month?"

---

## Complete Request Flow

### Phase 1: Frontend → WebSocket Connection

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. FRONTEND (ChatbotWidget.tsx / AI Chat Page)                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
User types: "What is the current sales pattern and net projection for this month?"
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Frontend Action:                                                 │
│ - Captures user message                                          │
│ - Adds to local message state                                    │
│ - Shows "thinking" animation                                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ WebSocket Send:                                                  │
│ ws.send({                                                        │
│   type: "chat_message",                                          │
│   data: {                                                        │
│     content: "What is the current sales pattern...",            │
│     conversationId: "conv_123",                                  │
│     userId: "user_456"                                           │
│   }                                                              │
│ })                                                               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    WebSocket Connection
                    ws://localhost:8003/ws/chat/conv_123?token=jwt_token
```

---

### Phase 2: Backend WebSocket Handler

```
┌─────────────────────────────────────────────────────────────────┐
│ 2. WEBSOCKET HANDLER (app/api/websocket/handlers/chat_handler.py)│
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Authentication:                                                  │
│ - Extract JWT token from query params                            │
│ - Validate token via Redis cache (30min TTL)                     │
│ - If not in cache, validate via gRPC auth service                │
│ - Extract user_id, role, permissions                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ RBAC Check (app/services/rbac_service.py):                      │
│ - Check if user has Permission.USE_AI_CHAT                       │
│ - Check if user has Permission.VIEW_ANALYTICS                    │
│ - If role = "viewer", deny forecast access                       │
│ - If role = "user/manager/admin", allow                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Message Processing:                                              │
│ - Store message in MongoDB (conversations collection)            │
│ - Load conversation history from MongoDB                          │
│ - Pass to LangChain Chat Service                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### Phase 3: LangChain Chat Service

```
┌─────────────────────────────────────────────────────────────────┐
│ 3. LANGCHAIN CHAT SERVICE (app/services/langchain_chat_service.py)│
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Initialize Components:                                           │
│ - Load LLM (OpenAI GPT-4 / Claude / Gemini / Ollama)            │
│ - Load conversation memory from MongoDB                          │
│ - Initialize LangGraph agent                                     │
│ - Register 5 tools (docs, database, API, tasks, charts)         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Send Reasoning Step 1:                                           │
│ WebSocket → Frontend:                                            │
│ {                                                                │
│   type: "reasoning_step",                                        │
│   step_number: 1,                                                │
│   icon: "🧠",                                                    │
│   title: "Analyzing query",                                      │
│   description: "Understanding user intent and requirements"      │
│ }                                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

### Phase 4: LangGraph Agent Processing

```
┌─────────────────────────────────────────────────────────────────┐
│ 4. LANGGRAPH AGENT (app/langgraph/agent_graph.py)              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Agent State Machine:                                             │
│                                                                  │
│  START → analyze_query → select_tools → execute_tools → respond │
│            ↓                  ↓              ↓            ↓      │
│         [Intent]          [Tools]       [Results]    [Answer]   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Step 1: Analyze Query (app/langgraph/nodes.py)                  │
│                                                                  │
│ LLM analyzes: "What is the current sales pattern and net        │
│                projection for this month?"                       │
│                                                                  │
│ Intent Detection:                                                │
│ - Primary: Data analysis + forecasting                           │
│ - Secondary: Visualization needed                                │
│ - Data source: Sales database                                    │
│ - Time range: Current month                                      │
│ - Output: Pattern analysis + projection chart                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Send Reasoning Step 2:                                           │
│ {                                                                │
│   type: "reasoning_step",                                        │
│   step_number: 2,                                                │
│   icon: "🔍",                                                    │
│   title: "Selecting tools",                                      │
│   description: "Need: database query + chart generation"         │
│ }                                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

### Phase 5: Tool Selection & Execution

```
┌─────────────────────────────────────────────────────────────────┐
│ 5. TOOL EXECUTION (app/langchain/tools.py)                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Tool 1: query_database                                           │
│                                                                  │
│ Send Reasoning Step 3:                                           │
│ {                                                                │
│   type: "reasoning_step",                                        │
│   step_number: 3,                                                │
│   icon: "📊",                                                    │
│   title: "Querying sales data",                                  │
│   description: "Fetching current month sales from database"      │
│ }                                                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Execute: query_data_tool()                                       │
│ → app/services/erp_data_service.py                              │
│ → app/services/api_gateway_client.py                            │
│                                                                  │
│ API Call:                                                        │
│ GET http://api-gateway:8000/api/v1/sales/analytics              │
│ Headers: { Authorization: Bearer <jwt_token> }                  │
│ Params: {                                                        │
│   start_date: "2024-11-01",                                      │
│   end_date: "2024-11-30",                                        │
│   group_by: "day"                                                │
│ }                                                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ API Gateway → Sales Service:                                     │
│ - Validates JWT token                                            │
│ - Checks user permissions (RBAC)                                 │
│ - Filters data by user's department (if manager)                 │
│ - Queries PostgreSQL sales database                              │
│ - Returns aggregated sales data                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Response Data:                                                   │
│ {                                                                │
│   "total_sales": 125000,                                         │
│   "daily_sales": [                                               │
│     {"date": "2024-11-01", "amount": 4200},                      │
│     {"date": "2024-11-02", "amount": 4500},                      │
│     ...                                                          │
│   ],                                                             │
│   "trend": "increasing",                                         │
│   "growth_rate": 12.5                                            │
│ }                                                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Tool 2: generate_chart                                           │
│                                                                  │
│ Send Reasoning Step 4:                                           │
│ {                                                                │
│   type: "reasoning_step",                                        │
│   step_number: 4,                                                │
│   icon: "📈",                                                    │
│   title: "Creating visualization",                               │
│   description: "Generating sales pattern chart with forecast"    │
│ }                                                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Execute: generate_chart_tool()                                   │
│ → app/services/chart_service.py                                 │
│                                                                  │
│ Chart Generation:                                                │
│ - Analyze sales data pattern                                     │
│ - Calculate trend line                                           │
│ - Generate forecast for remaining days                           │
│ - Create chart configuration (Plotly/Chart.js format)            │
│ - Return widget JSON                                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Chart Widget Data:                                               │
│ {                                                                │
│   "type": "widget",                                              │
│   "widgetType": "chart",                                         │
│   "data": {                                                      │
│     "chartType": "line",                                         │
│     "title": "November Sales Pattern & Projection",              │
│     "labels": ["Nov 1", "Nov 2", ..., "Nov 30"],                │
│     "datasets": [                                                │
│       {                                                          │
│         "label": "Actual Sales",                                 │
│         "data": [4200, 4500, 4800, ...],                         │
│         "borderColor": "rgb(34, 197, 94)"                        │
│       },                                                         │
│       {                                                          │
│         "label": "Projected",                                    │
│         "data": [null, null, ..., 5200, 5400],                   │
│         "borderColor": "rgb(249, 115, 22)",                      │
│         "borderDash": [5, 5]                                     │
│       }                                                          │
│     ]                                                            │
│   }                                                              │
│ }                                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

### Phase 6: Response Generation

```
┌─────────────────────────────────────────────────────────────────┐
│ 6. RESPONSE GENERATION (LangGraph → LLM)                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Send Reasoning Step 5:                                           │
│ {                                                                │
│   type: "reasoning_step",                                        │
│   step_number: 5,                                                │
│   icon: "✨",                                                    │
│   title: "Generating insights",                                  │
│   description: "Analyzing patterns and creating response"        │
│ }                                                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ LLM Prompt:                                                      │
│                                                                  │
│ System: You are an ERP AI assistant. Analyze the data and       │
│         provide insights.                                        │
│                                                                  │
│ Context:                                                         │
│ - Sales data: $125,000 total, 12.5% growth                      │
│ - Trend: Increasing                                              │
│ - Chart: Generated with forecast                                 │
│                                                                  │
│ User Query: "What is the current sales pattern and net          │
│              projection for this month?"                         │
│                                                                  │
│ Task: Provide comprehensive analysis with insights              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ LLM Response (Streaming):                                        │
│                                                                  │
│ "Based on the current sales data for November 2024, here's      │
│  the analysis:                                                   │
│                                                                  │
│  **Sales Pattern:**                                              │
│  - Total sales: $125,000 (as of Nov 28)                         │
│  - Daily average: $4,464                                         │
│  - Trend: Consistent upward trajectory (+12.5% growth)           │
│  - Peak days: Fridays and Saturdays                              │
│                                                                  │
│  **Net Projection:**                                             │
│  - Projected month-end total: $135,000                           │
│  - Remaining 2 days forecast: $10,000                            │
│  - Confidence level: 85%                                         │
│                                                                  │
│  **Key Insights:**                                               │
│  1. Sales momentum is strong and accelerating                    │
│  2. Weekend performance is 35% above weekday average             │
│  3. On track to exceed monthly target by 8%                      │
│                                                                  │
│  [Chart showing pattern and projection below]"                   │
└─────────────────────────────────────────────────────────────────┘
```

---

### Phase 7: Streaming Response to Frontend

```
┌─────────────────────────────────────────────────────────────────┐
│ 7. WEBSOCKET STREAMING (Backend → Frontend)                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Send: reasoning_complete                                         │
│ {                                                                │
│   type: "reasoning_complete",                                    │
│   data: { message: "Analysis complete" }                         │
│ }                                                                │
│ → Frontend hides thinking animation                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Stream Response Chunks:                                          │
│                                                                  │
│ Chunk 1: { type: "chunk", data: { content: "Based on the" }}    │
│ Chunk 2: { type: "chunk", data: { content: " current sales" }}  │
│ Chunk 3: { type: "chunk", data: { content: " data for" }}       │
│ ...                                                              │
│ Chunk N: { type: "chunk", data: {                               │
│            content: "8%",                                        │
│            isFinal: false                                        │
│          }}                                                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Send Chart Widget:                                               │
│ {                                                                │
│   type: "chunk",                                                 │
│   data: {                                                        │
│     content: JSON.stringify(chartWidget),                        │
│     isFinal: true                                                │
│   }                                                              │
│ }                                                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Store in MongoDB:                                                │
│ - Save complete response to conversations collection             │
│ - Update conversation metadata                                   │
│ - Cache in Redis for quick retrieval                             │
└─────────────────────────────────────────────────────────────────┘
```

---

### Phase 8: Frontend Rendering

```
┌─────────────────────────────────────────────────────────────────┐
│ 8. FRONTEND RENDERING (ChatbotWidget.tsx)                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Handle reasoning_step messages:                                  │
│ - Show thinking animation with current step                      │
│ - Display step icon and description                              │
│ - Cycle through steps with fade animation                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Handle reasoning_complete:                                       │
│ - Hide thinking animation                                        │
│ - Prepare for response streaming                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Handle chunk messages:                                           │
│ - Accumulate text chunks                                         │
│ - Update message in real-time (typewriter effect)                │
│ - Parse markdown formatting                                      │
│ - Detect widget JSON                                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Render Chart Widget:                                             │
│ - Parse widget JSON                                              │
│ - Render using Chart.js or Recharts                              │
│ - Display interactive chart in chat                              │
│ - Enable hover tooltips and zoom                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Final Display:                                                   │
│                                                                  │
│ ┌─────────────────────────────────────────────────────────┐     │
│ │ 🤖 AI Copilot                                           │     │
│ │                                                         │     │
│ │ Based on the current sales data for November 2024...   │     │
│ │                                                         │     │
│ │ **Sales Pattern:**                                      │     │
│ │ - Total sales: $125,000                                 │     │
│ │ - Daily average: $4,464                                 │     │
│ │ ...                                                     │     │
│ │                                                         │     │
│ │ [Interactive Line Chart]                                │     │
│ │  ┌────────────────────────────────────────┐            │     │
│ │  │     November Sales & Projection         │            │     │
│ │  │  $6k ┤                            ╱╱╱   │            │     │
│ │  │  $5k ┤                      ╱╱╱╱╱       │            │     │
│ │  │  $4k ┤            ╱╱╱╱╱╱╱╱╱             │            │     │
│ │  │  $3k ┤      ╱╱╱╱╱                       │            │     │
│ │  │      └────────────────────────────────  │            │     │
│ │  │       1   5   10  15  20  25  30       │            │     │
│ │  └────────────────────────────────────────┘            │     │
│ │                                                         │     │
│ │ 10:45 AM                                                │     │
│ └─────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Alternative Flow: Background Task

If the query requires heavy processing (e.g., "Generate a comprehensive sales report with forecasts"):

```
┌─────────────────────────────────────────────────────────────────┐
│ BACKGROUND TASK FLOW                                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
Agent selects: create_background_task tool
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 1. Create Task (app/services/background_task_service.py)        │
│    - Generate task_id                                            │
│    - Store in Redis with metadata                                │
│    - Send event to Kafka topic: "ai-copilot-tasks"              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. Immediate Response to User:                                   │
│    "I'm generating your comprehensive sales report. This will    │
│     take a few minutes. I'll notify you when it's ready."        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. Kafka Consumer Picks Up Event                                 │
│    - Worker processes task asynchronously                        │
│    - Generates report (PDF/Excel)                                │
│    - Creates charts and analytics                                │
│    - Stores result in Redis                                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. Task Complete Event                                           │
│    - Send to Kafka: "task_completed"                             │
│    - Send WebSocket notification to user                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. User Receives Notification:                                   │
│    "Your sales report is ready! 📊                               │
│     - 25 pages with charts and insights                          │
│     - Download: [Click here]"                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Components Summary

### 1. **Frontend** (`ChatbotWidget.tsx`)
- Captures user input
- Manages WebSocket connection
- Displays reasoning steps with animations
- Renders streaming responses
- Renders chart widgets

### 2. **WebSocket Handler** (`app/api/websocket/handlers/chat_handler.py`)
- Authenticates user via JWT
- Manages WebSocket connections
- Routes messages to chat service
- Streams responses back to frontend

### 3. **LangChain Chat Service** (`app/services/langchain_chat_service.py`)
- Initializes LLM and memory
- Manages conversation context
- Coordinates with LangGraph agent
- Handles streaming responses

### 4. **LangGraph Agent** (`app/langgraph/agent_graph.py`)
- Analyzes user intent
- Selects appropriate tools
- Executes tools in sequence
- Generates final response

### 5. **Tools** (`app/langchain/tools.py`)
- `search_documentation`: RAG search
- `query_database`: ERP data queries
- `call_api`: API Gateway calls
- `create_background_task`: Async tasks
- `generate_chart`: Visualizations

### 6. **Services**
- **RBAC Service**: Permission checks
- **Chart Service**: Visualization generation
- **ERP Data Service**: Data access
- **API Gateway Client**: ERP integration
- **Background Task Service**: Async processing
- **Kafka Service**: Event streaming

### 7. **Data Stores**
- **MongoDB**: Conversations, messages, memory
- **Redis**: Token cache, task results
- **Qdrant**: Vector embeddings for RAG
- **PostgreSQL**: ERP transactional data (via API Gateway)

---

## Performance Metrics

**Typical Response Times:**
- Simple query (documentation): 1-2 seconds
- Data query with chart: 2-4 seconds
- Complex analysis: 3-6 seconds
- Background task: 30 seconds - 5 minutes (async)

**Streaming:**
- First token: ~500ms
- Chunk rate: 50-100 tokens/second
- Chart rendering: Instant (client-side)

---

## Error Handling

At each phase, errors are caught and handled gracefully:

1. **Authentication failure** → "Please log in again"
2. **Permission denied** → "You don't have access to this data"
3. **Tool execution error** → Retry with fallback or inform user
4. **LLM timeout** → "Taking longer than expected, creating background task..."
5. **WebSocket disconnect** → Auto-reconnect with exponential backoff

---

## Security Flow

```
User Request
    ↓
JWT Validation (Redis cache → gRPC auth service)
    ↓
RBAC Permission Check (rbac_service)
    ↓
Data Filtering (by role: admin/manager/user/viewer)
    ↓
API Gateway Authentication
    ↓
Service-level Authorization
    ↓
Response (filtered by permissions)
```

---

This complete flow ensures:
- ✅ Real-time user feedback with reasoning steps
- ✅ Secure, role-based data access
- ✅ Intelligent tool selection and execution
- ✅ Interactive visualizations
- ✅ Async processing for heavy tasks
- ✅ Graceful error handling
- ✅ Scalable architecture
