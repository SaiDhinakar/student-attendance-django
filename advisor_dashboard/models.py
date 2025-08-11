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
        from django.db.models import Q
        
        # Prioritize more specific assignments over general ones
        filter_conditions = Q(student_regno__isnull=True)  # Start with empty condition
        
        # 1. Direct section assignments (most specific)
        if self.sections.exists():
            filter_conditions |= Q(section__in=self.sections.all())
        
        # 2. If no direct sections, check batch assignments
        elif self.batches.exists():
            filter_conditions |= Q(section__batch__in=self.batches.all())
            
        # 3. If no batches, check department assignments (least specific)
        elif self.departments.exists():
            filter_conditions |= Q(section__batch__dept__in=self.departments.all())
        
        # Return distinct students matching the conditions
        return Student.objects.filter(filter_conditions).distinct()
    
    def get_assigned_sections(self):
        """Get all sections under this advisor's supervision"""
        from django.db.models import Q
        from core.models import Section
        
        # Prioritize more specific assignments over general ones
        filter_conditions = Q(section_id__isnull=True)  # Start with empty condition
        
        # 1. Direct section assignments (most specific)
        if self.sections.exists():
            filter_conditions |= Q(section_id__in=self.sections.all().values_list('section_id', flat=True))
        
        # 2. If no direct sections, check batch assignments
        elif self.batches.exists():
            filter_conditions |= Q(batch__in=self.batches.all())
            
        # 3. If no batches, check department assignments (least specific)
        elif self.departments.exists():
            filter_conditions |= Q(batch__dept__in=self.departments.all())
        
        # Return distinct sections matching the conditions
        return Section.objects.filter(filter_conditions).distinct()
