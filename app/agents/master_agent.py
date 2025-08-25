from typing import Dict, Any, List, Optional
import asyncio
import logging
from datetime import datetime
from enum import Enum

from .base_agent import BaseAgent, AgentRequest, AgentResponse
from .query_agent import QueryAgent
from .action_agent import ActionAgent
from .analytics_agent import AnalyticsAgent
from .compliance_agent import ComplianceAgent
from .help_agent import HelpAgent
from .scheduler_agent import SchedulerAgent
from app.services.llm_service import LLMService


class AgentType(Enum):
    QUERY = "query"
    ACTION = "action"
    ANALYTICS = "analytics"
    COMPLIANCE = "compliance"
    HELP = "help"
    SCHEDULER = "scheduler"


class MasterAgent(BaseAgent):
    """
    Master orchestrator agent that coordinates specialized agents.
    Uses LLM service for intelligent orchestration and agent selection.
    """
    
    def __init__(self, llm_service: LLMService):
        """
        Initialize the master agent with LLM service and specialized agents.
        
        Args:
            llm_service: The LLM service for model interactions
        """
        super().__init__("master", llm_service)
        self.agents = {}
        self._initialize_agents(llm_service)
        self.performance_metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "average_response_time": 0.0,
            "agent_usage_stats": {},
            "last_updated": datetime.utcnow().isoformat()
        }
        
    def _initialize_agents(self, llm_service: LLMService):
        """Initialize all specialized agents."""
        self.agents = {
            AgentType.QUERY: QueryAgent(llm_service),
            AgentType.ACTION: ActionAgent(llm_service),
            AgentType.ANALYTICS: AnalyticsAgent(llm_service),
            AgentType.COMPLIANCE: ComplianceAgent(llm_service),
            AgentType.HELP: HelpAgent(llm_service),
            AgentType.SCHEDULER: SchedulerAgent(llm_service)
        }
    
    async def execute(self, request: AgentRequest) -> AgentResponse:
        """
        Execute the master agent's orchestration logic.
        
        Args:
            request: The agent request containing user message and metadata
            
        Returns:
            AgentResponse with orchestrated results
        """
        start_time = datetime.utcnow()
        self.performance_metrics["total_requests"] += 1
        
        try:
            # Use LLM for intelligent orchestration
            orchestration_prompt = self._build_orchestration_prompt(request)
            
            llm_request = {
                "messages": [{"role": "user", "content": orchestration_prompt}],
                "model": "gpt-4",
                "max_tokens": 500,
                "temperature": 0.3
            }
            
            response = await self.llm_service.generate(llm_request)
            orchestration_plan = self._parse_orchestration_response(response["content"])
            
            # Execute based on orchestration plan
            if orchestration_plan["strategy"] == "single_agent":
                result = await self._execute_single_agent(request, orchestration_plan)
            elif orchestration_plan["strategy"] == "multi_agent":
                result = await self._execute_multi_agent(request, orchestration_plan)
            elif orchestration_plan["strategy"] == "complex_workflow":
                result = await self._execute_complex_workflow(request, orchestration_plan)
            else:
                result = await self._execute_fallback(request)
            
            self.performance_metrics["successful_requests"] += 1
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            self._update_performance_metrics(execution_time, orchestration_plan)
            
            return result
            
        except Exception as e:
            logging.error(f"Master agent execution error: {e}")
            return await self._handle_execution_error(request, e)
    
    def _build_orchestration_prompt(self, request: AgentRequest) -> str:
        """Build prompt for LLM-based orchestration."""
        return f"""
        You are an intelligent orchestrator for an ERP AI Copilot system. 
        Analyze the user's request and determine the best strategy.
        
        User Request: {request.message}
        
        Available agents:
        - query: For data retrieval and information queries
        - action: For performing actions and updates
        - analytics: For data analysis and insights
        - compliance: For compliance and audit tasks
        - help: For help and guidance
        - scheduler: For scheduling and automation
        
        Respond with a JSON object:
        {{
            "strategy": "single_agent|multi_agent|complex_workflow",
            "selected_agents": ["agent_type"],
            "reasoning": "explanation",
            "priority": "high|medium|low"
        }}
        """
    
    def _parse_orchestration_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response for orchestration plan."""
        try:
            import json
            return json.loads(response.strip())
        except:
            return {
                "strategy": "single_agent",
                "selected_agents": [AgentType.QUERY],
                "reasoning": "Fallback to query agent",
                "priority": "medium"
            }
    
    async def _execute_single_agent(self, request: AgentRequest, plan: Dict[str, Any]) -> AgentResponse:
        """Execute single agent request."""
        agent_type = plan["selected_agents"][0]
        agent = self.agents[agent_type]
        return await agent.execute(request)
    
    async def _execute_multi_agent(self, request: AgentRequest, plan: Dict[str, Any]) -> AgentResponse:
        """Execute multiple agents in parallel."""
        selected_agents = plan["selected_agents"]
        tasks = []
        for agent_type in selected_agents:
            agent = self.agents[agent_type]
            tasks.append(agent.execute(request))
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        return await self._synthesize_responses(responses, selected_agents)
    
    async def _execute_complex_workflow(self, request: AgentRequest, plan: Dict[str, Any]) -> AgentResponse:
        """Execute complex multi-step workflow."""
        query_agent = self.agents[AgentType.QUERY]
        analytics_agent = self.agents[AgentType.ANALYTICS]
        
        query_response = await query_agent.execute(request)
        
        analytics_request = AgentRequest(
            message=f"Analyze this data: {query_response.response}",
            conversation_id=request.conversation_id,
            user_id=request.user_id,
            metadata={"previous_response": query_response.response}
        )
        analytics_response = await analytics_agent.execute(analytics_request)
        
        final_response = f"""
        **Comprehensive Analysis**
        
        **Data Summary**:
        {query_response.response}
        
        **Analysis Results**:
        {analytics_response.response}
        
        **Generated by Master Agent**: Coordinated Query and Analytics agents for comprehensive insights.
        """
        
        return AgentResponse(
            response=final_response,
            agent_type=AgentType.QUERY,
            conversation_id=request.conversation_id or "",
            execution_id="",
            metadata={
                "orchestration_type": "complex_workflow",
                "agents_used": [AgentType.QUERY, AgentType.ANALYTICS],
                "workflow_steps": ["query", "analyze", "synthesize"],
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    async def _execute_fallback(self, request: AgentRequest) -> AgentResponse:
        """Execute fallback strategy."""
        help_agent = self.agents[AgentType.HELP]
        fallback_request = AgentRequest(
            message=request.message,
            conversation_id=request.conversation_id,
            user_id=request.user_id,
            metadata={"fallback": True}
        )
        return await help_agent.execute(fallback_request)
    
    async def _synthesize_responses(self, responses: List[Any], agent_types: List[AgentType]) -> AgentResponse:
        """Synthesize responses from multiple agents."""
        successful_responses = []
        failed_responses = []
        
        for response, agent_type in zip(responses, agent_types):
            if isinstance(response, Exception):
                failed_responses.append({"agent": agent_type, "error": str(response)})
            else:
                successful_responses.append({
                    "agent": agent_type,
                    "response": response.response,
                    "metadata": response.metadata
                })
        
        if not successful_responses:
            return await self._execute_fallback(AgentRequest(
                message="All agents failed to respond",
                conversation_id="",
                user_id=""
            ))
        
        synthesized_content = "**Multi-Agent Response**\n\n"
        
        for resp in successful_responses:
            synthesized_content += f"**{resp['agent'].value.title()} Agent Response**:\n{resp['response']}\n\n"
        
        if failed_responses:
            synthesized_content += "**Note**: Some agents encountered issues:\n"
            for failure in failed_responses:
                synthesized_content += f"- {failure['agent'].value}: {failure['error']}\n"
        
        return AgentResponse(
            response=synthesized_content,
            agent_type=AgentType.QUERY,
            conversation_id=successful_responses[0]["response"].conversation_id if successful_responses else "",
            execution_id="",
            metadata={
                "orchestration_type": "multi_agent",
                "successful_agents": len(successful_responses),
                "failed_agents": len(failed_responses),
                "agents_used": [r["agent"] for r in successful_responses],
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    def _update_performance_metrics(self, execution_time: float, plan: Dict[str, Any]):
        """Update performance metrics after execution."""
        total_requests = self.performance_metrics["total_requests"]
        current_avg = self.performance_metrics["average_response_time"]
        new_avg = ((current_avg * (total_requests - 1)) + execution_time) / total_requests
        self.performance_metrics["average_response_time"] = new_avg
        
        for agent_type in plan.get("selected_agents", []):
            if agent_type not in self.performance_metrics["agent_usage_stats"]:
                self.performance_metrics["agent_usage_stats"][agent_type] = 0
            self.performance_metrics["agent_usage_stats"][agent_type] += 1
    
    async def _handle_execution_error(self, request: AgentRequest, error: Exception) -> AgentResponse:
        """Handle execution errors gracefully."""
        error_message = f"""
        **System Error**
        
        **Error Type**: {type(error).__name__}
        **Error Message**: {str(error)}
        
        **What to do next**:
        1. **Try Again**: The error might be temporary
        2. **Simplify Request**: Try a simpler version of your request
        3. **Check Documentation**: Refer to our help resources
        4. **Contact Support**: If the issue persists
        
        **Example Alternative**:
        Instead of: "{request.message}"
        Try: "Show me basic sales data"
        
        **Support Resources**:
        - **Help Center**: help.unibase.com
        - **Community Forum**: community.unibase.com
        - **Email Support**: support@unibase.com
        """
        
        return AgentResponse(
            response=error_message,
            agent_type=AgentType.HELP,
            conversation_id=request.conversation_id or "",
            execution_id="",
            metadata={
                "error_type": type(error).__name__,
                "error_message": str(error),
                "recovery_suggested": True,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report."""
        return {
            "summary": {
                "total_requests": self.performance_metrics["total_requests"],
                "success_rate": (
                    self.performance_metrics["successful_requests"] / 
                    max(self.performance_metrics["total_requests"], 1)
                ) * 100,
                "average_response_time": self.performance_metrics["average_response_time"],
                "uptime": "99.9%"
            },
            "agent_usage": {
                agent_type.value: count
                for agent_type, count in self.performance_metrics["agent_usage_stats"].items()
            },
            "recommendations": self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate performance recommendations."""
        recommendations = []
        
        if self.performance_metrics["agent_usage_stats"]:
            most_used = max(
                self.performance_metrics["agent_usage_stats"].items(),
                key=lambda x: x[1]
            )
            recommendations.append(
                f"Consider optimizing {most_used[0].value} agent for better performance"
            )
        
        if self.performance_metrics["average_response_time"] > 2.0:
            recommendations.append(
                "Consider implementing caching for frequently requested data"
            )
        
        success_rate = (
            self.performance_metrics["successful_requests"] / 
            max(self.performance_metrics["total_requests"], 1)
        ) * 100
        
        if success_rate < 95:
            recommendations.append(
                "Review error logs to identify common failure patterns"
            )
        
        return recommendations