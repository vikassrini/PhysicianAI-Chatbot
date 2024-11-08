from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from typing import List
import motor.motor_asyncio
import uuid
import toml
from datetime import datetime,timedelta
import os

from chatllm import OpenAIService
from gtts import gTTS
import os
import io
import base64
from fastapi.staticfiles import StaticFiles
import json
from PyPDF2 import PdfFileReader
from fastapi import WebSocketDisconnect

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

app.mount("/models", StaticFiles(directory="models"), name="models")
# Serve static files (including generated avatars)


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
            "QandA": {},
            "isReportUploaded":False,
            "filepath":None
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
    await manager.connect(websocket)
    try:
        while True:
            # Receive a message from the client
            data = await manager.receive_message(websocket)
            try:
                message = json.loads(data)
                print(f"Parsed message: {message}")
            except json.JSONDecodeError as e:
                print(f"JSON parsing error: {e}")
                await websocket.send_text("Error: Invalid message format")
                continue

            message_type = message.get("type")
            user_message = message.get("message", "")

            print(f"Message type: {message_type}")
            print(f"User message: {user_message}")

            try:
                if message_type == "file":
                    content = message.get("content")
                    if not content:
                        await websocket.send_text("Error: No file content provided")
                        continue

                    # Handle file upload
                    if content.startswith("data:application/pdf;base64,"):
                        base64_data = content.split(",")[1]
                        pdf_data = base64.b64decode(base64_data)
                        
                        os.makedirs("uploads", exist_ok=True)
                        file_path = "uploads/received_file.pdf"
                        with open(file_path, "wb") as pdf_file:
                            pdf_file.write(pdf_data)
                        manager.sessions[websocket]["isReportUploaded"]=True
                        manager.sessions[websocket]["filepath"]=file_path
                        
                        response = await openai_service.get_gpt_response(
                            manager.sessions[websocket], 
                            user_message, 
                            file_path
                        )
                    else:
                        await websocket.send_text("Error: Invalid file format")
                        continue

                elif message_type == "text":
                    if manager.sessions[websocket]["isReportUploaded"]==True:
                        response = await openai_service.get_gpt_response(
                        manager.sessions[websocket], 
                        user_message,manager.sessions[websocket]["filepath"])
                    else:
                        response = await openai_service.get_gpt_response(
                            manager.sessions[websocket], 
                            user_message
                        )
                else:
                    await websocket.send_text("Error: Invalid message type")
                    continue

                # Generate and send audio response
                tts = gTTS(text=response, lang="en", tld="com")
                audio_fp = io.BytesIO()
                tts.write_to_fp(audio_fp)
                audio_fp.seek(0)

                # Send responses
                await manager.send_message(websocket, response, user_message)
                await websocket.send_bytes(audio_fp.read())
                print("Response sent successfully")

            except Exception as e:
                print(f"Error processing message: {e}")
                await websocket.send_text(f"Error: {str(e)}")

    except WebSocketDisconnect:
        print("WebSocket disconnected")
        await manager.disconnect(websocket)
    except Exception as e:
        print(f"Unexpected error: {e}")
        await manager.disconnect(websocket)
