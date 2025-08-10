from django.db import models
from django.contrib.auth.models import User
from core.models import Department, Batch, Section

class Advisor(models.Model):
    """
    Model representing advisors and their assigned departments/batches/sections
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='advisor_profile')
    employee_id = models.CharField(max_length=20, unique=True)
    
    # Advisor assignments - many-to-many relationships for flexibility
    departments = models.ManyToManyField(Department, related_name='advisors', blank=True,
                                       help_text="Departments this advisor is responsible for")
    batches = models.ManyToManyField(Batch, related_name='advisors', blank=True,
                                   help_text="Specific batches this advisor is responsible for")
    sections = models.ManyToManyField(Section, related_name='advisors', blank=True,
                                    help_text="Specific sections this advisor is responsible for")
    
    # Permissions
    can_take_attendance = models.BooleanField(default=True)
    can_view_all_attendance = models.BooleanField(default=True)
    can_edit_attendance = models.BooleanField(default=True)
    can_generate_reports = models.BooleanField(default=True)
    
    # Contact information
    phone = models.CharField(max_length=15, blank=True)
    office_location = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'advisor_profiles'
        verbose_name = 'Advisor'
        verbose_name_plural = 'Advisors'
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.employee_id}"
    
    def get_assigned_students(self):
        """Get all students under this advisor's supervision"""
        from core.models import Student
        
        students = Student.objects.none()
        
        # Students from assigned sections
        if self.sections.exists():
            students = students.union(
                Student.objects.filter(section__in=self.sections.all())
            )
        
        # Students from assigned batches (if no specific sections)
        if self.batches.exists():
            students = students.union(
                Student.objects.filter(section__batch__in=self.batches.all())
            )
            
        # Students from assigned departments (if no specific batches/sections)
        if self.departments.exists() and not self.batches.exists() and not self.sections.exists():
            students = students.union(
                Student.objects.filter(section__batch__dept__in=self.departments.all())
            )
        
        return students.distinct()
    
    def get_assigned_sections(self):
        """Get all sections under this advisor's supervision"""
        sections = Section.objects.none()
        
        # Direct section assignments
        if self.sections.exists():
            sections = sections.union(self.sections.all())
        
        # Sections from assigned batches
        if self.batches.exists():
            sections = sections.union(
                Section.objects.filter(batch__in=self.batches.all())
            )
            
        # Sections from assigned departments
        if self.departments.exists():
            sections = sections.union(
                Section.objects.filter(batch__dept__in=self.departments.all())
            )
        
        return sections.distinct()
