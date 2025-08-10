import os
import json
import uuid
import re
import asyncio
import concurrent.futures
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from pydantic import BaseModel
import sqlite3
from pathlib import Path
import logging
from typing import List, Optional
from datetime import datetime, time, timedelta
import pandas as pd
import io
import torch
import cv2
import numpy as np
import base64
from PIL import Image
import torchvision.transforms as transforms
from scipy.spatial.distance import cosine
from ultralytics import YOLO
from backend.LightCNN.light_cnn import LightCNN_29Layers_v2  
from dotenv import load_dotenv
import uvicorn
import bcrypt
from jose import jwt
from jose.exceptions import JWTError, ExpiredSignatureError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import threading
from queue import Queue

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# trusted client IP (default: replace with your client IP or set via env)
HOST_IP = os.getenv("HOST_IP", "127.0.0.1")
ALLOWED_CLIENT_IP = os.getenv("ALLOWED_CLIENT_IP", HOST_IP)
# server host binding (default all interfaces)
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = os.getenv("SERVER_PORT", "5021")  # Set default port to 5021
FRONTEND_PORT = os.getenv("FRONTEND_PORT", "5022")  # Set default frontend port to 5022

print(f"Host IP: {HOST_IP}")
print(f"Server host: {SERVER_HOST}")
print(f"Server port: {SERVER_PORT}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global executor, db_pool, admin_db_pool, face_model, yolo_model, device
    
    # Initialize thread pool for CPU-intensive tasks
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    
    # Initialize database connection pools
    db_pool = DatabasePool(DB_PATH, pool_size=20)
    admin_db_pool = DatabasePool(ADMIN_DB_PATH, pool_size=10)
    
    # Initialize admin database schema and default superadmin
    init_admin_db()

    if not Path(DB_PATH).exists():
        raise FileNotFoundError("Database file 'attendance.db' not found.")

    model_path = "backend/checkpoints/LightCNN_29Layers_V2_checkpoint.pth.tar"
    yolo_path = "backend/yolo/weights/yolo11n-face.pt"

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using {device} for inference")

    try:
        face_model = LightCNN_29Layers_v2(num_classes=100)
        checkpoint = torch.load(model_path, map_location=device)
        new_state_dict = {k.replace("module.", ""): v for k, v in checkpoint.get("state_dict", checkpoint).items() if 'fc2' not in k}
        face_model.load_state_dict(new_state_dict, strict=False)
        face_model = face_model.to(device)
        face_model.eval()
        logger.info("Face recognition model loaded")
    except Exception as e:
        logger.error(f"Error loading face model: {e}")
        raise RuntimeError(f"Failed to load face recognition model: {e}")

    try:
        yolo_model = YOLO(yolo_path)
        logger.info("YOLO face detection model loaded")
    except Exception as e:
        logger.error(f"Error loading YOLO model: {e}")
        raise RuntimeError(f"Failed to load YOLO model: {e}")
    
    # Initialize time blocks during startup
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if time blocks already exist
        cursor.execute("SELECT COUNT(*) FROM TimeBlocks")
        count = cursor.fetchone()[0]
        
        if count == 0:
            # Define time blocks for 2nd year (1-hour periods)
            second_year_blocks = [
                (2, 1, "8:30", "9:30"),
                (2, 2, "9:30", "10:30"),
                (2, 3, "10:50", "11:50"),
                (2, 4, "11:50", "12:50"),
                (2, 5, "12:50", "1:40"),
                (2, 6, "1:40", "2:40"),
                (2, 7, "2:40", "3:25"),
                (2, 8, "3:45", "4:30"),
            ]
            
            # Define time blocks for 1st and 3rd years (45-minute periods)
            other_years_blocks = [
                (1, 1, "8:30", "9:15"),
                (1, 2, "9:15", "10:00"),
                (1, 3, "10:00", "10:45"),
                (1, 4, "11:05", "11:50"),
                (1, 5, "11:50", "12:35"),
                (1, 6, "1:20", "2:05"),
                (1, 7, "2:05", "2:50"),
                (1, 8, "3:05", "3:50"),
                (1, 9, "3:50", "4:35"),
                (3, 1, "8:30", "9:15"),
                (3, 2, "9:15", "10:00"),
                (3, 3, "10:00", "10:45"),
                (3, 4, "11:05", "11:50"),
                (3, 5, "11:50", "12:35"),
                (3, 6, "1:20", "2:05"),
                (3, 7, "2:05", "2:50"),
                (3, 8, "3:05", "3:50"),
                (3, 9, "3:50", "4:35"),
            ]
            
            # Insert the blocks
            cursor.executemany(
                "INSERT INTO TimeBlocks (batch_year, block_number, start_time, end_time) VALUES (?, ?, ?, ?)",
                second_year_blocks + other_years_blocks
            )
            
            conn.commit()
            logger.info("Time blocks initialized during startup")
        else:
            logger.info("Time blocks already exist, no initialization needed")
        
        return_db_connection(conn)
    except Exception as e:
        logger.error(f"Error initializing time blocks: {e}")
    
    logger.info("Application startup complete")
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    if executor:
        executor.shutdown(wait=True)
    if db_pool:
        db_pool.close_all()
    if admin_db_pool:
        admin_db_pool.close_all()
    logger.info("Application shutdown complete")

app = FastAPI(title="AI Student Attendance System", docs_url=None, redoc_url=None, lifespan=lifespan)

# CORS setup - Allow requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# middleware to reject any client except the trusted IP
@app.middleware("http")
async def restrict_remote_ip(request: Request, call_next):
    client_ip = request.client.host
    return await call_next(request)

DB_PATH = "backend/attendance.db"
ADMIN_DB_PATH = "backend/admin.db"

# Initialize admin database and schema at import

def init_admin_db():
    conn = get_admin_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)
    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM Admins WHERE role='superadmin'")
    if cursor.fetchone()[0] == 0:
        default_pwd = os.getenv("SUPERADMIN_PASSWORD", "admin123")
        pwd_hash = hash_password(default_pwd)
        cursor.execute(
            "INSERT INTO Admins (username, password_hash, role) VALUES (?, ?, ?)",
            ("superadmin", pwd_hash, "superadmin")
        )
        conn.commit()
    return_admin_db_connection(conn)

def get_db_connection():
    if db_pool:
        return db_pool.get_connection()
    else:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

def return_db_connection(conn):
    if db_pool:
        db_pool.return_connection(conn)
    else:
        conn.close()

def get_admin_db_connection():
    if admin_db_pool:
        return admin_db_pool.get_connection()
    else:
        conn = sqlite3.connect(ADMIN_DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

def return_admin_db_connection(conn):
    if admin_db_pool:
        admin_db_pool.return_connection(conn)
    else:
        conn.close()

# Global variables
face_model = None
yolo_model = None
device = None
transform = transforms.Compose([
    transforms.Resize((128, 128)),
    transforms.ToTensor(),
])

# Thread pool for CPU-intensive tasks
executor = None
db_lock = threading.Lock()

# Database connection pool
class DatabasePool:
    def __init__(self, db_path: str, pool_size: int = 10):
        self.db_path = db_path
        self.pool = Queue(maxsize=pool_size)
        self.pool_size = pool_size
        self._init_pool()
    
    def _init_pool(self):
        for _ in range(self.pool_size):
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self.pool.put(conn)
    
    def get_connection(self):
        return self.pool.get()
    
    def return_connection(self, conn):
        self.pool.put(conn)
    
    def close_all(self):
        while not self.pool.empty():
            conn = self.pool.get()
            conn.close()

# Connection pools
db_pool = None
admin_db_pool = None

# Pydantic Models
class DepartmentResponse(BaseModel):
    dept_name: str

class BatchResponse(BaseModel):
    batch_id: int
    dept_name: str
    year: int

class SectionResponse(BaseModel):
    section_id: int
    batch_id: int
    section_name: str

class SubjectResponse(BaseModel):
    subject_code: str
    subject_name: str
    dept_name: str
    year: int

class StudentResponse(BaseModel):
    register_number: str
    name: str
    section_id: int
    section_name: str
    batch_id: int

class AttendanceCreate(BaseModel):
    timetable_id: int
    register_number: str
    is_present: bool

class AttendanceUpdate(BaseModel):
    timetable_id: int
    register_number: str
    is_present: bool

class AttendanceEntry(BaseModel):
    register_number: str
    name: str
    is_present: int

class AttendanceRequest(BaseModel):
    timetable_id: int
    attendance: List[AttendanceEntry]

class DepartmentCreate(BaseModel):
    dept_name: str

class BatchCreate(BaseModel):
    dept_name: str
    year: int

class SectionCreate(BaseModel):
    batch_id: int
    section_name: str

class SubjectCreate(BaseModel):
    subject_code: str
    subject_name: str
    dept_name: str
    year: int

class StudentCreate(BaseModel):
    register_number: str
    name: str
    section_id: int

class TimetableSlotCreate(BaseModel):
    dept_name: str
    year: int
    section_name: str
    subject_code: str
    date: str
    start_time: str
    end_time: str

class TimeBlockCreate(BaseModel):
    batch_year: int
    block_number: int
    start_time: str
    end_time: str

class TimeBlockResponse(BaseModel):
    time_block_id: int
    batch_year: int
    block_number: int
    start_time: str
    end_time: str

# Model for admin login
class AdminLoginRequest(BaseModel):
    username: str
    password: str
    role: Optional[str] = "admin"

# Load gallery from .pth file
def load_gallery(dept_name: str, year: int, section_name: str):
    try:
        gallery_path = f"./gallery/gallery_{dept_name}_{year}.pth"
        if not Path(gallery_path).exists():
            logger.warning(f"Gallery file {gallery_path} not found")
            return {}
        gallery_data = torch.load(gallery_path, map_location='cpu')
        # Handle np.ndarray or tensor values
        gallery = {}
        for k, v in gallery_data.items():
            if isinstance(v, np.ndarray):
                gallery[k] = v
            elif isinstance(v, torch.Tensor):
                gallery[k] = v.cpu().numpy()
            else:
                logger.warning(f"Skipping invalid embedding for {k}: {type(v)}")
        logger.info(f"Loaded gallery {gallery_path} with {len(gallery)} identities")
        return gallery
    except Exception as e:
        logger.error(f"Error loading gallery {gallery_path}: {e}")
        return {}

def generate_image_filename(dept_name, year, section_name, date, subject_code, time_slot, suffix=""):
    # Clean inputs to make them safe for filenames
    dept_clean = re.sub(r'[^\w]', '_', dept_name)
    section_clean = re.sub(r'[^\w]', '_', section_name)
    subject_clean = re.sub(r'[^\w]', '_', subject_code)
    date_clean = re.sub(r'[^\w-]', '_', date)
    time_slot_clean = re.sub(r'[^\w-]', '_', time_slot)
    
    # Create base filename
    base_name = f"{dept_clean}_{year}_{section_clean}_{date_clean}_{subject_clean}_{time_slot_clean}"
    
    # Add suffix if provided
    if suffix:
        base_name = f"{base_name}_{suffix}"
        
    # Add unique identifier to prevent collisions
    unique_id = uuid.uuid4().hex[:8]
    
    return f"{base_name}_{unique_id}"

# Process image (using enhancements from old code) - Made async and CPU-intensive work moved to thread pool
async def process_image_async(image_bytes, threshold=0.45, gallery=None, save_path=None, filename_base=None, img_index=None, section_id=None):
    """Async wrapper for process_image that runs CPU-intensive work in thread pool"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        executor, 
        process_image_sync, 
        image_bytes, threshold, gallery, save_path, filename_base, img_index, section_id
    )

def process_image_sync(image_bytes, threshold=0.45, gallery=None, save_path=None, filename_base=None, img_index=None, section_id=None):
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not decode image")

        # Create image directory if it doesn't exist
        if save_path and not os.path.exists(save_path):
            os.makedirs(save_path, exist_ok=True)
            
        # Save original image if path is provided
        if save_path and filename_base:
            suffix = f"-{img_index}" if img_index is not None else ""
            orig_filename = f"{filename_base}{suffix}_original.jpg"
            orig_path = os.path.join(save_path, orig_filename)
            cv2.imwrite(orig_path, img)
            logger.info(f"Saved original image to {orig_path}")

        result_img = img.copy()
        detected_ids = set()
        
        # Get student IDs for the specific section if section_id is provided
        section_students = set()
        if section_id is not None:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT register_number FROM Students WHERE section_id = ?", (section_id,))
                section_students = {row["register_number"] for row in cursor.fetchall()}
                return_db_connection(conn)
                logger.info(f"Loaded {len(section_students)} student IDs for section {section_id}")
            except Exception as e:
                logger.error(f"Error loading section students: {e}")
                # Continue with empty set if database query fails
                pass
        
        # Detect faces using YOLO
        results = yolo_model(img)
        logger.info(f"YOLO detected {len(results[0].boxes)} faces")

        # Step 1: Get all faces and their embeddings
        faces_data = []
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                h, w = img.shape[:2]
                face_w, face_h = x2 - x1, y2 - y1
                pad_x, pad_y = int(face_w * 0.2), int(face_h * 0.2)
                x1, y1 = max(0, x1 - pad_x), max(0, y1 - pad_y)
                x2, y2 = min(w, x2 + pad_x), min(h, y2 + pad_y)

                if (x2 - x1) < 32 or (y2 - y1) < 32:
                    print(f"Skipping face too small ({x2-x1}x{y2-y1})")
                    continue

                face = img[y1:y2, x1:x2]
                if face.size == 0:
                    logger.warning(f"Empty face crop at {x1},{y1},{x2},{y2}")
                    continue

                gray_face = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
                face_pil = Image.fromarray(gray_face)
                face_tensor = transform(face_pil).unsqueeze(0).to(device)

                with torch.no_grad():
                    _, embedding = face_model(face_tensor)
                    face_embedding = embedding.cpu().squeeze().numpy()
                
                # Store all potential matches for this face
                matches = []
                for identity, gallery_embedding in gallery.items():
                    # Only consider matches for students in this section if section_id is provided
                    if section_id is not None and section_students and identity not in section_students:
                        continue
                        
                    similarity = 1 - cosine(face_embedding, gallery_embedding)
                    if similarity > threshold:
                        matches.append((identity, similarity))
                
                # Sort matches by similarity (highest first)
                matches.sort(key=lambda x: x[1], reverse=True)
                
                # Store all face data
                faces_data.append({
                    'coords': (x1, y1, x2, y2),
                    'embedding': face_embedding,
                    'matches': matches,
                    'best_match': "Unknown",
                    'best_score': -1
                })
        
        # Step 2: Assign identities based on highest confidence without duplicates
        used_identities = set()
        
        # First pass: assign identities to faces with highest confidence
        for face in sorted(faces_data, key=lambda x: max([m[1] for m in x['matches']]) if x['matches'] else 0, reverse=True):
            for identity, score in face['matches']:
                if identity not in used_identities:
                    face['best_match'] = identity
                    face['best_score'] = score
                    used_identities.add(identity)
                    detected_ids.add(identity)
                    break
        
        # Step 3: Draw the results
        for face in faces_data:
            x1, y1, x2, y2 = face['coords']
            best_match = face['best_match']
            best_score = face['best_score']
            
            color = (0, 255, 0) if best_match != "Unknown" else (0, 0, 255)
            cv2.rectangle(result_img, (x1, y1), (x2, y2), color, 2)
            label = f"{best_match} ({best_score:.2f})" if best_match != "Unknown" else "Unknown"
            cv2.putText(result_img, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Save the annotated image if path is provided
        if save_path and filename_base:
            suffix = f"-{img_index}" if img_index is not None else ""
            annotated_filename = f"{filename_base}{suffix}_annotated.jpg"
            annotated_path = os.path.join(save_path, annotated_filename)
            cv2.imwrite(annotated_path, result_img)
            logger.info(f"Saved annotated image to {annotated_path}")

        _, buffer = cv2.imencode('.jpg', result_img)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        return img_base64, detected_ids
    except Exception as e:
        logger.error(f"Error processing image: {e}")
        return None, []

# JWT and Auth settings
SECRET_KEY = os.getenv("SECRET_KEY", "changeme")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 1 day
security = HTTPBearer()

# Helper functions for password hashing and token

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None or role is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"username": username, "role": role}
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid credentials")

# Startup and shutdown handled by lifespan context manager above

# Health check endpoint for testing concurrency
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "message": "Server is running and ready to accept requests"
    }

# Simple test endpoint for concurrency testing
@app.get("/test-concurrent/{request_id}")
async def test_concurrent(request_id: str):
    # Simulate some async work
    await asyncio.sleep(1)  # 1 second delay
    return {
        "request_id": request_id,
        "timestamp": datetime.now().isoformat(),
        "message": f"Request {request_id} processed successfully"
    }

# Get current time block

# Get all time blocks
@app.get("/time-blocks", response_model=List[TimeBlockResponse])
async def get_all_time_blocks():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM TimeBlocks ORDER BY batch_year, block_number")
    blocks = cursor.fetchall()
    print(blocks)
    return_db_connection(conn)
    
    return [dict(block) for block in blocks]

# Find the current time block for a batch
@app.get("/current-time-block/{batch_year}")
async def get_current_time_block(batch_year: int):
    now = datetime.now()
    current_time = now.strftime("%I:%M")  # Use 12-hour format with AM/PM
    current_time_24h = now.strftime("%H:%M")  # Use 24-hour format with AM/PM
    print(f"Current Time: {type(current_time)}")

    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        """
        SELECT * FROM TimeBlocks 
        WHERE batch_year = ? 
        AND (
            (instr(start_time, ':') = 2 AND time('0' || start_time) <= time(?))
            OR (instr(start_time, ':') > 2 AND time(start_time) <= time(?))
        )
        AND (
            (instr(end_time, ':') = 2 AND time('0' || end_time) > time(?))
            OR (instr(end_time, ':') > 2 AND time(end_time) > time(?))
        )
        ORDER BY start_time ASC
        """,
        (batch_year, current_time, current_time, current_time, current_time)
    )
    
    block = cursor.fetchone()
    print("Blocks:",block)
    return_db_connection(conn)
    
    if block:
        return {"success": True, "data": dict(block)}
    else:
        return {"success": False, "message": "No active time block found for current time"}

# Admin endpoints to manage time blocks
@app.post("/time-blocks", response_model=TimeBlockResponse)
async def create_time_block(block: TimeBlockCreate, current_user: dict = Depends(get_current_admin)):
    if current_user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Forbidden")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        """
        INSERT INTO TimeBlocks (batch_year, block_number, start_time, end_time)
        VALUES (?, ?, ?, ?)
        """,
        (block.batch_year, block.block_number, block.start_time, block.end_time)
    )
    
    block_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return {**block.dict(), "time_block_id": block_id}

@app.put("/time-blocks/{time_block_id}", response_model=TimeBlockResponse)
async def update_time_block(time_block_id: int, block: TimeBlockCreate, current_user: dict = Depends(get_current_admin)):
    if current_user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Forbidden")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        """
        UPDATE TimeBlocks
        SET batch_year = ?, block_number = ?, start_time = ?, end_time = ?
        WHERE time_block_id = ?
        """,
        (block.batch_year, block.block_number, block.start_time, block.end_time, time_block_id)
    )
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Time block not found")
    
    conn.commit()
    conn.close()
    
    return {**block.dict(), "time_block_id": time_block_id}

@app.delete("/time-blocks/{time_block_id}")
async def delete_time_block(time_block_id: int, current_user: dict = Depends(get_current_admin)):
    if current_user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Forbidden")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM TimeBlocks WHERE time_block_id = ?", (time_block_id,))
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Time block not found")
    
    conn.commit()
    conn.close()
    
    return {"message": "Time block deleted successfully"}

# Normal User Endpoints
@app.get("/departments", response_model=List[DepartmentResponse])
async def get_departments():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT dept_name FROM Departments ORDER BY dept_name")
        departments = [{"dept_name": row["dept_name"]} for row in cursor.fetchall()]
        conn.close()
        if not departments:
            raise HTTPException(status_code=404, detail="No departments found")
        return departments
    except Exception as e:
        logger.error(f"Error fetching departments: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/years/{dept_name}", response_model=List[dict])
async def get_years(dept_name: str):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT b.year 
            FROM Batches b 
            JOIN Departments d ON b.dept_id = d.dept_id 
            WHERE d.dept_name = ?
            ORDER BY b.year
        """, (dept_name,))
        years = [{"year": row["year"]} for row in cursor.fetchall()]
        conn.close()
        if not years:
            raise HTTPException(status_code=404, detail=f"No years found for department {dept_name}")
        return years
    except Exception as e:
        logger.error(f"Error fetching years for {dept_name}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/sections/{dept_name}/{year}", response_model=List[SectionResponse])
async def get_sections(dept_name: str, year: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.section_id, s.batch_id, s.section_name 
            FROM Sections s 
            JOIN Batches b ON s.batch_id = b.batch_id 
            JOIN Departments d ON b.dept_id = d.dept_id 
            WHERE d.dept_name = ? AND b.year = ?
            ORDER BY s.section_name
        """, (dept_name, year))
        sections = [{"section_id": row["section_id"], "batch_id": row["batch_id"], "section_name": row["section_name"]} for row in cursor.fetchall()]
        conn.close()
        if not sections:
            raise HTTPException(status_code=404, detail=f"No sections found for {dept_name} year {year}")
        return sections
    except Exception as e:
        logger.error(f"Error fetching sections for {dept_name}, year {year}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/subjects/{dept_name}/{year}", response_model=List[SubjectResponse])
async def get_subjects_for_batch(dept_name: str, year: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.subject_code, s.subject_name, d.dept_name, s.year
            FROM Subjects s
            JOIN Departments d ON s.dept_id = d.dept_id
            WHERE d.dept_name = ? AND s.year = ?
            ORDER BY s.subject_name
        """, (dept_name, year))
        subjects = [
            {
                "subject_code": row["subject_code"],
                "subject_name": row["subject_name"],
                "dept_name": row["dept_name"],
                "year": row["year"]
            }
            for row in cursor.fetchall()
        ]
        conn.close()
        if not subjects:
            raise HTTPException(status_code=404, detail=f"No subjects found for {dept_name} year {year}")
        return subjects
    except Exception as e:
        logger.error(f"Error fetching subjects for {dept_name}, year {year}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/process-images")
async def process_images(
    images: List[UploadFile] = File(...),
    dept_name: str = Form(...),
    year: int = Form(...),
    section_name: str = Form(...),
    subject_code: str = Form(...),
    date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    threshold: float = Form(0.450)
):
    if face_model is None or yolo_model is None:
        logger.error("Models not loaded")
        raise HTTPException(status_code=500, detail="Models not loaded")

    if not 0 <= threshold <= 1:
        raise HTTPException(status_code=400, detail="Threshold must be between 0 and 1")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get section_id
        cursor.execute("""
            SELECT s.section_id 
            FROM Sections s 
            JOIN Batches b ON s.batch_id = b.batch_id 
            JOIN Departments d ON b.dept_id = d.dept_id 
            WHERE d.dept_name = ? AND b.year = ? AND s.section_name = ?
        """, (dept_name, year, section_name))
        section_result = cursor.fetchone()
        if not section_result:
            conn.close()
            raise HTTPException(status_code=404, detail="Section not found")
        section_id = section_result["section_id"]

        # Get subject_id
        cursor.execute("SELECT subject_id FROM Subjects WHERE subject_code = ?", (subject_code,))
        subject_result = cursor.fetchone()
        if not subject_result:
            conn.close()
            raise HTTPException(status_code=404, detail="Subject not found")
        subject_id = subject_result["subject_id"]

        # Create or get timetable slot
        cursor.execute("""
            SELECT timetable_id 
            FROM Timetable 
            WHERE section_id = ? AND subject_id = ? AND date = ? AND start_time = ? AND end_time = ?
        """, (section_id, subject_id, date, start_time, end_time))
        existing_slot = cursor.fetchone()
        if existing_slot:
            timetable_id = existing_slot["timetable_id"]
        else:
            cursor.execute("""
                INSERT INTO Timetable (section_id, subject_id, date, start_time, end_time)
                VALUES (?, ?, ?, ?, ?)
            """, (section_id, subject_id, date, start_time, end_time))
            timetable_id = cursor.lastrowid
            conn.commit()

        # Load gallery
        gallery = load_gallery(dept_name, year, section_name)
        if not gallery:
            logger.warning("Empty gallery; proceeding with all students marked absent")
            cursor.execute("""
                SELECT register_number, name 
                FROM Students 
                WHERE section_id = ?
            """, (section_id,))
            all_students = {row["register_number"]: row["name"] for row in cursor.fetchall()}
            conn.close()
            return {
                "attendance": [
                    {"register_number": reg_num, "name": name, "is_present": 0}
                    for reg_num, name in all_students.items()
                ],
                "images_base64": [],
                "timetable_id": timetable_id,
                "status": "success",
                "message": "No gallery data available; all students marked absent"
            }

        # Get all students
        cursor.execute("""
            SELECT register_number, name 
            FROM Students 
            WHERE section_id = ?
        """, (section_id,))
        all_students = {row["register_number"]: row["name"] for row in cursor.fetchall()}
        if not all_students:
            conn.close()
            logger.warning(f"No students found for section {dept_name} year {year} section {section_name}")
            return {
                "attendance": [],
                "images_base64": [],
                "timetable_id": timetable_id,
                "status": "success",
                "message": "No students enrolled in this section"
            }

        # Process images
        detected_students = set()
        images_base64 = []
        save_path = f"./processed_images/{dept_name}/{year}/{section_name}"
        filename_base = generate_image_filename(dept_name, year, section_name, date, subject_code, f"{start_time}-{end_time}")
        for img_index, image in enumerate(images):
            contents = await image.read()
            img_base64, detected_ids = await process_image_async(contents, threshold, gallery, save_path, filename_base, img_index, section_id)
            images_base64.append(img_base64)
            detected_students.update(detected_ids)
            
        # Prepare attendance
        attendance = [
            {
                "register_number": reg_num,
                "name": name,
                "is_present": 1 if reg_num in detected_students else 0
            }
            for reg_num, name in all_students.items()
        ]

        conn.close()
        logger.info(f"Processed {len(images)} images, detected {len(detected_students)} students")
        return {
            "attendance": attendance,
            "images_base64": images_base64,
            "timetable_id": timetable_id,
            "status": "success",
            "message": f"Processed {len(images)} images, recognized {len(detected_students)} students"
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error in /process-images: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing images: {str(e)}")

@app.post("/create-timetable-slot")
async def create_timetable_slot(slot: TimetableSlotCreate):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get section_id
        cursor.execute("""
            SELECT s.section_id 
            FROM Sections s 
            JOIN Batches b ON s.batch_id = b.batch_id 
            JOIN Departments d ON b.dept_id = d.dept_id 
            WHERE d.dept_name = ? AND b.year = ? AND s.section_name = ?
        """, (slot.dept_name, slot.year, slot.section_name))
        section_result = cursor.fetchone()
        if not section_result:
            conn.close()
            raise HTTPException(status_code=404, detail="Section not found")
        section_id = section_result["section_id"]

        # Get subject_id
        cursor.execute("SELECT subject_id FROM Subjects WHERE subject_code = ?", (slot.subject_code,))
        subject_result = cursor.fetchone()
        if not subject_result:
            conn.close()
            raise HTTPException(status_code=404, detail="Subject not found")
        subject_id = subject_result["subject_id"]

        # Check if a slot already exists
        cursor.execute("""
            SELECT timetable_id 
            FROM Timetable 
            WHERE section_id = ? AND subject_id = ? AND date = ? AND start_time = ? AND end_time = ?
        """, (section_id, subject_id, slot.date, slot.start_time, slot.end_time))
        existing_slot = cursor.fetchone()
        if existing_slot:
            conn.close()
            return {"timetable_id": existing_slot["timetable_id"]}

        cursor.execute("""
            INSERT INTO Timetable (section_id, subject_id, date, start_time, end_time)
            VALUES (?, ?, ?, ?, ?)
        """, (section_id, subject_id, slot.date, slot.start_time, slot.end_time))
        timetable_id = cursor.lastrowid
        conn.commit()
        conn.close()
        logger.info(f"Created timetable slot: timetable_id={timetable_id}")
        
        return {"timetable_id": timetable_id}
    except Exception as e:
        logger.error(f"Error creating timetable slot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/submit-attendance")
async def submit_attendance(
    timetable_id: int = Form(...),
    attendance: str = Form(...)
):
    logger.info(f"Received /submit-attendance: timetable_id={timetable_id}")
    try:
        # Parse attendance JSON
        try:
            attendance_list = json.loads(attendance)
            if not isinstance(attendance_list, list):
                raise ValueError("Attendance must be a list")
            for entry in attendance_list:
                if not all(key in entry for key in ["register_number", "name", "is_present"]):
                    raise ValueError("Each attendance entry must have register_number, name, is_present")
                if not isinstance(entry["is_present"], int) or entry["is_present"] not in [0, 1]:
                    raise ValueError("is_present must be 0 or 1")
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid attendance format: {str(e)}")
            raise HTTPException(status_code=422, detail=f"Invalid attendance format: {str(e)}")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify timetable_id
        cursor.execute("SELECT timetable_id FROM Timetable WHERE timetable_id = ?", (timetable_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Timetable slot not found")

        # Prepare attendance data
        attendance_data = []
        for entry in attendance_list:
            cursor.execute("SELECT student_id FROM Students WHERE register_number = ?", (entry["register_number"],))
            student_result = cursor.fetchone()
            if not student_result:
                conn.close()
                raise HTTPException(status_code=404, detail=f"Student {entry['register_number']} not found")
            student_id = student_result["student_id"]
            attendance_data.append((
                student_id,
                timetable_id,
                entry["is_present"]
            ))

        # Insert or update attendance
        cursor.executemany("""
            INSERT OR REPLACE INTO Attendance (
                student_id, timetable_id, is_present
            ) VALUES (?, ?, ?)
        """, attendance_data)
        conn.commit()
        conn.close()
        logger.info("Attendance submitted successfully")
        return {"message": "Attendance submitted successfully"}
    except HTTPException as e:
        logger.error(f"HTTP error in /submit-attendance: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Error submitting attendance: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    

@app.get("/attendance")
async def get_attendance_alt(
    dept_name: Optional[str] = None,
    year: Optional[int] = None,
    section_name: Optional[str] = None,
    subject_code: Optional[str] = None,
    date: Optional[str] = None
):
    """Alternative endpoint for GET /attendance that redirects to get-attendance functionality"""
    return await get_attendance(dept_name, year, section_name, subject_code, date)

@app.get("/get-attendance")
async def get_attendance(
    dept_name: Optional[str] = None,
    year: Optional[int] = None,
    section_name: Optional[str] = None,
    subject_code: Optional[str] = None,
    date: Optional[str] = None
):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            SELECT 
                a.attendance_id,
                s.register_number,
                s.name,
                sec.section_name,
                b.year,
                d.dept_name,
                sub.subject_code,
                sub.subject_name,
                t.date,
                t.start_time,
                t.end_time,
                a.is_present
            FROM Attendance a
            JOIN Students s ON a.student_id = s.student_id
            JOIN Timetable t ON a.timetable_id = t.timetable_id
            JOIN Sections sec ON t.section_id = sec.section_id
            JOIN Batches b ON sec.batch_id = b.batch_id
            JOIN Departments d ON b.dept_id = d.dept_id
            JOIN Subjects sub ON t.subject_id = sub.subject_id
            WHERE 1=1
        """
        params = []

        if dept_name:
            query += " AND d.dept_name = ?"
            params.append(dept_name)
        if year is not None:
            query += " AND b.year = ?"
            params.append(year)
        if section_name:
            query += " AND sec.section_name = ?"
            params.append(section_name)
        if subject_code:
            query += " AND sub.subject_code = ?"
            params.append(subject_code)
        if date:
            query += " AND t.date = ?"
            params.append(date)

        # Add sorting to ensure consistent results, regardless of filter settings
        query += " ORDER BY t.date DESC, t.start_time DESC, s.register_number ASC"

        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        attendance_records = [
            {
                "attendance_id": row["attendance_id"],
                "register_number": row["register_number"],
                "name": row["name"],
                "section_name": row["section_name"],
                "dept_name": row["dept_name"], 
                "year": row["year"],
                "subject_code": row["subject_code"],
                "subject_name": row["subject_name"],
                "date": row["date"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "is_present": row["is_present"],
            }
            for row in results
        ]
        return {"attendance": attendance_records}
    except Exception as e:
        logger.error(f"Error in /get-attendance: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching attendance: {str(e)}")

@app.delete("/delete-attendance/{attendance_id}")
async def delete_attendance(attendance_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT attendance_id FROM Attendance WHERE attendance_id = ?", (attendance_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Attendance record not found")

        cursor.execute("DELETE FROM Attendance WHERE attendance_id = ?", (attendance_id,))
        conn.commit()
        conn.close()
        logger.info(f"Deleted attendance_id={attendance_id}")
        return {"message": "Attendance record deleted successfully"}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error in /delete-attendance: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting attendance: {str(e)}")
   

# Super Admin Endpoints
@app.get("/batches", response_model=List[BatchResponse])
async def get_batches(current_user: dict = Depends(get_current_admin)):
    if current_user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.batch_id, d.dept_name, b.year 
            FROM Batches b 
            JOIN Departments d ON b.dept_id = d.dept_id
            ORDER BY d.dept_name, b.year
        """)
        batches = [{"batch_id": row["batch_id"], "dept_name": row["dept_name"], "year": row["year"]} for row in cursor.fetchall()]
        conn.close()
        return batches
    except Exception as e:
        logger.error(f"Error fetching batches: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/sections", response_model=List[SectionResponse])
async def get_all_sections(current_user: dict = Depends(get_current_admin)):
    if current_user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT section_id, batch_id, section_name FROM Sections ORDER BY section_name")
        sections = [{"section_id": row["section_id"], "batch_id": row["batch_id"], "section_name": row["section_name"]} for row in cursor.fetchall()]
        conn.close()
        return sections
    except Exception as e:
        logger.error(f"Error fetching sections: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/subjects", response_model=List[SubjectResponse])
async def get_subjects(current_user: dict = Depends(get_current_admin)):
    if current_user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.subject_code, s.subject_name, d.dept_name, s.year 
            FROM Subjects s 
            JOIN Departments d ON s.dept_id = d.dept_id
            ORDER BY s.subject_code
        """)
        subjects = [{"subject_code": row["subject_code"], "subject_name": row["subject_name"], "dept_name": row["dept_name"], "year": row["year"]} for row in cursor.fetchall()]
        conn.close()
        return subjects
    except Exception as e:
        logger.error(f"Error fetching subjects: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/students", response_model=List[StudentResponse])
async def get_students(current_user: dict = Depends(get_current_admin)):
    if current_user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.register_number, s.name, s.section_id, sec.section_name, sec.batch_id
            FROM Students s
            JOIN Sections sec ON s.section_id = sec.section_id
            ORDER BY s.register_number
        """)
        students = [
            {
                "register_number": row["register_number"],
                "name": row["name"],
                "section_id": row["section_id"],
                "section_name": row["section_name"],
                "batch_id": row["batch_id"]
            }
            for row in cursor.fetchall()
        ]
        conn.close()
        return students
    except Exception as e:
        logger.error(f"Error fetching students: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/departments", response_model=DepartmentResponse)
async def add_department(dept: DepartmentCreate):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO Departments (dept_name) VALUES (?)", (dept.dept_name,))
        conn.commit()
        conn.close()
        return {"dept_name": dept.dept_name}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Department already exists")
    except Exception as e:
        logger.error(f"Error adding department: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.put("/departments/{old_dept_name}", response_model=DepartmentResponse)
async def update_department(old_dept_name: str, dept: DepartmentCreate):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE Departments SET dept_name = ? WHERE dept_name = ?", (dept.dept_name, old_dept_name))
        if cursor.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="Department not found")
        conn.commit()
        conn.close()
        return {"dept_name": dept.dept_name}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Department name already exists")
    except Exception as e:
        logger.error(f"Error updating department: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/departments/{dept_name}")
async def delete_department(dept_name: str):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Departments WHERE dept_name = ?", (dept_name,))
        if cursor.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="Department not found")
        conn.commit()
        conn.close()
        return {"message": "Department deleted successfully"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Cannot delete department with associated batches")
    except Exception as e:
        logger.error(f"Error deleting department: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/batches", response_model=BatchResponse)
async def add_batch(batch: BatchCreate):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT dept_id FROM Departments WHERE dept_name = ?", (batch.dept_name,))
        dept_result = cursor.fetchone()
        if not dept_result:
            conn.close()
            raise HTTPException(status_code=404, detail="Department not found")
        dept_id = dept_result["dept_id"]

        cursor.execute("INSERT INTO Batches (dept_id, year) VALUES (?, ?)", (dept_id, batch.year))
        batch_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return {"batch_id": batch_id, "dept_name": batch.dept_name, "year": batch.year}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Batch already exists for this department and year")
    except Exception as e:
        logger.error(f"Error adding batch: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.put("/batches/{batch_id}", response_model=BatchResponse)
async def update_batch(batch_id: int, batch: BatchCreate):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT dept_id FROM Departments WHERE dept_name = ?", (batch.dept_name,))
        dept_result = cursor.fetchone()
        if not dept_result:
            conn.close()
            raise HTTPException(status_code=404, detail="Department not found")
        dept_id = dept_result["dept_id"]

        cursor.execute("UPDATE Batches SET dept_id = ?, year = ? WHERE batch_id = ?", (dept_id, batch.year, batch_id))
        if cursor.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="Batch not found")
        conn.commit()
        conn.close()
        return {"batch_id": batch_id, "dept_name": batch.dept_name, "year": batch.year}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Batch already exists for this department and year")
    except Exception as e:
        logger.error(f"Error updating batch: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/batches/{batch_id}")
async def delete_batch(batch_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Batches WHERE batch_id = ?", (batch_id,))
        if cursor.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="Batch not found")
        conn.commit()
        conn.close()
        return {"message": "Batch deleted successfully"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Cannot delete batch with associated sections")
    except Exception as e:
        logger.error(f"Error deleting batch: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/sections", response_model=SectionResponse)
async def add_section(section: SectionCreate):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT batch_id FROM Batches WHERE batch_id = ?", (section.batch_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Batch not found")

        cursor.execute("INSERT INTO Sections (batch_id, section_name) VALUES (?, ?)", (section.batch_id, section.section_name))
        section_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return {"section_id": section_id, "batch_id": section.batch_id, "section_name": section.section_name}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Section already exists for this batch")
    except Exception as e:
        logger.error(f"Error adding section: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.put("/sections/{section_id}", response_model=SectionResponse)
async def update_section(section_id: int, section: SectionCreate):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT batch_id FROM Batches WHERE batch_id = ?", (section.batch_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Batch not found")

        cursor.execute("UPDATE Sections SET batch_id = ?, section_name = ? WHERE section_id = ?", (section.batch_id, section.section_name, section_id))
        if cursor.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="Section not found")
        conn.commit()
        conn.close()
        return {"section_id": section_id, "batch_id": section.batch_id, "section_name": section.section_name}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Section already exists for this batch")
    except Exception as e:
        logger.error(f"Error updating section: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/sections/{section_id}")
async def delete_section(section_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Sections WHERE section_id = ?", (section_id,))
        if cursor.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="Section not found")
        conn.commit()
        conn.close()
        return {"message": "Section deleted successfully"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Cannot delete section with associated students or timetable")
    except Exception as e:
        logger.error(f"Error deleting section: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/subjects", response_model=SubjectResponse)
async def add_subject(subject: SubjectCreate):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT dept_id FROM Departments WHERE dept_name = ?", (subject.dept_name,))
        dept_result = cursor.fetchone()
        if not dept_result:
            conn.close()
            raise HTTPException(status_code=404, detail="Department not found")
        dept_id = dept_result["dept_id"]

        cursor.execute(
            "INSERT INTO Subjects (subject_code, subject_name, dept_id, year) VALUES (?, ?, ?, ?)",
            (subject.subject_code, subject.subject_name, dept_id, subject.year)
        )
        conn.commit()
        conn.close()
        return {"subject_code": subject.subject_code, "subject_name": subject.subject_name, "dept_name": subject.dept_name, "year": subject.year}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Subject code already exists")
    except Exception as e:
        logger.error(f"Error adding subject: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.put("/subjects/{old_subject_code}", response_model=SubjectResponse)
async def update_subject(old_subject_code: str, subject: SubjectCreate):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT dept_id FROM Departments WHERE dept_name = ?", (subject.dept_name,))
        dept_result = cursor.fetchone()
        if not dept_result:
            conn.close()
            raise HTTPException(status_code=404, detail="Department not found")
        dept_id = dept_result["dept_id"]

        cursor.execute(
            "UPDATE Subjects SET subject_code = ?, subject_name = ?, dept_id = ?, year = ? WHERE subject_code = ?",
            (subject.subject_code, subject.subject_name, dept_id, subject.year, old_subject_code)
        )
        if cursor.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="Subject not found")
        conn.commit()
        conn.close()
        return {"subject_code": subject.subject_code, "subject_name": subject.subject_name, "dept_name": subject.dept_name, "year": subject.year}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Subject code already exists")
    except Exception as e:
        logger.error(f"Error updating subject: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/subjects/{subject_code}")
async def delete_subject(subject_code: str):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Subjects WHERE subject_code = ?", (subject_code,))
        if cursor.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="Subject not found")
        conn.commit()
        conn.close()
        return {"message": "Subject deleted successfully"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Cannot delete subject with associated timetable")
    except Exception as e:
        logger.error(f"Error deleting subject: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/students", response_model=StudentResponse)
async def add_student(student: StudentCreate):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT section_id, section_name, batch_id FROM Sections WHERE section_id = ?", (student.section_id,))
        section_result = cursor.fetchone()
        if not section_result:
            conn.close()
            raise HTTPException(status_code=404, detail="Section not found")
        section_name = section_result["section_name"]
        batch_id = section_result["batch_id"]

        cursor.execute(
            "INSERT INTO Students (register_number, name, section_id) VALUES (?, ?, ?)",
            (student.register_number, student.name, student.section_id)
        )
        conn.commit()
        conn.close()
        return {
            "register_number": student.register_number,
            "name": student.name,
            "section_id": student.section_id,
            "section_name": section_name,
            "batch_id": batch_id
        }
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Register number already exists")
    except Exception as e:
        logger.error(f"Error adding student: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.put("/students/{old_register_number}", response_model=StudentResponse)
async def update_student(old_register_number: str, student: StudentCreate):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT section_id, section_name, batch_id FROM Sections WHERE section_id = ?", (student.section_id,))
        section_result = cursor.fetchone()
        if not section_result:
            conn.close()
            raise HTTPException(status_code=404, detail="Section not found")
        section_name = section_result["section_name"]
        batch_id = section_result["batch_id"]

        cursor.execute(
            "UPDATE Students SET register_number = ?, name = ?, section_id = ? WHERE register_number = ?",
            (student.register_number, student.name, student.section_id, old_register_number)
        )
        if cursor.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="Student not found")
        conn.commit()
        conn.close()
        return {
            "register_number": student.register_number,
            "name": student.name,
            "section_id": student.section_id,
            "section_name": section_name,
            "batch_id": batch_id
        }
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Register number already exists")
    except Exception as e:
        logger.error(f"Error updating student: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/students/{register_number}")
async def delete_student(register_number: str):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Students WHERE register_number = ?", (register_number,))
        if cursor.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="Student not found")
        conn.commit()
        conn.close()
        return {"message": "Student deleted successfully"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Cannot delete student with associated attendance")
    except Exception as e:
        logger.error(f"Error deleting student: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/upload-students-csv", response_model=dict)
async def upload_students_csv(
    file: UploadFile = File(...),
    dept_name: str = Form(...),
    year: int = Form(...)
):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify department
        cursor.execute("SELECT dept_id FROM Departments WHERE dept_name = ?", (dept_name,))
        dept_result = cursor.fetchone()
        if not dept_result:
            conn.close()
            raise HTTPException(status_code=404, detail="Department not found")
        dept_id = dept_result["dept_id"]

        # Verify batch
        cursor.execute("SELECT batch_id FROM Batches WHERE dept_id = ? AND year = ?", (dept_id, year))
        batch_result = cursor.fetchone()
        if not batch_result:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Batch not found for {dept_name} year {year}")
        batch_id = batch_result["batch_id"]

        # Fetch sections
        cursor.execute("SELECT section_id, section_name FROM Sections WHERE batch_id = ?", (batch_id,))
        sections = {row["section_name"]: row["section_id"] for row in cursor.fetchall()}
        if not sections:
            conn.close()
            raise HTTPException(status_code=404, detail=f"No sections found for {dept_name} year {year}")

        # Read CSV
        contents = await file.read()
        df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        required_columns = {'RegisterNumber', 'Name', 'Section'}
        if not required_columns.issubset(df.columns):
            conn.close()
            raise HTTPException(status_code=400, detail="CSV must contain RegisterNumber, Name, and Section columns")

        # Process students
        students_data = []
        for _, row in df.iterrows():
            register_number = str(row['RegisterNumber']).strip()
            name = str(row['Name']).strip()
            section_name = str(row['Section']).strip()

            if section_name not in sections:
                conn.close()
                raise HTTPException(status_code=400, detail=f"Section '{section_name}' not found for {dept_name} year {year}")

            section_id = sections[section_name]
            students_data.append((register_number, name, section_id))

        # Upsert students
        cursor.executemany("""
            INSERT INTO Students (register_number, name, section_id)
            VALUES (?, ?, ?)
            ON CONFLICT(register_number) DO UPDATE SET
                name = excluded.name,
                section_id = excluded.section_id
        """, students_data)
        conn.commit()

        # Fetch updated students
        cursor.execute("""
            SELECT s.register_number, s.name, s.section_id, sec.section_name, sec.batch_id
            FROM Students s
            JOIN Sections sec ON s.section_id = sec.section_id
            ORDER BY s.register_number
        """)
        students = [
            {
                "register_number": row["register_number"],
                "name": row["name"],
                "section_id": row["section_id"],
                "section_name": row["section_name"],
                "batch_id": row["batch_id"]
            }
            for row in cursor.fetchall()
        ]
        conn.close()

        return {"message": "Students uploaded successfully", "students": students}
    except pd.errors.EmptyDataError:
        raise HTTPException(status_code=400, detail="CSV file is empty")
    except pd.errors.ParserError:
        raise HTTPException(status_code=400, detail="Invalid CSV format")
    except sqlite3.IntegrityError as e:
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")
    except Exception as e:
        logger.error(f"Error uploading students CSV: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/timetables/{dept_name}/{year}")
async def get_timetables(dept_name: str, year: int):
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT timetable_id, subject_name, subject_code, date, start_time, end_time
        FROM Timetable
        WHERE dept_name = ? AND year = ?
        """,
        (dept_name, year),
    )
    timetables = [
        {
            "timetable_id": row[0],
            "subject_name": row[1],
            "subject_code": row[2],
            "date": row[3],
            "start_time": row[4],
            "end_time": row[5],
        }
        for row in cursor.fetchall()
    ]
    conn.close()
    return timetables

@app.get("/students/{dept_name}/{year}/{section_name}")
async def get_students(dept_name: str, year: int, section_name: str):
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT register_number, name
        FROM Students
        WHERE dept_name = ? AND year = ? AND section_name = ?
        """,
        (dept_name, year, section_name),
    )
    students = [
        {"register_number": row[0], "name": row[1]} for row in cursor.fetchall()
    ]
    conn.close()
    return students

@app.post("/attendance")
async def create_attendance(attendance: AttendanceCreate):
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO Attendance (timetable_id, register_number, is_present)
        VALUES (?, ?, ?)
        """,
        (
            attendance.timetable_id,
            attendance.register_number,
            attendance.is_present,
        ),
    )
    attendance_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"attendance_id": attendance_id}

@app.put("/attendance/{attendance_id}")
async def update_attendance(attendance_id: int, attendance: AttendanceUpdate):
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE Attendance
        SET timetable_id = ?, register_number = ?, is_present = ?
        WHERE attendance_id = ?
        """,
        (
            attendance.timetable_id,
            attendance.register_number,
            attendance.is_present,
            attendance_id,
        ),
    )
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Attendance not found")
    conn.commit()
    conn.close()
    return {"message": "Updated"}

@app.delete("/attendance/{attendance_id}")
async def delete_attendance(attendance_id: int):
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM Attendance WHERE attendance_id = ?", (attendance_id,)
    )
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Attendance not found")
    conn.commit()
    conn.close()
    return {"message": "Deleted"}

# Login endpoint
@app.post("/admin/login")
async def admin_login(login: AdminLoginRequest):
    conn = get_admin_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, password_hash, role FROM Admins WHERE username = ?", (login.username,))
    row = cursor.fetchone()
    conn.close()
    if row and verify_password(login.password, row["password_hash"]):
        access_token = create_access_token(data={"sub": row["username"], "role": row["role"]})
        return {"access_token": access_token, "token_type": "bearer"}
    raise HTTPException(status_code=401, detail="Invalid username or password")

# Admin management endpoints for SuperAdmin
@app.get("/admins")
async def list_admins(current_user: dict = Depends(get_current_admin)):
    if current_user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Forbidden")
    conn = get_admin_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role FROM Admins ORDER BY id")
    admins = [{"id": row["id"], "username": row["username"], "role": row["role"]} for row in cursor.fetchall()]
    conn.close()
    return admins

@app.post("/admins")
async def create_admin(user: AdminLoginRequest, current_user: dict = Depends(get_current_admin)):
    if current_user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Forbidden")
    pwd_hash = hash_password(user.password)
    conn = get_admin_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO Admins (username, password_hash, role) VALUES (?, ?, ?)",
            (user.username, pwd_hash, user.role)
        )
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return {"id": new_id, "username": user.username, "role": user.role}
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Username already exists")

@app.put("/admins/{admin_id}")
async def update_admin(admin_id: int, user: AdminLoginRequest, current_user: dict = Depends(get_current_admin)):
    if current_user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Forbidden")
    
    conn = get_admin_db_connection()
    cursor = conn.cursor()
    
    # Handle empty password case (don't update password if empty)
    if user.password:
        pwd_hash = hash_password(user.password)
        cursor.execute(
            "UPDATE Admins SET username = ?, password_hash = ?, role = ? WHERE id = ?", 
            (user.username, pwd_hash, user.role, admin_id)
        )
    else:
        # If password is empty, don't update the password
        cursor.execute(
            "UPDATE Admins SET username = ?, role = ? WHERE id = ?", 
            (user.username, user.role, admin_id)
        )
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Admin not found")
    
    conn.commit()
    conn.close()
    return {"id": admin_id, "username": user.username, "role": user.role}

@app.delete("/admins/{admin_id}")
async def delete_admin(admin_id: int, current_user: dict = Depends(get_current_admin)):
    if current_user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Forbidden")
    conn = get_admin_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Admins WHERE id = ?", (admin_id,))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Admin not found")
    conn.commit()
    conn.close()
    return {"message": "Admin deleted successfully"}

if __name__ == "__main__":
    print(f"Starting server with optimized concurrency settings...")
    uvicorn.run(
        "main:app", 
        host=SERVER_HOST, 
        port=int(SERVER_PORT), 
        reload=True,
        workers=1,  # Single worker for development; increase for production
        loop="asyncio",
        access_log=True,
        log_level="info"
    )