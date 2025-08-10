from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class TimestampedModel(models.Model):
    """
    Abstract base model that provides timestamp fields for all models
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class AuditModel(TimestampedModel):
    """
    Abstract base model that provides audit fields for all models
    """
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created"
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_updated"
    )
    
    class Meta:
        abstract = True


class Department(TimestampedModel):
    """
    Model representing academic departments
    """
    dept_id = models.IntegerField(primary_key=True, unique=True, help_text="Department ID (manually assigned)")
    dept_name = models.CharField(max_length=100, unique=True)
    
    class Meta:
        db_table = 'Departments'
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'
    
    def __str__(self):
        return self.dept_name


class Batch(TimestampedModel):
    """
    Model representing academic batches (year groups within departments)
    """
    batch_id = models.AutoField(primary_key=True)
    dept = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        db_column='dept_id'
    )
    batch_year = models.PositiveIntegerField(
        help_text="Graduation year (e.g., 2027, 2028)"
    )
    
    class Meta:
        db_table = 'Batches'
        verbose_name = 'Batch'
        verbose_name_plural = 'Batches'
        unique_together = ['dept', 'batch_year']
    
    def __str__(self):
        return f"{self.dept.dept_name} - {self.display_year}"
    
    @property
    def display_year(self):
        """Returns display format like 2023-2027"""
        start_year = self.batch_year - 3  # 4 year course, so start year is graduation year - 3
        return f"{start_year}-{self.batch_year}"
    
    @property
    def current_year(self):
        """Calculate current academic year (1-4) based on graduation year"""
        current_date = timezone.now().date()
        current_academic_year = current_date.year
        if current_date.month >= 6:  # Academic year starts in June
            current_academic_year += 1
        
        years_until_graduation = self.batch_year - current_academic_year
        return max(1, min(4, 4 - years_until_graduation))


class Section(TimestampedModel):
    """
    Model representing sections within batches
    """
    section_id = models.AutoField(primary_key=True)
    batch = models.ForeignKey(
        Batch,
        on_delete=models.CASCADE,
        db_column='batch_id'
    )
    section_name = models.CharField(max_length=10)
    
    class Meta:
        db_table = 'Sections'
        verbose_name = 'Section'
        verbose_name_plural = 'Sections'
        unique_together = ['batch', 'section_name']
    
    def __str__(self):
        return f"{self.batch} - Section {self.section_name}"


class Subject(TimestampedModel):
    """
    Model representing academic subjects
    """
    subject_id = models.AutoField(primary_key=True)
    subject_code = models.CharField(max_length=20, unique=True)
    subject_name = models.CharField(max_length=200, unique=True)
    departments = models.ManyToManyField(
        Department,
        related_name='subjects',
        help_text="Departments that offer this subject"
    )
    year = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(4)],
        help_text="Academic year (1-4)"
    )
    
    class Meta:
        db_table = 'Subjects'
        verbose_name = 'Subject'
        verbose_name_plural = 'Subjects'
    
    def __str__(self):
        return f"{self.subject_code} - {self.subject_name}"
    
    def get_departments_display(self):
        """Return comma-separated list of department names"""
        return ", ".join([dept.dept_name for dept in self.departments.all()])


class Student(TimestampedModel):
    """
    Model representing students
    """
    student_id = models.AutoField(primary_key=True)
    register_number = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        db_column='section_id'
    )
    embedding = models.BinaryField(null=True, blank=True, help_text="Face recognition embedding data")
    
    class Meta:
        db_table = 'Students'
        verbose_name = 'Student'
        verbose_name_plural = 'Students'
    
    def __str__(self):
        return f"{self.register_number} - {self.name}"


class TimeBlock(TimestampedModel):
    """
    Model representing time blocks for different academic years
    """
    time_block_id = models.AutoField(primary_key=True)
    batch_year = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(4)]
    )
    block_number = models.PositiveIntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    class Meta:
        db_table = 'TimeBlocks'
        verbose_name = 'Time Block'
        verbose_name_plural = 'Time Blocks'
    
    def __str__(self):
        return f"Year {self.batch_year} - Block {self.block_number} ({self.start_time}-{self.end_time})"


class Timetable(TimestampedModel):
    """
    Model representing class timetable entries
    """
    timetable_id = models.AutoField(primary_key=True)
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        db_column='section_id'
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        db_column='subject_id'
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    class Meta:
        db_table = 'Timetable'
        verbose_name = 'Timetable Entry'
        verbose_name_plural = 'Timetable Entries'
    
    def __str__(self):
        return f"{self.section} - {self.subject} on {self.date}"


class Attendance(TimestampedModel):
    """
    Model representing student attendance records
    """
    attendance_id = models.AutoField(primary_key=True)
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        db_column='student_id'
    )
    timetable = models.ForeignKey(
        Timetable,
        on_delete=models.CASCADE,
        db_column='timetable_id'
    )
    is_present = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'Attendance'
        verbose_name = 'Attendance Record'
        verbose_name_plural = 'Attendance Records'
        unique_together = ['student', 'timetable']
    
    def __str__(self):
        status = "Present" if self.is_present else "Absent"
        return f"{self.student.name} - {status} ({self.timetable.date})"


class Admin(TimestampedModel):
    """
    Model representing system administrators
    """
    id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=150, unique=True)
    password_hash = models.CharField(max_length=255)
    role = models.CharField(max_length=50)
    
    class Meta:
        db_table = 'Admins'
        verbose_name = 'Administrator'
        verbose_name_plural = 'Administrators'
    
    def __str__(self):
        return f"{self.username} ({self.role})"
