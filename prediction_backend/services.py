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

# Set up logging first before any logger usage
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join('logs','prediction_service.log'))
    ]
)
logger = logging.getLogger(__name__)

# Import the LightCNN model
import sys
# Add the backend directory to Python path to import LightCNN
backend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

try:
    logger.info("🔍 Attempting to import LightCNN_29Layers_v2 from LightCNN.light_cnn")
    from LightCNN.light_cnn import LightCNN_29Layers_v2
    logger.info("✅ LightCNN_29Layers_v2 imported successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import LightCNN_29Layers_v2: {e}")
    print(f"Warning: LightCNN model not found. Error: {e}. Prediction service will not work.")
    LightCNN_29Layers_v2 = None

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
                    logger.info(f"🔍 Model file exists: {os.path.exists(model_path)}")
                    logger.info(f"🔍 LightCNN_29Layers_v2 is available: {LightCNN_29Layers_v2 is not None}")
                    
                    if os.path.exists(model_path) and LightCNN_29Layers_v2:
                    # if os.path.exists(model_path):
                        with TimedLogger(logger, "Face model loading"):
                            logger.info("📄 Face model file found, loading...")
                            try:
                                self.face_model = LightCNN_29Layers_v2(num_classes=100)
                                logger.info("✅ LightCNN_29Layers_v2 model instance created")
                                
                                checkpoint = torch.load(model_path, map_location=self.device)
                                logger.info(f"✅ Checkpoint loaded, keys: {list(checkpoint.keys())}")
                                
                                new_state_dict = {
                                    k.replace("module.", ""): v 
                                    for k, v in checkpoint.get("state_dict", checkpoint).items() 
                                    if 'fc2' not in k
                                }
                                logger.info(f"✅ State dict prepared with {len(new_state_dict)} keys")
                                
                                self.face_model.load_state_dict(new_state_dict, strict=False)
                                logger.info("✅ State dict loaded into model")
                                
                                self.face_model = self.face_model.to(self.device)
                                logger.info(f"✅ Model moved to device: {self.device}")
                                
                                self.face_model.eval()
                                logger.info("✅ Face recognition model loaded successfully and set to eval mode")
                            except Exception as model_e:
                                logger.error(f"❌ Error loading face model: {model_e}")
                                logger.exception("Face model loading exception details:")
                                self.face_model = None
                    else:
                        if not os.path.exists(model_path):
                            logger.error(f"❌ Face recognition model file not found at {model_path} (abs: {abs_model_path})")
                        if not LightCNN_29Layers_v2:
                            logger.error("❌ LightCNN_29Layers_v2 class not available")
                        logger.warning("⚠️  Using mock predictions for face recognition")
                        self.face_model = None
                        
                    # Load YOLO model
                    yolo_path = "prediction_backend/yolo/weights/yolo11n-face.pt"
                    abs_yolo_path = os.path.abspath(yolo_path)
                    logger.info(f"🔍 Attempting to load YOLO model from: {yolo_path} (abs: {abs_yolo_path})")
                    logger.info(f"🔍 YOLO model file exists: {os.path.exists(yolo_path)}")
                    
                    if os.path.exists(yolo_path):
                        with TimedLogger(logger, "YOLO model loading"):
                            logger.info("📄 YOLO model file found, loading...")
                            try:
                                self.yolo_model = YOLO(yolo_path)
                                logger.info("✅ YOLO face detection model loaded successfully")
                            except Exception as yolo_e:
                                logger.error(f"❌ Error loading YOLO model: {yolo_e}")
                                logger.exception("YOLO model loading exception details:")
                                self.yolo_model = None
                    else:
                        logger.error(f"❌ YOLO model file not found at {yolo_path} (abs: {abs_yolo_path})")
                        logger.warning("⚠️  Using mock face detection")
                        self.yolo_model = None
                        
                    # Set up transforms
                    try:
                        self.transform = transforms.Compose([
                            transforms.Resize((128, 128)),
                            transforms.ToTensor(),
                            transforms.Normalize(mean=[0.5], std=[0.5])
                        ])
                        logger.info("✅ Image transforms initialized successfully")
                    except Exception as transform_e:
                        logger.error(f"❌ Error setting up transforms: {transform_e}")
                        logger.exception("Transform setup exception details:")
                        raise
                    
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
            logger.info(f"🔍 Gallery file exists: {os.path.exists(gallery_path)}")
            logger.info(f"🔍 Gallery file size: {os.path.getsize(abs_gallery_path) if os.path.exists(abs_gallery_path) else 'N/A'} bytes")
            
            # DEBUG: Show what files exist and what we're looking for
            gallery_dir = os.path.dirname(abs_gallery_path)
            if os.path.exists(gallery_dir):
                available_files = [f for f in os.listdir(gallery_dir) if f.endswith('.pth')]
                logger.debug(f"🔍 DEBUG - Available .pth files in {gallery_dir}: {available_files}")
            else:
                logger.debug(f"🔍 DEBUG - Gallery directory {gallery_dir} does not exist")
            
            logger.debug(f"🔍 DEBUG - Looking for gallery file: gallery_{department_name}_{batch_year}.pth")
            logger.debug(f"🔍 DEBUG - Department name requested: '{department_name}'")
            logger.debug(f"🔍 DEBUG - Batch year requested: '{batch_year}'")
            logger.debug(f"🔍 DEBUG - Expected full filename: 'gallery_{department_name}_{batch_year}.pth'")
            
            if not Path(abs_gallery_path).exists():
                logger.error(f"❌ Gallery file {gallery_path} not found (abs: {abs_gallery_path})")
                return {}
            
            # Load gallery data
            with TimedLogger(logger, f"Gallery loading from {gallery_path}"):
                logger.info(f"📄 Loading gallery data from {gallery_path} (abs: {abs_gallery_path})")
                try:
                    # Try safe loading first: allowlist numpy reconstruct and ndarray
                    try:
                        from numpy._core import multiarray as _multiarray
                        torch.serialization.add_safe_globals([_multiarray._reconstruct, np.ndarray])
                        logger.debug("✅ Added numpy._core.multiarray._reconstruct and numpy.ndarray to torch safe globals")
                    except Exception as ge:
                        logger.debug(f"⚠️  Could not add safe globals: {ge}")
                    
                    gallery_data = torch.load(gallery_path, map_location='cpu')
                    logger.info(f"✅ Gallery loaded with torch.load (safe mode)")
                    
                except Exception as e:
                    logger.warning(f"⚠️  Safe torch.load failed: {e}, falling back to weights_only=False")
                    try:
                        gallery_data = torch.load(abs_gallery_path, map_location='cpu', weights_only=False)
                        logger.info(f"✅ Gallery loaded with torch.load (weights_only=False)")
                    except TypeError as te:
                        logger.warning(f"⚠️  weights_only parameter not supported: {te}, using basic torch.load")
                        gallery_data = torch.load(abs_gallery_path, map_location='cpu')
                        logger.info(f"✅ Gallery loaded with basic torch.load")
                    except Exception as e2:
                        logger.error(f"❌ Failed to load gallery with all methods: {e2}")
                        logger.exception("Gallery loading exception details:")
                        return {}
                
                logger.info(f"📊 Raw gallery data type: {type(gallery_data)}, keys: {list(gallery_data.keys()) if isinstance(gallery_data, dict) else 'Not a dict'}")
            
                # Handle np.ndarray or tensor values
                gallery = {}
                logger.info("🔄 Processing gallery data entries...")
                for k, v in gallery_data.items():
                    # Convert keys to integers like test_detection.py
                    try:
                        idx = int(k)
                    except Exception:
                        idx = k  # fallback to string label
                    if isinstance(v, np.ndarray):
                        gallery[k] = v
                        logger.debug(f"✅ Added numpy array for {k}: shape {v.shape}")
                    elif isinstance(v, torch.Tensor):
                        gallery[k] = v.cpu().numpy()
                        logger.debug(f"✅ Added tensor (converted to numpy) for {k}: shape {v.shape}")
                    else:
                        logger.warning(f"⚠️  Skipping invalid embedding for {k}: {type(v)}")
                
                logger.info(f"📊 Processed {len(gallery)} valid embeddings from {len(gallery_data)} entries")
            
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

    def _filter_gallery_by_sections(self, gallery: Dict, 
                                   department_name: str, batch_year: int, 
                                   section_names: List[str] = None) -> Dict:
        """Filter gallery by specific sections"""
        logger.info(f"Filtering gallery by sections: {section_names}")
        
        if not section_names:
            logger.info(f"No section filter applied, returning full gallery with {len(gallery)} students")
            return gallery
            
        try:
            # Since test_detection.py uses integer indices, we'll return the full gallery
            # The section filtering logic would need to be adjusted based on how 
            # integer class indices map to actual students
            logger.info(f"Gallery filtering with integer keys - returning full gallery for now")
            return gallery
            
        except Exception as e:
            logger.error(f"Error filtering gallery by sections: {e}")
            return gallery
            
    async def process_image_async(self, image_bytes: bytes, threshold: float = 0.45, 
                                 sections_data: List[Dict] = None) -> Tuple[str, List[Dict]]:
        """Async wrapper for image processing with support for multiple sections"""
        logger.info(f"🖼️  Starting async image processing (threshold: {threshold})")
        logger.info(f"📊 Input: image_bytes size: {len(image_bytes)} bytes, sections_data: {len(sections_data) if sections_data else 0} sections")
        
        if not self.initialized:
            logger.warning("⚠️  Service not initialized, initializing now...")
            try:
                self.initialize()
                logger.info("✅ Service initialized successfully")
            except Exception as init_e:
                logger.error(f"❌ Failed to initialize service: {init_e}")
                logger.exception("Service initialization exception details:")
                return None, []
            
        if not self.face_model or not self.yolo_model:
            logger.warning("⚠️  Models not available (face_model: {}, yolo_model: {}), returning mock data".format(
                "available" if self.face_model else "missing",
                "available" if self.yolo_model else "missing"
            ))
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
                    try:
                        # Load gallery for this department/batch/sections via sync_to_async
                        gallery = await sync_to_async(self.load_gallery)(dept_name, batch_year, section_names)
                        combined_gallery.update(gallery)
                        logger.info(f"📚 Added {len(gallery)} embeddings to combined gallery (total: {len(combined_gallery)})")
                    except Exception as gallery_e:
                        logger.error(f"❌ Error loading gallery for {dept_name}_{batch_year}: {gallery_e}")
                        logger.exception("Gallery loading exception details:")
                        continue
                    
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
                            logger.info(f"👥 Added {len(student_list)} students from section {section_name} (total: {len(all_section_students)})")
                        except Exception as student_e:
                            logger.error(f"❌ Error fetching students for section {section_name}: {student_e}")
                            logger.exception("Student fetching exception details:")
                else:
                    logger.warning(f"⚠️  Incomplete section info for group {i+1}: dept_name={dept_name}, batch_year={batch_year}")
        else:
            logger.warning("⚠️  No sections_data provided")
        
        logger.info(f"📊 Final combined gallery size: {len(combined_gallery)} students")
        logger.info(f"👥 Final section students size: {len(all_section_students)} students")
        
        # Run processing in thread pool
        logger.info("🧵 Submitting image processing to thread pool executor...")
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                self.executor,
                self._process_image_sync,
                image_bytes, threshold, combined_gallery, all_section_students
            )
            logger.info(f"✅ Thread pool execution completed successfully")
            return result
        except Exception as executor_e:
            logger.error(f"❌ Error in thread pool execution: {executor_e}")
            logger.exception("Thread pool execution exception details:")
            return None, []
        
    def _process_image_sync(self, image_bytes: bytes, threshold: float, 
                           gallery: Dict[str, np.ndarray], section_students: Set[str]) -> Tuple[str, List[Dict]]:
        """Synchronous image processing logic based on temp_main.py"""
        try:
            with TimedLogger(logger, "Image processing"):
                logger.info(f"🔍 Starting image processing with threshold {threshold}")
                logger.info(f"📚 Gallery size: {len(gallery)} students")
                logger.info(f"👥 Section students: {len(section_students)} students")
                logger.info(f"📸 Image bytes size: {len(image_bytes)} bytes")
                
                # Decode image
                try:
                    nparr = np.frombuffer(image_bytes, np.uint8)
                    logger.debug(f"✅ Created numpy array from bytes: shape {nparr.shape}")
                    
                    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    if img is None:
                        logger.error("❌ Could not decode image - cv2.imdecode returned None")
                        raise ValueError("Could not decode image")
                    
                    logger.info(f"✅ Image decoded successfully: {img.shape[1]}x{img.shape[0]} pixels, channels: {img.shape[2] if len(img.shape) > 2 else 'N/A'}")
                except Exception as decode_e:
                    logger.error(f"❌ Error decoding image: {decode_e}")
                    logger.exception("Image decoding exception details:")
                    return None, []
                    
                result_img = img.copy()
                detected_students = []
                detected_ids = set()
                
                # Detect faces using YOLO
                logger.info("🔍 Running YOLO face detection...")
                try:
                    results = self.yolo_model(img)
                    logger.info(f"✅ YOLO inference completed")
                    
                    total_faces = len(results[0].boxes) if results and len(results) > 0 else 0
                    logger.info(f"👤 YOLO detected {total_faces} faces")
                    
                    if total_faces == 0:
                        logger.warning("⚠️  No faces detected by YOLO")
                    
                except Exception as yolo_e:
                    logger.error(f"❌ Error during YOLO face detection: {yolo_e}")
                    logger.exception("YOLO detection exception details:")
                    return None, []
                
                # Step 1: Get all faces and their embeddings
                faces_data = []
                valid_faces = 0
                
                for result in results:
                    for i, box in enumerate(result.boxes):
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        
                        # Crop and preprocess face (no padding like test_detection.py)
                        face = img[y1:y2, x1:x2]
                        if face.size == 0:
                            logger.warning(f"⚠️  Empty face crop at {x1},{y1},{x2},{y2}")
                            continue
                        
                        valid_faces += 1
                        logger.debug(f"🔄 Processing face {valid_faces}: {x2-x1}x{y2-y1} pixels")
                        
                        # Convert to grayscale and process like test_detection.py
                        gray_face = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
                        face_pil = Image.fromarray(gray_face)
                        face_tensor = self.transform(face_pil).unsqueeze(0).to(self.device)
                        
                        # First approach: Cosine similarity with gallery (like test_detection.py)
                        with torch.no_grad():
                            _, embedding = self.face_model(face_tensor)
                            face_embedding = embedding.cpu().squeeze().numpy()
                        
                        # Cosine similarity with gallery (all)
                        similarities = []
                        gallery_indices = list(gallery.keys())
                        for class_idx in gallery_indices:
                            gallery_emb = gallery[class_idx]
                            sim = 1 - cosine(face_embedding, gallery_emb)
                            similarities.append((class_idx, sim))
                        similarities.sort(key=lambda x: x[1], reverse=True)
                        pred_class_cosine, best_sim = similarities[0] if similarities else ("Unknown", 0)
                        
                        # Log top 3 cosine similarities like test_detection.py
                        top_n = 3
                        logger.info(f"Face {valid_faces}: bbox=({x1},{y1},{x2},{y2}), predicted class index (cosine)={pred_class_cosine}, best similarity={best_sim:.4f}, embedding[:5]={face_embedding[:5]}")
                        logger.info(f"  Top {top_n} cosine similarities:")
                        for rank, (class_idx, sim) in enumerate(similarities[:top_n], 1):
                            logger.info(f"    {rank}. class {class_idx}: {sim:.4f}")
                        
                        faces_data.append({
                            'coords': (x1, y1, x2, y2),
                            'embedding': face_embedding,
                            'best_match': pred_class_cosine,
                            'best_score': best_sim
                        })
                        
                        # Second approach: Softmax probabilities (duplicate processing like test_detection.py)
                        # This duplicates the face processing exactly like test_detection.py
                        face = img[y1:y2, x1:x2]  # Re-crop face
                        if face.size == 0:
                            logger.info(f"Face {valid_faces}: empty crop, skipping.")
                            continue
                        gray_face = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
                        face_pil = Image.fromarray(gray_face)
                        face_tensor = self.transform(face_pil).unsqueeze(0).to(self.device)
                        
                        with torch.no_grad():
                            logits, embedding = self.face_model(face_tensor)
                            face_embedding = embedding.cpu().squeeze().numpy()
                            probs = torch.softmax(logits, dim=1).cpu().numpy().squeeze()
                            
                            # Restrict to class indices like test_detection.py
                            class_start = 0
                            class_end = 111
                            restricted_probs = probs[class_start : class_end + 1]
                            restricted_indices = np.arange(class_start, class_end + 1)
                            pred_idx_in_restricted = int(np.argmax(restricted_probs))
                            pred_class_softmax = int(restricted_indices[pred_idx_in_restricted])
                        
                        # Print softmax results like test_detection.py
                        top_indices_in_restricted = np.argsort(restricted_probs)[::-1][:top_n]
                        logger.info(f"Face {valid_faces}: bbox=({x1},{y1},{x2},{y2}), predicted class index (restricted)={pred_class_softmax}, embedding[:5]={face_embedding[:5]}")
                        logger.info(f"  Top {top_n} classes in [{class_start}-{class_end}]:")
                        for rank, idx_in_restricted in enumerate(top_indices_in_restricted, 1):
                            class_idx = int(restricted_indices[idx_in_restricted])
                            prob = restricted_probs[idx_in_restricted]
                            logger.info(f"    {rank}. class {class_idx}: {prob:.4f}")
                
                logger.info(f"🎯 Processed {valid_faces} valid faces from {total_faces} detected faces")
                
                # Simple assignment like test_detection.py (no duplicate prevention)
                logger.info("🎯 Drawing results like test_detection.py...")
                for face_idx, face in enumerate(faces_data):
                    x1, y1, x2, y2 = face['coords']
                    best_match = face['best_match']
                    best_score = face['best_score']
                    
                    # Draw bounding box like test_detection.py
                    cv2.rectangle(result_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(result_img, f"{best_match}", (x1, max(15, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    
                    # Add to detected students if it's a valid match
                    if best_match != "Unknown" and best_score > threshold:
                        # Try to map class index to student (this may need adjustment based on your gallery structure)
                        try:
                            # For now, we'll use the class index as register number
                            # You may need to adjust this mapping based on your data
                            detected_students.append({
                                'register_number': str(best_match),
                                'name': f'Student_{best_match}',
                                'confidence': best_score
                            })
                            detected_ids.add(str(best_match))
                            logger.info(f"👤 Added student: {best_match} - confidence: {best_score:.3f}")
                        except Exception as e:
                            logger.warning(f"⚠️  Could not add student {best_match}: {e}")
                    
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
