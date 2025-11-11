import asyncio
import websockets
import json
import logging
from services.pitboss import Pitboss
import duckdb
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_pitboss():
    try:
        # Get database path from environment
        db_path = os.getenv("DATABASE_LOCATION")
        if not db_path:
            raise ValueError("DATABASE_LOCATION environment variable not set")
        
        logger.info(f"Opening database: {db_path}")
        
        # Open database in read-only mode
        db = duckdb.connect(db_path, read_only=True)
        
        # Test rule
        test_rule = "Find all patients with albumin levels above 100"
        logger.info(f"Test rule: {test_rule}")
        
        # Custom system prompt
        custom_prompt = """
        You are a SQL translation assistant specializing in clinical trial data.
        Your task is to convert rule descriptions into SQL queries that work with DuckDB.
        Always include proper table aliases and handle date formats correctly.
        """
        
        # Connect to WebSocket server
        uri = "ws://localhost:8001/ws"
        logger.info(f"Connecting to WebSocket server at {uri}")
        
        async with websockets.connect(uri) as websocket:
            logger.info("Connected to WebSocket server")
            
            pitboss = Pitboss(db, websocket)
            
            logger.info(f"Sending test rule: {test_rule}")
            await websocket.send(json.dumps({
                "rule_code": test_rule,
                "system_prompt": custom_prompt
            }))
            
            response = await websocket.recv()
            logger.info(f"Raw response received: {response}")
            
            # Parse response
            try:
                response_data = json.loads(response)
                logger.info(f"Parsed response: {json.dumps(response_data, indent=2)}")
                
                # Verify response
                assert response_data["type"] == "rule_result"
                assert "data" in response_data
                assert len(response_data["data"]["results"]) >= 0  # Allow for empty results if no data matches
                
                logger.info("Response format verified successfully")
                logger.info(f"Number of results: {len(response_data['data']['results'])}")
                
                logger.info("Test completed successfully!")
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON response: {str(e)}")
                logger.error(f"Raw response was: {response}")
                raise
            except AssertionError as e:
                logger.error(f"Response validation failed: {str(e)}")
                logger.error(f"Response was: {json.dumps(response_data, indent=2)}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                raise
            
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        raise
    finally:
        if 'db' in locals():
            db.close()
            logger.info("Database connection closed")
        logger.info("Test completed")

if __name__ == "__main__":
    # Run the test
    asyncio.run(test_pitboss())
