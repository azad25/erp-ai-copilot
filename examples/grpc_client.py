#!/usr/bin/env python3
"""
Example gRPC client for AI Copilot service.

This script demonstrates how to connect to the AI Copilot gRPC service
and make requests for both regular and streaming chat.

Usage:
    python3 grpc_client.py
"""

import asyncio
import argparse
import grpc
import os
import sys

# Add the parent directory to the path so we can import the proto modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.proto.ai_copilot_pb2 import ChatRequest, HealthCheckRequest
from app.proto.ai_copilot_pb2_grpc import AICopilotStub


async def run_chat(stub, message, conversation_id, user_id, agent_type, stream=False):
    """Run a chat request."""
    # Create request
    request = ChatRequest(
        message=message,
        conversation_id=conversation_id,
        user_id=user_id,
        agent_type=agent_type,
        model="gpt-4",
        temperature=0.7,
        max_tokens=1000
    )
    
    # Make request
    if stream:
        print(f"Sending streaming chat request: {message}")
        async for response in stub.StreamChat(request):
            print(f"Received chunk: {response.content}")
    else:
        print(f"Sending chat request: {message}")
        response = await stub.Chat(request)
        print(f"Received response: {response.content}")
        print(f"Message ID: {response.message_id}")
        print(f"Response type: {response.response_type}")
        print(f"Timestamp: {response.timestamp}")
        if response.suggested_actions:
            print(f"Suggested actions: {response.suggested_actions}")


async def run_health_check(stub):
    """Run a health check request."""
    # Create request
    request = HealthCheckRequest(check_type="full")
    
    # Make request
    print("Sending health check request")
    response = await stub.HealthCheck(request)
    print(f"Health status: {response.status}")
    print(f"Details: {response.details}")
    print(f"Version: {response.version}")
    print(f"Timestamp: {response.timestamp}")


async def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description="gRPC client for AI Copilot service")
    parser.add_argument("--host", default="localhost", help="Server host")
    parser.add_argument("--port", type=int, default=50052, help="Server port")
    parser.add_argument("--secure", action="store_true", help="Use secure connection")
    parser.add_argument("--stream", action="store_true", help="Use streaming chat")
    parser.add_argument("--health", action="store_true", help="Run health check")
    parser.add_argument("--message", default="Hello, AI Copilot!", help="Message to send")
    parser.add_argument("--conversation", default="conv123", help="Conversation ID")
    parser.add_argument("--user", default="user456", help="User ID")
    parser.add_argument("--agent", default="general", help="Agent type")
    args = parser.parse_args()
    
    # Create channel
    server_addr = f"{args.host}:{args.port}"
    if args.secure:
        # Create secure channel with SSL credentials
        creds = grpc.ssl_channel_credentials()
        channel = grpc.aio.secure_channel(server_addr, creds)
    else:
        # Create insecure channel for development
        channel = grpc.aio.insecure_channel(server_addr)
    
    # Create stub
    stub = AICopilotStub(channel)
    
    try:
        # Run health check if requested
        if args.health:
            await run_health_check(stub)
        else:
            # Run chat request
            await run_chat(
                stub, 
                args.message, 
                args.conversation, 
                args.user, 
                args.agent, 
                args.stream
            )
    finally:
        # Close channel
        await channel.close()


if __name__ == "__main__":
    asyncio.run(main())