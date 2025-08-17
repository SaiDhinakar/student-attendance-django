from django import forms
from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.models import Group
from django.db import models
from django.http import HttpResponseForbidden
from core.models import Student, Section, Batch, Department, Attendance, Timetable
from .models import Advisor


# Custom form for advisor admin
class AdvisorForm(forms.ModelForm):
    class Meta:
        model = Advisor
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add custom styling and help text
        self.fields['employee_id'].widget.attrs.update({
            'placeholder': 'e.g., ADV001, EMP123',
            'class': 'vTextField'
        })
        
        self.fields['phone'].widget.attrs.update({
            'placeholder': 'e.g., +1234567890',
            'class': 'vTextField'
        })
        
        self.fields['office_location'].widget.attrs.update({
            'placeholder': 'e.g., CS Building, Room 201',
            'class': 'vTextField'
        })
        
        # Group sections by department and batch for easier selection
        if 'sections' in self.fields:
            sections = Section.objects.select_related('batch__dept').order_by(
                'batch__dept__dept_name', 'batch__batch_year', 'section_name'
            )
            choices = []
            for section in sections:
                label = f"{section.batch.dept.dept_name} - {section.batch.display_year} - Section {section.section_name}"
                choices.append((section.pk, label))
            self.fields['sections'].choices = choices


@admin.register(Advisor)
class AdvisorAdmin(admin.ModelAdmin):
    form = AdvisorForm
    list_display = ['user', 'employee_id', 'get_departments', 'get_batches', 'get_sections', 'phone', 'office_location', 'created_at']
    list_filter = ['departments', 'batches', 'can_take_attendance', 'can_edit_attendance']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'employee_id', 'phone']
    filter_horizontal = ['departments', 'batches', 'sections']
    ordering = ['user__username']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'employee_id'),
            'description': 'Basic user information and employee ID'
        }),
        ('Contact Information', {
            'fields': ('phone', 'office_location'),
            'description': 'Contact details for the advisor'
        }),
        ('Assignments', {
            'fields': ('departments', 'batches', 'sections'),
            'description': '''
            <strong>Assignment Strategy:</strong><br>
            • <strong>Specific Sections:</strong> Assign individual sections for precise control<br>
            • <strong>Batches:</strong> Assign entire batches (all sections in those batches)<br>
            • <strong>Departments:</strong> Assign entire departments (all batches and sections)<br>
            <br>
            <strong>Priority:</strong> Sections > Batches > Departments<br>
            If sections are assigned, only those sections will be shown.<br>
            If only batches are assigned, all sections in those batches will be shown.<br>
            If only departments are assigned, all sections in those departments will be shown.
            '''
        }),
        ('Permissions', {
            'fields': ('can_take_attendance', 'can_view_all_attendance', 'can_edit_attendance', 'can_generate_reports'),
            'classes': ('collapse',),
            'description': 'Advisor permissions for various operations'
        }),
    )
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        
        # Add help text for better guidance
        if 'employee_id' in form.base_fields:
            form.base_fields['employee_id'].help_text = "Unique employee identifier (e.g., ADV001, EMP123)"
        
        if 'phone' in form.base_fields:
            form.base_fields['phone'].help_text = "Contact phone number (e.g., +1234567890)"
            
        if 'office_location' in form.base_fields:
            form.base_fields['office_location'].help_text = "Office location (e.g., CS Building, Room 201)"
        
        return form
    
    def save_model(self, request, obj, form, change):
        # Save the advisor
        super().save_model(request, obj, form, change)
        
        # Add user to Advisors group if not already added
        advisors_group, created = Group.objects.get_or_create(name='Advisors')
        obj.user.groups.add(advisors_group)
        
        # Show assignment summary in admin messages
        if change:
            sections_count = obj.get_assigned_sections().count()
            students_count = obj.get_assigned_students().count()
            self.message_user(
                request,
                f"Advisor {obj.user.get_full_name()} updated. "
                f"Now supervises {students_count} students across {sections_count} sections.",
                level=messages.SUCCESS
            )
    
    def get_departments(self, obj):
        return ", ".join([dept.dept_name for dept in obj.departments.all()[:3]]) + ("..." if obj.departments.count() > 3 else "")
    get_departments.short_description = 'Departments'
    
    def get_batches(self, obj):
        return ", ".join([f"{batch.dept.dept_name} {batch.batch_year}" for batch in obj.batches.all()[:3]]) + ("..." if obj.batches.count() > 3 else "")
    get_batches.short_description = 'Batches'
    
    def get_sections(self, obj):
        return ", ".join([section.section_name for section in obj.sections.all()[:3]]) + ("..." if obj.sections.count() > 3 else "")
    get_sections.short_description = 'Sections'


# Custom Admin classes that respect advisor permissions
class AdvisorFilteredAdminMixin:
    """Mixin to filter admin views based on advisor permissions"""
    
    def has_view_permission(self, request, obj=None):
        # Superusers can see everything
        if request.user.is_superuser:
            return True
        
        # Staff with advisor profile can see their assigned data
        if hasattr(request.user, 'advisor_profile'):
            return True
        
        # Regular staff can see everything (for now)
        return request.user.is_staff
    
    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        
        if hasattr(request.user, 'advisor_profile'):
            advisor = request.user.advisor_profile
            return advisor.can_edit_attendance
        
        return request.user.is_staff
    
    def has_delete_permission(self, request, obj=None):
        # Only superusers can delete
        return request.user.is_superuser
    
    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        
        if hasattr(request.user, 'advisor_profile'):
            return True
        
        return request.user.is_staff


class AdvisorStudentAdmin(AdvisorFilteredAdminMixin, admin.ModelAdmin):
    """Admin for students - filtered by advisor assignments"""
    list_display = ['student_regno', 'name', 'department', 'batch', 'section']
    list_filter = ['department', 'batch__batch_year', 'section__section_name']
    search_fields = ['student_regno', 'name']
    ordering = ['student_regno']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        
        # Superusers see everything
        if request.user.is_superuser:
            return qs
        
        # Advisors see only their assigned students
        if hasattr(request.user, 'advisor_profile'):
            advisor = request.user.advisor_profile
            return advisor.get_assigned_students()
        
        # Regular staff see everything (for now)
        return qs


class AdvisorSectionAdmin(AdvisorFilteredAdminMixin, admin.ModelAdmin):
    """Admin for sections - filtered by advisor assignments"""
    list_display = ['section_name', 'batch', 'get_department', 'student_count']
    list_filter = ['batch__dept', 'batch__batch_year']
    search_fields = ['section_name', 'batch__dept__dept_name']
    ordering = ['batch', 'section_name']
    
    def get_department(self, obj):
        return obj.batch.dept.dept_name
    get_department.short_description = 'Department'
    
    def student_count(self, obj):
        return obj.student_set.count()
    student_count.short_description = 'Students'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        
        # Superusers see everything
        if request.user.is_superuser:
            return qs
        
        # Advisors see only their assigned sections
        if hasattr(request.user, 'advisor_profile'):
            advisor = request.user.advisor_profile
            return advisor.get_assigned_sections()
        
        # Regular staff see everything
        return qs


class AdvisorAttendanceAdmin(AdvisorFilteredAdminMixin, admin.ModelAdmin):
    """Admin for attendance - filtered by advisor assignments"""
    list_display = ['student', 'timetable', 'is_present', 'created_at']
    list_filter = ['is_present', 'timetable__date', 'timetable__subject']
    search_fields = ['student__name', 'student__student_regno']
    ordering = ['-timetable__date', 'student__name']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        
        # Superusers see everything
        if request.user.is_superuser:
            return qs
        
        # Advisors see only attendance for their assigned students
        if hasattr(request.user, 'advisor_profile'):
            advisor = request.user.advisor_profile
            return qs.filter(student__in=advisor.get_assigned_students())
        
        # Regular staff see everything
        return qs


# Register the custom admin views
# Note: We need to unregister the default ones first if they exist
try:
    admin.site.unregister(Student)
    admin.site.unregister(Section) 
    admin.site.unregister(Attendance)
except admin.sites.NotRegistered:
    pass

# Register our custom filtered admin views
admin.site.register(Student, AdvisorStudentAdmin)
admin.site.register(Section, AdvisorSectionAdmin)
admin.site.register(Attendance, AdvisorAttendanceAdmin)
