from django.contrib import admin
from .models import (
    Department, Batch, Section, Subject, Student, 
    TimeBlock, Timetable, Attendance, Admin
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['dept_id', 'dept_name', 'created_at']
    search_fields = ['dept_name', 'dept_id']
    ordering = ['dept_id']
    fields = ['dept_id', 'dept_name']
    readonly_fields = []  # Allow manual editing of dept_id
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'dept_id' in form.base_fields:
            form.base_fields['dept_id'].help_text = "Enter a unique department ID (e.g., 1, 2, 3, etc.)"
        return form


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ['dept', 'batch_year', 'created_at']
    list_filter = ['dept', 'batch_year']
    search_fields = ['dept__dept_name']
    ordering = ['dept', 'batch_year']


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ['batch', 'section_name', 'created_at']
    list_filter = ['batch__dept', 'batch__batch_year']
    search_fields = ['section_name', 'batch__dept__dept_name']
    ordering = ['batch', 'section_name']


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['subject_code', 'subject_name', 'get_departments_display', 'year']
    list_filter = ['departments', 'year']
    search_fields = ['subject_code', 'subject_name', 'departments__dept_name']
    ordering = ['subject_code']
    filter_horizontal = ['departments']  # Makes it easier to select multiple departments
    
    def get_departments_display(self, obj):
        """Display departments as comma-separated list"""
        return obj.get_departments_display()
    get_departments_display.short_description = 'Departments'


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['register_number', 'name', 'section', 'created_at']
    list_filter = ['section__batch__dept', 'section__batch__batch_year', 'section']
    search_fields = ['register_number', 'name', 'section__section_name']
    ordering = ['register_number']


@admin.register(TimeBlock)
class TimeBlockAdmin(admin.ModelAdmin):
    list_display = ['batch_year', 'block_number', 'start_time', 'end_time']
    list_filter = ['batch_year']
    ordering = ['batch_year', 'block_number']


@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = ['section', 'subject', 'date', 'start_time', 'end_time']
    list_filter = ['date', 'section__batch__dept', 'section__batch__batch_year', 'subject']
    search_fields = ['section__section_name', 'subject__subject_name']
    ordering = ['date', 'start_time']


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['student', 'timetable', 'is_present', 'created_at']
    list_filter = ['is_present', 'timetable__date', 'timetable__subject']
    search_fields = ['student__name', 'student__register_number']
    ordering = ['-timetable__date', 'student__name']


@admin.register(Admin)
class AdminUserAdmin(admin.ModelAdmin):
    list_display = ['username', 'role', 'created_at']
    list_filter = ['role']
    search_fields = ['username']
    ordering = ['username']
