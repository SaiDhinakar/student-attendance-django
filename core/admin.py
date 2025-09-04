from django.contrib import admin
from .models import (
    Department, Batch, Section, Subject, Student, 
    TimeBlock, Timetable, Attendance, Admin
)
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction
import csv
import io


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
    list_display = ['subject_code', 'subject_name', 'batch', 'created_by', 'get_departments_display']
    list_filter = ['batch__dept', 'batch__batch_year', 'created_by', 'departments']
    search_fields = ['subject_code', 'subject_name', 'created_by__dept_name', 'departments__dept_name', 'batch__batch_year']
    ordering = ['batch__batch_year', 'subject_code']
    filter_horizontal = ['departments']  # Makes it easier to select multiple departments
    # Include created_by in the form for manual assignment
    fields = ['subject_code', 'subject_name', 'created_by', 'batch', 'departments']
    
    def get_departments_display(self, obj):
        """Display departments as comma-separated list"""
        return obj.get_departments_display()
    get_departments_display.short_description = 'Departments'


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['student_regno', 'name', 'department', 'batch', 'section', 'created_at']
    list_filter = ['department', 'batch__batch_year', 'section__section_name']
    search_fields = ['student_regno', 'name', 'department__dept_name', 'section__section_name']
    ordering = ['student_regno']

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                'import-csv/',
                self.admin_site.admin_view(self.import_csv_view),
                name='core_student_import_csv'
            ),
        ]
        return my_urls + urls

    def import_csv_view(self, request):
        """Custom admin view to upload and import students from a CSV file."""
        if not self.has_add_permission(request):
            messages.error(request, "You do not have permission to import students.")
            return redirect('admin:core_student_changelist')

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'Import Students from CSV',
        }

        if request.method == 'POST':
            file = request.FILES.get('csv_file')
            if not file:
                messages.error(request, 'Please choose a CSV file to upload.')
                return render(request, 'admin/core/student/import_csv.html', context)

            try:
                decoded = file.read().decode('utf-8-sig')  # handle BOM
            except UnicodeDecodeError:
                messages.error(request, 'Could not decode file. Please upload a UTF-8 encoded CSV.')
                return render(request, 'admin/core/student/import_csv.html', context)

            f = io.StringIO(decoded)
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                messages.error(request, 'CSV appears to be empty or has no header row.')
                return render(request, 'admin/core/student/import_csv.html', context)

            # Normalize headers: lowercase, remove spaces/underscores
            norm = lambda s: (s or '').strip().lower().replace(' ', '').replace('_', '')
            headers = [norm(h) for h in reader.fieldnames]
            required_any = ['registernumber', 'studentregno', 'regno']
            name_any = ['name', 'studentname']
            dept_any = ['deptid', 'departmentid', 'department', 'dept', 'departmentname', 'deptname']
            batch_any = ['batchyear', 'batch', 'year', 'gradyear']
            section_any = ['section', 'sectionname']

            def pick(row, keys):
                for k in keys:
                    for orig_key in row.keys():
                        if norm(orig_key) == k:
                            return row.get(orig_key)
                return None

            created = 0
            updated = 0
            errors = []
            row_num = 1  # header is row 1 for reporting

            with transaction.atomic():
                for row in reader:
                    row_num += 1
                    try:
                        regno = (pick(row, required_any) or '').strip()
                        name = (pick(row, name_any) or '').strip()
                        dept_val = (pick(row, dept_any) or '').strip()
                        batch_val = (pick(row, batch_any) or '').strip()
                        section_name = (pick(row, section_any) or '').strip()

                        if not regno or not name or not dept_val or not batch_val or not section_name:
                            raise ValueError('Missing one of required fields: RegisterNumber, Name, Department, BatchYear, Section')

                        # Resolve Department (by ID or Name)
                        dept_obj = None
                        if dept_val.isdigit():
                            dept_obj = Department.objects.filter(dept_id=int(dept_val)).first()
                        if dept_obj is None:
                            dept_obj = Department.objects.filter(dept_name__iexact=dept_val).first()
                        if dept_obj is None:
                            raise ValueError(f"Department not found: {dept_val}")

                        # Resolve Batch
                        try:
                            batch_year = int(batch_val)
                        except Exception:
                            raise ValueError(f"Invalid BatchYear: {batch_val}")
                        batch_obj = Batch.objects.filter(dept=dept_obj, batch_year=batch_year).first()
                        if batch_obj is None:
                            raise ValueError(f"Batch not found for {dept_obj.dept_name} - {batch_year}")

                        # Resolve or create Section
                        section_obj, _ = Section.objects.get_or_create(batch=batch_obj, section_name=section_name)

                        # Create or update Student
                        obj, was_created = Student.objects.update_or_create(
                            student_regno=regno,
                            defaults={
                                'name': name,
                                'department': dept_obj,
                                'batch': batch_obj,
                                'section': section_obj,
                            }
                        )
                        created += 1 if was_created else 0
                        updated += 0 if was_created else 1
                    except Exception as e:
                        errors.append(f"Row {row_num}: {e}")

            if errors:
                for msg in errors[:10]:
                    messages.error(request, msg)
                if len(errors) > 10:
                    messages.error(request, f"...and {len(errors) - 10} more errors")

            if created or updated:
                messages.success(request, f"Import complete. Created: {created}, Updated: {updated}.")
            elif not errors:
                messages.info(request, "No rows processed.")

            return redirect('admin:core_student_changelist')

        return render(request, 'admin/core/student/import_csv.html', context)


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
    search_fields = ['student__name', 'student__student_regno']
    ordering = ['-timetable__date', 'student__name']


@admin.register(Admin)
class AdminUserAdmin(admin.ModelAdmin):
    list_display = ['username', 'role', 'created_at']
    list_filter = ['role']
    search_fields = ['username']
    ordering = ['username']
