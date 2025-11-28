"""
Chart Generation Service

Creates interactive charts and visualizations for AI responses.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class ChartType:
    """Chart types"""
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    AREA = "area"
    SCATTER = "scatter"
    DONUT = "donut"


class ChartService:
    """Service for generating chart data"""
    
    def generate_sales_chart(self, period: str = "month", 
                            chart_type: str = ChartType.LINE) -> Dict[str, Any]:
        """
        Generate sales chart data
        
        Args:
            period: Time period (day, week, month, year)
            chart_type: Type of chart
            
        Returns:
            Chart configuration for frontend
        """
        # Generate sample data based on period
        if period == "month":
            labels = self._get_month_labels()
            data = [12000, 19000, 15000, 25000, 22000, 30000, 28000, 32000, 35000, 38000, 40000, 42000]
        elif period == "week":
            labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            data = [5000, 6000, 5500, 7000, 8500, 9000, 7500]
        elif period == "year":
            labels = ["2020", "2021", "2022", "2023", "2024"]
            data = [250000, 320000, 380000, 450000, 520000]
        else:
            labels = ["Q1", "Q2", "Q3", "Q4"]
            data = [95000, 110000, 125000, 140000]
        
        return {
            "type": "widget",
            "widgetType": "chart",
            "data": {
                "chartType": chart_type,
                "title": f"Sales Trend - {period.capitalize()}",
                "labels": labels,
                "datasets": [{
                    "label": "Sales Revenue",
                    "data": data,
                    "borderColor": "rgb(59, 130, 246)",
                    "backgroundColor": "rgba(59, 130, 246, 0.1)",
                    "tension": 0.4
                }]
            }
        }
    
    def generate_forecast_chart(self, metric: str = "revenue", 
                               periods: int = 3) -> Dict[str, Any]:
        """Generate forecast chart with predictions"""
        historical_labels = ["Q1", "Q2", "Q3", "Q4"]
        historical_data = [95000, 110000, 125000, 140000]
        
        forecast_labels = [f"Q{i+1} 2024" for i in range(periods)]
        forecast_data = [155000, 170000, 185000][:periods]
        
        all_labels = historical_labels + forecast_labels
        
        return {
            "type": "widget",
            "widgetType": "chart",
            "data": {
                "chartType": ChartType.LINE,
                "title": f"{metric.capitalize()} Forecast",
                "labels": all_labels,
                "datasets": [
                    {
                        "label": "Actual",
                        "data": historical_data + [None] * periods,
                        "borderColor": "rgb(34, 197, 94)",
                        "backgroundColor": "rgba(34, 197, 94, 0.1)",
                        "tension": 0.4
                    },
                    {
                        "label": "Forecast",
                        "data": [None] * len(historical_data) + forecast_data,
                        "borderColor": "rgb(249, 115, 22)",
                        "backgroundColor": "rgba(249, 115, 22, 0.1)",
                        "borderDash": [5, 5],
                        "tension": 0.4
                    }
                ]
            }
        }
    
    def generate_category_pie_chart(self, categories: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Generate pie chart for category distribution"""
        if not categories:
            categories = [
                {"name": "Electronics", "value": 42},
                {"name": "Clothing", "value": 28},
                {"name": "Home & Garden", "value": 18},
                {"name": "Sports", "value": 12}
            ]
        
        return {
            "type": "widget",
            "widgetType": "chart",
            "data": {
                "chartType": ChartType.PIE,
                "title": "Revenue by Category",
                "labels": [cat["name"] for cat in categories],
                "datasets": [{
                    "data": [cat["value"] for cat in categories],
                    "backgroundColor": [
                        "rgb(59, 130, 246)",
                        "rgb(34, 197, 94)",
                        "rgb(249, 115, 22)",
                        "rgb(168, 85, 247)"
                    ]
                }]
            }
        }
    
    def generate_comparison_bar_chart(self, comparison_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Generate bar chart for comparisons"""
        if not comparison_data:
            comparison_data = {
                "labels": ["North", "South", "East", "West"],
                "datasets": [
                    {
                        "label": "Q3 2023",
                        "data": [45000, 38000, 52000, 41000]
                    },
                    {
                        "label": "Q4 2023",
                        "data": [52000, 43000, 58000, 47000]
                    }
                ]
            }
        
        return {
            "type": "widget",
            "widgetType": "chart",
            "data": {
                "chartType": ChartType.BAR,
                "title": "Regional Sales Comparison",
                "labels": comparison_data["labels"],
                "datasets": [
                    {
                        **dataset,
                        "backgroundColor": f"rgba({59 + i*50}, {130 + i*30}, {246 - i*40}, 0.8)"
                    }
                    for i, dataset in enumerate(comparison_data["datasets"])
                ]
            }
        }
    
    def generate_kpi_widget(self, kpis: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Generate KPI metrics widget"""
        if not kpis:
            kpis = [
                {
                    "label": "Total Revenue",
                    "value": "$520,000",
                    "change": "+12.5%",
                    "trend": "up"
                },
                {
                    "label": "Active Customers",
                    "value": "1,234",
                    "change": "+8.3%",
                    "trend": "up"
                },
                {
                    "label": "Avg Order Value",
                    "value": "$421",
                    "change": "-2.1%",
                    "trend": "down"
                },
                {
                    "label": "Conversion Rate",
                    "value": "3.2%",
                    "change": "+0.5%",
                    "trend": "up"
                }
            ]
        
        return {
            "type": "widget",
            "widgetType": "kpi",
            "data": {
                "title": "Key Performance Indicators",
                "metrics": kpis
            }
        }
    
    def generate_data_table_widget(self, data: Optional[List[Dict]] = None, 
                                   title: str = "Data Table") -> Dict[str, Any]:
        """Generate data table widget"""
        if not data:
            data = [
                {"customer": "Acme Corp", "revenue": "$125,000", "orders": 45, "status": "Active"},
                {"customer": "TechStart Inc", "revenue": "$98,000", "orders": 32, "status": "Active"},
                {"customer": "Global Solutions", "revenue": "$87,000", "orders": 28, "status": "Active"},
                {"customer": "Innovation Labs", "revenue": "$76,000", "orders": 24, "status": "Active"},
                {"customer": "Digital Dynamics", "revenue": "$65,000", "orders": 19, "status": "Active"}
            ]
        
        return {
            "type": "widget",
            "widgetType": "table",
            "data": {
                "title": title,
                "columns": list(data[0].keys()) if data else [],
                "rows": data
            }
        }
    
    def _get_month_labels(self) -> List[str]:
        """Get month labels for current year"""
        return ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    def create_chart_from_query(self, query: str, data: Any) -> Dict[str, Any]:
        """
        Create appropriate chart based on user query and data
        
        Args:
            query: User's query
            data: Data to visualize
            
        Returns:
            Chart widget configuration
        """
        query_lower = query.lower()
        
        # Determine chart type from query
        if "forecast" in query_lower or "predict" in query_lower:
            return self.generate_forecast_chart()
        elif "compare" in query_lower or "comparison" in query_lower:
            return self.generate_comparison_bar_chart()
        elif "category" in query_lower or "distribution" in query_lower:
            return self.generate_category_pie_chart()
        elif "kpi" in query_lower or "metrics" in query_lower:
            return self.generate_kpi_widget()
        elif "table" in query_lower or "list" in query_lower:
            return self.generate_data_table_widget()
        else:
            # Default to sales chart
            return self.generate_sales_chart()


# Global instance
chart_service = ChartService()
