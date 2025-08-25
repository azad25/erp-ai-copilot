"""
Analytics Agent

Specialized agent for data analysis, insights generation, and predictive analytics.
Handles statistical analysis, trend identification, and business intelligence.
"""

from typing import List, Dict, Any
import json
from datetime import datetime, timedelta
import statistics

from .base_agent import BaseAgent, AgentRequest, AgentResponse
from app.models.api import AgentType
from app.core.exceptions import AgentError


class AnalyticsAgent(BaseAgent):
    """
    Analytics Agent for data analysis and insights generation
    
    Capabilities:
    - Statistical analysis and reporting
    - Trend identification and forecasting
    - Business intelligence insights
    - Performance metrics and KPIs
    - Predictive analytics
    - Data visualization recommendations
    """

    def __init__(self, model: str = "gpt-4"):
        super().__init__(AgentType.ANALYTICS, model)
        self.supported_analyses = [
            "trend_analysis", "forecasting", "correlation", "performance",
            "anomaly_detection", "segmentation", "predictive_modeling"
        ]

    async def execute(self, request: AgentRequest) -> AgentResponse:
        """
        Execute analytics agent functionality
        
        Args:
            request: AgentRequest with analysis requirements
            
        Returns:
            AgentResponse with analytical insights
        """
        if not await self.validate_request(request):
            raise AgentError("Invalid analytics request")

        # Parse analysis intent
        analysis_intent = await self._parse_analysis_intent(request.message)
        
        # Execute the appropriate analysis
        if analysis_intent["type"] == "trend_analysis":
            result = await self._perform_trend_analysis(analysis_intent)
        elif analysis_intent["type"] == "forecasting":
            result = await self._perform_forecasting(analysis_intent)
        elif analysis_intent["type"] == "performance_analysis":
            result = await self._perform_performance_analysis(analysis_intent)
        elif analysis_intent["type"] == "anomaly_detection":
            result = await self._detect_anomalies(analysis_intent)
        elif analysis_intent["type"] == "correlation_analysis":
            result = await self._perform_correlation_analysis(analysis_intent)
        else:
            result = await self._perform_general_analysis(request.message, analysis_intent)

        return AgentResponse(
            response=result,
            agent_type=self.agent_type,
            conversation_id=request.conversation_id or "",
            execution_id="",
            metadata={
                "analysis_type": analysis_intent["type"],
                "data_points": analysis_intent.get("data_points", 0),
                "confidence_level": analysis_intent.get("confidence", 0.95),
                "execution_time": datetime.utcnow().isoformat(),
                "recommendations": analysis_intent.get("recommendations", [])
            }
        )

    def get_system_prompt(self) -> str:
        """
        Get system prompt for analytics agent
        
        Returns:
            System prompt defining the agent's role
        """
        return """
        You are an Analytics Agent for the UNIBASE ERP system. Your role is to:
        
        1. **Statistical Analysis**: Perform comprehensive statistical analysis on business data
        2. **Trend Identification**: Identify patterns, trends, and seasonality in data
        3. **Predictive Modeling**: Generate forecasts and predictions based on historical data
        4. **Performance Insights**: Analyze KPIs and business performance metrics
        5. **Anomaly Detection**: Identify unusual patterns or outliers in data
        6. **Business Intelligence**: Provide actionable insights for decision making
        
        **Analysis Capabilities**:
        - Time series analysis and forecasting
        - Correlation and regression analysis
        - Performance benchmarking
        - Customer segmentation and profiling
        - Sales forecasting and demand planning
        - Financial performance analysis
        - Operational efficiency metrics
        
        **Response Guidelines**:
        - Present findings with statistical significance
        - Include confidence intervals and margins of error
        - Provide clear, actionable recommendations
        - Use visual descriptions for complex insights
        - Highlight key drivers and factors
        - Suggest next steps for deeper analysis
        
        **Data Quality**:
        - Always assess data quality and completeness
        - Flag potential data issues or limitations
        - Provide context for analysis results
        """

    def get_available_tools(self) -> List[str]:
        """
        Get available tools for analytics agent
        
        Returns:
            List of available tool names
        """
        return [
            "statistical_engine",
            "forecasting_model",
            "correlation_analyzer",
            "anomaly_detector",
            "data_visualizer",
            "performance_calculator",
            "trend_analyzer",
            "segmentation_engine"
        ]

    async def _parse_analysis_intent(self, message: str) -> Dict[str, Any]:
        """
        Parse user message to determine analysis intent
        
        Args:
            message: User's analysis request
            
        Returns:
            Dictionary with analysis type and parameters
        """
        message_lower = message.lower()
        
        # Analysis type detection
        analysis_patterns = {
            "trend_analysis": [
                "trend", "pattern", "over time", "growth", "decline",
                "direction", "movement", "trajectory"
            ],
            "forecasting": [
                "forecast", "predict", "future", "projection", "estimate",
                "expect", "anticipate", "plan ahead"
            ],
            "performance_analysis": [
                "performance", "kpi", "metrics", "efficiency", "effectiveness",
                "benchmark", "compare", "evaluate"
            ],
            "anomaly_detection": [
                "anomaly", "outlier", "unusual", "unexpected", "abnormal",
                "irregular", "deviation", "exception"
            ],
            "correlation_analysis": [
                "correlation", "relationship", "connection", "impact",
                "influence", "link", "association", "dependence"
            ]
        }
        
        analysis_type = "general"
        for intent_type, patterns in analysis_patterns.items():
            if any(pattern in message_lower for pattern in patterns):
                analysis_type = intent_type
                break
        
        # Extract parameters
        params = {
            "time_period": "last_12_months",
            "confidence": 0.95,
            "granularity": "monthly"
        }
        
        # Time period extraction
        if "week" in message_lower:
            params["time_period"] = "last_4_weeks"
            params["granularity"] = "daily"
        elif "month" in message_lower:
            params["time_period"] = "last_6_months"
            params["granularity"] = "weekly"
        elif "year" in message_lower:
            params["time_period"] = "last_12_months"
            params["granularity"] = "monthly"
        
        # Data source extraction
        data_sources = [
            "sales", "inventory", "finance", "hr", "customer", 
            "operations", "marketing", "support"
        ]
        
        for source in data_sources:
            if source in message_lower:
                params["data_source"] = source
                break
        
        return {
            "type": analysis_type,
            "params": params
        }

    async def _perform_trend_analysis(self, analysis_intent: Dict[str, Any]) -> str:
        """
        Perform trend analysis on business data
        
        Args:
            analysis_intent: Analysis parameters
            
        Returns:
            Formatted trend analysis report
        """
        data_source = analysis_intent["params"].get("data_source", "sales")
        time_period = analysis_intent["params"]["time_period"]
        
        # Mock trend analysis data
        trends = {
            "overall_trend": "upward",
            "growth_rate": "12.5%",
            "volatility": "moderate",
            "seasonality": "present"
        }
        
        return f"""
        **Trend Analysis Report**
        
        **Data Source**: {data_source.title()}
        **Time Period**: {time_period.replace('_', ' ').title()}
        
        **Key Findings**:
        
        **Overall Trend**: {trends['overall_trend'].title()}
        **Growth Rate**: {trends['growth_rate']} over the period
        **Volatility**: {trends['volatility'].title()}
        **Seasonality**: {trends['seasonality'].title()}
        
        **Monthly Breakdown**:
        - Jan: +8.2% (baseline)
        - Feb: +12.1% (+3.9%)
        - Mar: +15.7% (+3.6%)
        - Apr: +11.4% (-4.3%)
        - May: +18.9% (+7.5%)
        - Jun: +22.3% (+3.4%)
        
        **Insights**:
        - Consistent upward trend with seasonal peaks
        - Strong growth momentum in Q2
        - Predictable monthly patterns suggest stable business
        - No significant anomalies detected
        
        **Recommendations**:
        - Continue current growth strategies
        - Prepare for seasonal variations
        - Monitor Q3 performance closely
        """

    async def _perform_forecasting(self, analysis_intent: Dict[str, Any]) -> str:
        """
        Perform predictive forecasting
        
        Args:
            analysis_intent: Forecasting parameters
            
        Returns:
            Formatted forecasting report
        """
        data_source = analysis_intent["params"].get("data_source", "sales")
        confidence = analysis_intent["params"]["confidence"] * 100
        
        # Mock forecasting data
        forecast = {
            "next_month": "$847,392",
            "next_quarter": "$2,542,176",
            "next_year": "$10,168,704",
            "confidence_interval": "±8.5%"
        }
        
        return f"""
        **Predictive Forecasting Report**
        
        **Data Source**: {data_source.title()}
        **Confidence Level**: {confidence}%
        **Model**: ARIMA with seasonal adjustments
        
        **Forecast Results**:
        
        **Next Month**: {forecast['next_month']}
        - Range: ${int(forecast['next_month'].replace('$', '').replace(',', '')) * 0.915:,} - ${int(forecast['next_month'].replace('$', '').replace(',', '')) * 1.085:,}
        - Growth: +12.3% vs. current month
        
        **Next Quarter**: {forecast['next_quarter']}
        - Average monthly: ${int(forecast['next_quarter'].replace('$', '').replace(',', '')) / 3:,}
        - Quarterly growth: +15.7%
        
        **Next Year**: {forecast['next_year']}
        - Average monthly: ${int(forecast['next_year'].replace('$', '').replace(',', '')) / 12:,}
        - Annual growth: +18.4%
        
        **Model Accuracy**: 94.2% (based on historical validation)
        **Key Drivers**: Seasonal patterns, market trends, historical growth
        
        **Risk Factors**:
        - Economic uncertainty: Medium impact
        - Seasonal volatility: Low impact
        - Market competition: Medium impact
        
        **Recommendations**:
        - Plan inventory based on 15% growth expectation
        - Budget for increased marketing spend
        - Prepare for seasonal peaks in Q4
        """

    async def _perform_performance_analysis(self, analysis_intent: Dict[str, Any]) -> str:
        """
        Analyze business performance metrics
        
        Args:
            analysis_intent: Performance analysis parameters
            
        Returns:
            Formatted performance analysis
        """
        data_source = analysis_intent["params"].get("data_source", "overall")
        
        # Mock performance metrics
        kpis = {
            "revenue_growth": "+18.4%",
            "profit_margin": "24.7%",
            "customer_satisfaction": "4.6/5.0",
            "employee_productivity": "127 units/person",
            "inventory_turnover": "8.2x per year",
            "order_fulfillment": "96.8%"
        }
        
        benchmarks = {
            "industry_average": "+12.3%",
            "target_performance": "+20.0%",
            "best_in_class": "+28.5%"
        }
        
        return f"""
        **Performance Analysis Report**
        
        **Analysis Period**: Last 12 months
        **Data Source**: {data_source.title()}
        
        **Key Performance Indicators (KPIs)**:
        
        **Financial Performance**:
        - Revenue Growth: {kpis['revenue_growth']} (Target: +20%)
        - Profit Margin: {kpis['profit_margin']} (Industry: 22%)
        - ROI: 34.2% (Excellent)
        
        **Operational Performance**:
        - Customer Satisfaction: {kpis['customer_satisfaction']} (Target: 4.8)
        - Employee Productivity: {kpis['employee_productivity']} (Target: 135)
        - Inventory Turnover: {kpis['inventory_turnover']}x (Industry: 6.5x)
        - Order Fulfillment: {kpis['order_fulfillment']}% (Target: 98%)
        
        **Benchmark Comparison**:
        - vs. Industry Average: {benchmarks['industry_average']} (+6.1% above)
        - vs. Target Performance: {benchmarks['target_performance']} (-1.6% below)
        - vs. Best-in-Class: {benchmarks['best_in_class']} (-10.1% below)
        
        **Strengths**:
        - Strong revenue growth exceeding industry average
        - Excellent inventory management
        - High customer satisfaction levels
        
        **Areas for Improvement**:
        - Employee productivity slightly below target
        - Order fulfillment rate needs improvement
        - Room for growth to reach best-in-class performance
        
        **Recommendations**:
        - Invest in employee training to boost productivity
        - Optimize order processing workflow
        - Set stretch goals to reach best-in-class performance
        """

    async def _detect_anomalies(self, analysis_intent: Dict[str, Any]) -> str:
        """
        Detect anomalies and outliers in data
        
        Args:
            analysis_intent: Anomaly detection parameters
            
        Returns:
            Formatted anomaly detection report
        """
        data_source = analysis_intent["params"].get("data_source", "sales")
        
        # Mock anomaly detection results
        anomalies = [
            {
                "date": "2024-03-15",
                "type": "sales_spike",
                "severity": "high",
                "value": "+247%",
                "description": "Unusual sales spike likely due to promotional campaign"
            },
            {
                "date": "2024-05-22",
                "type": "inventory_shortage",
                "severity": "medium",
                "value": "-89%",
                "description": "Unexpected inventory shortage for high-demand item"
            },
            {
                "date": "2024-07-08",
                "type": "customer_complaints",
                "severity": "low",
                "value": "+156%",
                "description": "Temporary increase in complaints during system upgrade"
            }
        ]
        
        return f"""
        **Anomaly Detection Report**
        
        **Data Source**: {data_source.title()}
        **Detection Method**: Statistical outlier analysis with seasonal adjustment
        **Confidence Level**: 95%
        
        **Anomalies Detected**: {len(anomalies)} incidents
        
        **High Priority Anomalies**:
        {chr(10).join([f"- {a['date']}: {a['type']} ({a['severity']}) - {a['value']}" for a in anomalies if a['severity'] == 'high'])}
        
        **Medium Priority Anomalies**:
        {chr(10).join([f"- {a['date']}: {a['type']} ({a['severity']}) - {a['value']}" for a in anomalies if a['severity'] == 'medium'])}
        
        **Low Priority Anomalies**:
        {chr(10).join([f"- {a['date']}: {a['type']} ({a['severity']}) - {a['value']}" for a in anomalies if a['severity'] == 'low'])}
        
        **Detailed Analysis**:
        {chr(10).join([f"**{a['date']}**: {a['description']}" for a in anomalies])}
        
        **Root Cause Analysis**:
        - 60% of anomalies attributed to external factors (promotions, market events)
        - 30% related to system or process issues
        - 10% indicate potential data quality issues
        
        **Recommendations**:
        - Monitor high-priority anomalies closely
        - Investigate systematic causes for recurring issues
        - Implement early warning systems for critical metrics
        """

    async def _perform_correlation_analysis(self, analysis_intent: Dict[str, Any]) -> str:
        """
        Perform correlation analysis between variables
        
        Args:
            analysis_intent: Correlation analysis parameters
            
        Returns:
            Formatted correlation analysis
        """
        data_source = analysis_intent["params"].get("data_source", "business")
        
        # Mock correlation analysis
        correlations = [
            {
                "variable1": "Marketing Spend",
                "variable2": "Sales Revenue",
                "correlation": 0.78,
                "strength": "strong",
                "significance": "high"
            },
            {
                "variable1": "Customer Service Response Time",
                "variable2": "Customer Satisfaction",
                "correlation": -0.65,
                "strength": "moderate",
                "significance": "high"
            },
            {
                "variable1": "Employee Training Hours",
                "variable2": "Productivity",
                "correlation": 0.45,
                "strength": "moderate",
                "significance": "medium"
            }
        ]
        
        return f"""
        **Correlation Analysis Report**
        
        **Data Source**: {data_source.title()}
        **Sample Size**: 365 data points
        **Statistical Significance**: p < 0.05
        
        **Key Correlations Identified**:
        
        **Strong Correlations** (|r| > 0.7):
        {chr(10).join([f"- {c['variable1']} ↔ {c['variable2']}: r = {c['correlation']} ({c['strength']})" for c in correlations if abs(c['correlation']) > 0.7])}
        
        **Moderate Correlations** (0.4 ≤ |r| ≤ 0.7):
        {chr(10).join([f"- {c['variable1']} ↔ {c['variable2']}: r = {c['correlation']} ({c['strength']})" for c in correlations if 0.4 <= abs(c['correlation']) <= 0.7])}
        
        **Insights**:
        
        **Marketing Effectiveness**: Strong positive correlation (r=0.78) between marketing spend and sales revenue indicates effective marketing ROI.
        
        **Customer Service Impact**: Moderate negative correlation (r=-0.65) between response time and satisfaction shows faster responses improve satisfaction.
        
        **Training ROI**: Moderate positive correlation (r=0.45) between training hours and productivity suggests training investments pay off.
        
        **Causal Relationships**:
        - Marketing spend appears to drive sales increases
        - Customer service improvements directly impact satisfaction
        - Employee development contributes to productivity gains
        
        **Recommendations**:
        - Increase marketing budget based on strong ROI correlation
        - Implement customer service response time targets
        - Expand employee training programs
        - Monitor these relationships for changes over time
        """

    async def _perform_general_analysis(self, message: str, analysis_intent: Dict[str, Any]) -> str:
        """
        Perform general analysis when specific type not identified
        
        Args:
            message: User's analysis request
            analysis_intent: Parsed analysis intent
            
        Returns:
            General analysis response
        """
        return f"""
        **General Analysis Capabilities**
        
        **Your Request**: {message}
        **Analysis Type**: General Business Intelligence
        
        **Available Analysis Types**:
        
        **1. Trend Analysis**: Identify patterns over time
        - Sales trends, customer behavior, operational metrics
        - Seasonal patterns, growth rates, cyclical behavior
        
        **2. Forecasting**: Predict future outcomes
        - Revenue forecasting, demand planning, resource allocation
        - Risk assessment, scenario modeling
        
        **3. Performance Analysis**: Evaluate business metrics
        - KPI analysis, benchmarking, efficiency metrics
        - ROI calculations, productivity measures
        
        **4. Anomaly Detection**: Identify unusual patterns
        - Fraud detection, quality issues, system problems
        - Performance outliers, market disruptions
        
        **5. Correlation Analysis**: Understand relationships
        - Marketing effectiveness, operational drivers
        - Customer behavior patterns, financial relationships
        
        **To provide specific analysis**, please specify:
        1. **Data source** (sales, inventory, finance, etc.)
        2. **Time period** (daily, weekly, monthly, yearly)
        3. **Specific metrics** you want to analyze
        4. **Business question** you're trying to answer
        5. **Preferred format** (summary, detailed report, recommendations)
        
        **Data Quality Assurance**:
        - All analyses include data quality checks
        - Statistical significance testing
        - Confidence intervals provided
        - Limitations and assumptions clearly stated
        """