import websockets
import sys
import time
import logging
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_websocket():
    uri = "ws://localhost:8002/ws"
    logger.info(f"Connecting to WebSocket server at {uri}...")
    
    try:
        # Wait a moment to ensure the server is ready
        await asyncio.sleep(1)
        
        async with websockets.connect(uri) as websocket:
            logger.info("Connected successfully!")
            
            # Send hello world message
            message = "Hello World"
            logger.info(f"\nSending: {message}")
            await websocket.send(message)
            
            # Wait for response
            response = await websocket.recv()
            logger.info(f"Received: {response}")
            
            logger.info("\nTest completed successfully!")
            
    except Exception as e:
        logger.error(f"\nError during test: {str(e)}")
        logger.error("\nMake sure the WebSocket server is running on port 8001")
        logger.error("Start the server with: python -m services.server")
        sys.exit(1)

if __name__ == "__main__":
    logger.info("Starting WebSocket client test...")
    asyncio.run(test_websocket())
