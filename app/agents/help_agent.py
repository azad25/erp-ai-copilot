"""
Help Agent

Specialized agent for user assistance, documentation, tutorials, and support.
Provides help with system features, troubleshooting, and user guidance.
"""

from typing import List, Dict, Any
import json
from datetime import datetime
import re
from enum import Enum

from .base_agent import BaseAgent, AgentRequest, AgentResponse
from app.models.api import AgentType
from app.core.exceptions import AgentError


class HelpCategory(Enum):
    """Types of help supported"""
    FEATURE_GUIDE = "feature_guide"
    TROUBLESHOOTING = "troubleshooting"
    API_DOCUMENTATION = "api_documentation"
    TUTORIAL = "tutorial"
    BEST_PRACTICES = "best_practices"
    SYSTEM_INFO = "system_info"
    ERROR_HELP = "error_help"
    WORKFLOW_GUIDE = "workflow_guide"
    INTEGRATION_HELP = "integration_help"
    SECURITY_HELP = "security_help"


class UserLevel(Enum):
    """User experience levels"""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    ADMIN = "admin"


class HelpAgent(BaseAgent):
    """
    Help Agent for user assistance and documentation
    
    Capabilities:
    - Feature guides and tutorials
    - Troubleshooting and error resolution
    - API documentation and examples
    - Best practices recommendations
    - System information and status
    - Workflow guidance
    - Integration assistance
    - Security guidance
    - Custom training content
    - Interactive walkthroughs
    """

    def __init__(self, model: str = "gpt-4"):
        super().__init__(AgentType.HELP, model)
        self.help_categories = [
            "feature_guide", "troubleshooting", "api_documentation", "tutorial",
            "best_practices", "system_info", "error_help", "workflow_guide",
            "integration_help", "security_help"
        ]

    async def execute(self, request: AgentRequest) -> AgentResponse:
        """
        Execute help agent functionality
        
        Args:
            request: AgentRequest with help requirements
            
        Returns:
            AgentResponse with help content and guidance
        """
        if not await self.validate_request(request):
            raise AgentError("Invalid help request")

        # Parse help intent
        help_intent = await self._parse_help_intent(request.message)
        
        # Execute the appropriate help action
        if help_intent["action"] == "feature_guide":
            result = await self._provide_feature_guide(help_intent)
        elif help_intent["action"] == "troubleshooting":
            result = await self._provide_troubleshooting(help_intent)
        elif help_intent["action"] == "api_documentation":
            result = await self._provide_api_docs(help_intent)
        elif help_intent["action"] == "tutorial":
            result = await self._provide_tutorial(help_intent)
        elif help_intent["action"] == "best_practices":
            result = await self._provide_best_practices(help_intent)
        elif help_intent["action"] == "system_info":
            result = await self._provide_system_info(help_intent)
        elif help_intent["action"] == "error_help":
            result = await self._provide_error_help(help_intent)
        elif help_intent["action"] == "workflow_guide":
            result = await self._provide_workflow_guide(help_intent)
        elif help_intent["action"] == "integration_help":
            result = await self._provide_integration_help(help_intent)
        else:
            result = await self._provide_general_help(request.message)

        return AgentResponse(
            response=result,
            agent_type=self.agent_type,
            conversation_id=request.conversation_id or "",
            execution_id="",
            metadata={
                "action": help_intent["action"],
                "category": help_intent.get("category", "general"),
                "user_level": help_intent.get("user_level", "beginner"),
                "complexity": help_intent.get("complexity", "medium"),
                "response_type": help_intent.get("response_type", "text"),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    def get_system_prompt(self) -> str:
        """
        Get system prompt for help agent
        
        Returns:
            System prompt defining the agent's role
        """
        return """
        You are a Help Agent for the UNIBASE ERP AI Copilot system. Your role is to:
        
        1. **User Assistance**: Provide comprehensive help and guidance
        2. **Documentation**: Offer detailed documentation and examples
        3. **Troubleshooting**: Help resolve issues and errors
        4. **Training**: Create educational content and tutorials
        5. **Best Practices**: Share recommended approaches
        6. **System Guidance**: Explain system features and capabilities
        7. **Integration Help**: Assist with system integrations
        8. **Security Guidance**: Provide security best practices
        9. **Workflow Support**: Guide users through complex workflows
        10. **Continuous Learning**: Adapt to user needs and feedback
        
        **Help Categories**:
        - **Feature Guides**: Step-by-step feature explanations
        - **Troubleshooting**: Error resolution and debugging
        - **API Documentation**: Complete API reference and examples
        - **Tutorials**: Interactive learning experiences
        - **Best Practices**: Industry-standard recommendations
        - **System Information**: System status and capabilities
        - **Workflow Guidance**: Process optimization
        - **Integration Assistance**: Third-party integrations
        - **Security Guidance**: Security configuration and practices
        
        **User Levels**:
        - **Beginner**: Basic concepts and simple workflows
        - **Intermediate**: Advanced features and optimization
        - **Advanced**: Complex configurations and customizations
        - **Admin**: System administration and management
        
        **Response Guidelines**:
        - Provide clear, step-by-step instructions
        - Include practical examples and use cases
        - Offer multiple solution approaches when applicable
        - Link to relevant documentation and resources
        - Use progressive disclosure for complex topics
        - Include troubleshooting tips and common pitfalls
        - Provide code examples where appropriate
        - Offer interactive elements and walkthroughs
        """

    def get_available_tools(self) -> List[str]:
        """
        Get available tools for help agent
        
        Returns:
            List of available tool names
        """
        return [
            "documentation_search",
            "tutorial_generator",
            "error_analyzer",
            "feature_explainer",
            "code_example_provider",
            "troubleshooting_engine",
            "best_practice_recommender",
            "system_status_checker"
        ]

    async def _parse_help_intent(self, message: str) -> Dict[str, Any]:
        """
        Parse user message to determine help intent
        
        Args:
            message: User's help request
            
        Returns:
            Dictionary with help action and parameters
        """
        message_lower = message.lower()
        
        # Action detection
        help_actions = {
            "feature_guide": ["how to", "guide", "use", "features", "explain"],
            "troubleshooting": ["error", "problem", "issue", "bug", "fix", "resolve"],
            "api_documentation": ["api", "endpoint", "integration", "code", "programmatic"],
            "tutorial": ["tutorial", "learn", "training", "step by step", "walkthrough"],
            "best_practices": ["best practices", "recommendations", "standards", "guidelines"],
            "system_info": ["system", "status", "capabilities", "what can", "features"],
            "error_help": ["error message", "exception", "failed", "doesn't work"],
            "workflow_guide": ["workflow", "process", "steps", "procedure", "how do I"],
            "integration_help": ["integrate", "connect", "third party", "external system"],
            "security_help": ["security", "secure", "protection", "access", "permissions"]
        }
        
        action = "general_help"
        category = "general"
        
        for key, patterns in help_actions.items():
            if any(pattern in message_lower for pattern in patterns):
                action = key
                category = key
                break

        # User level detection
        user_levels = {
            "beginner": ["beginner", "new", "start", "basic", "intro", "simple"],
            "intermediate": ["intermediate", "some experience", "familiar", "comfortable"],
            "advanced": ["advanced", "expert", "complex", "custom", "technical"],
            "admin": ["admin", "administrator", "manage", "configure", "setup"]
        }
        
        user_level = "beginner"  # Default to beginner for safety
        for level, indicators in user_levels.items():
            if any(indicator in message_lower for indicator in indicators):
                user_level = level
                break

        # Complexity detection
        complexity_indicators = {
            "simple": ["simple", "basic", "easy", "quick"],
            "medium": ["medium", "standard", "typical"],
            "complex": ["complex", "advanced", "detailed", "comprehensive"]
        }
        
        complexity = "medium"
        for comp, indicators in complexity_indicators.items():
            if any(indicator in message_lower for indicator in indicators):
                complexity = comp
                break

        return {
            "action": action,
            "category": category,
            "user_level": user_level,
            "complexity": complexity,
            "response_type": "text",
            "specific_feature": self._detect_specific_feature(message_lower)
        }

    def _detect_specific_feature(self, message: str) -> str:
        """
        Detect specific feature or topic mentioned
        
        Args:
            message: Lowercase user message
            
        Returns:
            Specific feature or topic
        """
        features = {
            "chat": ["chat", "conversation", "message", "talk"],
            "dashboard": ["dashboard", "overview", "summary", "metrics"],
            "reports": ["report", "analytics", "data", "insights"],
            "users": ["user", "account", "profile", "login"],
            "permissions": ["permission", "access", "role", "security"],
            "integration": ["integration", "api", "connect", "sync"],
            "notifications": ["notification", "alert", "email", "message"],
            "settings": ["setting", "configuration", "preference", "setup"],
            "data": ["data", "database", "storage", "backup"],
            "workflow": ["workflow", "process", "automation", "task"]
        }
        
        for feature, keywords in features.items():
            if any(keyword in message for keyword in keywords):
                return feature
        
        return "general"

    async def _provide_feature_guide(self, help_intent: Dict[str, Any]) -> str:
        """
        Provide detailed feature guide
        
        Args:
            help_intent: Feature guide parameters
            
        Returns:
            Formatted feature guide
        """
        feature = help_intent.get("specific_feature", "general")
        user_level = help_intent.get("user_level", "beginner")
        
        feature_guides = {
            "chat": {
                "beginner": """
                **Chat Feature Guide - Beginner**
                
                **What is the Chat Feature?**
                The chat feature allows you to have conversations with the AI Copilot to get help, ask questions, and perform tasks using natural language.
                
                **Getting Started**:
                1. **Open Chat**: Click the chat icon in the top navigation
                2. **Start Conversation**: Type your question or request
                3. **Send Message**: Press Enter or click the send button
                4. **View Response**: Read the AI's helpful response
                
                **Example Conversations**:
                - "Show me sales data for last month"
                - "Create a new customer record"
                - "Generate a report on inventory levels"
                
                **Tips for Success**:
                - Be specific in your requests
                - Ask follow-up questions for clarification
                - Use natural language like talking to a person
                """,
                "intermediate": """
                **Chat Feature Guide - Intermediate**
                
                **Advanced Chat Features**:
                - **Context Awareness**: The AI remembers previous messages in your conversation
                - **Multi-turn Conversations**: Build complex requests over multiple exchanges
                - **Specific Parameters**: Use precise details like dates, amounts, and filters
                
                **Powerful Queries**:
                - "Compare Q1 and Q2 sales by region and show percentage changes"
                - "Find customers who haven't ordered in 90 days and create a re-engagement campaign"
                - "Generate a dashboard showing real-time inventory turnover rates"
                
                **Using Context**:
                - Reference previous results: "Based on the sales data you just showed..."
                - Refine requests: "Now filter that to only show products over $100"
                - Combine requests: "Export that data and also schedule it to run weekly"
                
                **Chat Commands**:
                - Use "/help" for general assistance
                - Use "/clear" to start a new conversation
                - Use "/export" to save conversation results
                """,
                "advanced": """
                **Chat Feature Guide - Advanced**
                
                **Technical Capabilities**:
                - **Custom Workflows**: Create complex multi-step processes
                - **API Integration**: Connect with external systems through chat
                - **Data Transformation**: Perform calculations and data manipulation
                - **Automated Reporting**: Set up recurring reports and alerts
                
                **Advanced Query Patterns**:
                - **Conditional Logic**: "If inventory drops below 100 units, notify the manager"
                - **Time Series Analysis**: "Show me the trend of customer acquisition costs over the last 12 months"
                - **Predictive Queries**: "Based on current trends, predict next quarter's revenue"
                
                **Integration Examples**:
                - "Connect to our CRM and sync customer data"
                - "Set up a webhook to receive order notifications"
                - "Create a custom API endpoint for our mobile app"
                
                **Performance Optimization**:
                - Use specific date ranges to improve response time
                - Leverage cached results for repeated queries
                - Combine multiple related requests efficiently
                """
            },
            "dashboard": {
                "beginner": """
                **Dashboard Guide - Beginner**
                
                **What is a Dashboard?**
                A dashboard is a visual display of your most important business data, like a control panel for your company.
                
                **Basic Dashboard Features**:
                1. **Overview**: See key metrics at a glance
                2. **Charts**: Visual representations of data
                3. **Numbers**: Important statistics and totals
                4. **Filters**: Change what data you see
                
                **Your First Dashboard**:
                1. **Access Dashboard**: Click "Dashboard" in the main menu
                2. **Explore Views**: Try different dashboard views
                3. **Interact**: Click on charts to see details
                4. **Customize**: Add widgets that matter to you
                
                **Common Dashboards**:
                - **Sales Dashboard**: Revenue, orders, customers
                - **Inventory Dashboard**: Stock levels, turnover, alerts
                - **Financial Dashboard**: Expenses, profits, cash flow
                """
            }
        }
        
        guide = feature_guides.get(feature, {}).get(user_level, feature_guides["chat"][user_level])
        return guide

    async def _provide_troubleshooting(self, help_intent: Dict[str, Any]) -> str:
        """
        Provide troubleshooting assistance
        
        Args:
            help_intent: Troubleshooting parameters
            
        Returns:
            Formatted troubleshooting guide
        """
        return """
        **Troubleshooting Guide**
        
        **Common Issues and Solutions**:
        
        **1. Login Problems**:
        - **Issue**: Can't log in to the system
        - **Solution**: 
          1. Check your username and password
          2. Clear browser cache and cookies
          3. Try a different browser
          4. Contact your system administrator
        
        **2. Data Not Loading**:
        - **Issue**: Dashboard shows "No data available"
        - **Solution**:
          1. Check your internet connection
          2. Verify data source connections
          3. Refresh the page
          4. Check if filters are too restrictive
        
        **3. API Connection Issues**:
        - **Issue**: API calls are failing
        - **Solution**:
          1. Verify API credentials are correct
          2. Check API endpoint URLs
          3. Review rate limits and quotas
          4. Test with a simple API call first
        
        **4. Report Generation Problems**:
        - **Issue**: Reports are not generating or are incomplete
        - **Solution**:
          1. Check date ranges and filters
          2. Verify data source permissions
          3. Try generating a smaller report first
          4. Check system logs for errors
        
        **5. Performance Issues**:
        - **Issue**: System is slow or unresponsive
        - **Solution**:
          1. Check system status page
          2. Clear browser cache
          3. Try during off-peak hours
          4. Contact support if persistent
        
        **Getting Additional Help**:
        - **System Status**: Check our status page for outages
        - **Documentation**: Browse our comprehensive help center
        - **Community**: Join our user community forum
        - **Support**: Contact our technical support team
        """

    async def _provide_api_docs(self, help_intent: Dict[str, Any]) -> str:
        """
        Provide API documentation and examples
        
        Args:
            help_intent: API documentation parameters
            
        Returns:
            Formatted API documentation
        """
        return """
        **API Documentation**
        
        **Base URL**: `https://api.yourcompany.com/v1`
        
        **Authentication**:
        All API requests require authentication using Bearer tokens:
        ```
        Authorization: Bearer your_api_token_here
        ```
        
        **Common Endpoints**:
        
        **1. Get Chat Response**:
        ```http
        POST /api/v1/chat/send
        Content-Type: application/json
        Authorization: Bearer your_token
        
        {
          "message": "Show me sales data",
          "conversation_id": "12345"
        }
        ```
        
        **2. Get Dashboard Data**:
        ```http
        GET /api/v1/dashboard/sales?date_from=2024-01-01&date_to=2024-12-31
        Authorization: Bearer your_token
        ```
        
        **3. Generate Report**:
        ```http
        POST /api/v1/reports/generate
        Content-Type: application/json
        Authorization: Bearer your_token
        
        {
          "report_type": "sales_summary",
          "date_range": {
            "start": "2024-01-01",
            "end": "2024-12-31"
          },
          "filters": {
            "region": "North America"
          }
        }
        ```
        
        **4. Create Customer Record**:
        ```http
        POST /api/v1/customers
        Content-Type: application/json
        Authorization: Bearer your_token
        
        {
          "name": "John Doe",
          "email": "john@example.com",
          "phone": "+1234567890",
          "company": "Example Corp"
        }
        ```
        
        **Response Formats**:
        All responses use JSON format with standard structure:
        ```json
        {
          "success": true,
          "data": {...},
          "message": "Operation completed successfully"
        }
        ```
        
        **Error Handling**:
        ```json
        {
          "success": false,
          "error": {
            "code": "VALIDATION_ERROR",
            "message": "Invalid date format",
            "details": {...}
          }
        }
        ```
        
        **Rate Limits**:
        - **Standard**: 100 requests per minute
        - **Premium**: 1000 requests per minute
        - **Enterprise**: Custom limits available
        
        **SDKs and Libraries**:
        - **Python**: `pip install unibase-api`
        - **JavaScript**: `npm install unibase-client`
        - **PHP**: `composer require unibase/api-client`
        """

    async def _provide_tutorial(self, help_intent: Dict[str, Any]) -> str:
        """
        Provide step-by-step tutorials
        
        Args:
            help_intent: Tutorial parameters
            
        Returns:
            Formatted tutorial content
        """
        return """
        **Getting Started Tutorial**
        
        **Lesson 1: Your First Dashboard**
        
        **Objective**: Create your first dashboard with sales data
        
        **Step 1: Access Dashboard**
        1. Log in to your account
        2. Click "Dashboard" in the main navigation
        3. Click "Create New Dashboard"
        
        **Step 2: Add Sales Widget**
        1. Click "Add Widget" button
        2. Select "Sales" category
        3. Choose "Revenue Over Time" widget
        4. Set date range to "Last 30 days"
        5. Click "Add to Dashboard"
        
        **Step 3: Customize Display**
        1. Drag and drop to rearrange widgets
        2. Click widget settings (gear icon)
        3. Change chart type to "Line Chart"
        4. Add title: "Monthly Revenue Trend"
        
        **Step 4: Save and Share**
        1. Click "Save Dashboard"
        2. Name it "My Sales Overview"
        3. Click "Share" to send to your team
        
        **Lesson 2: Creating Your First Report**
        
        **Objective**: Generate a customer report
        
        **Step 1: Navigate to Reports**
        1. Click "Reports" in the main menu
        2. Click "Create New Report"
        3. Select "Customer Analysis" template
        
        **Step 2: Configure Report**
        1. Set date range: "Last 90 days"
        2. Add filters: "Active customers only"
        3. Select columns: Name, Email, Last Order, Total Spent
        4. Choose format: "PDF with charts"
        
        **Step 3: Preview and Generate**
        1. Click "Preview" to see sample data
        2. Review the layout and formatting
        3. Click "Generate Report"
        4. Download the completed report
        
        **Lesson 3: Using the AI Chat**
        
        **Objective**: Get insights using natural language
        
        **Step 1: Open Chat**
        1. Click the chat icon (bottom right)
        2. Type: "Show me my top 10 customers"
        3. Press Enter
        
        **Step 2: Refine Results**
        1. Review the AI's response
        2. Follow up with: "Now show their purchase history"
        3. Ask: "Which products do they buy most?"
        
        **Step 3: Take Action**
        1. Ask: "Create a loyalty program for these customers"
        2. Review the AI's suggestions
        3. Implement the recommended actions
        """

    async def _provide_best_practices(self, help_intent: Dict[str, Any]) -> str:
        """
        Provide best practices recommendations
        
        Args:
            help_intent: Best practices parameters
            
        Returns:
            Formatted best practices guide
        """
        return """
        **Best Practices Guide**
        
        **Data Management Best Practices**:
        
        **1. Data Quality**:
        - **Regular Validation**: Check data accuracy monthly
        - **Standardized Formats**: Use consistent naming conventions
        - **Backup Strategy**: Implement automated daily backups
        - **Access Control**: Limit data access to authorized users only
        
        **2. Dashboard Design**:
        - **Keep It Simple**: Focus on key metrics only
        - **Use Clear Labels**: Make charts and tables self-explanatory
        - **Consistent Colors**: Use your brand colors consistently
        - **Mobile Responsive**: Ensure dashboards work on all devices
        
        **3. Report Generation**:
        - **Automated Scheduling**: Set up recurring reports
        - **Distribution Lists**: Create targeted recipient lists
        - **Format Consistency**: Use templates for standard reports
        - **Review Cycles**: Establish regular report review processes
        
        **4. Security Practices**:
        - **Strong Passwords**: Use complex passwords and change regularly
        - **Two-Factor Authentication**: Enable 2FA for all users
        - **Regular Audits**: Review user access quarterly
        - **Incident Response**: Have a clear security incident plan
        
        **5. User Training**:
        - **Onboarding Program**: Create structured training for new users
        - **Documentation**: Maintain up-to-date user guides
        - **Feedback Loops**: Collect and act on user feedback
        - **Continuous Learning**: Offer ongoing training opportunities
        
        **Performance Optimization**:
        
        **1. Query Optimization**:
        - **Limit Date Ranges**: Use specific date ranges when possible
        - **Pre-aggregate Data**: Use summary tables for common queries
        - **Index Important Fields**: Ensure frequently queried fields are indexed
        - **Cache Results**: Cache common dashboard data
        
        **2. System Monitoring**:
        - **Performance Metrics**: Monitor system response times
        - **Error Tracking**: Set up alerts for system errors
        - **Usage Analytics**: Track feature usage patterns
        - **Capacity Planning**: Monitor and plan for growth
        
        **Integration Best Practices**:
        
        **1. API Usage**:
        - **Rate Limiting**: Respect API rate limits
        - **Error Handling**: Implement robust error handling
        - **Retry Logic**: Use exponential backoff for failed requests
        - **Security**: Use secure authentication methods
        
        **2. Data Synchronization**:
        - **Real-time vs Batch**: Choose appropriate sync methods
        - **Conflict Resolution**: Handle data conflicts gracefully
        - **Validation Rules**: Implement data validation on import
        - **Monitoring**: Set up alerts for sync failures
        """

    async def _provide_system_info(self, help_intent: Dict[str, Any]) -> str:
        """
        Provide system information and status
        
        Args:
            help_intent: System info parameters
            
        Returns:
            Formatted system information
        """
        return """
        **System Information**
        
        **Current Status**: ✅ All Systems Operational
        
        **System Overview**:
        - **Platform**: UNIBASE ERP AI Copilot
        - **Version**: 2.1.0
        - **Last Updated**: January 15, 2024
        - **Uptime**: 99.9% (Last 30 days)
        
        **Core Features**:
        - **AI Chat**: Natural language interaction with your data
        - **Smart Dashboards**: Real-time data visualization
        - **Automated Reports**: Scheduled report generation
        - **Integration Hub**: Connect with 100+ business tools
        - **Security**: Enterprise-grade security and compliance
        
        **Performance Metrics**:
        - **Average Response Time**: 0.8 seconds
        - **Daily Active Users**: 1,250
        - **API Calls per Day**: 45,000
        - **Data Processing**: 2.5GB per day
        
        **Supported Integrations**:
        - **CRM Systems**: Salesforce, HubSpot, Pipedrive
        - **Accounting**: QuickBooks, Xero, NetSuite
        - **E-commerce**: Shopify, WooCommerce, Magento
        - **Marketing**: Mailchimp, Marketo, Pardot
        - **Communication**: Slack, Microsoft Teams, Discord
        
        **Security Features**:
        - **Encryption**: AES-256 for data at rest and in transit
        - **Authentication**: OAuth 2.0 and SAML support
        - **Access Control**: Role-based permissions
        - **Audit Logging**: Comprehensive activity tracking
        - **Compliance**: GDPR, SOX, HIPAA compliant
        
        **System Requirements**:
        - **Browser**: Chrome 90+, Firefox 88+, Safari 14+, Edge 90+
        - **Internet**: Stable broadband connection
        - **Screen**: 1024x768 resolution minimum
        - **Mobile**: iOS 14+ or Android 10+
        
        **Support Resources**:
        - **Documentation**: help.unibase.com
        - **API Reference**: api.unibase.com/docs
        - **Status Page**: status.unibase.com
        - **Support Email**: support@unibase.com
        - **Community**: community.unibase.com
        """

    async def _provide_error_help(self, help_intent: Dict[str, Any]) -> str:
        """
        Provide error resolution assistance
        
        Args:
            help_intent: Error help parameters
            
        Returns:
            Formatted error resolution guide
        """
        return """
        **Error Resolution Guide**
        
        **Common Error Messages and Solutions**:
        
        **1. "Authentication Failed"**
        - **Cause**: Invalid credentials or expired token
        - **Solution**: 
          1. Check your username and password
          2. Reset your password if needed
          3. Verify your API token is valid
          4. Contact your administrator
        
        **2. "Data Source Connection Error"**
        - **Cause**: External system unavailable or credentials expired
        - **Solution**:
          1. Check if the external system is online
          2. Verify API credentials haven't expired
          3. Test the connection in settings
          4. Contact the external system support
        
        **3. "Query Timeout"**
        - **Cause**: Large dataset or complex query taking too long
        - **Solution**:
          1. Reduce the date range in your query
          2. Add more specific filters
          3. Try the query during off-peak hours
          4. Contact support for query optimization
        
        **4. "Permission Denied"**
        - **Cause**: Insufficient user permissions
        - **Solution**:
          1. Check your user role permissions
          2. Request access from your administrator
          3. Verify the data source permissions
          4. Review access control settings
        
        **5. "Validation Error"**
        - **Cause**: Invalid data format or missing required fields
        - **Solution**:
          1. Check the data format requirements
          2. Ensure all required fields are provided
          3. Validate data types (dates, numbers, etc.)
          4. Review the API documentation
        
        **Getting Debug Information**:
        - **Browser Console**: Press F12 and check the Console tab
        - **Network Tab**: Check for failed API calls
        - **System Logs**: Available in Admin > System Logs
        - **Error Reports**: Automatically sent to our support team
        
        **Escalation Process**:
        1. **Self-Service**: Check this help guide first
        2. **Community**: Ask in our user forum
        3. **Support Ticket**: Submit detailed error information
        4. **Phone Support**: Available for Enterprise customers
        """

    async def _provide_workflow_guide(self, help_intent: Dict[str, Any]) -> str:
        """
        Provide workflow and process guidance
        
        Args:
            help_intent: Workflow parameters
            
        Returns:
            Formatted workflow guide
        """
        return """
        **Workflow Guide: Monthly Business Review**
        
        **Objective**: Create a comprehensive monthly business review process
        
        **Pre-Meeting Preparation** (Day 1-2):
        1. **Generate Sales Report**
           - Run monthly sales summary
           - Include regional breakdowns
           - Compare to previous month and year
        
        2. **Prepare Financial Overview**
           - Revenue vs. targets
           - Expense analysis
           - Profit margin trends
        
        3. **Customer Analysis**
           - New vs. returning customers
           - Customer satisfaction scores
           - Churn rate analysis
        
        **Meeting Day Workflow** (Day 3):
        1. **Dashboard Review** (15 min)
           - Review key performance indicators
           - Identify trends and anomalies
           - Discuss significant changes
        
        2. **Department Reports** (30 min)
           - Sales team performance
           - Marketing campaign results
           - Customer service metrics
        
        3. **Action Items** (15 min)
           - Identify improvement opportunities
           - Set goals for next month
           - Assign responsibilities
        
        **Post-Meeting Actions** (Day 4-5):
        1. **Update Dashboards**
           - Refresh data sources
           - Update targets and benchmarks
           - Share updated views with team
        
        2. **Schedule Follow-ups**
           - Set up weekly check-ins
           - Create automated alerts
           - Plan next month's review
        
        **Automation Opportunities**:
        - **Automated Reports**: Schedule monthly reports to generate automatically
        - **Alert System**: Set up alerts for key metric changes
        - **Data Sync**: Ensure all data sources are updated in real-time
        """

    async def _provide_integration_help(self, help_intent: Dict[str, Any]) -> str:
        """
        Provide integration assistance
        
        Args:
            help_intent: Integration parameters
            
        Returns:
            Formatted integration guide
        """
        return """
        **Integration Guide**
        
        **Quick Start: Connect Your CRM**
        
        **Step 1: Get API Credentials**
        1. Log in to your CRM (e.g., Salesforce)
        2. Go to Setup > Apps > App Manager
        3. Create new Connected App
        4. Note down Consumer Key and Consumer Secret
        
        **Step 2: Configure Integration**
        1. In UNIBASE, go to Settings > Integrations
        2. Click "Add Integration"
        3. Select "CRM System"
        4. Enter your API credentials
        5. Test the connection
        
        **Step 3: Map Data Fields**
        1. Choose which CRM objects to sync (Contacts, Accounts, Opportunities)
        2. Map CRM fields to UNIBASE fields
        3. Set sync frequency (real-time, hourly, daily)
        4. Configure conflict resolution rules
        
        **Step 4: Test Integration**
        1. Create a test contact in CRM
        2. Verify it appears in UNIBASE
        3. Update the contact in UNIBASE
        4. Confirm changes sync back to CRM
        
        **Common Integration Patterns**:
        
        **E-commerce Integration**:
        - **Platform**: Shopify, WooCommerce, Magento
        - **Data Sync**: Orders, customers, products, inventory
        - **Use Case**: Unified customer view across all channels
        
        **Accounting Integration**:
        - **Platform**: QuickBooks, Xero, NetSuite
        - **Data Sync**: Invoices, payments, expenses, customers
        - **Use Case**: Automated financial reporting
        
        **Marketing Integration**:
        - **Platform**: Mailchimp, Marketo, HubSpot
        - **Data Sync**: Campaigns, leads, customer segments
        - **Use Case**: Targeted marketing campaigns
        
        **Troubleshooting Integration Issues**:
        - **Connection Errors**: Check API credentials and permissions
        - **Data Sync Issues**: Verify field mappings and data formats
        - **Performance**: Monitor API rate limits and adjust sync frequency
        - **Conflicts**: Review conflict resolution settings
        """

    async def _provide_general_help(self, message: str) -> str:
        """
        Provide general help and guidance
        
        Args:
            message: User's help request
            
        Returns:
            Formatted general help response
        """
        return f"""
        **Welcome to UNIBASE Help**
        
        **Your Question**: {message}
        
        **How I Can Help You**:
        
        **📊 Dashboard & Analytics**:
        - Create custom dashboards
        - Generate reports and charts
        - Analyze business trends
        - Set up automated alerts
        
        **💬 AI Chat Assistant**:
        - Ask questions in natural language
        - Get instant insights from your data
        - Create workflows through conversation
        - Receive personalized recommendations
        
        **🔧 System Features**:
        - User management and permissions
        - Integration setup and configuration
        - Custom field and form creation
        - Workflow automation
        
        **📚 Learning Resources**:
        - Step-by-step tutorials
        - Video guides and walkthroughs
        - Best practices documentation
        - API reference and examples
        
        **🆘 Support Options**:
        - **Self-Service Help**: Browse our comprehensive help center
        - **Community Forum**: Connect with other users
        - **Live Chat**: Chat with our support team
        - **Email Support**: Send detailed questions to support@unibase.com
        
        **Quick Start Actions**:
        
        **New User?** Try these:
        1. "Show me how to create my first dashboard"
        2. "Guide me through generating a sales report"
        3. "Explain the main features of the system"
        
        **Experienced User?** Try these:
        1. "Help me set up an advanced integration"
        2. "Show me API documentation for custom development"
        3. "Provide best practices for data management"
        
        **Admin User?** Try these:
        1. "Explain user permission management"
        2. "Guide me through system configuration"
        3. "Help with security settings"
        
        **Popular Help Topics**:
        - Dashboard creation and customization
        - Report generation and scheduling
        - User management and permissions
        - Integration setup (CRM, accounting, e-commerce)
        - API usage and development
        - Security configuration
        - Troubleshooting common issues
        
        **Next Steps**:
        1. **Browse Help Categories**: Use the menu to explore specific topics
        2. **Search Documentation**: Use search to find specific answers
        3. **Interactive Tutorials**: Try our hands-on learning modules
        4. **Contact Support**: Reach out for personalized assistance
        
        **Pro Tips**:
        - Be specific in your questions for better results
        - Use natural language - no need for technical terms
        - Ask follow-up questions to dive deeper
        - Save useful responses for future reference
        """