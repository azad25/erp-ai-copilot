#!/usr/bin/env python3
"""
Start Agent Task Worker

Starts the Kafka-based agent task worker that processes tasks.
Can run multiple workers for parallel processing.
"""

import asyncio
import sys
import argparse
import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger(__name__)


async def start_worker(worker_id: int = 1):
    """
    Start a single worker instance
    
    Args:
        worker_id: Worker instance ID
    """
    from app.workers.agent_task_worker import AgentTaskWorker
    
    logger.info("Starting agent task worker", worker_id=worker_id)
    
    worker = AgentTaskWorker()
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal", worker_id=worker_id)
        worker.stop()
    except Exception as e:
        logger.error("Worker error", worker_id=worker_id, error=str(e))
        raise


async def start_multiple_workers(count: int):
    """
    Start multiple worker instances
    
    Args:
        count: Number of workers to start
    """
    logger.info("Starting multiple workers", count=count)
    
    tasks = []
    for i in range(count):
        task = asyncio.create_task(start_worker(worker_id=i+1))
        tasks.append(task)
    
    await asyncio.gather(*tasks)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Start Agent Task Worker")
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker instances to start (default: 1)"
    )
    parser.add_argument(
        "--worker-id",
        type=int,
        default=1,
        help="Worker ID for single worker mode (default: 1)"
    )
    
    args = parser.parse_args()
    
    try:
        if args.workers > 1:
            asyncio.run(start_multiple_workers(args.workers))
        else:
            asyncio.run(start_worker(args.worker_id))
    except KeyboardInterrupt:
        logger.info("Shutdown complete")
        sys.exit(0)
    except Exception as e:
        logger.error("Fatal error", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
