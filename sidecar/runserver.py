from main import app
import uvicorn
import os

port = int(os.getenv('APP_PORT', '9696'))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=port)
