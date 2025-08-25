# AI Copilot gRPC Service

This directory contains the Protocol Buffer definitions and generated code for the AI Copilot gRPC service.

## Overview

The AI Copilot gRPC service provides a high-performance interface for integrating with the API gateway and other services. It offers the following RPCs:

- `Chat`: For sending a message and receiving a response
- `StreamChat`: For sending a message and receiving a streaming response
- `HealthCheck`: For checking the health of the service

## Protocol Buffer Definition

The service is defined in `ai_copilot.proto`. The generated Python code includes:

- `ai_copilot_pb2.py`: Contains message classes
- `ai_copilot_pb2_grpc.py`: Contains service classes

## Regenerating Code

If you modify the `.proto` file, you need to regenerate the Python code using:

```bash
python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. ai_copilot.proto
```

Run this command from the `app/proto` directory.

## Configuration

The gRPC server is configured through environment variables:

- `GRPC_PORT`: Port for the gRPC server (default: 50052)
- `GRPC_MAX_WORKERS`: Maximum number of workers (default: 10)
- `GRPC_MAX_CONCURRENT_RPCS`: Maximum concurrent RPCs (default: 100)
- `GRPC_MAX_CONNECTION_IDLE`: Maximum idle connection time in seconds (default: 300)
- `GRPC_MAX_CONNECTION_AGE`: Maximum connection age in seconds (default: 600)
- `GRPC_MAX_MESSAGE_SIZE`: Maximum message size in bytes (default: 50MB)
- `GRPC_SSL_CERT_PATH`: Path to SSL certificate (default: /etc/ssl/certs/grpc-server.crt)
- `GRPC_SSL_KEY_PATH`: Path to SSL key (default: /etc/ssl/private/grpc-server.key)

## Security

In production, the gRPC server uses SSL/TLS for secure communication. In development mode, it runs in insecure mode for easier testing.

## Client Example

Here's a simple example of how to create a client in Python:

```python
import grpc
from app.proto.ai_copilot_pb2 import ChatRequest
from app.proto.ai_copilot_pb2_grpc import AICopilotStub

# Create a channel
channel = grpc.insecure_channel('localhost:50052')  # Use secure_channel in production

# Create a stub
stub = AICopilotStub(channel)

# Create a request
request = ChatRequest(
    message="Hello, AI Copilot!",
    conversation_id="conv123",
    user_id="user456",
    agent_type="general"
)

# Make the call
response = stub.Chat(request)
print(f"Response: {response.content}")
```

For streaming responses:

```python
# Make a streaming call
for response in stub.StreamChat(request):
    print(f"Chunk: {response.content}")
```