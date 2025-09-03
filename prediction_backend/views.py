import json
import uuid
import logging
import asyncio
import base64
import os
import tempfile
import shutil
from typing import List, Dict
from datetime import datetime, timedelta
from asgiref.sync import sync_to_async

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db import models

from core.models import Student, Subject, Section, Department, Batch, Attendance, Timetable
from .models import AttendancePrediction, AttendanceSubmission, ProcessedImage
from .services import prediction_service

logger = logging.getLogger(__name__)


def cleanup_old_temp_directories(hours_old=24):
    """Clean up temp directories older than specified hours"""
    try:
        temp_dir = tempfile.gettempdir()
        current_time = datetime.now()
        
        for item in os.listdir(temp_dir):
            if item.startswith("attendance_session_"):
                item_path = os.path.join(temp_dir, item)
                if os.path.isdir(item_path):
                    # Check if directory is older than specified hours
                    creation_time = datetime.fromtimestamp(os.path.getctime(item_path))
                    if current_time - creation_time > timedelta(hours=hours_old):
                        logger.info(f"🗑️  Cleaning up old temp directory: {item_path}")
                        shutil.rmtree(item_path, ignore_errors=True)
        
    except Exception as e:
        logger.warning(f"⚠️  Error during temp directory cleanup: {e}")


def get_session_temp_directory(session_id):
    """Get or create temp directory for a session"""
    session_temp_dir = os.path.join(tempfile.gettempdir(), f"attendance_session_{session_id}")
    os.makedirs(session_temp_dir, exist_ok=True)
    return session_temp_dir


@csrf_exempt
@require_http_methods(["POST"])
def process_images(request):
    """API endpoint to process multiple uploaded images and predict student attendance"""
    start_time = datetime.now()
    logger.info(f"🚀 Starting image processing request at {start_time}")
    
    try:
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        logger.info(f"📋 Generated session ID: {session_id}")

        # Parse request data
        data = (
            json.loads(request.body)
            if request.content_type == "application/json"
            else request.POST
        )
        logger.info(f"📥 Received request data: {list(data.keys())}")

        # Get image data (list of base64 encoded images)
        images_data = data.get("images_data", [])
        if not images_data:
            logger.warning("❌ No image data provided in request")
            return JsonResponse({"error": "No image data provided"}, status=400)
        
        logger.info(f"📸 Received {len(images_data)} images for processing")

        # Get session parameters
        dept_name = data.get("dept_name")
        batch_year = int(data.get("batch_year")) if data.get("batch_year") else None
        subject_code = data.get("subject_code")
        sections_str = data.get("sections", "")
        time_slot = data.get("time_slot")  # Extract time slot information
        threshold = float(data.get("threshold", 0.45))
        
        logger.info(f"📊 Session parameters: dept={dept_name}, batch={batch_year}, subject={subject_code}, sections={sections_str}, time_slot={time_slot}, threshold={threshold}")

        if not all([dept_name, batch_year, subject_code]):
            logger.warning("❌ Missing required parameters")
            return JsonResponse({"error": "Missing required parameters"}, status=400)

        # Parse sections (format: "Department-Section,Department-Section")
        sections_data = []
        if sections_str:
            logger.info(f"🔍 Parsing sections string: {sections_str}")
            section_parts = sections_str.split(",")
            for section_part in section_parts:
                try:
                    if "-" in section_part:
                        dept_section = section_part.strip()
                        section_name = dept_section.split("-")[
                            -1
                        ]  # Get the last part as section name
                        sections_data.append(
                            {
                                "department": dept_name,
                                "batch_year": batch_year,
                                "section_names": [section_name],
                            }
                        )
                        logger.info(f"✅ Parsed section: {dept_name}-{section_name}")
                except Exception as e:
                    logger.warning(f"⚠️  Error parsing section {section_part}: {e}")

        # If no sections parsed, use all sections for the department/batch
        if not sections_data:
            logger.info("📂 No specific sections parsed, using all sections for department/batch")
            sections_data.append(
                {"department": dept_name, "batch_year": batch_year, "section_names": []}
            )
        
        logger.info(f"📋 Final sections data: {sections_data}")

        # Get subject and section objects for database operations
        try:
            logger.info(f"🔍 Looking up database objects...")
            department = Department.objects.get(dept_name=dept_name)
            logger.info(f"✅ Found department: {department}")
            
            batch = Batch.objects.get(dept=department, batch_year=batch_year)
            logger.info(f"✅ Found batch: {batch}")
            
            subject = Subject.objects.get(subject_code=subject_code, batch=batch)
            logger.info(f"✅ Found subject: {subject}")

            # Get the first section for database storage (we'll process all specified sections)
            if sections_data and sections_data[0]["section_names"]:
                section_name = sections_data[0]["section_names"][0]
                section = Section.objects.get(batch=batch, section_name=section_name)
                logger.info(f"✅ Found section: {section}")
            else:
                section = Section.objects.filter(batch=batch).first()
                logger.info(f"✅ Using first available section: {section}")

            if not section:
                logger.warning("❌ No section found")
                return JsonResponse({"error": "Section not found"}, status=404)

        except (
            Department.DoesNotExist,
            Batch.DoesNotExist,
            Subject.DoesNotExist,
            Section.DoesNotExist,
        ) as e:
            logger.error(f"❌ Database object not found: {str(e)}")
            return JsonResponse(
                {"error": f"Database object not found: {str(e)}"}, status=404
            )

        # Initialize prediction service
        logger.info("🔧 Initializing prediction service...")
        prediction_service.initialize()
        logger.info("✅ Prediction service initialized")

        # Create temp directory for this session and cleanup old ones
        cleanup_old_temp_directories(hours_old=24)
        session_temp_dir = get_session_temp_directory(session_id)
        logger.info(f"📁 Created temp directory: {session_temp_dir}")

        # Process all images synchronously (avoid async issues)
        all_detected_students = {}  # Use dict to avoid duplicates
        processed_images = []
        
        logger.info(f"🖼️  Starting to process {len(images_data)} images...")

        for i, image_data in enumerate(images_data):
            logger.info(f"🔄 Processing image {i+1}/{len(images_data)}")
            try:
                # Decode base64 image
                if image_data.startswith("data:image"):
                    image_data = image_data.split(",")[1]
                image_bytes = base64.b64decode(image_data)
                logger.info(f"✅ Decoded image {i+1} ({len(image_bytes)} bytes)")

                # Save original image to temp folder
                # original_image_path = os.path.join(session_temp_dir, f"original_image_{i+1}.jpg")
                # with open(original_image_path, 'wb') as f:
                #     f.write(image_bytes)
                # logger.info(f"💾 Saved original image to: {original_image_path}")

                # Process image synchronously - avoid async entirely for this version
                logger.info(f"🤖 Running ML prediction for image {i+1}...")
                
                try:
                    # Instead of using async, let's call a synchronous version
                    processed_image_b64, detected_students = prediction_service.process_image_sync(
                        image_bytes, threshold, sections_data
                    )
                    logger.info(f"✅ Image {i+1} processed, detected {len(detected_students)} students")
                except Exception as e:
                    logger.error(f"❌ Error in sync processing for image {i+1}: {e}")
                    # Fallback: try the old method but with better error handling
                    try:
                        import concurrent.futures
                        import threading

                        def run_in_isolated_thread():
                            # Create completely new thread with new event loop
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                result = loop.run_until_complete(
                                    prediction_service.process_image_async(
                                        image_bytes, threshold, sections_data
                                    )
                                )
                                return result
                            finally:
                                loop.close()
                                asyncio.set_event_loop(None)
                        
                        # Run in a separate thread to avoid the CurrentThreadExecutor issue
                        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                            future = executor.submit(run_in_isolated_thread)
                            processed_image_b64, detected_students = future.result(timeout=30)
                            logger.info(f"✅ Image {i+1} processed via fallback, detected {len(detected_students)} students")
                            
                    except Exception as fallback_error:
                        logger.error(f"❌ Fallback processing also failed for image {i+1}: {fallback_error}")
                        processed_image_b64, detected_students = None, []
                logger.info(f"✅ Image {i+1} processed, detected {len(detected_students)} students")

                if processed_image_b64:
                    # # Save processed image to temp folder
                    # processed_image_path = os.path.join(session_temp_dir, f"processed_image_{i+1}.jpg")
                    # processed_image_bytes = base64.b64decode(processed_image_b64)
                    # with open(processed_image_path, 'wb') as f:
                    #     f.write(processed_image_bytes)
                    # logger.info(f"💾 Saved processed image to: {processed_image_path}")

                    # # Create database record with file paths instead of image data
                    # ProcessedImage.objects.create(
                    #     session_id=session_id,
                    #     image_data=processed_image_path,  # Store file path instead of base64
                    #     detected_faces_count=len(detected_students),
                    #     original_filename=f"original_image_{i+1}.jpg",
                    # )
                    # logger.info(f"💾 Saved processed image {i+1} record to database")

                    # Still add base64 to response for frontend display
                    processed_images.append(processed_image_b64)

                    # Collect unique detected students
                    for student_data in detected_students:
                        reg_num = student_data["register_number"]
                        if (
                            reg_num not in all_detected_students
                            or student_data["confidence"]
                            > all_detected_students[reg_num]["confidence"]
                        ):
                            all_detected_students[reg_num] = student_data
                            logger.info(f"👤 Added/updated student {reg_num} (confidence: {student_data['confidence']:.3f})")

            except Exception as e:
                logger.error(f"❌ Error processing image {i+1}: {e}")
                continue
        
        logger.info(f"🎯 Image processing complete. Detected {len(all_detected_students)} unique students")

        # Get all students from the specified sections
        logger.info("👥 Fetching all students from specified sections...")
        all_students_query = Student.objects.none()
        for section_info in sections_data:
            for section_name in section_info["section_names"]:
                try:
                    section_students = Student.objects.filter(
                        section__section_name=section_name,
                        section__batch__batch_year=batch_year,
                        section__batch__dept__dept_name=dept_name,
                    )
                    all_students_query = all_students_query.union(section_students)
                    logger.info(f"✅ Added students from section {section_name}")
                except Exception as e:
                    logger.error(
                        f"❌ Error getting students for section {section_name}: {e}"
                    )

        # If no specific sections, get all students in the batch
        if not any(section_info["section_names"] for section_info in sections_data):
            logger.info("📂 No specific sections, getting all students in batch")
            all_students_query = Student.objects.filter(
                section__batch__batch_year=batch_year,
                section__batch__dept__dept_name=dept_name,
            )

        all_students = list(all_students_query.distinct())
        detected_reg_numbers = set(all_detected_students.keys())
        
        logger.info(f"📊 Total students in sections: {len(all_students)}")
        logger.info(f"🎯 Students detected: {len(detected_reg_numbers)}")

        # Create predictions for all students
        logger.info("💾 Creating prediction records in database...")
        predictions = []
        for student in all_students:
            is_present = student.student_regno in detected_reg_numbers
            confidence = (
                all_detected_students.get(student.student_regno, {}).get(
                    "confidence", 0.0
                )
                if is_present
                else 0.0
            )

            # Create prediction in database
            time_slot_json = json.dumps({"time_slot": time_slot}) if time_slot else ""
            prediction = AttendancePrediction.objects.create(
                session_id=session_id,
                student=student,
                subject=subject,
                section=student.section,  # Use student's actual section
                predicted_present=is_present,
                confidence_score=confidence,
                detection_method="camera",
                time_slot_info=time_slot_json,
            )

            predictions.append(
                {
                    "register_number": student.student_regno,
                    "name": student.name,
                    "confidence": float(confidence),  # Convert numpy.float32 to Python float
                    "is_present": is_present,
                    "prediction_id": prediction.id,
                    "section": student.section.section_name,
                    "department": student.section.batch.dept.dept_name,
                }
            )

        # Sort by register number
        predictions.sort(key=lambda x: x["register_number"])
        
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"⏱️  Total processing time: {processing_time:.2f} seconds")

        response_data = {
            "success": True,
            "session_id": session_id,
            "processed_images": processed_images,
            "detected_students": predictions,
            "total_detected": len(detected_reg_numbers),
            "total_students": len(predictions),
            "images_processed": len(processed_images),
            "processing_time": processing_time,
            "temp_directory": session_temp_dir,
            "message": f"Processed {len(processed_images)} images, detected {len(detected_reg_numbers)} students out of {len(predictions)} total students. Files saved to {session_temp_dir}",
        }
        
        logger.info(f"✅ Returning successful response: {len(predictions)} predictions, session {session_id}")
        logger.info(f"📁 Session files stored in: {session_temp_dir}")
        return JsonResponse(response_data)

    except Exception as e:
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.error(f"❌ Error in process_images after {processing_time:.2f}s: {e}")
        logger.exception("Full exception details:")
        return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def submit_attendance(request):
    """Submit final attendance after user editing"""
    logger.info("📝 Starting attendance submission process")
    
    try:
        data = json.loads(request.body)

        session_id = data.get("session_id")
        attendance_data = data.get("attendance", [])
        submitted_by = data.get("submitted_by", "anonymous")

        logger.info(f"📋 Session ID: {session_id}")
        logger.info(f"👥 Attendance data for {len(attendance_data)} students")

        if not session_id or not attendance_data:
            logger.warning("❌ Missing session_id or attendance data")
            return JsonResponse(
                {"error": "Missing session_id or attendance data"}, status=400
            )

        # Get original predictions
        predictions = AttendancePrediction.objects.filter(session_id=session_id)
        predictions_dict = {p.student.student_regno: p for p in predictions}
        
        logger.info(f"🔍 Found {len(predictions)} predictions for session")

        if not predictions:
            logger.warning("❌ No predictions found for session")
            return JsonResponse(
                {"error": "No predictions found for this session"}, status=404
            )

        # Get the first prediction to extract session info for timetable
        first_prediction = predictions.first()
        session_subject = first_prediction.subject
        session_section = first_prediction.section
        
        logger.info(f"📚 Session info: {session_subject} for {session_section}")

        # Create or get timetable entry for today with time block validation
        from django.utils import timezone
        from core.models import TimeBlock
        from datetime import datetime, time as datetime_time
        
        today = timezone.now().date()
        current_time = timezone.now().time()
        
        # Get the current time block for the batch
        batch = session_section.batch
        batch_year = batch.batch_year
        
        # Try to get time block from submission data first (for camera-based attendance)
        current_time_block = None
        time_slot_from_session = None
        
        # Check if we have time slot info from the session (stored in prediction data if available)
        session_predictions = AttendancePrediction.objects.filter(session_id=session_id).first()
        if session_predictions and hasattr(session_predictions, 'time_slot_info'):
            try:
                import json as json_module
                time_slot_from_session = json_module.loads(session_predictions.time_slot_info).get('time_slot')
            except:
                time_slot_from_session = None
        
        # Find appropriate time block
        time_blocks = TimeBlock.objects.filter(
            models.Q(batch_year=batch_year) | models.Q(batch_year=0)
        ).order_by('batch_year', 'block_number')
        
        # If we have time slot number from session, use it
        if time_slot_from_session:
            try:
                current_time_block = time_blocks.filter(block_number=int(time_slot_from_session)).first()
                logger.info(f"🎯 Using time block from session: Block {time_slot_from_session}")
            except (ValueError, TypeError):
                logger.warning(f"⚠️  Invalid time slot from session: {time_slot_from_session}")
        
        # Otherwise, find the most appropriate time block based on current time
        if not current_time_block:
            for block in time_blocks:
                # Check if current time falls within this block (with some tolerance)
                if block.start_time <= current_time <= block.end_time:
                    current_time_block = block
                    break
                elif block.batch_year == batch_year:  # Exact batch match gets priority
                    current_time_block = block
            
            # If no specific block found, use the first available block for the batch
            if not current_time_block:
                current_time_block = time_blocks.filter(batch_year=batch_year).first()
                if not current_time_block:
                    current_time_block = time_blocks.filter(batch_year=0).first()
        
        if current_time_block:
            block_start = current_time_block.start_time
            block_end = current_time_block.end_time
            logger.info(f"🕒 Using time block {current_time_block.block_number}: {block_start}-{block_end}")
        else:
            # Fallback if no time blocks are defined
            block_start = current_time
            block_end = current_time
            logger.warning("⚠️  No time blocks found, using current time")
        
        # Check for existing timetable entry for this section, subject, date, and time block
        existing_timetables = Timetable.objects.filter(
            section=session_section,
            subject=session_subject,
            date=today,
            start_time=block_start,
            end_time=block_end
        )
        
        if existing_timetables.exists():
            timetable_entry = existing_timetables.first()
            logger.info(f"📅 Found existing timetable entry: {timetable_entry}")
            
            # Check if attendance has already been submitted for this timetable
            existing_attendance = Attendance.objects.filter(timetable=timetable_entry)
            if existing_attendance.exists():
                logger.warning(f"⚠️  Attendance already exists for this time block! Found {existing_attendance.count()} records")
                
                # Return an error to prevent duplicate submissions
                time_block_desc = f"Block {current_time_block.block_number} ({block_start}-{block_end})" if current_time_block else f"{block_start}-{block_end}"
                return JsonResponse({
                    "error": f"Attendance has already been submitted for {session_subject} - {session_section} at {time_block_desc} on {today}. "
                            f"Found {existing_attendance.count()} existing attendance records. "
                            f"Please contact administrator if you need to update attendance.",
                    "error_type": "duplicate_submission",
                    "existing_count": existing_attendance.count(),
                    "timetable_id": timetable_entry.timetable_id,
                    "time_block": time_block_desc
                }, status=409)  # 409 Conflict status
        else:
            # Create new timetable entry
            timetable_entry = Timetable.objects.create(
                section=session_section,
                subject=session_subject,
                date=today,
                start_time=block_start,
                end_time=block_end,
            )
            logger.info(f"✅ Created new timetable entry: {timetable_entry}")
        
        created = not existing_timetables.exists()
        
        if created:
            logger.info(f"✅ Created new timetable entry: {timetable_entry}")
        else:
            logger.info(f"📅 Using existing timetable entry: {timetable_entry}")

        submissions = []
        attendance_records_created = 0
        attendance_records_updated = 0
        
        for attendance in attendance_data:
            reg_number = attendance.get("register_number")
            final_present = attendance.get("is_present", False)

            if reg_number in predictions_dict:
                prediction = predictions_dict[reg_number]
                original_prediction = prediction.predicted_present
                was_edited = original_prediction != final_present

                # Create AttendanceSubmission record (for tracking purposes)
                submission = AttendanceSubmission.objects.create(
                    session_id=session_id,
                    student=prediction.student,
                    subject=prediction.subject,
                    section=prediction.section,
                    final_present=final_present,
                    was_edited=was_edited,
                    original_prediction=original_prediction,
                    submitted_by=submitted_by,
                )

                # Create or update core Attendance record
                attendance_record, attendance_created = Attendance.objects.update_or_create(
                    student=prediction.student,
                    timetable=timetable_entry,
                    defaults={
                        'is_present': final_present,
                    }
                )
                
                if attendance_created:
                    attendance_records_created += 1
                    logger.info(f"✅ Created attendance record for {reg_number}: {'Present' if final_present else 'Absent'}")
                else:
                    attendance_records_updated += 1
                    logger.info(f"🔄 Updated attendance record for {reg_number}: {'Present' if final_present else 'Absent'}")

                submissions.append(
                    {
                        "register_number": reg_number,
                        "final_present": final_present,
                        "was_edited": was_edited,
                        "submission_id": submission.id,
                        "attendance_record_id": attendance_record.attendance_id,
                    }
                )

        logger.info(f"💾 Attendance submission complete:")
        logger.info(f"   - Submissions: {len(submissions)}")
        logger.info(f"   - Edited: {sum(1 for s in submissions if s['was_edited'])}")
        logger.info(f"   - Attendance records created: {attendance_records_created}")
        logger.info(f"   - Attendance records updated: {attendance_records_updated}")

        return JsonResponse(
            {
                "success": True,
                "submissions_count": len(submissions),
                "edited_count": sum(1 for s in submissions if s["was_edited"]),
                "attendance_records_created": attendance_records_created,
                "attendance_records_updated": attendance_records_updated,
                "timetable_id": timetable_entry.timetable_id,
                "message": f"Successfully submitted attendance for {len(submissions)} students. Created {attendance_records_created} and updated {attendance_records_updated} attendance records.",
            }
        )

    except Exception as e:
        logger.error(f"❌ Error in submit_attendance: {e}")
        logger.exception("Full exception details:")
        return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_session_data(request, session_id):
    """Get prediction and submission data for a session"""
    try:
        predictions = AttendancePrediction.objects.filter(
            session_id=session_id
        ).select_related("student", "subject", "section")

        submissions = AttendanceSubmission.objects.filter(
            session_id=session_id
        ).select_related("student")

        processed_images = ProcessedImage.objects.filter(session_id=session_id)

        response_data = {
            "session_id": session_id,
            "predictions": [
                {
                    "register_number": p.student.student_regno,
                    "name": p.student.name,
                    "predicted_present": p.predicted_present,
                    "confidence_score": float(p.confidence_score),  # Convert to Python float
                    "predicted_at": p.predicted_at.isoformat(),
                }
                for p in predictions
            ],
            "submissions": [
                {
                    "register_number": s.student.student_regno,
                    "name": s.student.name,
                    "final_present": s.final_present,
                    "was_edited": s.was_edited,
                    "original_prediction": s.original_prediction,
                    "submitted_at": s.submitted_at.isoformat(),
                }
                for s in submissions
            ],
            "processed_images": [
                {
                    "id": img.id,
                    "detected_faces_count": img.detected_faces_count,
                    "processed_at": img.processed_at.isoformat(),
                }
                for img in processed_images
            ],
        }

        return JsonResponse(response_data)

    except Exception as e:
        logger.error(f"Error in get_session_data: {e}")
        return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def debug_temp_directory(request, session_id):
    """Debug endpoint to view contents of temp directory for a session"""
    try:
        session_temp_dir = get_session_temp_directory(session_id)
        
        if not os.path.exists(session_temp_dir):
            return JsonResponse({"error": f"Temp directory not found: {session_temp_dir}"}, status=404)
        
        files = []
        for filename in os.listdir(session_temp_dir):
            filepath = os.path.join(session_temp_dir, filename)
            if os.path.isfile(filepath):
                stat = os.stat(filepath)
                files.append({
                    "filename": filename,
                    "size_bytes": stat.st_size,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "full_path": filepath
                })
        
        return JsonResponse({
            "session_id": session_id,
            "temp_directory": session_temp_dir,
            "total_files": len(files),
            "total_size_mb": round(sum(f["size_bytes"] for f in files) / (1024 * 1024), 2),
            "files": files
        })
        
    except Exception as e:
        logger.error(f"Error in debug_temp_directory: {e}")
        return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def list_all_temp_directories(request):
    """Debug endpoint to list all attendance temp directories"""
    try:
        temp_dir = tempfile.gettempdir()
        directories = []
        
        for item in os.listdir(temp_dir):
            if item.startswith("attendance_session_"):
                item_path = os.path.join(temp_dir, item)
                if os.path.isdir(item_path):
                    stat = os.stat(item_path)
                    file_count = len([f for f in os.listdir(item_path) if os.path.isfile(os.path.join(item_path, f))])
                    
                    directories.append({
                        "session_id": item.replace("attendance_session_", ""),
                        "directory": item_path,
                        "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "file_count": file_count,
                        "age_hours": round((datetime.now() - datetime.fromtimestamp(stat.st_ctime)).total_seconds() / 3600, 1)
                    })
        
        return JsonResponse({
            "temp_base_directory": temp_dir,
            "total_session_directories": len(directories),
            "directories": directories
        })
        
    except Exception as e:
        logger.error(f"Error in list_all_temp_directories: {e}")
        return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def check_attendance_records(request):
    """Check what attendance records were created today"""
    try:
        from django.utils import timezone
        today = timezone.now().date()
        
        # Get today's attendance records
        attendance_records = Attendance.objects.filter(
            timetable__date=today
        ).select_related('student', 'timetable__subject', 'timetable__section')
        
        records_data = []
        for record in attendance_records:
            records_data.append({
                "attendance_id": record.attendance_id,
                "student_regno": record.student.student_regno,
                "student_name": record.student.name,
                "subject": record.timetable.subject.subject_name,
                "section": record.timetable.section.section_name,
                "is_present": record.is_present,
                "date": record.timetable.date.isoformat(),
                "created_at": record.created_at.isoformat(),
                "updated_at": record.updated_at.isoformat(),
            })
        
        # Get today's timetable entries
        timetable_entries = Timetable.objects.filter(date=today)
        timetable_data = []
        for entry in timetable_entries:
            timetable_data.append({
                "timetable_id": entry.timetable_id,
                "subject": entry.subject.subject_name,
                "section": entry.section.section_name,
                "date": entry.date.isoformat(),
                "start_time": entry.start_time.isoformat(),
                "end_time": entry.end_time.isoformat(),
            })
        
        logger.info(f"📊 Found {len(records_data)} attendance records and {len(timetable_data)} timetable entries for {today}")
        
        return JsonResponse({
            "success": True,
            "date": today.isoformat(),
            "attendance_records_count": len(records_data),
            "timetable_entries_count": len(timetable_data),
            "attendance_records": records_data,
            "timetable_entries": timetable_data,
        })
        
    except Exception as e:
        logger.error(f"❌ Error checking attendance records: {e}")
        logger.exception("Full exception details:")
        return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)


@csrf_exempt  
@require_http_methods(["GET"])
def debug_session_info(request, session_id):
    """Debug endpoint to check all data for a session"""
    try:
        logger.info(f"🔍 Debug info for session: {session_id}")
        
        # Get predictions
        predictions = AttendancePrediction.objects.filter(session_id=session_id)
        predictions_data = [{
            "id": p.id,
            "student_regno": p.student.student_regno,
            "student_name": p.student.name,
            "predicted_present": p.predicted_present,
            "confidence_score": float(p.confidence_score),  # Convert to Python float
        } for p in predictions]
        
        # Get submissions
        submissions = AttendanceSubmission.objects.filter(session_id=session_id)
        submissions_data = [{
            "id": s.id,
            "student_regno": s.student.student_regno,
            "student_name": s.student.name,
            "final_present": s.final_present,
            "was_edited": s.was_edited,
            "original_prediction": s.original_prediction,
        } for s in submissions]
        
        # Get related attendance records
        if submissions:
            first_submission = submissions.first()
            from django.utils import timezone
            today = timezone.now().date()
            
            attendance_records = Attendance.objects.filter(
                student__in=[s.student for s in submissions],
                timetable__date=today,
                timetable__subject=first_submission.subject,
                timetable__section=first_submission.section,
            )
            attendance_data = [{
                "attendance_id": a.attendance_id,
                "student_regno": a.student.student_regno,
                "student_name": a.student.name,
                "is_present": a.is_present,
                "timetable_id": a.timetable.timetable_id,
            } for a in attendance_records]
        else:
            attendance_data = []
        
        return JsonResponse({
            "success": True,
            "session_id": session_id,
            "predictions": predictions_data,
            "submissions": submissions_data,
            "attendance_records": attendance_data,
            "summary": {
                "predictions_count": len(predictions_data),
                "submissions_count": len(submissions_data),
                "attendance_records_count": len(attendance_data),
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Error in debug session info: {e}")
        logger.exception("Full exception details:")
        return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)
