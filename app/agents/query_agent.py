"""
Query Agent

Specialized agent for information retrieval and reporting across ERP modules.
Handles natural language queries about inventory, sales, finance, and HR data.
"""

import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import structlog

from app.agents.base_agent import BaseAgent, AgentRequest, AgentResponse
from app.core.exceptions import QueryError


class QueryAgent(BaseAgent):
    """
    Query Agent for ERP information retrieval and reporting.
    
    Capabilities:
    - Natural language queries across ERP modules
    - Data analysis and reporting
    - Inventory tracking and alerts
    - Sales performance analysis
    - Financial reporting
    - HR analytics
    """

    def __init__(self, model: str = "gpt-4"):
        super().__init__(
            name="query_agent",
            model=model,
            system_prompt=self._get_default_system_prompt(),
            max_tokens=3000,
            temperature=0.3
        )
        self.logger = structlog.get_logger("query_agent")

    def _get_default_system_prompt(self) -> str:
        """Get the default system prompt for query agent"""
        return """You are an expert ERP Query Assistant specialized in retrieving and analyzing information from enterprise resource planning systems.

Your role is to:
1. Understand natural language queries about business data
2. Translate queries into structured database queries
3. Analyze results and provide clear, actionable insights
4. Generate comprehensive reports with visualizations
5. Identify trends, anomalies, and opportunities

Available ERP Modules:
- INVENTORY: Stock levels, product movements, supplier information, reorder alerts
- SALES: Order history, customer data, revenue analysis, sales trends
- FINANCE: Financial transactions, budgets, expenses, profit/loss reports
- HR: Employee data, payroll, attendance, performance metrics
- PRODUCTION: Manufacturing schedules, resource allocation, quality control

Knowledge Sources:
- Real-time database queries for current data
- Historical data analysis for trends
- Documentation and help systems
- Business rules and policies

Response Guidelines:
- Always provide accurate, up-to-date information
- Include relevant context and explanations
- Format data clearly with tables and summaries
- Highlight key insights and recommendations
- Provide actionable next steps when appropriate
- Use professional, business-appropriate language

When handling queries:
1. First identify the ERP modules involved
2. Determine the type of analysis needed
3. Check for any constraints or filters
4. Execute appropriate queries
5. Analyze and format results
6. Provide insights and recommendations

For complex queries, break down the response into:
- Executive Summary
- Key Findings
- Detailed Analysis
- Recommendations
- Next Steps"""

    def get_tools(self) -> List[Dict[str, Any]]:
        """Get available tools for query agent"""
        return [
            {
                "name": "database_query",
                "description": "Execute SQL queries against ERP database",
                "parameters": {
                    "query": {
                        "type": "string",
                        "description": "SQL query to execute"
                    },
                    "module": {
                        "type": "string",
                        "description": "ERP module (inventory, sales, finance, hr, production)",
                        "enum": ["inventory", "sales", "finance", "hr", "production"]
                    }
                },
                "required": ["query", "module"]
            },
            {
                "name": "get_inventory_summary",
                "description": "Get current inventory summary with stock levels",
                "parameters": {
                    "product_filter": {
                        "type": "string",
                        "description": "Optional product name or category filter"
                    },
                    "include_low_stock": {
                        "type": "boolean",
                        "description": "Include low stock alerts"
                    }
                }
            },
            {
                "name": "get_sales_report",
                "description": "Generate sales performance report",
                "parameters": {
                    "date_range": {
                        "type": "string",
                        "description": "Date range (e.g., 'last_30_days', 'this_month', 'this_year')"
                    },
                    "group_by": {
                        "type": "string",
                        "description": "Grouping criteria",
                        "enum": ["product", "customer", "region", "sales_rep"]
                    }
                }
            },
            {
                "name": "get_financial_summary",
                "description": "Get financial summary and key metrics",
                "parameters": {
                    "period": {
                        "type": "string",
                        "description": "Financial period",
                        "enum": ["monthly", "quarterly", "yearly"]
                    },
                    "include_budget": {
                        "type": "boolean",
                        "description": "Include budget comparison"
                    }
                }
            },
            {
                "name": "get_employee_analytics",
                "description": "Get HR analytics and employee metrics",
                "parameters": {
                    "department": {
                        "type": "string",
                        "description": "Department filter"
                    },
                    "metrics": {
                        "type": "array",
                        "description": "Metrics to include",
                        "items": {
                            "type": "string",
                            "enum": ["headcount", "turnover", "performance", "satisfaction"]
                        }
                    }
                }
            },
            {
                "name": "documentation_search",
                "description": "Search ERP documentation and help resources",
                "parameters": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "doc_type": {
                        "type": "string",
                        "description": "Documentation type",
                        "enum": ["user_guide", "api_docs", "troubleshooting", "best_practices"]
                    }
                }
            }
        ]

    async def process_request(self, request: AgentRequest) -> AgentResponse:
        """
        Process a query request with enhanced query understanding.
        
        Args:
            request: AgentRequest containing the user's query
            
        Returns:
            AgentResponse with query results and analysis
        """
        try:
            # Parse query intent
            query_intent = await self._parse_query_intent(request.message)
            
            # Add query context to request
            enhanced_context = {
                **request.context,
                "query_intent": query_intent,
                "tools_available": [tool["name"] for tool in self.get_tools()]
            }
            
            enhanced_request = AgentRequest(
                message=request.message,
                context=enhanced_context,
                session_id=request.session_id,
                metadata=request.metadata
            )
            
            return await super().process_request(enhanced_request)
            
        except Exception as e:
            self.logger.error("Error processing query request", error=str(e))
            raise QueryError(f"Failed to process query: {str(e)}")

    async def _parse_query_intent(self, query: str) -> Dict[str, Any]:
        """
        Parse user query to determine intent and extract relevant parameters.
        
        Args:
            query: Natural language query from user
            
        Returns:
            Dictionary containing query intent and extracted parameters
        """
        query_lower = query.lower()
        
        # Determine query type
        query_type = "general"
        if any(word in query_lower for word in ["inventory", "stock", "product"]):
            query_type = "inventory"
        elif any(word in query_lower for word in ["sales", "revenue", "order"]):
            query_type = "sales"
        elif any(word in query_lower for word in ["finance", "budget", "expense", "profit"]):
            query_type = "finance"
        elif any(word in query_lower for word in ["employee", "hr", "staff", "payroll"]):
            query_type = "hr"
        elif any(word in query_lower for word in ["production", "manufacturing", "schedule"]):
            query_type = "production"

        # Extract date ranges
        date_range = self._extract_date_range(query)
        
        # Extract numeric filters
        numeric_filters = self._extract_numeric_filters(query)
        
        # Extract entity names
        entities = self._extract_entities(query)

        return {
            "query_type": query_type,
            "date_range": date_range,
            "numeric_filters": numeric_filters,
            "entities": entities,
            "original_query": query
        }

    def _extract_date_range(self, query: str) -> Optional[str]:
        """Extract date range from query"""
        query_lower = query.lower()
        
        date_patterns = {
            "today": ["today"],
            "yesterday": ["yesterday"],
            "last_7_days": ["last 7 days", "past 7 days", "last week"],
            "last_30_days": ["last 30 days", "past 30 days", "last month"],
            "last_90_days": ["last 90 days", "past 90 days", "last quarter"],
            "this_month": ["this month"],
            "this_year": ["this year"],
            "last_year": ["last year"]
        }
        
        for range_name, patterns in date_patterns.items():
            if any(pattern in query_lower for pattern in patterns):
                return range_name
                
        return None

    def _extract_numeric_filters(self, query: str) -> Dict[str, Any]:
        """Extract numeric filters from query"""
        filters = {}
        
        # Extract quantity thresholds
        quantity_match = re.search(r'(\d+)\s*(?:units?|items?|quantity)', query.lower())
        if quantity_match:
            filters["quantity_threshold"] = int(quantity_match.group(1))
            
        # Extract price ranges
        price_match = re.search(r'\$(\d+(?:\.\d{2})?)', query)
        if price_match:
            filters["price_threshold"] = float(price_match.group(1))
            
        return filters

    def _extract_entities(self, query: str) -> List[str]:
        """Extract entity names from query"""
        entities = []
        
        # Simple entity extraction based on capitalization
        words = query.split()
        current_entity = []
        
        for word in words:
            if word[0].isupper():
                current_entity.append(word)
            elif current_entity:
                entities.append(" ".join(current_entity))
                current_entity = []
                
        if current_entity:
            entities.append(" ".join(current_entity))
            
        return entities

    async def generate_inventory_report(self, filters: Dict[str, Any] = None) -> str:
        """Generate inventory report based on filters"""
        filters = filters or {}
        
        report = f"""
# Inventory Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary
- Total Products: [To be populated from database]
- Low Stock Items: [To be populated from database]
- Total Value: [To be populated from database]

## Detailed Analysis
[Report content will be generated based on actual database queries]
        """
        
        return report.strip()

    async def generate_sales_report(self, date_range: str = "last_30_days") -> str:
        """Generate sales report for specified date range"""
        report = f"""
# Sales Report - {date_range.replace('_', ' ').title()}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Key Metrics
- Total Revenue: [To be populated from database]
- Total Orders: [To be populated from database]
- Average Order Value: [To be populated from database]

## Top Products
[Product analysis will be populated from database]

## Customer Insights
[Customer analysis will be populated from database]
        """
        
        return report.strip()

    async def get_recommendations(self, query_intent: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on query intent"""
        recommendations = []
        
        query_type = query_intent.get("query_type")
        
        if query_type == "inventory":
            recommendations.extend([
                "Check low stock items and set up reorder alerts",
                "Review slow-moving inventory for potential promotions",
                "Analyze supplier performance and delivery times"
            ])
        elif query_type == "sales":
            recommendations.extend([
                "Identify top-performing products and sales channels",
                "Analyze customer segments for targeted marketing",
                "Review pricing strategies based on performance data"
            ])
        elif query_type == "finance":
            recommendations.extend([
                "Monitor budget vs actual spending",
                "Review cash flow projections",
                "Identify cost reduction opportunities"
            ])
        elif query_type == "hr":
            recommendations.extend([
                "Track employee satisfaction metrics",
                "Review training and development needs",
                "Analyze turnover patterns and retention strategies"
            ])
        
        return recommendations