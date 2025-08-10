import os
import json
import uuid
import base64
import logging
import asyncio
import concurrent.futures
import threading
from typing import List, Dict, Tuple, Optional, Set
import numpy as np
import cv2
import torch
import torchvision.transforms as transforms
from PIL import Image
from scipy.spatial.distance import cosine
from ultralytics import YOLO
from pathlib import Path
import pickle
from collections import defaultdict
import time

# Django imports
from django.conf import settings
from django.core.cache import cache
from core.models import Student, Department, Batch, Section
from asgiref.sync import sync_to_async

# Import the LightCNN model
try:
    from backend.LightCNN.light_cnn import LightCNN_29Layers_v2
except ImportError:
    print("Warning: LightCNN model not found. Prediction service will not work.")
    LightCNN_29Layers_v2 = None

# Enhanced logging configuration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/prediction_service.log')
    ]
)
logger = logging.getLogger(__name__)

class TimedLogger:
    """Helper class for timing operations"""
    def __init__(self, logger, operation_name):
        self.logger = logger
        self.operation_name = operation_name
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        self.logger.info(f"Starting {self.operation_name}...")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        if exc_type is None:
            self.logger.info(f"✓ {self.operation_name} completed in {duration:.2f}s")
        else:
            self.logger.error(f"✗ {self.operation_name} failed after {duration:.2f}s: {exc_val}")


class PredictionService:
    """Service class that handles image processing and student prediction with concurrency support"""
    
    def __init__(self):
        self.face_model = None
        self.yolo_model = None
        self.device = None
        self.transform = None
        self.executor = None
        self.initialized = False
        self._init_lock = threading.Lock()
        self._gallery_cache = {}
        self._gallery_lock = threading.RLock()
        
        logger.info("🚀 PredictionService instance created")
        
    def initialize(self):
        """Initialize models and resources (thread-safe)"""
        if self.initialized:
            logger.info("✅ PredictionService already initialized")
            return
        
        with self._init_lock:
            if self.initialized:  # Double-check pattern
                logger.info("✅ PredictionService already initialized (double-check)")
                return
            
            try:
                with TimedLogger(logger, "PredictionService initialization"):
                    logger.info("🔧 Starting PredictionService initialization...")
                    
                    # Set device
                    self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                    logger.info(f"🖥️  Using {self.device} for inference")
                    
                    # Initialize thread pool for CPU-intensive tasks with higher worker count for concurrency
                    self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)
                    logger.info("🧵 Thread pool executor initialized with 8 workers")
                    
                    # Load face recognition model
                    model_path = "backend/checkpoints/LightCNN_29Layers_V2_checkpoint.pth.tar"
                    abs_model_path = os.path.abspath(model_path)
                    logger.info(f"🔍 Attempting to load face model from: {model_path} (abs: {abs_model_path})")
                    
                    if os.path.exists(model_path) and LightCNN_29Layers_v2:
                        with TimedLogger(logger, "Face model loading"):
                            logger.info("📄 Face model file found, loading...")
                            self.face_model = LightCNN_29Layers_v2(num_classes=100)
                            checkpoint = torch.load(model_path, map_location=self.device)
                            new_state_dict = {
                                k.replace("module.", ""): v 
                                for k, v in checkpoint.get("state_dict", checkpoint).items() 
                                if 'fc2' not in k
                            }
                            self.face_model.load_state_dict(new_state_dict, strict=False)
                            self.face_model = self.face_model.to(self.device)
                            self.face_model.eval()
                            logger.info("✅ Face recognition model loaded successfully")
                    else:
                        logger.warning(f"⚠️  Face recognition model not found at {model_path} (abs: {abs_model_path}) or LightCNN not available, using mock predictions")
                        
                    # Load YOLO model
                    yolo_path = "backend/yolo/weights/yolo11n-face.pt"
                    abs_yolo_path = os.path.abspath(yolo_path)
                    logger.info(f"🔍 Attempting to load YOLO model from: {yolo_path} (abs: {abs_yolo_path})")
                    
                    if os.path.exists(yolo_path):
                        with TimedLogger(logger, "YOLO model loading"):
                            logger.info("📄 YOLO model file found, loading...")
                            self.yolo_model = YOLO(yolo_path)
                            logger.info("✅ YOLO face detection model loaded successfully")
                    else:
                        logger.warning(f"⚠️  YOLO model not found at {yolo_path} (abs: {abs_yolo_path}), using mock face detection")
                    
                    # Set up transforms
                    self.transform = transforms.Compose([
                        transforms.Resize((128, 128)),
                        transforms.ToTensor(),
                        transforms.Normalize(mean=[0.5], std=[0.5])
                    ])
                    logger.info("🔄 Image transforms initialized")
                    
                    self.initialized = True
                    logger.info("🎉 PredictionService initialized successfully")
            
            except Exception as e:
                logger.error(f"❌ Error initializing PredictionService: {e}")
                logger.exception("Full exception details:")
                self.initialized = False

    def load_gallery(self, department_name: str, batch_year: int, section_names: List[str] = None) -> Dict[str, np.ndarray]:
        """Load student gallery embeddings from .pth files with thread-safe caching"""
        try:
            logger.info(f"📚 Loading gallery for dept: {department_name}, batch: {batch_year}, sections: {section_names}")
            
            # Create cache key based on department and batch
            cache_key = f"gallery_{department_name}_{batch_year}"
            
            # Try to get from cache first (thread-safe)
            with self._gallery_lock:
                if cache_key in self._gallery_cache:
                    gallery = self._gallery_cache[cache_key]
                    logger.info(f"💾 Loaded gallery from cache for {department_name}_{batch_year} with {len(gallery)} students")
                    return self._filter_gallery_by_sections(gallery, department_name, batch_year, section_names)
            
            # Load from file system
            gallery_path = f"gallery/gallery_{department_name}_{batch_year}.pth"
            abs_gallery_path = os.path.abspath(gallery_path)
            logger.info(f"🔍 Attempting to load gallery from: {gallery_path} (abs: {abs_gallery_path})")
            
            if not Path(abs_gallery_path).exists():
                logger.warning(f"⚠️  Gallery file {gallery_path} not found (abs: {abs_gallery_path})")
                return {}
            
            # Load gallery data
            with TimedLogger(logger, f"Gallery loading from {gallery_path}"):
                logger.info(f"📄 Loading gallery data from {gallery_path} (abs: {abs_gallery_path})")
                # Try safe loading first: allowlist numpy reconstruct and ndarray
                try:
                    try:
                        from numpy._core import multiarray as _multiarray
                        torch.serialization.add_safe_globals([_multiarray._reconstruct, np.ndarray])
                        logger.debug("Added numpy._core.multiarray._reconstruct and numpy.ndarray to torch safe globals")
                    except Exception as ge:
                        logger.debug(f"Could not add safe globals: {ge}")
                    gallery_data = torch.load(abs_gallery_path, map_location='cpu')
                except Exception as e:
                    logger.warning(
                        "Safe torch.load failed, falling back to weights_only=False as the gallery file is trusted: %s",
                        e,
                    )
                    try:
                        gallery_data = torch.load(abs_gallery_path, map_location='cpu', weights_only=False)
                    except TypeError:
                        gallery_data = torch.load(abs_gallery_path, map_location='cpu')
            
                # Handle np.ndarray or tensor values
                gallery = {}
                for k, v in gallery_data.items():
                    if isinstance(v, np.ndarray):
                        gallery[k] = v
                    elif isinstance(v, torch.Tensor):
                        gallery[k] = v.cpu().numpy()
                    else:
                        logger.warning(f"⚠️  Skipping invalid embedding for {k}: {type(v)}")
            
            # Cache the gallery (thread-safe)
            with self._gallery_lock:
                self._gallery_cache[cache_key] = gallery
                
            logger.info(f"✅ Loaded gallery {gallery_path} with {len(gallery)} identities")
            
            # Filter by sections if provided
            return self._filter_gallery_by_sections(gallery, department_name, batch_year, section_names)
            
        except Exception as e:
            logger.error(f"❌ Error loading gallery {gallery_path}: {e}")
            logger.exception("Gallery loading exception details:")
            return {}

    def _filter_gallery_by_sections(self, gallery: Dict[str, np.ndarray], 
                                   department_name: str, batch_year: int, 
                                   section_names: List[str] = None) -> Dict[str, np.ndarray]:
        """Filter gallery by specific sections"""
        logger.info(f"Filtering gallery by sections: {section_names}")
        
        if not section_names:
            logger.info(f"No section filter applied, returning full gallery with {len(gallery)} students")
            return gallery
            
        try:
            # Get student register numbers for the specified sections
            section_students = set()
            
            for section_name in section_names:
                logger.info(f"Getting students for section: {section_name}")
                students = Student.objects.filter(
                    section__section_name=section_name,
                    section__batch__batch_year=batch_year,
                    section__batch__dept__dept_name=department_name
                ).values_list('student_regno', flat=True)
                
                student_list = list(students)
                logger.info(f"Found {len(student_list)} students in section {section_name}: {student_list[:5]}...")
                section_students.update(student_list)
            
            logger.info(f"Total unique students across all sections: {len(section_students)}")
            
            # Filter gallery to only include students from these sections
            filtered_gallery = {
                reg_num: embedding 
                for reg_num, embedding in gallery.items() 
                if reg_num in section_students
            }
            
            logger.info(f"Filtered gallery from {len(gallery)} to {len(filtered_gallery)} students for sections {section_names}")
            return filtered_gallery
            
        except Exception as e:
            logger.error(f"Error filtering gallery by sections: {e}")
            return gallery
            
    async def process_image_async(self, image_bytes: bytes, threshold: float = 0.45, 
                                 sections_data: List[Dict] = None) -> Tuple[str, List[Dict]]:
        """Async wrapper for image processing with support for multiple sections"""
        logger.info(f"🖼️  Starting async image processing (threshold: {threshold})")
        
        if not self.initialized:
            logger.info("🔧 Service not initialized, initializing now...")
            self.initialize()
            
        if not self.face_model or not self.yolo_model:
            logger.warning("⚠️  Models not available, returning mock data")
            return await self._mock_process_image(image_bytes)
            
        # Process sections data to get combined gallery and student lists
        combined_gallery = {}
        all_section_students = set()
        
        logger.info(f"📋 Processing {len(sections_data) if sections_data else 0} section groups")
        
        if sections_data:
            for i, section_info in enumerate(sections_data):
                dept_name = section_info.get('department')
                batch_year = section_info.get('batch_year')
                section_names = section_info.get('section_names', [])
                
                logger.info(f"📊 Processing section group {i+1}: {dept_name} {batch_year} - {section_names}")
                
                if dept_name and batch_year:
                    # Load gallery for this department/batch/sections via sync_to_async
                    gallery = await sync_to_async(self.load_gallery)(dept_name, batch_year, section_names)
                    combined_gallery.update(gallery)
                    logger.info(f"📚 Added {len(gallery)} embeddings to combined gallery")
                    
                    # Get students for these sections using sync_to_async
                    for section_name in section_names:
                        try:
                            student_list = await sync_to_async(list)(
                                Student.objects.filter(
                                    section__section_name=section_name,
                                    section__batch__batch_year=batch_year,
                                    section__batch__dept__dept_name=dept_name
                                ).values_list('student_regno', flat=True)
                            )
                            all_section_students.update(student_list)
                            logger.info(f"👥 Added {len(student_list)} students from section {section_name}")
                        except Exception as e:
                            logger.error(f"❌ Error fetching students for section {section_name}: {e}")
        
        # Run processing in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._process_image_sync,
            image_bytes, threshold, combined_gallery, all_section_students
        )
        
    def _process_image_sync(self, image_bytes: bytes, threshold: float, 
                           gallery: Dict[str, np.ndarray], section_students: Set[str]) -> Tuple[str, List[Dict]]:
        """Synchronous image processing logic based on temp_main.py"""
        try:
            with TimedLogger(logger, "Image processing"):
                logger.info(f"🔍 Starting image processing with threshold {threshold}")
                logger.info(f"📚 Gallery size: {len(gallery)} students")
                logger.info(f"👥 Section students: {len(section_students)} students")
                
                # Decode image
                nparr = np.frombuffer(image_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is None:
                    raise ValueError("Could not decode image")
                
                logger.info(f"📸 Image decoded: {img.shape[1]}x{img.shape[0]} pixels")
                    
                result_img = img.copy()
                detected_students = []
                detected_ids = set()
                
                # Detect faces using YOLO
                logger.info("🔍 Running YOLO face detection...")
                results = self.yolo_model(img)
                total_faces = len(results[0].boxes) if results and len(results) > 0 else 0
                logger.info(f"👤 YOLO detected {total_faces} faces")
                
                # Step 1: Get all faces and their embeddings
                faces_data = []
                valid_faces = 0
                
                for result in results:
                    for i, box in enumerate(result.boxes):
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        h, w = img.shape[:2]
                        
                        # Add padding
                        face_w, face_h = x2 - x1, y2 - y1
                        pad_x, pad_y = int(face_w * 0.2), int(face_h * 0.2)
                        x1, y1 = max(0, x1 - pad_x), max(0, y1 - pad_y)
                        x2, y2 = min(w, x2 + pad_x), min(h, y2 + pad_y)
                        
                        # Skip too small faces
                        if (x2 - x1) < 32 or (y2 - y1) < 32:
                            logger.debug(f"⚠️  Skipping face {i+1} too small ({x2-x1}x{y2-y1})")
                            continue
                            
                        face = img[y1:y2, x1:x2]
                        if face.size == 0:
                            logger.warning(f"⚠️  Empty face crop at {x1},{y1},{x2},{y2}")
                            continue
                        
                        valid_faces += 1
                        logger.debug(f"🔄 Processing face {valid_faces}: {x2-x1}x{y2-y1} pixels")
                            
                        # Extract embedding
                        gray_face = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
                        face_pil = Image.fromarray(gray_face)
                        face_tensor = self.transform(face_pil).unsqueeze(0).to(self.device)
                        
                        with torch.no_grad():
                            _, embedding = self.face_model(face_tensor)
                            face_embedding = embedding.cpu().squeeze().numpy()
                        
                        logger.debug(f"🧠 Extracted embedding for face {valid_faces}")
                            
                        # Store all potential matches for this face
                        matches = []
                        gallery_checked = 0
                        for identity, gallery_embedding in gallery.items():
                            # Only consider matches for students in the selected sections
                            if section_students and identity not in section_students:
                                continue
                            
                            gallery_checked += 1
                            similarity = 1 - cosine(face_embedding, gallery_embedding)
                            if similarity > threshold:
                                matches.append((identity, similarity))
                                logger.debug(f"✅ Face {valid_faces} matches {identity}: {similarity:.3f}")
                        
                        logger.debug(f"🔍 Face {valid_faces}: checked {gallery_checked} gallery entries, found {len(matches)} matches")
                                
                        # Sort matches by similarity (highest first)
                        matches.sort(key=lambda x: x[1], reverse=True)
                        
                        faces_data.append({
                            'coords': (x1, y1, x2, y2),
                            'embedding': face_embedding,
                            'matches': matches,
                            'best_match': "Unknown",
                            'best_score': -1
                        })
                
                logger.info(f"🎯 Processed {valid_faces} valid faces from {total_faces} detected faces")
                
                # Step 2: Assign identities based on highest confidence without duplicates
                used_identities = set()
                
                # First pass: assign identities to faces with highest confidence
                logger.info("🎯 Assigning identities to faces...")
                for face_idx, face in enumerate(sorted(faces_data, key=lambda x: max([m[1] for m in x['matches']]) if x['matches'] else 0, reverse=True)):
                    for identity, score in face['matches']:
                        if identity not in used_identities:
                            face['best_match'] = identity
                            face['best_score'] = score
                            used_identities.add(identity)
                            detected_ids.add(identity)
                            logger.info(f"✅ Assigned {identity} to face {face_idx+1} (confidence: {score:.3f})")
                            break
                            
                # Step 3: Draw the results and collect detected students
                logger.info("📝 Collecting student information...")
                for face_idx, face in enumerate(faces_data):
                    x1, y1, x2, y2 = face['coords']
                    best_match = face['best_match']
                    best_score = face['best_score']
                    
                    if best_match != "Unknown":
                        # Get student info
                        try:
                            student = Student.objects.get(student_regno=best_match)
                            detected_students.append({
                                'register_number': best_match,
                                'name': student.name,
                                'confidence': best_score
                            })
                            logger.info(f"👤 Added student: {best_match} ({student.name}) - confidence: {best_score:.3f}")
                        except Student.DoesNotExist:
                            logger.warning(f"⚠️  Student {best_match} not found in database")
                            
                    # Draw bounding box
                    color = (0, 255, 0) if best_match != "Unknown" else (0, 0, 255)
                    cv2.rectangle(result_img, (x1, y1), (x2, y2), color, 2)
                    label = f"{best_match} ({best_score:.2f})" if best_match != "Unknown" else "Unknown"
                    cv2.putText(result_img, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                    
                # Encode result image
                _, buffer = cv2.imencode('.jpg', result_img)
                img_base64 = base64.b64encode(buffer).decode('utf-8')
                
                logger.info(f"🎉 Image processing complete: detected {len(detected_students)} students from {len(faces_data)} faces")
                return img_base64, detected_students
            
        except Exception as e:
            logger.error(f"❌ Error processing image: {e}")
            logger.exception("Image processing exception details:")
            return None, []
            
    async def _mock_process_image(self, image_bytes: bytes) -> Tuple[str, List[Dict]]:
        """Mock image processing for testing when models are not available"""
        try:
            logger.info("🎭 Using mock image processing (models not available)")
            
            # Just return the original image encoded
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            logger.info(f"📸 Mock processing image: {img.shape[1]}x{img.shape[0]} pixels")
            
            # Add some mock bounding boxes
            cv2.rectangle(img, (50, 50), (150, 150), (0, 255, 0), 2)
            cv2.putText(img, "Mock Detection", (50, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            _, buffer = cv2.imencode('.jpg', img)
            img_base64 = base64.b64encode(buffer).decode('utf-8')
            
            # Return mock detected students
            mock_students = [
                {
                    'register_number': '2027CS001',
                    'name': 'Mock Student 1',
                    'confidence': 0.85
                },
                {
                    'register_number': '2027CS002', 
                    'name': 'Mock Student 2',
                    'confidence': 0.92
                }
            ]
            
            logger.info(f"🎭 Mock processing complete: returning {len(mock_students)} mock students")
            return img_base64, mock_students
            
            return img_base64, mock_students
            
        except Exception as e:
            logger.error(f"Error in mock processing: {e}")
            return None, []


# Global service instance
prediction_service = PredictionService()
