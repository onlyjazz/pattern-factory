from dotenv import load_dotenv
load_dotenv()
import os
import uvicorn
print("OPENAI_API_KEY prefix before run():", os.getenv("OPENAI_API_KEY")[:12] if os.getenv("OPENAI_API_KEY") else "MISSING")

if __name__ == "__main__":
    uvicorn.run("services.api:app", host="127.0.0.1", port=8000, reload=True)