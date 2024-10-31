from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from typing import List
import motor.motor_asyncio
import uuid
import toml
from datetime import datetime,timedelta
import os
from avatar_generator import create_avatar_app
from chatllm import OpenAIService
from gtts import gTTS
import os
import io
import jwt
from fastapi.staticfiles import StaticFiles


SECRET_KEY = "vsrinivasa"
ALGORITHM = "HS256"

    
app = FastAPI()
keys = toml.load("keys.toml")
key = keys["api_keys"]["service_1_key"]

client = motor.motor_asyncio.AsyncIOMotorClient("mongodb://localhost:27017/")
db = client["mydatabase"]
collection = db["sessions"]
openai_service = OpenAIService(api_key=key)

# Create and mount the avatar generator app
avatar_app = create_avatar_app()
app.mount("/avatar", avatar_app)
app.mount("/models", StaticFiles(directory="models"), name="models")
# Serve static files (including generated avatars)
app.mount("/avatars", StaticFiles(directory="avatars"), name="avatars")

# Add these near your other StaticFiles mounts
app.mount("/models", StaticFiles(directory="models"), name="models")
app.mount("/videos", StaticFiles(directory="."), name="videos")

class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []
        self.sessions = {}

    async def connect(self, websocket: WebSocket): 
        """
        Accepts the web socket connection and initializes session data.

        Parameter
        ---------
        websocket : WebSocket
            Object of FAST API's WebSocket class, used to establish and
            manage websocket connection with the server.
        """
        await websocket.accept()
        self.active_connections.append(websocket)
        session_id = str(uuid.uuid4())
        sessionstart = datetime.now()
        userid = websocket.client[0]
        self.sessions[websocket] = {
            "SessionID": session_id,
            "UserID": userid,
            "SessionStart": sessionstart,
            "QandA": {}  
        }

    async def disconnect(self, websocket: WebSocket):
        """
        Disconnects the web socket connection and appends end timestamp
        to the session data.

        Parameter
        ---------
        websocket : WebSocket
            Object of FAST API's WebSocket class, used to establish and
            manage websocket connection with the server.
        """
        if websocket in self.active_connections:  
            self.sessions[websocket]["SessionEnd"] = datetime.now()
            await self.store_session_in_db(websocket)
            self.active_connections.remove(websocket)
            try:
                await websocket.close()
            except RuntimeError:
                print("WebSocket already closed, ignoring close attempt.") 
       

    async def send_message(self, websocket: WebSocket, message: str, question: str):
        """
        Sends the response to the client and updates session history.

        Parameters
        ----------
        websocket : WebSocket
            Object of FAST API's WebSocket class, used to establish and
            manage websocket connection with the server.

        message : str
            Response sent to the client.
        
        question : str
            The request to the server from the client.
        """
        if "QandA" not in self.sessions[websocket]:
            self.sessions[websocket]["QandA"] = {}
        self.sessions[websocket]["QandA"][question] = message  
        await websocket.send_text(message)
        await self.store_session_in_db(websocket)

    async def receive_message(self, websocket: WebSocket):
        """
        Receives the request from the client.

        Parameters
        ----------
        websocket : WebSocket
            Object of FAST API's WebSocket class, used to establish and
            manage websocket connection with the server.
        """
        return await websocket.receive_text()

    async def store_session_in_db(self, websocket: WebSocket):
        """
        Updates the session data in MongoDB after each prompt-response pair.

        Parameters
        ----------
        websocket : WebSocket
            Object of FAST API's WebSocket class, used to establish and
            manage websocket connection with the server.
        """
        session_data = self.sessions.get(websocket)
        if session_data:
            serializable_data = {
                "SessionID": session_data.get("SessionID"),
                "UserID": session_data.get("UserID"),
                "SessionStart": session_data.get("SessionStart"),
                "SessionEnd": session_data.get("SessionEnd", None),  
                "QandA": session_data.get("QandA", {})  
            }

            await collection.update_one(
                {"SessionID": serializable_data["SessionID"]},  
                {"$set": serializable_data},                   
                upsert=True                                    
            )

@app.get("/", response_class=HTMLResponse)
async def serve_html():
    """
    Serves the main HTML page for the FastAPI application.

    This function reads the content of the 'client.html' file located 
    in the same directory as the current script and returns it as an 
    HTML response. This allows users to access the HTML file at the 
    root endpoint ('/') of the FastAPI app.

    Returns:
        HTMLResponse: The content of 'client.html' served as an HTML 
                      response with a status code of 200.
    """
    file_path = os.path.join(os.path.dirname(__file__), "client.html")
    with open(file_path, "r") as file:
        return HTMLResponse(content=file.read(), status_code=200)

manager = ConnectionManager()

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    Handles the websocket chatting using functions defined
    in the OpenAIService. 

    Parameters
    ----------
    websocket : WebSocket
        Object of FAST API's WebSocket class, used to establish and
        manage websocket connection with the server.
    """
    await manager.connect(websocket)
    try:
        while True:
            # Receive a message from the client
            data = await manager.receive_message(websocket)
            print(f"Message received: {data}")

            # Generate a response using the OpenAIService
            response = await openai_service.get_gpt_response(manager.sessions[websocket], data)
            tts=gTTS(text=response,lang="en",tld="com")
            audio_fp = io.BytesIO()
            tts.write_to_fp(audio_fp)
            audio_fp.seek(0)
            # Send the response back to the client and save the session
            await manager.send_message(websocket, response, data)
            await websocket.send_bytes(audio_fp.read())
            print("Audio response sent.")
    except:
        await manager.disconnect(websocket)