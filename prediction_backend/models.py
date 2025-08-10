from django.db import models
from core.models import Student, Subject, Section, Department, Batch


class AttendancePrediction(models.Model):
    """Store ML model predictions before user editing"""
    session_id = models.CharField(max_length=100)  # Unique session identifier
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    predicted_present = models.BooleanField()
    confidence_score = models.FloatField()
    detection_method = models.CharField(max_length=50, default='camera')
    predicted_at = models.DateTimeField(auto_now_add=True)
    image_data = models.TextField(blank=True)  # Base64 encoded image for reference
    
    class Meta:
        db_table = 'attendance_predictions'
        unique_together = ['session_id', 'student']


class AttendanceSubmission(models.Model):
    """Store final user-edited attendance submissions"""
    session_id = models.CharField(max_length=100)  # Links to prediction session
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    final_present = models.BooleanField()
    was_edited = models.BooleanField(default=False)  # True if user changed from prediction
    original_prediction = models.BooleanField(null=True, blank=True)  # Store original prediction
    submitted_by = models.CharField(max_length=100)  # Staff/advisor username
    submitted_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'attendance_submissions'
        unique_together = ['session_id', 'student']


class ProcessedImage(models.Model):
    """Store information about processed images"""
    session_id = models.CharField(max_length=100)
    image_data = models.TextField()  # File path to processed image in temp directory
    original_filename = models.CharField(max_length=255, blank=True)
    detected_faces_count = models.IntegerField(default=0)
    processed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'processed_images'
